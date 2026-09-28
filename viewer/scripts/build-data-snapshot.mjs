#!/usr/bin/env node
/**
 * Pre-fetch the Worker data SSG needs to disk so `next build` reads it
 * from the filesystem rather than refetching live per-page.
 *
 * ## What this fixes
 *
 * ### 1. Over-2MB endpoints blow the Next.js Data Cache
 *
 * Next.js's Data Cache rejects fetched responses larger than 2MB. Two of
 * our Worker endpoints exceed that cap and keep growing:
 *
 *   /v1/catalog            ~5.7 MB  (genome-wide catalog)
 *   /v1/benchmark/matrix   ~3.0 MB  (147 × per-DB × per-model)
 *
 * Each SSG worker that calls them gets a Data-Cache miss, refetches from
 * the Worker, and the build log fills with "Failed to set Next.js data
 * cache, items over 2MB can not be cached". On a recent build that was
 * ~15 identical fetches against a single endpoint — costing build wall
 * time AND hammering D1 every deploy.
 *
 * ### 2. The ~1.2k per-gene record fetches trip the Worker rate limiter
 *
 * `generateStaticParams` emits a page per deep-dive gene (~1.2k today),
 * and each page's server component calls `loadSurfaceomeRecord(sym)` →
 * `/v1/genes/{sym}`. Next fires those as a large CONCURRENT burst during
 * SSG. That burst trips the Worker's per-IP rate limiter (429s) — and
 * `loadSurfaceomeRecord` historically swallowed ANY fetch error as
 * `null`, so the gene page's `if (!rec) notFound()` baked a NOT-FOUND
 * page for every rate-limited gene while the build still exited 0.
 * Symptom in production: every gene page 404s (client-side not-found)
 * even though the Worker serves the record fine and the catalog page
 * (pre-fetched here) renders — because the catalog was snapshotted and
 * the per-gene records were not. See the record loop below.
 *
 * ## What this script does
 *
 * - Reads SURFACEOME_API_BASE the same way the runtime loaders do.
 * - Fetches /v1/catalog + /v1/benchmark/matrix.
 * - Enumerates /v1/genes and pre-fetches EVERY per-gene record under a
 *   small concurrency cap with retry-on-429/5xx, writing each to
 *   `viewer/build-cache/records/{SYMBOL}.json`. A high miss rate FAILS
 *   the build (exit 1) rather than silently shipping not-found pages.
 * - Writes everything to `viewer/build-cache/` (gitignored — derived
 *   artifacts).
 * - Exits 0 (with a no-op) when API_BASE is `local` or empty so the
 *   offline smoke build still works without network.
 *
 * The runtime loaders in `viewer/lib/surfaceome.ts` look at the
 * build-cache directory first via `readBuildCache()`, then fall back to
 * a live fetch if the file is missing — so a contributor running
 * `next dev` without first running the snapshot still gets data.
 *
 * Wired into `package.json` BEFORE `next build`:
 *
 *   "build": "npm run build:exports && npm run build:snapshot && next build --webpack"
 */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import {
  createLimiter,
  fetchWithRetry,
  resolveBuildFetchTuning,
  resolveMaxFailFrac,
} from "./lib/build-fetch.mjs";

const API_BASE = process.env.SURFACEOME_API_BASE
  || "https://api.deliverome.org/surfaceome";

const CACHE_DIR = path.resolve("build-cache");
const RECORDS_DIR = path.join(CACHE_DIR, "records");

// Shipped static assets (served at /data/… on the site origin, not the
// Worker). The gene-page dropdown fetches gene-synonyms.json from here.
const PUBLIC_DATA_DIR = path.resolve("public", "data");
// Same NCBI gene_info TSV `lib/surfaceome.ts::loadGeneNamesMap` reads for
// the homepage catalog search. The gene page is a client shell and can't
// read it directly, so we bake a slim symbol→synonyms overlay from it.
const GENE_INFO_TSV = path.resolve(
  "..", "data", "external", "ncbi_gene_info",
  "Homo_sapiens.protein_coding.with_hgnc.triageable.tsv",
);

const ENDPOINTS = [
  { endpoint: "/v1/catalog", file: "catalog.json" },
  { endpoint: "/v1/benchmark/matrix", file: "benchmark-matrix.json" },
];

