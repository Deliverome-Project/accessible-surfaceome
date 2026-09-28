/*
 * Behavioral test for loadSurfaceomeRecord()'s live-fetch fallback
 * (`_fetchRecordFromWorker`, not directly exported) — pins the
 * degraded/retry hardening added alongside the build's pacing fix:
 *
 *   - a 200 carrying X-Surfaceome-Degraded is retried, and a subsequent
 *     healthy response is what's actually returned (never the degraded
 *     bytes);
 *   - a PERSISTENTLY degraded response falls back to `null` — exactly the
 *     same fallback a persistent 5xx/network error already produced, so
 *     the page's existing `if (!rec) notFound()` handling is unchanged;
 *   - Retry-After is honoured for the wait between attempts.
 *
 * The viewer has no JS unit-test runner, so — mirroring
 * list_surfaceome_genes.test.ts — this is a standalone tsx script, one
 * scenario per process (module-level state must start fresh each time):
 *
 *   npx --yes tsx tests/surfaceome_record_degraded.test.ts <scenario>
 *
 * Scenarios: degraded-then-healthy | persistent-degraded | retry-after
 * Run all via tests/run_surfaceome_record_degraded_tests.sh.
 *
 * No build-cache directory exists in a fresh checkout/worktree (it's
 * gitignored, written only by build-data-snapshot.mjs), so
 * loadSurfaceomeRecord's readBuildCache() lookup misses and this
 * exercises the live-fetch fallback path deterministically.
 */
const scenario = process.argv[2] ?? "";

const DEGRADED_HEADER = "X-Surfaceome-Degraded";
let fetchCalls = 0;
const retryDelays: number[] = [];

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

const HEALTHY_RECORD = {
  triage_reasoning: "stable",
  triage_reason: "yes",
  triage_confidence: "high",
  evidence: [],
  gene: { hgnc_symbol: "EGFR" },
};

// Install the fetch stub BEFORE importing the module under test.
globalThis.fetch = (async (): Promise<Response> => {
  fetchCalls += 1;
  switch (scenario) {
    case "degraded-then-healthy":
      if (fetchCalls <= 2) {
        return jsonResponse({ degraded: true }, 200, { [DEGRADED_HEADER]: "triage_run_public" });
      }
      return jsonResponse(HEALTHY_RECORD);
    case "persistent-degraded":
      return jsonResponse({ degraded: true }, 200, { [DEGRADED_HEADER]: "paper_metadata" });
    case "retry-after":
      if (fetchCalls === 1) {
        return new Response("busy", { status: 429, headers: { "Retry-After": "0" } });
      }
      return jsonResponse(HEALTHY_RECORD);
    default:
      throw new Error(`fetch unexpectedly called in scenario '${scenario}'`);
  }
}) as typeof fetch;

// Capture the real setTimeout delay used for the retry wait so
// "retry-after" can assert Retry-After (0s here — kept fast for the
// test) was honoured rather than the default 750ms/2000ms backoff.
const realSetTimeout = globalThis.setTimeout;
// @ts-expect-error — test instrumentation, not a full setTimeout polyfill
globalThis.setTimeout = (fn: (...args: unknown[]) => void, ms?: number, ...args: unknown[]) => {
  if (typeof ms === "number") retryDelays.push(ms);
  return realSetTimeout(fn, ms, ...args);
};

function fail(msg: string): never {
  console.error(`FAIL [${scenario}] ${msg}`);
  process.exit(1);
}
function pass(msg: string): void {
  console.log(`PASS [${scenario}] ${msg}`);
}

process.env.SURFACEOME_API_BASE = "https://example.test/surfaceome";

const { loadSurfaceomeRecord } = await import("../lib/surfaceome.ts");

if (scenario === "degraded-then-healthy") {
  const rec = await loadSurfaceomeRecord("EGFR");
  if (!rec) fail("expected a record, got null");
  if ((rec as unknown as { gene: { hgnc_symbol: string } }).gene.hgnc_symbol !== "EGFR") {
    fail(`expected EGFR, got ${JSON.stringify(rec)}`);
  }
  if (fetchCalls !== 3) fail(`expected 3 fetches (2 degraded + 1 healthy), got ${fetchCalls}`);
  pass("degraded responses retried; the healthy response is what's returned");
} else if (scenario === "persistent-degraded") {
  const rec = await loadSurfaceomeRecord("EGFR");
  if (rec !== null) fail(`expected null (never degraded bytes), got ${JSON.stringify(rec)}`);
  if (fetchCalls !== 3) fail(`expected 3 attempts exhausted, got ${fetchCalls}`);
  pass("persistently-degraded record falls back to null, same as a persistent error");
} else if (scenario === "retry-after") {
  const rec = await loadSurfaceomeRecord("EGFR");
  if (!rec) fail("expected a record after the 429 recovered, got null");
  if (fetchCalls !== 2) fail(`expected 2 fetches, got ${fetchCalls}`);
  // Other setTimeout calls in the code path are the per-attempt
  // FETCH_TIMEOUT_MS (8000ms) abort timers, not the retry wait — filter
  // to delays that could plausibly BE the retry wait (< 8000) and confirm
  // a 0ms wait (Retry-After: 0) is among them, and the DEFAULT backoff
  // (750ms, used when Retry-After is absent) is NOT — i.e. the header,
  // not the default schedule, drove the wait.
  const candidateWaits = retryDelays.filter((d) => d < 8000);
  if (!candidateWaits.includes(0)) {
    fail(`expected a 0ms wait (Retry-After: 0), got candidate delays=${JSON.stringify(candidateWaits)}`);
  }
  if (candidateWaits.includes(750)) {
    fail("used the default 750ms backoff instead of honouring Retry-After: 0");
  }
  pass("Retry-After honoured for the wait between attempts");
} else {
  fail(`unknown scenario '${scenario}'`);
}
