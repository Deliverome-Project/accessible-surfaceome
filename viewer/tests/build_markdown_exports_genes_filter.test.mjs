/*
 * Unit test for SURFACEOME_MD_GENES — the operator re-export filter
 * (viewer/scripts/build-markdown-exports.mjs). Separate file from
 * build_markdown_exports_driver.test.mjs because the filter is captured
 * as a module-level constant at import time, so it needs its own env
 * before the dynamic import runs.
 *
 *   npx --yes tsx --test tests/build_markdown_exports_genes_filter.test.mjs
 */
import { test } from "node:test";
import assert from "node:assert/strict";

process.env.SURFACEOME_API_BASE = "https://example.test/surfaceome";
process.env.SURFACEOME_MD_SOURCE = "api";
process.env.SURFACEOME_BUILD_FETCH_CONCURRENCY = "8";
process.env.SURFACEOME_BUILD_FETCH_RPS = "100000";
process.env.SURFACEOME_MD_GENES = "AAA, CCC"; // filter to a 2-gene subset
delete process.env.SURFACEOME_MD_LIMIT;

const BASE = "https://example.test/surfaceome";

function fakeResponse({ status = 200, jsonBody } = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => null },
    json: async () => jsonBody,
    text: async () => "",
  };
}

let routes;
let requestedUrls = [];
globalThis.fetch = async (url) => {
  requestedUrls.push(url);
  const handler = routes.get(url);
  if (!handler) throw new Error(`no stub route for ${url}`);
  return handler();
};

const { loadRecordsFromApi } = await import("../scripts/build-markdown-exports.mjs");

test("SURFACEOME_MD_GENES restricts loadRecordsFromApi to exactly the listed symbols", async () => {
  routes = new Map([
    [
      `${BASE}/v1/genes`,
      () =>
        fakeResponse({
          status: 200,
          jsonBody: {
            genes: [
              { gene_symbol: "AAA" },
              { gene_symbol: "BBB" }, // NOT in the filter — must be skipped, no fetch at all
              { gene_symbol: "CCC" },
            ],
          },
        }),
    ],
    [`${BASE}/v1/genes/AAA`, () => fakeResponse({ status: 200, jsonBody: { gene: { hgnc_symbol: "AAA" } } })],
    [`${BASE}/v1/genes/AAA/evidence`, () => fakeResponse({ status: 200, jsonBody: { evidence: [] } })],
    [`${BASE}/v1/genes/CCC`, () => fakeResponse({ status: 200, jsonBody: { gene: { hgnc_symbol: "CCC" } } })],
    [`${BASE}/v1/genes/CCC/evidence`, () => fakeResponse({ status: 200, jsonBody: { evidence: [] } })],
  ]);
  requestedUrls = [];

  const result = await loadRecordsFromApi({ retryOpts: { sleep: async () => {} } });

  assert.equal(result.totalAttempted, 2, "BBB must be filtered out before any fetch is attempted");
  assert.deepEqual(
    result.records.map((r) => r.rec.gene.hgnc_symbol).sort(),
    ["AAA", "CCC"],
  );
  assert.ok(
    !requestedUrls.some((u) => u.includes("/v1/genes/BBB")),
    "BBB must never be fetched — the whole point of the filter is to avoid touching genes outside it",
  );
});

test("SURFACEOME_MD_GENES: a symbol not in /v1/genes throws with a case-insensitive suggestion (M1)", async () => {
  // The filter asks for exact "AAA" and "CCC", but the published list only
  // has "aaa" (wrong case) and "CCC" — "CCC" resolves fine, "AAA" doesn't
  // match anything exactly, and the lowercase near-match should be
  // surfaced as a suggestion without being silently accepted (the filter
  // itself stays exact-case).
  routes = new Map([
    [
      `${BASE}/v1/genes`,
      () =>
        fakeResponse({
          status: 200,
          jsonBody: { genes: [{ gene_symbol: "aaa" }, { gene_symbol: "CCC" }] },
        }),
    ],
  ]);
  requestedUrls = [];

  await assert.rejects(
    () => loadRecordsFromApi({ retryOpts: { sleep: async () => {} } }),
    (err) => {
      assert.match(err.message, /AAA/);
      assert.match(err.message, /did you mean aaa/i);
      return true;
    },
  );
  assert.ok(
    !requestedUrls.some((u) => u.includes("/v1/genes/CCC") || u.includes("/v1/genes/aaa")),
    "must fail BEFORE fetching any per-gene record, exact-case filter unchanged by the suggestion",
  );
});
