// Per-IP rate limiting and Worker edge/KV caching helpers.

import { CACHE_TTL_LONG, CORS_HEADERS, DEGRADED_HEADER, cacheControl, json } from "./http.js";
import { isArchiveBypass, timingSafeEqualStr } from "./crypto.js";

export async function checkRate(env, request, path) {
  if (path === "/v1/health") return null;
  // Trusted-build bypass: the Cloudflare Pages build pre-fetches ~5k per-gene
  // records from ONE egress IP and would otherwise trip the per-IP limiter
  // (~10 min of forced pacing). A request carrying the shared
  // BUILD_BYPASS_TOKEN secret in `X-Build-Bypass` skips the limiter so the build
  // fetches at full concurrency. If the secret isn't configured (env var unset)
  // there is NO bypass; public traffic can't reach this path without the exact
  // secret, so it stays rate-limited.
  const bypass = env.BUILD_BYPASS_TOKEN;
  const gotBypass = request.headers.get("X-Build-Bypass") ?? "";
  if (bypass && gotBypass && timingSafeEqualStr(gotBypass, bypass)) return null;
  // Archive bypass (see isArchiveBypass) also skips the rate limiter — the
  // archiver sweeps ~5k genes from one IP just like the build does above.
  if (await isArchiveBypass(request, env)) return null;
  const heavy = path === "/v1/catalog" || path.endsWith(".tsv") || /^\/v1\/releases\/[^/]+$/.test(path);
  const limiter = heavy ? env.RATE_LIMITER_HEAVY : env.RATE_LIMITER;
  if (!limiter) return null;
  const ip = request.headers.get("CF-Connecting-IP") || "anon";
  const { success } = await limiter.limit({ key: ip });
  if (success) return null;
  return new Response(JSON.stringify({ error: "rate_limited" }), {
    status: 429,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Retry-After": "60",
      "Cache-Control": "no-store",
      ...CORS_HEADERS,
    },
  });
}


// Parse the integer `max-age` (seconds) out of a Cache-Control header so the
// KV mirror's `expirationTtl` matches the response's own TTL. Returns 0 when
// absent — but callers only ever cache 200/404, both of which carry a
// positive max-age from json()/tsv()/notFound().
export function maxAgeFromCacheControl(cc) {
  const m = /max-age=(\d+)/.exec(cc || "");
  return m ? parseInt(m[1], 10) : 0;
}

// Two-tier read-through cache for a cacheable handler:
//
//   (1) caches.default   — per-POP, isolate-local, fastest.
//   (2) RECORD_CACHE (KV) — shared GLOBAL mirror: a record populated once
//       (in any POP) is served worldwide without re-running the D1 handler,
//       and it survives isolate eviction / cold POPs that caches.default
//       doesn't. Read with a 3600s `cacheTtl` so a KV hit is itself edge-
//       cached for an hour.
//   (3) handler (D1)     — full miss; result populates BOTH tiers.
//
// The KV binding is OPTIONAL. Pre-binding (or a `wrangler dev` without the
// namespace) leaves `env.RECORD_CACHE` undefined and this degrades to the
// original caches.default-only path — the Worker never crashes on `.get`.
//
// KV stores only the response body, so the response's status + content-type
// (and its max-age → TTL) ride along as KV metadata; the KV-hit branch
// reads them back via getWithMetadata (same arrayBuffer read + cacheTtl a
// plain .get would do) and rebuilds the Response with the correct headers.
//
// Cache-key strategy: URL path only by default (matches the zone Cache Rule
// that strips query strings). Pass `includeQuery: true` where the query
// genuinely parameterizes the response (e.g. /v1/triage/export.tsv?run_id=X).
// The key uses a SYNTHETIC host, not the real api.deliverome.org origin: the
// zone cache rule (http.host eq "api.deliverome.org") excludes ALL query
// strings, so with includeQuery it would strip run_id and collide
// ?run_id=X with ?run_id=Y (the bug that duplicated a genome run in the
// Zenodo deposit). An internal host the zone rule can't match preserves the
// full keyPath. Mirrors the catalog handler's `https://catalog.cache` key.
// The KV key is that same cache-key URL verbatim — one string per cached
// surface — so the post-publish purge (surface_annotation._purge_kv_for)
// can reproduce and delete it exactly.
//
// Only 200 and 404 are cached (both carry positive TTLs); 400/405 opt out.
// Deploy epoch folded into every cache key.
//
// Neither cache tier had any notion of the RESPONSE SHAPE, so a deploy that
// changed the shape kept serving the old one until each entry's own TTL —
// up to an hour for a KV read (its `cacheTtl`) and up to a day for a
// caches.default entry. Purging cannot fix that: the KV read's edge cache
// is not invalidated by deleting the KV key, and purging every gene by
// hand after every deploy is not a plan. Keying on the Worker version
// makes a deploy start a clean cache namespace, which is the correct
// granularity — a shape change IS a deploy.
//
// `CF_VERSION_METADATA` is a `[version_metadata]` binding whose `id`
// changes on every deploy. It is OPTIONAL here: a config without the
// binding (or `wrangler dev`) falls back to a fixed token and behaves
// exactly as before rather than crashing. Orphaned keys need no cleanup —
// every kv.put already carries an `expirationTtl` matched to the
// response's max-age, so old-epoch entries age out on their own.
export function cacheEpoch(env) {
  return env?.CF_VERSION_METADATA?.id || "v0";
}