// Per-gene record pre-fetch tuning. Paced through the shared
// createLimiter/fetchWithRetry (viewer/scripts/lib/build-fetch.mjs) so the
// build can never again fire the ~5.3k per-gene fetches as an unbounded
// burst against the Worker — that burst is what drove 27k-62k Worker
// requests/15min (baseline 6-16k) and 500s on the shared public D1 during
// the 2026-09-28 incident. Concurrency AND request-rate are both capped;
// override via SURFACEOME_BUILD_FETCH_CONCURRENCY / SURFACEOME_BUILD_FETCH_RPS
// (defaults 4 / 8 req/s — see build-fetch.mjs). Retry absorbs the transient
// 429/5xx a cold D1 still throws under load, AND a 200 that carries
// `X-Surfaceome-Degraded` (serve-time enrichment failed) — a degraded
// record must never be baked into the static build. `MAX_FAIL_FRAC`
// (env SURFACEOME_BUILD_MAX_FAILED_FRAC, default kept at the pre-existing
// 0.02 here) is the guardrail: a high miss/degraded rate means the
// Worker/D1 is unhealthy, and we must fail LOUD instead of shipping a site
// full of not-found (or silently-degraded) gene pages.
const { concurrency: RECORD_CONCURRENCY, rps: RECORD_RPS } = resolveBuildFetchTuning();
const RECORD_ATTEMPTS = 5;
const RECORD_MAX_FAIL_FRAC = resolveMaxFailFrac(0.02);

function fmtMB(bytes) {
  return `${(bytes / 1_000_000).toFixed(2)} MB`;
}

/**
 * Fetch a per-gene record URL through the shared limiter, retrying
 * transient failures (429 rate-limit, 5xx cold-D1, network errors) AND a
 * degraded-but-200 response with backoff. Returns a discriminated result
 * so the caller can tell the kinds of miss apart — they mean opposite
 * things for the build guard:
 *
 *   { body }         — success (healthy, non-degraded); write it.
 *   { notFound }     — deterministic 404 / hard 4xx. The gene is in
 *                      /v1/genes but the record endpoint can't serve it
 *                      (a Worker list/record inconsistency, e.g. the
 *                      renamed-Cxorf genes). Tolerated — the gene page
 *                      would `notFound()` regardless, correctly. Does
 *                      NOT count against the fail-rate guard.
 *   { failed, degraded } — retries exhausted on a transient error OR a
 *                      persistently-degraded response. THIS is the
 *                      rate-limit/blocking/D1-outage signal the guard
 *                      exists to catch; a high rate of these fails the
 *                      build. `degraded` is set when the LAST attempt was
 *                      a degraded 200 rather than an error, for logging.
 */
async function fetchRecordBody(url, limiter, { retryOpts } = {}) {
  const r = await limiter(() =>
    fetchWithRetry(url, { maxAttempts: RECORD_ATTEMPTS, ...retryOpts }),
  );
  if (r.ok) return { body: r.body };
  if (r.hardFailure) return { notFound: true };
  return { failed: true, degraded: r.degraded };
}

async function snapshotEndpoints() {
  for (const { endpoint, file } of ENDPOINTS) {
    const url = `${API_BASE}${endpoint}`;
    const t0 = performance.now();
    console.log(`[snapshot] fetching ${url}`);
    let res;
    try {
      res = await fetch(url);
    } catch (e) {
      console.error(`[snapshot] ${endpoint} → fetch failed: ${e.message}`);
      process.exit(1);
    }
    if (!res.ok) {
      console.error(`[snapshot] ${endpoint} → HTTP ${res.status}`);
      process.exit(1);
    }
    const body = await res.text();
    const out = path.join(CACHE_DIR, file);
    await writeFile(out, body);
    const dt = Math.round(performance.now() - t0);
    console.log(`  wrote ${out} (${fmtMB(body.length)}, ${dt} ms)`);
  }
}

