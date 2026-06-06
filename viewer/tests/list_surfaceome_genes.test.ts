/*
 * Behavioral test for listSurfaceomeGenes() / listSurfaceomeGeneEntries() —
 * the build-time fetch that drives which gene pages generateStaticParams()
 * emits and the GeneJump dropdown's per-gene freshness dot.
 *
 * The viewer has no JS unit-test runner, so this is a standalone tsx
 * script. The result is memoized in a module-level promise, so each scenario
 * must run in its OWN process to re-exercise the function cleanly:
 *
 *   npx --yes tsx tests/list_surfaceome_genes.test.ts <scenario>
 *
 * Scenarios: local | happy | retry5xx | fail4xx | entries | entries-stale
 * Run all (fresh process each) via tests/run_list_genes_tests.sh.
 *
 * What it pins:
 *   - local         → returns [] WITHOUT fetching (offline CI-smoke stub).
 *   - happy         → gene_symbol list, sorted, empties filtered.
 *   - retry5xx      → THROWS after 3 attempts on persistent 5xx (no silent []).
 *   - fail4xx       → THROWS after 1 attempt on 4xx (deterministic, no retry).
 *   - entries       → listSurfaceomeGeneEntries() returns {symbol, stale};
 *                     no manifest → nothing stale; sorted, empties filtered.
 *   - entries-stale → a gene listed in schema_status.json's `stale` set gets
 *                     stale=true; others stay false.
 * retry5xx/fail4xx are the hardening: a flaky Worker must fail the build
 * loudly instead of returning [] (an empty list silently drops every gene
 * route AND flips every catalog row to deep_dive=false via the loadCatalog
 * reconciliation).
 */

import { writeFileSync } from "node:fs";

const scenario = process.argv[2] ?? "";
let fetchCalls = 0;

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

// Install the fetch stub BEFORE importing the module under test.
globalThis.fetch = (async (): Promise<Response> => {
  fetchCalls += 1;
  switch (scenario) {
    case "happy":
      return jsonResponse({
        genes: [
          { gene_symbol: "KIR2DL1" },
          { gene_symbol: "EGFR" },
          { gene_symbol: "" }, // filtered out (falsy)
          {}, // no gene_symbol -> filtered out
        ],
      });
    case "entries":
    case "entries-stale":
      return jsonResponse({
        genes: [
          { gene_symbol: "KIR2DL1" },
          { gene_symbol: "EGFR" },
          { gene_symbol: "ZED" },
          { gene_symbol: "" }, // filtered out (falsy)
          {}, // no gene_symbol -> filtered out
        ],
      });
    case "retry5xx":
      return new Response("upstream busy", { status: 503 });
    case "fail4xx":
      return new Response("not found", { status: 404 });
    default:
      throw new Error(`fetch unexpectedly called in scenario '${scenario}'`);
  }
}) as typeof fetch;

function fail(msg: string): never {
  console.error(`FAIL [${scenario}] ${msg}`);
  process.exit(1);
}
function pass(msg: string): void {
  console.log(`PASS [${scenario}] ${msg}`);
}

process.env.SURFACEOME_API_BASE =
  scenario === "local" ? "local" : "https://example.test/surfaceome";

// Isolate the on-disk snapshot union: lib/surfaceome.ts unions the
// /v1/genes list with the committed public/data/surfaceome/*.json
// snapshots. Point at a non-existent dir so _localSnapshotGenes() catches
// readdir's ENOENT and returns [] — these scenarios then exercise ONLY
// the /v1/genes fetch+parse path, deterministically (independent of how
// many snapshots happen to be committed).
process.env.SURFACEOME_SNAPSHOT_DIR = "/tmp/__surfaceome_no_snapshots__";

// Isolate the schema-freshness manifest. Most scenarios point at a
// non-existent path (loadSchemaStatus() → null → nothing stale). The
// 'entries-stale' scenario writes a fixture marking EGFR stale.
if (scenario === "entries-stale") {
  const fixture = "/tmp/__surfaceome_schema_status_fixture.json";
  writeFileSync(
    fixture,
    JSON.stringify({ stale: ["EGFR"], current: ["KIR2DL1", "ZED"] }),
  );
  process.env.SCHEMA_STATUS_PATH = fixture;
} else {
  process.env.SCHEMA_STATUS_PATH = "/tmp/__surfaceome_no_schema_status__";
}

const { listSurfaceomeGenes, listSurfaceomeGeneEntries } = await import(
  "../lib/surfaceome.ts"
);

if (scenario === "local") {
  const genes = await listSurfaceomeGenes();
  if (fetchCalls !== 0) fail(`expected 0 fetches, got ${fetchCalls}`);
  if (genes.length !== 0) fail(`expected [], got ${JSON.stringify(genes)}`);
  pass("base=local returns [] without fetching");
} else if (scenario === "happy") {
  const genes = await listSurfaceomeGenes();
  const expected = ["EGFR", "KIR2DL1"];
  if (JSON.stringify(genes) !== JSON.stringify(expected)) {
    fail(`expected ${JSON.stringify(expected)}, got ${JSON.stringify(genes)}`);
  }
  if (fetchCalls !== 1) fail(`expected 1 fetch, got ${fetchCalls}`);
  pass("happy path returns sorted, empty-filtered list");
} else if (scenario === "retry5xx") {
  let threw = false;
  try {
    await listSurfaceomeGenes();
  } catch {
    threw = true;
  }
  if (!threw) fail("expected a throw on persistent 503, but it resolved");
  if (fetchCalls !== 3) fail(`expected 3 attempts, got ${fetchCalls}`);
  pass("throws after 3 attempts on persistent 5xx");
} else if (scenario === "fail4xx") {
  let threw = false;
  try {
    await listSurfaceomeGenes();
  } catch {
    threw = true;
  }
  if (!threw) fail("expected a throw on 404, but it resolved");
  if (fetchCalls !== 1) {
    fail(`expected 1 attempt (no retry on 4xx), got ${fetchCalls}`);
  }
  pass("throws immediately on 4xx without retrying");
} else if (scenario === "entries") {
  const entries = await listSurfaceomeGeneEntries();
  const expected = [
    { symbol: "EGFR", stale: false },
    { symbol: "KIR2DL1", stale: false },
    { symbol: "ZED", stale: false },
  ];
  if (JSON.stringify(entries) !== JSON.stringify(expected)) {
    fail(`expected ${JSON.stringify(expected)}, got ${JSON.stringify(entries)}`);
  }
  if (fetchCalls !== 1) fail(`expected 1 fetch, got ${fetchCalls}`);
  pass("entries are {symbol, stale:false} with no manifest, sorted, filtered");
} else if (scenario === "entries-stale") {
  const entries = await listSurfaceomeGeneEntries();
  const expected = [
    { symbol: "EGFR", stale: true },
    { symbol: "KIR2DL1", stale: false },
    { symbol: "ZED", stale: false },
  ];
  if (JSON.stringify(entries) !== JSON.stringify(expected)) {
    fail(`expected ${JSON.stringify(expected)}, got ${JSON.stringify(entries)}`);
  }
  pass("manifest 'stale' set marks the right entry stale");
} else {
  fail(
    `unknown scenario '${scenario}' ` +
      `(use local|happy|retry5xx|fail4xx|entries|entries-stale)`,
  );
}
