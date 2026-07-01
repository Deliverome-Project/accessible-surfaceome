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
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const API_BASE = process.env.SURFACEOME_API_BASE
  || "https://api.deliverome.org/surfaceome";

const CACHE_DIR = path.resolve("build-cache");
const RECORDS_DIR = path.join(CACHE_DIR, "records");

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
// Concurrency 8 keeps request rate comfortably under the Worker's per-IP
// limiter with margin for the Pages build environment (a local run at 12
// saw ~27 transient 429s that the retry recovered; 8 drives that toward
// zero). Build cost is ~60-90s once per deploy — cheap insurance against
// a flaky build. ATTEMPTS×backoff still recovers the occasional blip.
const RECORD_CONCURRENCY = 8;
const RECORD_ATTEMPTS = 4;
const RECORD_MAX_FAIL_FRAC = 0.02;

function fmtMB(bytes) {
  return `${(bytes / 1_000_000).toFixed(2)} MB`;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

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
  // Fixed-size worker pool over a shared cursor — keeps at most
  // RECORD_CONCURRENCY fetches in flight so the burst never trips the
  // Worker's per-IP rate limiter (unlike Next's unbounded SSG fan-out).
  let cursor = 0;
  async function worker() {
    while (cursor < symbols.length) {
      const sym = symbols[cursor++];
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
  await snapshotRecords();
}

await snapshot();
