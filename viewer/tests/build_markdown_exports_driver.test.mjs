/*
 * Unit tests for build-markdown-exports.mjs's driver logic:
 *   - fetchEvidenceLedger: genuine-empty-ledger vs failure discrimination,
 *     and degraded-then-healthy retry.
 *   - loadRecordsFromApi: a genuine 404 record is tolerated silently; a
 *     persistently-failing/degraded record OR evidence fetch skips that
 *     gene and is counted (never a partial/empty-evidence export).
 *   - uploadMarkdownToR2: retries transient failures, returns false
 *     (never throws) after retries are exhausted.
 *   - computeFailFraction / reportSummaryAndMaybeFail: the failure-fraction
 *     exit-gate arithmetic AND that it fires even on a total wipeout (zero
 *     records survived to the export loop) — a real regression caught while
 *     writing these tests: the early `records.length === 0` return in
 *     main() used to skip the gate entirely, so an all-genes-failed run
 *     exited 0 instead of loudly.
 *
 * The underlying pacing/retry machinery is covered by build_fetch.test.mjs;
 * these tests pin this script's OWN translation/bookkeeping logic.
 *
 * Global `fetch` is stubbed before importing the module. The module's
 * `main()` auto-run is guarded behind an import.meta.url === argv[1]
 * check, so importing it here for its exports does not touch the network
 * or the filesystem. Env vars that affect module-load-time constants
 * (SURFACEOME_API_BASE, SURFACEOME_BUILD_FETCH_*) are set BEFORE the
 * dynamic import, below.
 *
 *   npx --yes tsx --test tests/build_markdown_exports_driver.test.mjs
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { DEGRADED_HEADER } from "../scripts/lib/build-fetch.mjs";

process.env.SURFACEOME_API_BASE = "https://example.test/surfaceome";
process.env.SURFACEOME_MD_SOURCE = "api";
// Large rps/concurrency so the shared limiter never adds real pacing delay
// in this fast unit-test run (production keeps the small defaults).
process.env.SURFACEOME_BUILD_FETCH_CONCURRENCY = "8";
process.env.SURFACEOME_BUILD_FETCH_RPS = "100000";
delete process.env.SURFACEOME_MD_GENES;
delete process.env.SURFACEOME_MD_LIMIT;

function fakeResponse({ status = 200, headers = {}, jsonBody } = {}) {
  const h = new Map(Object.entries(headers).map(([k, v]) => [k.toLowerCase(), v]));
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name) => h.get(String(name).toLowerCase()) ?? null },
    json: async () => {
      if (jsonBody === undefined) throw new SyntaxError("no body");
      return jsonBody;
    },
    text: async () => "",
  };
}

// Routing table the stub `fetch` consults, keyed by exact URL. Tests
// mutate this before each call; `fetchCounts` tracks calls per URL so
// tests can assert retry counts. `defaultRoute(url)`, when set, handles
// any URL with no exact entry — used by tests that pad the gene list with
// many uniformly-healthy "filler" genes (so a single real failure stays
// under the early-abort threshold — see the I1 note below) without
// needing one Map entry per filler gene.
let routes = new Map();
let defaultRoute = null;
let fetchCounts = new Map();
globalThis.fetch = async (url) => {
  fetchCounts.set(url, (fetchCounts.get(url) ?? 0) + 1);
  const handler = routes.get(url) ?? (defaultRoute ? () => defaultRoute(url) : null);
  if (!handler) throw new Error(`no stub route for ${url}`);
  return handler(fetchCounts.get(url));
};

const NO_WAIT = { sleep: async () => {} };

// Generic healthy responses for "filler" genes that pad a test's /v1/genes
// list. With I1's early-abort circuit breaker, `floor(MD_MAX_FAIL_FRAC ×
// total)` needs to be >= the number of INTENTIONAL failures a test wants
// to exercise, or loadRecordsFromApi aborts before finishing — at the
// default 1% threshold that means total >= 100 to tolerate even a single
// failure. Padding with filler genes (routed through `defaultRoute`
// rather than one Map entry each) keeps these tests realistic without
// bloating the fixture by hand.
function fillerGeneEntries(n) {
  return Array.from({ length: n }, (_, i) => ({ gene_symbol: `FILLER${i}` }));
}
function fillerDefaultRoute(url) {
  const m = url.match(/\/v1\/genes\/(FILLER\d+)(\/evidence)?$/);
  if (!m) return fakeResponse({ status: 404 });
  if (m[2]) return fakeResponse({ status: 200, jsonBody: { evidence: [] } });
  return fakeResponse({ status: 200, jsonBody: { gene: { hgnc_symbol: m[1] } } });
}

const {
  fetchEvidenceLedger,
  loadRecordsFromApi,
  uploadMarkdownToR2,
  computeFailFraction,
  reportSummaryAndMaybeFail,
  shouldSkipBuildCache,
} = await import("../scripts/build-markdown-exports.mjs");

const BASE = "https://example.test/surfaceome";

// ----------------------------------------------------------------
// fetchEvidenceLedger
// ----------------------------------------------------------------

test("fetchEvidenceLedger: a genuine empty ledger (200, evidence: []) is a real ok:true, not a failure", async () => {
  routes = new Map([
    [`${BASE}/v1/genes/AAA/evidence`, () => fakeResponse({ status: 200, jsonBody: { evidence: [] } })],
  ]);
  const r = await fetchEvidenceLedger("AAA", { retryOpts: NO_WAIT });
  assert.deepEqual(r, { ok: true, evidence: [] });
});

test("fetchEvidenceLedger: degraded then healthy retries and returns the real ledger", async () => {
  let calls = 0;
  routes = new Map([
    [
      `${BASE}/v1/genes/BBB/evidence`,
      () => {
        calls += 1;
        if (calls <= 2) {
          return fakeResponse({ status: 200, headers: { [DEGRADED_HEADER]: "paper_metadata" } });
        }
        return fakeResponse({ status: 200, jsonBody: { evidence: [{ evidence_id: "e1" }] } });
      },
    ],
  ]);
  const r = await fetchEvidenceLedger("BBB", { retryOpts: NO_WAIT });
  assert.equal(r.ok, true);
  assert.deepEqual(r.evidence, [{ evidence_id: "e1" }]);
  assert.equal(calls, 3);
});

test("fetchEvidenceLedger: persistent failure after retries is ok:false with a reason (never a silent [])", async () => {
  routes = new Map([
    [`${BASE}/v1/genes/CCC/evidence`, () => fakeResponse({ status: 500 })],
  ]);
  const r = await fetchEvidenceLedger("CCC", { retryOpts: NO_WAIT });
  assert.equal(r.ok, false);
  assert.ok(r.reason, "must carry a reason for the log line");
});

test("fetchEvidenceLedger: malformed payload (not an array) is a failure", async () => {
  routes = new Map([
    [`${BASE}/v1/genes/DDD/evidence`, () => fakeResponse({ status: 200, jsonBody: { evidence: "nope" } })],
  ]);
  const r = await fetchEvidenceLedger("DDD", { retryOpts: NO_WAIT });
  assert.equal(r.ok, false);
});

// ----------------------------------------------------------------
// loadRecordsFromApi
// ----------------------------------------------------------------

test("loadRecordsFromApi: 404 record tolerated, healthy gene included, degraded-evidence gene skipped", async () => {
  const FILLER_COUNT = 150; // see fillerGeneEntries doc — keeps CCC's 1 failure under the default early-abort threshold
  routes = new Map([
    [
      `${BASE}/v1/genes`,
      () =>
        fakeResponse({
          status: 200,
          jsonBody: {
            genes: [
              { gene_symbol: "AAA" },
              { gene_symbol: "BBB" },
              { gene_symbol: "CCC" },
              ...fillerGeneEntries(FILLER_COUNT),
            ],
          },
        }),
    ],
    [`${BASE}/v1/genes/AAA`, () => fakeResponse({ status: 200, jsonBody: { gene: { hgnc_symbol: "AAA" } } })],
    [`${BASE}/v1/genes/AAA/evidence`, () => fakeResponse({ status: 200, jsonBody: { evidence: [] } })],
    [`${BASE}/v1/genes/BBB`, () => fakeResponse({ status: 404 })],
    [`${BASE}/v1/genes/CCC`, () => fakeResponse({ status: 200, jsonBody: { gene: { hgnc_symbol: "CCC" } } })],
    [`${BASE}/v1/genes/CCC/evidence`, () => fakeResponse({ status: 200, headers: { [DEGRADED_HEADER]: "x" } })],
  ]);
  defaultRoute = fillerDefaultRoute;
  fetchCounts = new Map();

  const result = await loadRecordsFromApi({ retryOpts: NO_WAIT });
  defaultRoute = null;

  assert.equal(result.totalAttempted, 3 + FILLER_COUNT);
  assert.equal(result.records.length, 1 + FILLER_COUNT, "AAA + every filler gene should make it through");
  assert.ok(result.records.some((r) => r.rec.gene.hgnc_symbol === "AAA"));
  assert.deepEqual(result.skippedRecord, [], "a plain 404 is tolerated, not counted as a skip");
  assert.deepEqual(result.skippedEvidence, ["CCC"], "CCC's persistently-degraded evidence must skip the gene");
});

test("loadRecordsFromApi: a persistently-failing record fetch is counted in skippedRecord, without tripping the early-abort at a tolerable rate", async () => {
  const FILLER_COUNT = 150; // ZZZ's 1 failure among 151 genes is well under the default 1% early-abort threshold
  routes = new Map([
    [
      `${BASE}/v1/genes`,
      () =>
        fakeResponse({
          status: 200,
          jsonBody: { genes: [{ gene_symbol: "ZZZ" }, ...fillerGeneEntries(FILLER_COUNT)] },
        }),
    ],
    [`${BASE}/v1/genes/ZZZ`, () => fakeResponse({ status: 500 })],
  ]);
  defaultRoute = fillerDefaultRoute;
  const result = await loadRecordsFromApi({ retryOpts: NO_WAIT });
  defaultRoute = null;
  assert.equal(result.records.length, FILLER_COUNT, "every filler gene should still make it through despite ZZZ's failure");
  assert.deepEqual(result.skippedRecord, ["ZZZ"]);
  assert.deepEqual(result.skippedEvidence, []);
});

// ----------------------------------------------------------------
// loadRecordsFromApi — I1 early-abort circuit breaker
// ----------------------------------------------------------------

test("loadRecordsFromApi: aborts early (throws) once failures exceed floor(MAX_FAIL_FRAC × total), BEFORE returning any records", async () => {
  // total=3, default threshold 1% → floor(0.01*3)=0 — the very FIRST
  // failure (CCC's persistently-degraded evidence) must trip the breaker.
  routes = new Map([
    [
      `${BASE}/v1/genes`,
      () =>
        fakeResponse({
          status: 200,
          jsonBody: { genes: [{ gene_symbol: "AAA" }, { gene_symbol: "BBB" }, { gene_symbol: "CCC" }] },
        }),
    ],
    [`${BASE}/v1/genes/AAA`, () => fakeResponse({ status: 200, jsonBody: { gene: { hgnc_symbol: "AAA" } } })],
    [`${BASE}/v1/genes/AAA/evidence`, () => fakeResponse({ status: 200, jsonBody: { evidence: [] } })],
    [`${BASE}/v1/genes/BBB`, () => fakeResponse({ status: 200, jsonBody: { gene: { hgnc_symbol: "BBB" } } })],
    [`${BASE}/v1/genes/BBB/evidence`, () => fakeResponse({ status: 200, jsonBody: { evidence: [] } })],
    [`${BASE}/v1/genes/CCC`, () => fakeResponse({ status: 200, jsonBody: { gene: { hgnc_symbol: "CCC" } } })],
    [`${BASE}/v1/genes/CCC/evidence`, () => fakeResponse({ status: 200, headers: { [DEGRADED_HEADER]: "x" } })],
  ]);
  await assert.rejects(
    () => loadRecordsFromApi({ retryOpts: NO_WAIT }),
    /OUTAGE DETECTED/,
    "expected loadRecordsFromApi to throw once the failure threshold is crossed",
  );
});

test("loadRecordsFromApi: /v1/genes returning 0 genes is fatal, like the snapshot script (M2)", async () => {
  routes = new Map([
    [`${BASE}/v1/genes`, () => fakeResponse({ status: 200, jsonBody: { genes: [] } })],
  ]);
  await assert.rejects(
    () => loadRecordsFromApi({ retryOpts: NO_WAIT }),
    /0 genes/,
  );
});

// ----------------------------------------------------------------
// uploadMarkdownToR2
// ----------------------------------------------------------------

test("uploadMarkdownToR2: retries a transient failure then succeeds", async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    if (calls === 1) return { ok: false, status: 503, text: async () => "busy" };
    return { ok: true, status: 200, text: async () => "" };
  };
  const ok = await uploadMarkdownToR2("EGFR.md", "body", {
    attempts: 3,
    backoff: [1, 1],
    sleep: async () => {},
  });
  assert.equal(ok, true);
  assert.equal(calls, 2);
});

test("uploadMarkdownToR2: returns false (never throws) after retries are exhausted", async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return { ok: false, status: 500, text: async () => "down" };
  };
  const ok = await uploadMarkdownToR2("EGFR.md", "body", {
    attempts: 3,
    backoff: [1, 1],
    sleep: async () => {},
  });
  assert.equal(ok, false);
  assert.equal(calls, 3);
});

test("uploadMarkdownToR2: a hard 4xx does not retry", async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return { ok: false, status: 403, text: async () => "forbidden" };
  };
  const ok = await uploadMarkdownToR2("EGFR.md", "body", {
    attempts: 5,
    backoff: [1, 1, 1, 1],
    sleep: async () => {},
  });
  assert.equal(ok, false);
  assert.equal(calls, 1);
});

// ----------------------------------------------------------------
// computeFailFraction
// ----------------------------------------------------------------

test("computeFailFraction: under the 1% default cap", () => {
  const stats = { totalAttempted: 1000, skippedRecord: ["a"], skippedEvidence: [], failedUpload: [] };
  const { totalFailed, failFrac } = computeFailFraction(stats);
  assert.equal(totalFailed, 1);
  assert.equal(failFrac, 0.001);
});

test("computeFailFraction: exactly at the boundary is NOT over the cap (strict >)", () => {
  const stats = { totalAttempted: 100, skippedRecord: [], skippedEvidence: [], failedUpload: Array(1).fill("x") };
  const { failFrac } = computeFailFraction(stats);
  assert.equal(failFrac, 0.01);
});

test("computeFailFraction: over the cap sums all three failure kinds", () => {
  const stats = {
    totalAttempted: 10,
    skippedRecord: ["a"],
    skippedEvidence: ["b"],
    failedUpload: ["c"],
  };
  const { totalFailed, failFrac } = computeFailFraction(stats);
  assert.equal(totalFailed, 3);
  assert.equal(failFrac, 0.3);
});

test("computeFailFraction: totalAttempted=0 doesn't divide by zero", () => {
  const stats = { totalAttempted: 0, skippedRecord: [], skippedEvidence: [], failedUpload: [] };
  const { totalFailed, failFrac } = computeFailFraction(stats);
  assert.equal(totalFailed, 0);
  assert.equal(Number.isFinite(failFrac), true);
});

// ----------------------------------------------------------------
// reportSummaryAndMaybeFail — the process.exitCode side effect, including
// the "total wipeout" regression (records.length === 0 must still trip
// the gate, not exit 0 silently).
// ----------------------------------------------------------------

test("reportSummaryAndMaybeFail: under the cap leaves exitCode unset", () => {
  process.exitCode = undefined;
  reportSummaryAndMaybeFail({
    totalAttempted: 1000,
    skippedRecord: ["a"],
    skippedEvidence: [],
    failedUpload: [],
    uploaded: 0,
    written: 999,
  });
  assert.equal(process.exitCode, undefined);
});

test("reportSummaryAndMaybeFail: a total wipeout (0 records survived) still sets exitCode=1", () => {
  process.exitCode = undefined;
  // Every one of 50 attempted genes failed its record fetch — the exact
  // shape main() has when `records.length === 0` triggers its early
  // return. reportSummaryAndMaybeFail must be reachable from THAT path,
  // not only from the bottom of a successful run.
  reportSummaryAndMaybeFail({
    totalAttempted: 50,
    skippedRecord: Array.from({ length: 50 }, (_, i) => `GENE${i}`),
    skippedEvidence: [],
    failedUpload: [],
    uploaded: 0,
    written: 0,
  });
  assert.equal(process.exitCode, 1);
  process.exitCode = undefined; // don't leak into the test runner's own exit
});

test("reportSummaryAndMaybeFail: over the cap sets exitCode=1", () => {
  process.exitCode = undefined;
  reportSummaryAndMaybeFail({
    totalAttempted: 10,
    skippedRecord: ["a", "b"],
    skippedEvidence: [],
    failedUpload: [],
    uploaded: 8,
    written: 0,
  });
  assert.equal(process.exitCode, 1);
  process.exitCode = undefined;
});

// ----------------------------------------------------------------
// shouldSkipBuildCache (C1) — never read viewer/build-cache/records when
// this is an ops job re-publishing to a live surface, since that cache
// can be a stale local artifact from before this incident's pacing fix.
// ----------------------------------------------------------------

test("shouldSkipBuildCache: MD_TARGET=r2 always skips the build-cache", () => {
  assert.equal(shouldSkipBuildCache("r2", null), true);
  assert.equal(shouldSkipBuildCache("r2", new Set(["EGFR"])), true);
});

test("shouldSkipBuildCache: SURFACEOME_MD_GENES set always skips the build-cache, regardless of MD_TARGET", () => {
  assert.equal(shouldSkipBuildCache("public", new Set(["EGFR"])), true);
});

test("shouldSkipBuildCache: neither r2 nor a gene filter — the build-cache is used normally", () => {
  assert.equal(shouldSkipBuildCache("public", null), false);
});
