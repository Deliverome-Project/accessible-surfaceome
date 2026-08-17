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

// Per-gene record pre-fetch tuning. Concurrency stays well under the
// Worker's per-IP rate limiter — the whole point is that a naive
// next-build burst of ~1.2k SIMULTANEOUS fetches is exactly what trips
// it. Retry absorbs the transient 429/5xx a cold D1 still throws under
// load. `MAX_FAIL_FRAC` is the guardrail: a high miss rate means the
// Worker/WAF is blocking the build, and we must fail LOUD instead of
// shipping a site full of not-found gene pages.
// Concurrency bounds how many fetches are in flight (for latency overlap); the
// STEADY-STATE request rate is bounded separately by `ratePace()` below —
// because concurrency alone does NOT bound req/min when per-request latency
// varies. At concurrency 8 with no pacer the build reached ~640 req/min
// (measured: 5130 records / 480 s) — just OVER the Worker's 600/60 s per-IP
// general limiter — so ~2-3% of records 429'd past the retry budget and
// tripped the fail-rate guard (a real dev/prod build failure, not a flake).
// `ratePace()` now caps request STARTS at ~480/min (20% under the limiter),
// which eliminates the rate-limit misses; concurrency 8 keeps latency overlap
// so the paced record pre-fetch is still ~11 min, once per deploy.
const RECORD_CONCURRENCY = 8;
const RECORD_ATTEMPTS = 4;
const RECORD_MAX_FAIL_FRAC = 0.02;
// Minimum spacing between per-gene request STARTS across all workers. 125 ms ⇒
// ~8 req/s ⇒ ~480 req/min, ~20% under the Worker's 600/60 s per-IP general
// limiter. Latency-independent (unlike concurrency), so it stays under the cap
// as the cohort grows or D1 latency shifts.
const RECORD_MIN_INTERVAL_MS = 125;

function fmtMB(bytes) {
  return `${(bytes / 1_000_000).toFixed(2)} MB`;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Global request-rate pacer shared by all record-fetch workers. Hands out
// monotonic "slots" spaced RECORD_MIN_INTERVAL_MS apart so the aggregate
// request-START rate is bounded regardless of concurrency or per-request
// latency — the concurrency cap alone can't do that (throughput = concurrency
// ÷ latency, which drifts over the Worker's fixed 600/60 s per-IP limit as
// latency varies). A worker awaits its slot before each initial fetch.
let _nextSlotMs = 0;
async function ratePace() {
  const now = Date.now();
  const slot = Math.max(now, _nextSlotMs);
  _nextSlotMs = slot + RECORD_MIN_INTERVAL_MS;
  const wait = slot - now;
  if (wait > 0) await sleep(wait);
}

// Backoff schedule for transient retries. attempt 0→0.5s, 1→1.5s, 2→3s,
// then capped at 6s.
function backoffMs(attempt) {
  return [500, 1500, 3000, 6000][attempt] ?? 6000;
}

/**
 * Fetch a per-gene record URL, retrying transient failures (429
 * rate-limit, 5xx cold-D1, network errors) with backoff. Returns a
 * discriminated result so the caller can tell the two kinds of miss
 * apart — they mean opposite things for the build guard:
 *
 *   { body }         — success; write it.
 *   { notFound }     — deterministic 404 / hard 4xx. The gene is in
 *                      /v1/genes but the record endpoint can't serve it
 *                      (a Worker list/record inconsistency, e.g. the
 *                      renamed-Cxorf genes). Tolerated — the gene page
 *                      would `notFound()` regardless, correctly. Does
 *                      NOT count against the fail-rate guard.
 *   { failed }       — retries exhausted on a transient error. THIS is
 *                      the rate-limit/blocking signal the guard exists
 *                      to catch; a high rate of these fails the build.
 */
async function fetchRecordBody(url) {
  for (let attempt = 0; attempt < RECORD_ATTEMPTS; attempt += 1) {
    let res = null;
    try {
      res = await fetch(url);
    } catch {
      res = null; // network error / abort — transient
    }
    if (res) {
      if (res.ok) return { body: await res.text() };
      // 404 (unpublished) or any other hard 4xx — deterministic, tolerated.
      if (res.status === 404 || (res.status !== 429 && res.status < 500)) {
        return { notFound: true };
      }
    }
    // transient (network error, 429, or 5xx) — back off and retry
    if (attempt < RECORD_ATTEMPTS - 1) await sleep(backoffMs(attempt));
  }
  return { failed: true };
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
      `(concurrency ${RECORD_CONCURRENCY}, ${RECORD_ATTEMPTS} attempts each)…`,
  );
  const failed = []; // transient — retries exhausted (the rate-limit bug)
  const notFound = []; // deterministic 404 — Worker can't serve; tolerated
  let written = 0;
  let done = 0;
  // Fixed-size worker pool over a shared cursor keeps at most
  // RECORD_CONCURRENCY fetches in flight; `ratePace()` additionally bounds the
  // aggregate request-START rate under the Worker's per-IP limiter (unlike
  // Next's unbounded SSG fan-out, and unlike concurrency alone).
  let cursor = 0;
  async function worker() {
    while (cursor < symbols.length) {
      const sym = symbols[cursor++];
      await ratePace(); // stay under the Worker's 600/60s per-IP general limiter
      const r = await fetchRecordBody(`${API_BASE}/v1/genes/${sym}`);
      if (r.body) {
        await writeFile(path.join(RECORDS_DIR, `${sym}.json`), r.body);
        written += 1;
      } else if (r.notFound) {
        notFound.push(sym);
      } else {
        failed.push(sym);
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
      `(${dt} ms; ${failed.length} transient-failed, ${notFound.length} 404)`,
  );
  // Guardrail: a high TRANSIENT-failure rate means the Worker is
  // rate-limiting / blocking the build. Fail LOUD — shipping now would
  // bake not-found pages for those genes, the exact bug this snapshot
  // prevents. Genuine 404s (gene in /v1/genes but no serveable record —
  // a separate Worker inconsistency) are NOT counted here: those pages
  // would `notFound()` regardless, so tolerating them is correct.
  if (failFrac > RECORD_MAX_FAIL_FRAC) {
    console.error(
      `[snapshot] ${failed.length}/${symbols.length} record fetches hit ` +
        `TRANSIENT failure after ${RECORD_ATTEMPTS} attempts ` +
        `(${(failFrac * 100).toFixed(1)}% > ${(RECORD_MAX_FAIL_FRAC * 100).toFixed(0)}% cap). ` +
        `The Worker is rate-limiting/blocking the build; refusing to ship a ` +
        `site full of not-found gene pages. Failed sample: ` +
        `${failed.slice(0, 10).join(", ")}`,
    );
    process.exit(1);
  }
  if (failed.length > 0) {
    console.warn(
      `  ⚠ ${failed.length} transient failure(s) under the cap, tolerated: ` +
        `${failed.slice(0, 20).join(", ")}`,
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

await snapshot();
