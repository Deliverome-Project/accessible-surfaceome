// HTTP response helpers, cache-control headers, CORS, validation, and D1 error detection.

export const CACHE_TTL_SHORT = 60;        // 1 min for list endpoints
export const CACHE_TTL_LONG  = 86400;     // 1 day for per-gene records
export const CACHE_SWR       = 86400;     // serve-stale window (revalidate / on-error)

// Build the Cache-Control header. On cacheable responses (ttl > 0) we add
// `stale-while-revalidate` so the edge serves the stale copy instantly on a
// miss while refreshing in the background, and `stale-if-error` so it keeps
// serving the stale copy when the Worker/origin errors — that's what absorbs
// the catalog handler's historical CPU-budget 503s (cf-error 1102) instead
// of surfacing them to readers. Freshness after a republish is handled by
// purge-on-publish (cloud/surface_annotation.publish_record), so the long
// TTL + serve-stale window costs nothing in staleness. ttl === 0 (e.g. a 400
// on bad input) opts out — a non-cacheable error must not be served stale.
// `immutable` is an opt-in for content that's genuinely permanent (e.g. a
// data release once its Zenodo DOI is set) — it replaces the
// stale-while-revalidate/stale-if-error pair (which imply the content MAY
// still change) with the `immutable` directive instead.
export function cacheControl(ttl, { immutable = false } = {}) {
  const base = `public, max-age=${ttl}, s-maxage=${ttl}`;
  if (ttl <= 0) return base;
  if (immutable) return `${base}, immutable`;
  return `${base}, stale-while-revalidate=${CACHE_SWR}, stale-if-error=${CACHE_SWR}`;
}

export const CORS_HEADERS = {
  "Access-Control-Allow-Origin":  "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, X-L1-Review-Token, X-L1-Invite-Token",
  // Let cross-origin clients read the record-history / degraded headers the
  // API docs tell them to act on (browsers hide non-safelisted headers).
  "Access-Control-Expose-Headers": "ETag, X-Surfaceome-Degraded, X-Surfaceome-Revision, X-Surfaceome-Content-Hash",
};

// The header a serve-time-enrichment failure sets on an otherwise-200
// response (see the `soft`/`degraded` machinery around handleGene /
// handleGeneEvidence below). `json()` centralizes it so every caller that
// passes `degraded` gets the same two behaviors for free: the header itself,
// and forcing `Cache-Control: no-store` so `withEdgeCache` never persists
// the degraded bytes (edge or KV) even though it still returns them to this
// one caller. Mirrored as DEGRADED_HEADER in
// src/accessible_surfaceome/cloud/record_history/archive.py; a test pins the
// two literals together so the archiver's check can't drift.
export const DEGRADED_HEADER = "X-Surfaceome-Degraded";

export function json(data, { status = 200, ttl = CACHE_TTL_SHORT, immutable = false, degraded = null } = {}) {
  const isDegraded = Array.isArray(degraded) && degraded.length > 0;
  const headers = {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": isDegraded ? "no-store" : cacheControl(ttl, { immutable }),
    ...CORS_HEADERS,
  };
  if (isDegraded) headers[DEGRADED_HEADER] = degraded.join(",");
  return new Response(JSON.stringify(data, null, 2), { status, headers });
}

export function notFound(msg = "not_found") {
  return json({ error: msg }, { status: 404, ttl: 60 });
}

export function badRequest(msg) {
  return json({ error: msg }, { status: 400, ttl: 0 });
}

// A D1 error whose message names a missing table is a PERSISTENT,
// intentional condition (the table hasn't been provisioned by this point in
// a rollout — e.g. deploying the Worker before a new table's sync has run
// once), not a transient hiccup. It reads the same on every request until
// the table exists, so treating it as "degraded" would permanently poison
// the cache for that route (every request forced to no-store) instead of
// just degrading gracefully to nulls, same as today. Real transient errors
// (timeout, isolate reset, temporary D1 unavailability) do NOT match this
// and fall through to the degraded path. Mirrors the existing tolerance in
// handleTagSites ("Resilient to deploy order: if tag_site_public isn't
// provisioned yet...") and fetchPaperMetadata's comment ("or when the table
// hasn't been created yet") — same intentional case, now applied uniformly
// via `soft()` instead of ad hoc per callsite.
// Schema-rollout errors (a table or column the Worker reads before its
// migration/sync has landed) are persistent, not transient: flagging them as
// degraded would force no-store on every gene and disable caching
// cohort-wide. Treat them as "absent" like before, but log loudly.
export function isMissingTable(e) {
  const msg = String(e?.message ?? e ?? "");
  if (!/no such (table|column)/i.test(msg)) return false;
  if (/no such column/i.test(msg)) console.error("schema_rollout_missing_column", msg);
  return true;
}

// TSV response — same cache/CORS posture as `json` but text/tsv.
// Used by /v1/triage/export.tsv so reproducibility scripts can `pd.read_csv(url, sep="\t")`
// straight from the API.
export function tsv(content, { status = 200, ttl = CACHE_TTL_SHORT } = {}) {
  return new Response(content, {
    status,
    headers: {
      "Content-Type": "text/tab-separated-values; charset=utf-8",
      "Cache-Control": cacheControl(ttl),
      ...CORS_HEADERS,
    },
  });
}

