/*
 * Unit tests for build-data-snapshot.mjs's `fetchRecordBody` — the
 * translation of the shared fetchWithRetry/createLimiter result into the
 * script-local { body } / { notFound } / { failed, degraded } shape that
 * drives snapshotRecords()'s written/notFound/failed bookkeeping and the
 * failure-fraction exit guard.
 *
 * The underlying pacing/retry machinery is covered by build_fetch.test.mjs;
 * this file only pins fetchRecordBody's own mapping logic. Global `fetch`
 * is stubbed before importing the module (module-level `snapshot()` is
 * guarded behind an import.meta.url === argv[1] check, so importing this
 * file for its exports does NOT run the whole snapshot pipeline or touch
 * the network).
 *
 *   npx --yes tsx --test tests/build_data_snapshot_fetch.test.mjs
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { DEGRADED_HEADER, createLimiter } from "../scripts/lib/build-fetch.mjs";

function fakeResponse({ status = 200, headers = {}, textBody = "" } = {}) {
  const h = new Map(Object.entries(headers).map(([k, v]) => [k.toLowerCase(), v]));
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name) => h.get(String(name).toLowerCase()) ?? null },
    text: async () => textBody,
    json: async () => JSON.parse(textBody || "{}"),
  };
}

// Stub the module-level `fetch` build-data-snapshot.mjs's own top-level
// `snapshot()` call would use IF it ran — it won't, because it's guarded.
// fetchRecordBody itself routes through fetchWithRetry's DEFAULT fetchImpl
// (global `fetch`), so we stub globalThis.fetch here.
let scenario = "healthy";
let calls = 0;
globalThis.fetch = async (url) => {
  calls += 1;
  switch (scenario) {
    case "healthy":
      return fakeResponse({ status: 200, textBody: '{"gene":{"hgnc_symbol":"EGFR"}}' });
    case "degraded-then-healthy":
      if (calls <= 2) {
        return fakeResponse({ status: 200, headers: { [DEGRADED_HEADER]: "x" }, textBody: "degraded" });
      }
      return fakeResponse({ status: 200, textBody: '{"gene":{"hgnc_symbol":"EGFR"}}' });
    case "persistent-degraded":
      return fakeResponse({ status: 200, headers: { [DEGRADED_HEADER]: "x" }, textBody: "degraded" });
    case "404":
      return fakeResponse({ status: 404 });
    case "persistent-500":
      return fakeResponse({ status: 500 });
    default:
      throw new Error(`unexpected scenario ${scenario} for ${url}`);
  }
};

const { fetchRecordBody } = await import("../scripts/build-data-snapshot.mjs");

function fastLimiter() {
  // rps large enough that pacing never adds real delay in a fast test run.
  return createLimiter({ concurrency: 4, rps: 100_000 });
}

test("fetchRecordBody: healthy response returns { body }", async () => {
  scenario = "healthy";
  calls = 0;
  const r = await fetchRecordBody("https://example.test/v1/genes/EGFR", fastLimiter(), { retryOpts: { sleep: async () => {} } });
  assert.deepEqual(r, { body: '{"gene":{"hgnc_symbol":"EGFR"}}' });
});

test("fetchRecordBody: degraded then healthy retries and returns the healthy body", async () => {
  scenario = "degraded-then-healthy";
  calls = 0;
  const r = await fetchRecordBody("https://example.test/v1/genes/EGFR", fastLimiter(), { retryOpts: { sleep: async () => {} } });
  assert.equal(r.body, '{"gene":{"hgnc_symbol":"EGFR"}}');
  assert.equal(calls, 3);
});

test("fetchRecordBody: persistently degraded is reported as failed+degraded, never written", async () => {
  scenario = "persistent-degraded";
  calls = 0;
  const r = await fetchRecordBody("https://example.test/v1/genes/EGFR", fastLimiter(), { retryOpts: { sleep: async () => {} } });
  assert.equal(r.body, undefined);
  assert.equal(r.failed, true);
  assert.equal(r.degraded, "x");
});

test("fetchRecordBody: 404 is tolerated as notFound (not counted as failed)", async () => {
  scenario = "404";
  calls = 0;
  const r = await fetchRecordBody("https://example.test/v1/genes/NOPE", fastLimiter(), { retryOpts: { sleep: async () => {} } });
  assert.deepEqual(r, { notFound: true });
});

test("fetchRecordBody: persistent 5xx is failed, not degraded", async () => {
  scenario = "persistent-500";
  calls = 0;
  const r = await fetchRecordBody("https://example.test/v1/genes/EGFR", fastLimiter(), { retryOpts: { sleep: async () => {} } });
  assert.equal(r.failed, true);
  assert.equal(r.degraded, null);
});
