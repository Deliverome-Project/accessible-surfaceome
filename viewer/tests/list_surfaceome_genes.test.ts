/*
 * Behavioral test for listSurfaceomeGenes() — the build-time fetch that
 * drives which gene pages generateStaticParams() emits.
 *
 * The viewer has no JS unit-test runner, so this is a standalone tsx
 * script. listSurfaceomeGenes memoizes its result in a module-level
 * promise, so each scenario must run in its OWN process to re-exercise
 * the function cleanly:
 *
 *   npx --yes tsx tests/list_surfaceome_genes.test.ts <scenario>
 *
 * Scenarios: local | happy | retry5xx | fail4xx
 * Run all four (fresh process each) via tests/run_list_genes_tests.sh.
 *
 * What it pins:
 *   - local    → returns [] WITHOUT fetching (offline CI-smoke stub).
 *   - happy    → returns the gene_symbol list, sorted, empties filtered.
 *   - retry5xx → THROWS after 3 attempts on persistent 5xx (no silent []).
 *   - fail4xx  → THROWS after 1 attempt on 4xx (deterministic, no retry).
 * The last two are the hardening: a flaky Worker must fail the build
 * loudly instead of returning [] (an empty list silently drops every
 * gene route AND flips every catalog row to deep_dive=false via the
 * loadCatalog reconciliation).
 */

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

const { listSurfaceomeGenes } = await import("../lib/surfaceome.ts");

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
} else {
  fail(`unknown scenario '${scenario}' (use local|happy|retry5xx|fail4xx)`);
}