export async function withEdgeCache(request, env, ctx, handler, { includeQuery = false } = {}) {
  // Archiver reads the live state: no cache read, no cache write. The echo
  // header lets the archiver refuse to archive if the bypass was NOT honoured
  // (wrong token / old Worker) instead of silently archiving cached bytes.
  if (await isArchiveBypass(request, env)) {
    const fresh = await handler();
    const headers = new Headers(fresh.headers);
    headers.set("X-Archive-Bypass-Honored", "1");
    headers.set("Cache-Control", "no-store");
    return new Response(fresh.body, { status: fresh.status, headers });
  }

  const cache = caches.default;
  const url = new URL(request.url);
  const keyPath = includeQuery ? url.pathname + url.search : url.pathname;
  const cacheKey = new Request(new URL(`/${cacheEpoch(env)}${keyPath}`, "https://surfaceome-api.cache").href, {
    method: "GET",
  });
  // (1) per-POP edge cache
  const hit = await cache.match(cacheKey);
  if (hit) return hit;

  const kv = env && env.RECORD_CACHE;
  const kvKey = cacheKey.url;

  // (2) shared global KV mirror
  if (kv) {
    let kvEntry = null;
    try {
      kvEntry = await kv.getWithMetadata(kvKey, { type: "arrayBuffer", cacheTtl: 3600 });
    } catch {
      kvEntry = null; // fail-open: a KV read hiccup falls through to D1
    }
    if (kvEntry && kvEntry.value) {
      const meta = kvEntry.metadata || {};
      const ttl = typeof meta.ttl === "number" ? meta.ttl : CACHE_TTL_LONG;
      const rebuilt = new Response(kvEntry.value, {
        status: typeof meta.status === "number" ? meta.status : 200,
        headers: {
          "Content-Type": meta.ct || "application/json; charset=utf-8",
          "Cache-Control": cacheControl(ttl),
          ...CORS_HEADERS,
        },
      });
      // Backfill the per-POP edge cache so the next hit in this POP skips KV.
      ctx.waitUntil(cache.put(cacheKey, rebuilt.clone()));
      return rebuilt;
    }
  }

  // (3) full miss — run the handler (D1) and populate both tiers.
  const response = await handler();
  // A response whose serve-time enrichment hit a real (non-missing-table)
  // D1 error carries DEGRADED_HEADER and Cache-Control: no-store (see
  // `json()`'s `degraded` param). Never persist those bytes to either cache
  // tier — the whole point of the header is that this response reflects a
  // transient failure, not the record's actual content, and caching it
  // would serve the degraded shape to every other reader for up to a day
  // (S100A7A revision 3's null topology fields were exactly this). The
  // response is still returned to THIS caller below, degraded header and
  // all — same posture as the archive-bypass path above, which also never
  // caches.
  const isDegraded = response.headers.has(DEGRADED_HEADER);
  if (!isDegraded && (response.status === 200 || response.status === 404)) {
    if (kv) {
      const ttl = maxAgeFromCacheControl(response.headers.get("Cache-Control"));
      const meta = {
        status: response.status,
        ct: response.headers.get("Content-Type"),
        ttl,
      };
      const body = await response.clone().arrayBuffer();
      // KV's expirationTtl floor is 60s; every 200/404 cached here carries
      // >= 60 (CACHE_TTL_LONG / CACHE_TTL_SHORT / notFound's 60).
      const expirationTtl = Math.max(60, ttl);
      ctx.waitUntil(Promise.all([
        kv.put(kvKey, body, { expirationTtl, metadata: meta }),
        cache.put(cacheKey, response.clone()),
      ]));
    } else {
      // Old caches.default-only path (KV binding absent / pre-binding).
      await cache.put(cacheKey, response.clone());
    }
  }
  return response;
}


export async function checkRateLimit(kv, ipHash, { prefix = "rl", max = 5 } = {}) {
  const key = `${prefix}:${ipHash}:${Math.floor(Date.now() / 3600_000)}`; // hour bucket
  const v = await kv.get(key);
  const n = v ? parseInt(v, 10) : 0;
  if (n >= max) return false;
  await kv.put(key, String(n + 1), { expirationTtl: 3600 });
  return true;
}

// Send the feedback notification email via Resend. Returns true on
// success, false on failure (the caller still 200's the submission —
// we don't lose the row just because email is slow).