// Minimal TSV escaping: tabs/CR/LF in a cell would break the row,
// so collapse them to a single space. Don't quote — TSV doesn't.
export function tsvCell(v) {
  if (v == null) return "";
  return String(v).replace(/[\t\r\n]+/g, " ");
}

// D1 cost note (2026-09-28): the topology release lookups below use EXISTS
// probes on idx_topology_public_cohort_version instead of
// `IN (SELECT DISTINCT topology_version FROM topology_public WHERE cohort=…)`,
// which read every row of the cohort (6k–23k rows, 3× per record) and made
// public D1 fragile under load. Same result, ~7 rows read.
// Light gene-symbol validation: alnum + dash + dot, ≤30 chars.
export const SYMBOL_OK = /^[A-Za-z0-9][A-Za-z0-9._-]{0,29}$/;

export function checkSymbol(sym) {
  if (!sym || !SYMBOL_OK.test(sym)) return null;
  // NOTE: this uppercases, but most per-symbol D1 lookups compare the
  // stored `gene_symbol` COLLATE NOCASE. That's load-bearing: a minority
  // of HGNC symbols are stored MIXED-CASE (the `Cxorf` class, e.g.
  // `C11orf24`, lowercase "orf"), so an uppercased `= ?` match silently
  // misses them and the record endpoint 404s while `/v1/genes` still
  // lists them. Keep new per-symbol WHERE clauses `COLLATE NOCASE`.
  return sym.toUpperCase();
}

export const CACHE_TTL_IMMUTABLE = 31536000;  // 1 year

export function safeJsonParse(s) {
  if (s == null) return null;
  if (typeof s === "object") return s;
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}

// Read-time DDF projection from a set of pre-extracted sub-blocks
// rather than the full ~120 KB record JSON.
//
// Historical shape: this function took the entire `annotation_json`
// string, JSON.parsed it, and walked half a dozen sub-paths. At scale
// (~1.2k deep-dive records × ~120 KB each) that meant handleCatalog
// pulled ~145 MB of JSON through one D1 query and blew D1's per-query
// isolate-memory cap (see runbook + wrangler tail on 2026-07-01 —
// "D1_ERROR: D1 DB's isolate exceeded its memory limit and was reset").
//
// New shape: the two catalog queries `json_extract` just the 6
// sub-paths this projection reads — `$.filters`,
// `$....primary_compartment`, `$....restricted_subdomain`,
// `$....secreted_form`, `$....surface_bind`,
// `$....homo_oligomerization` — total ~4 KB per row instead of ~120 KB.
// Same public output; ~30× headroom under D1's cap.
//
// `parts` fields (all null-safe):
//   * `filters`             — parsed `$.filters` object (or null)
//   * `primary_compartment` — scalar string (or null)
//   * `restricted_subdomain`, `secreted_form`,
//     `surface_bind`, `homo_oligomerization` — parsed objects (or null)

export function htmlResponse(content, { status = 200 } = {}) {
  return new Response(content, {
    status,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
      ...CORS_HEADERS,
    },
  });
}


export const D1_BUSY_PATTERNS = [
  /long-running export/i,
  /D1 DB is overloaded/i,
  /overloaded/i,
  /Network connection lost/i,
  /storage operation exceeded timeout/i,
];

export function isD1Busy(e) {
  const msg = String(e?.message ?? e ?? "");
  return D1_BUSY_PATTERNS.some((re) => re.test(msg));
}

// ---------------------------------------------------------------------------
// Anonymous usage events: POST /v1/events
//
// The viewer beacons one event per click on a link or button so we can see
// which pages and controls people use. Each click becomes one Workers
// Analytics Engine data point of (page kind, gene, element kind, label) and
// nothing else: no IP, user agent, country, cookie or visitor id is written,
// so clicks can't be joined into a visitor or a session.
//
// It also beacons one "pageview" per page, for a daily unique-visitor count.
// That data point carries a visitor hash in place of a label: SHA-256 of a
// random per-day salt, the IP and the user agent, truncated. The salt lives in
// KV for 48 hours and is never written anywhere else, so once it expires a
// hash can't be recomputed from an IP; the same person gets a new hash every
// day, and the IP and user agent themselves are never stored. Counting
// distinct hashes per day gives daily unique visitors and nothing finer. The
// viewer's /privacy page describes all of this; keep the two in step.
//
// The endpoint always answers 204, whatever the body, so a beacon never
// surfaces an error in the visitor's console and a junk payload learns
// nothing. Without the USAGE_EVENTS binding it is a no-op.

export function databaseBusy() {
  return new Response(
    JSON.stringify({ error: "database_busy", retry_after_s: 30 }, null, 2),
    {
      status: 503,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "no-store",
        "Retry-After": "30",
        ...CORS_HEADERS,
      },
    },
  );
}