async function snapshotRecords() {
  // Enumerate the deep-dive gene set the same way generateStaticParams
  // does (Worker /v1/genes). One small fetch — same as the catalog above,
  // which already succeeds on the Pages build, so this is not the thing
  // the WAF/rate-limiter blocks.
  const listUrl = `${API_BASE}/v1/genes`;
  console.log(`[snapshot] fetching ${listUrl}`);
  let listRes;
  try {
    listRes = await fetch(listUrl);
  } catch (e) {
    console.error(`[snapshot] /v1/genes → fetch failed: ${e.message}`);
    process.exit(1);
  }
  if (!listRes.ok) {
    console.error(`[snapshot] /v1/genes → HTTP ${listRes.status}`);
    process.exit(1);
  }
  const listBody = await listRes.json();
  const symbols = (listBody.genes ?? [])
    .map((g) => g.gene_symbol)
    .filter(Boolean);
  if (symbols.length === 0) {
    console.error(
      "[snapshot] /v1/genes returned 0 genes — refusing to ship a site " +
        "with no gene pages",
    );
    process.exit(1);
  }
  await mkdir(RECORDS_DIR, { recursive: true });

  const t0 = performance.now();
  console.log(
    `[snapshot] pre-fetching ${symbols.length} per-gene records ` +
      `(concurrency ${RECORD_CONCURRENCY}, ${RECORD_RPS} req/s, ${RECORD_ATTEMPTS} attempts each)…`,
  );
  const failed = []; // transient — retries exhausted (the rate-limit/outage bug)
  const degradedFailed = []; // subset of `failed` whose last attempt was a degraded 200
  const notFound = []; // deterministic 404 — Worker can't serve; tolerated
  let written = 0;
  let done = 0;
  // Every fetch is scheduled through the shared limiter, which caps BOTH
  // concurrency and request rate — the burst that caused the incident was
  // concurrency-bounded but rate-UNbounded (12 in flight, no pacing).
  const limiter = createLimiter({ concurrency: RECORD_CONCURRENCY, rps: RECORD_RPS });
  let cursor = 0;
  async function worker() {
    while (cursor < symbols.length) {
      const sym = symbols[cursor++];
      const r = await fetchRecordBody(`${API_BASE}/v1/genes/${sym}`, limiter);
      if (r.body) {
        await writeFile(path.join(RECORDS_DIR, `${sym}.json`), r.body);
        written += 1;
      } else if (r.notFound) {
        notFound.push(sym);
      } else {
        failed.push(sym);
        if (r.degraded) degradedFailed.push(sym);
      }
      done += 1;
      if (done % 250 === 0) console.log(`  … ${done}/${symbols.length}`);
    }
  }
  await Promise.all(
    Array.from({ length: Math.min(RECORD_CONCURRENCY, symbols.length) }, worker),
  );
  const dt = Math.round(performance.now() - t0);
  const failFrac = failed.length / symbols.length;
  console.log(
    `  wrote ${written}/${symbols.length} records to ${RECORDS_DIR} ` +
      `(${dt} ms; ${failed.length} transient-failed [${degradedFailed.length} degraded], ${notFound.length} 404)`,
  );
  // Guardrail: a high TRANSIENT-failure rate (which now also counts a
  // persistently-degraded 200 — serve-time enrichment failed on the
  // Worker) means the Worker/D1 is rate-limiting, blocking, or unhealthy.
  // Fail LOUD — shipping now would bake not-found pages, or worse a
  // degraded record, for those genes. Genuine 404s (gene in /v1/genes but
  // no serveable record — a separate Worker inconsistency) are NOT
  // counted here: those pages would `notFound()` regardless, so
  // tolerating them is correct.
  if (failFrac > RECORD_MAX_FAIL_FRAC) {
    console.error(
      `[snapshot] ${failed.length}/${symbols.length} record fetches hit ` +
        `TRANSIENT failure (${degradedFailed.length} still degraded) after ` +
        `${RECORD_ATTEMPTS} attempts ` +
        `(${(failFrac * 100).toFixed(1)}% > ${(RECORD_MAX_FAIL_FRAC * 100).toFixed(0)}% cap). ` +
        `The Worker/D1 is rate-limiting/blocking/unhealthy; refusing to ship a ` +
        `site full of not-found or degraded gene pages. Failed sample: ` +
        `${failed.slice(0, 10).join(", ")}`,
    );
    process.exit(1);
  }
  if (failed.length > 0) {
    console.warn(
      `  ⚠ ${failed.length} transient failure(s) under the cap, tolerated ` +
        `(${degradedFailed.length} degraded): ${failed.slice(0, 20).join(", ")}`,
    );
  }
  if (notFound.length > 0) {
    console.warn(
      `  ⚠ ${notFound.length} gene(s) in /v1/genes have no serveable record ` +
        `(Worker list/record inconsistency — will render not-found): ` +
        `${notFound.slice(0, 20).join(", ")}`,
    );
  }
  return symbols;
}

// Bake public/data/gene-synonyms.json — a slim {SYMBOL: synonyms[]} overlay
// for the deep-dive gene set, so the client gene-page dropdown can match
// alias queries ("Nav1.7" → SCN9A) exactly like the homepage catalog search.
// The synonyms come from the same NCBI gene_info TSV that
// lib/surfaceome.ts::loadGeneNamesMap reads for the homepage; the gene page
// is a client shell and can't read that TSV itself. Restricted to deep-dive
// symbols (from /v1/genes) so the shipped asset stays small.
//
// Degrades gracefully: a missing TSV writes an empty map (the dropdown falls
// back to symbol-only matching) rather than failing the build — synonyms are
// a search convenience, not load-bearing for navigation.
async function snapshotGeneSynonyms(symbolsList) {
  // Reuse the deep-dive gene list snapshotRecords() already fetched rather than
  // re-hitting /v1/genes. A second call here 429s against the rate-limiter left
  // hot by the ~5k-record pre-fetch burst, and that 429 was fataling the whole
  // build (process.exit(1)) despite this overlay being a search-only
  // convenience. Empty list → empty overlay, never fatal.
  const symbols = new Set(symbolsList ?? []);
  if (symbols.size === 0) {
    console.warn(
      "[snapshot] gene-synonyms → no gene list available; shipping empty " +
        "overlay (dropdown falls back to symbol-only).",
    );
  }

  // Mirrors loadGeneNamesMap's Pass-1 parse: NCBI gene_info, pipe-delimited
  // `synonyms` column, "-" and empties dropped.
  const overlay = {};
  try {
    const tsv = await readFile(GENE_INFO_TSV, "utf-8");
    const lines = tsv.split(/\r?\n/);
    const header = (lines[0] ?? "").split("\t");
    const symIdx = header.indexOf("gene_symbol");
    const synIdx = header.indexOf("synonyms");
    if (symIdx >= 0 && synIdx >= 0) {
      for (let i = 1; i < lines.length; i += 1) {
        if (!lines[i]) continue;
        const cols = lines[i].split("\t");
        const sym = cols[symIdx]?.trim();
        if (!sym || !symbols.has(sym)) continue;
        const raw = cols[synIdx]?.trim() ?? "";
        const syn = raw && raw !== "-"
          ? raw.split("|").filter((s) => s && s !== "-")
          : [];
        if (syn.length > 0) overlay[sym] = syn;
      }
    } else {
      console.warn(
        "[snapshot] gene-synonyms → TSV missing gene_symbol/synonyms columns; " +
          "shipping empty overlay (dropdown falls back to symbol-only).",
      );
    }
  } catch (e) {
    console.warn(
      `[snapshot] gene-synonyms → cannot read ${GENE_INFO_TSV} (${e.message}); ` +
        "shipping empty overlay (dropdown falls back to symbol-only).",
    );
  }

  await mkdir(PUBLIC_DATA_DIR, { recursive: true });
  const out = path.join(PUBLIC_DATA_DIR, "gene-synonyms.json");
  const body = JSON.stringify(overlay);
  await writeFile(out, body);
  console.log(
    `  wrote ${out} (${Object.keys(overlay).length}/${symbols.size} deep-dive ` +
      `genes with synonyms, ${fmtMB(body.length)})`,
  );
}

async function snapshot() {
  if (!API_BASE || API_BASE === "local") {
    console.log(
      `[snapshot] SURFACEOME_API_BASE=${API_BASE || "<empty>"} — skipping ` +
        `pre-fetch (runtime loaders will return empty stubs).`,
    );
    return;
  }

  await mkdir(CACHE_DIR, { recursive: true });
  await snapshotEndpoints();
  const symbols = await snapshotRecords();
  await snapshotGeneSynonyms(symbols);
}

// Exported for unit tests (viewer/tests/build_data_snapshot_fetch.test.mjs)
// — `fetchRecordBody`'s translation of `fetchWithRetry`'s discriminated
// result into { body } / { notFound } / { failed, degraded } is the
// script-local logic worth pinning directly; the underlying pacing/retry
// machinery is covered by build-fetch.test.mjs.
export { fetchRecordBody, snapshot, snapshotRecords };

// Only auto-run when executed directly (`node build-data-snapshot.mjs`),
// not when imported by a test.
const isMain =
  process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) {
  await snapshot();
}
