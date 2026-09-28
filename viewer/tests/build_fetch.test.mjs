/*
 * Unit tests for viewer/scripts/lib/build-fetch.mjs — the shared pacing +
 * retry infrastructure every bulk per-gene build fetcher routes through
 * (build-data-snapshot.mjs, build-markdown-exports.mjs).
 *
 *   npx --yes tsx --test tests/build_fetch.test.mjs
 *
 * (Plain Node's native test runner also works — `node --test
 * tests/build_fetch.test.mjs` — since this file has no TS/JSX; tsx is used
 * here only for consistency with the rest of the suite's invocation.)
 *
 * Uses ONLY injected clocks / sleeps / fetch stubs — no real waiting, no
 * network. Never hits the production API.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  DEGRADED_HEADER,
  createLimiter,
  fetchWithRetry,
  fetchJsonWithRetry,
  parseRetryAfterMs,
  parseGeneListEnv,
  resolveBuildFetchTuning,
  resolveMaxFailFrac,
  shouldAbortEarly,
} from "../scripts/lib/build-fetch.mjs";

// ----------------------------------------------------------------
// Virtual clock — deterministic time for createLimiter tests. `advance`
// fires any pending `sleep()` timers due by the new virtual time, yielding
// a microtask turn after each so chained .then()s can run before the next
// timer is checked.
// ----------------------------------------------------------------
function makeFakeClock() {
  let time = 0;
  const timers = [];
  return {
    now: () => time,
    sleep: (ms) =>
      new Promise((resolve) => {
        timers.push({ at: time + ms, resolve });
      }),
    async advance(ms) {
      time += ms;
      timers.sort((a, b) => a.at - b.at);
      while (timers.length && timers[0].at <= time) {
        const t = timers.shift();
        t.resolve();
        await Promise.resolve();
        await Promise.resolve();
      }
    },
  };
}

async function drain(donePromise, clock, { stepMs = 1, maxSteps = 200_000 } = {}) {
  let settled = false;
  donePromise.then(
    () => {
      settled = true;
    },
    () => {
      settled = true;
    },
  );
  for (let i = 0; i < maxSteps && !settled; i += 1) {
    await clock.advance(stepMs);
    await Promise.resolve();
  }
  return donePromise;
}

// ----------------------------------------------------------------
// createLimiter
// ----------------------------------------------------------------

test("createLimiter: never exceeds max concurrency, even when rate is unbounded", async () => {
  const clock = makeFakeClock();
  const limiter = createLimiter({
    concurrency: 2,
    rps: 100_000, // effectively no rate pacing — concurrency is the only cap
    now: clock.now,
    sleep: clock.sleep,
  });

  let active = 0;
  let maxActive = 0;
  let completed = 0;
  const N = 6;
  const HOLD_MS = 50;

  const tasks = Array.from({ length: N }, () =>
    limiter(async () => {
      active += 1;
      maxActive = Math.max(maxActive, active);
      await clock.sleep(HOLD_MS);
      active -= 1;
      completed += 1;
      return "ok";
    }),
  );

  await drain(Promise.all(tasks), clock);

  assert.equal(completed, N, "every task eventually completes");
  assert.ok(maxActive <= 2, `max concurrent active was ${maxActive}, expected <= 2`);
  assert.equal(maxActive, 2, "concurrency cap should actually be reached with 6 tasks / cap 2");
});

test("createLimiter: paces task STARTS to no faster than 1000/rps ms apart", async () => {
  const clock = makeFakeClock();
  const rps = 5; // 200ms between starts
  const limiter = createLimiter({
    concurrency: 100, // not the bottleneck here
    rps,
    now: clock.now,
    sleep: clock.sleep,
  });

  const starts = [];
  const N = 5;
  const tasks = Array.from({ length: N }, () =>
    limiter(async () => {
      starts.push(clock.now());
      return "ok"; // instant task — rate pacing is the only thing spacing these out
    }),
  );

  await drain(Promise.all(tasks), clock);

  assert.equal(starts.length, N);
  const interval = 1000 / rps;
  for (let i = 1; i < starts.length; i += 1) {
    const gap = starts[i] - starts[i - 1];
    assert.ok(
      gap >= interval - 1,
      `gap between start ${i - 1} and ${i} was ${gap}ms, expected >= ${interval}ms`,
    );
  }
  // Total span for 5 tasks paced at 200ms apart is ~4*200 = 800ms.
  const span = starts[starts.length - 1] - starts[0];
  assert.ok(span >= (N - 1) * interval - 1, `total span ${span}ms too short for ${rps} rps pacing`);
});

test("createLimiter: rejects non-positive concurrency/rps", () => {
  assert.throws(() => createLimiter({ concurrency: 0 }));
  assert.throws(() => createLimiter({ rps: 0 }));
  assert.throws(() => createLimiter({ rps: -1 }));
});

test("createLimiter: a rejected task doesn't stall the queue", async () => {
  const clock = makeFakeClock();
  const limiter = createLimiter({ concurrency: 2, rps: 1000, now: clock.now, sleep: clock.sleep });
  const results = [];
  const p1 = limiter(async () => {
    throw new Error("boom");
  }).catch((e) => results.push(`err:${e.message}`));
  const p2 = limiter(async () => {
    results.push("ok2");
    return "ok2";
  });
  await drain(Promise.all([p1, p2]), clock);
  assert.deepEqual(results.sort(), ["err:boom", "ok2"]);
});

test("createLimiter: enqueuing N tasks up front schedules O(n) pacing wakeups, not O(n^2) (I4)", async () => {
  // Regression test: before the `waitingForSlot` guard, every schedule()
  // call that landed while rate-limited independently created its OWN
  // `sleep(wait).then(pump)` chain. Queuing N tasks in a tight synchronous
  // loop (the common `Promise.all(tasks.map(fn => limiter(fn)))` shape)
  // then created up to N REDUNDANT pending timers all waking near the
  // same instant, instead of one wakeup per actual pacing interval.
  const clock = makeFakeClock();
  let sleepCalls = 0;
  const countingSleep = (ms) => {
    sleepCalls += 1;
    return clock.sleep(ms);
  };
  const limiter = createLimiter({
    concurrency: 1000, // not the bottleneck — rate pacing is what's under test
    rps: 10, // 100ms between starts
    now: clock.now,
    sleep: countingSleep,
  });

  const N = 30;
  // Enqueue all N tasks in a tight synchronous loop — exactly the shape
  // that exposed the O(n) redundant-timer bug (schedule() calls pump()
  // synchronously on every push, before any of the earlier calls' timers
  // have fired).
  const tasks = Array.from({ length: N }, () => limiter(async () => "ok"));

  await drain(Promise.all(tasks), clock);

  // One wakeup roughly per task once pacing is the bottleneck (N-1 waits
  // for N tasks paced apart, since the very first task starts immediately
  // with no wait) — bounded well under the O(n) trigger's actual behavior
  // (which would produce many MORE than N sleep() calls, one per
  // redundant pump() invocation rather than one per pacing interval).
  assert.ok(
    sleepCalls <= 3 * N,
    `expected O(n) pacing wakeups (<= ${3 * N}), got ${sleepCalls} sleep() calls for ${N} tasks`,
  );
});

// ----------------------------------------------------------------
// fetchWithRetry / fetchJsonWithRetry
// ----------------------------------------------------------------

function fakeResponse({ status = 200, headers = {}, jsonBody, textBody = "" } = {}) {
  const h = new Map(Object.entries(headers).map(([k, v]) => [k.toLowerCase(), v]));
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name) => h.get(String(name).toLowerCase()) ?? null },
    json: async () => {
      if (jsonBody === undefined) throw new SyntaxError("Unexpected end of JSON input");
      return jsonBody;
    },
    text: async () => textBody,
  };
}

function noopSleep() {
  return Promise.resolve();
}

test("fetchWithRetry: healthy 200 (no degraded header) returns immediately", async () => {
  let calls = 0;
  const fetchImpl = async () => {
    calls += 1;
    return fakeResponse({ status: 200, textBody: "hello" });
  };
  const r = await fetchWithRetry("https://example.test/x", { fetchImpl, sleep: noopSleep });
  assert.equal(r.ok, true);
  assert.equal(r.body, "hello");
  assert.equal(calls, 1);
});

test("fetchWithRetry: 404 is a hard failure, no retry", async () => {
  let calls = 0;
  const fetchImpl = async () => {
    calls += 1;
    return fakeResponse({ status: 404 });
  };
  const r = await fetchWithRetry("https://example.test/x", { fetchImpl, sleep: noopSleep });
  assert.equal(r.ok, false);
  assert.equal(r.hardFailure, true);
  assert.equal(r.status, 404);
  assert.equal(calls, 1);
});

test("fetchWithRetry: 500 retried, then a healthy 200 succeeds", async () => {
  let calls = 0;
  const fetchImpl = async () => {
    calls += 1;
    if (calls < 3) return fakeResponse({ status: 500 });
    return fakeResponse({ status: 200, textBody: "recovered" });
  };
  const r = await fetchWithRetry("https://example.test/x", { fetchImpl, sleep: noopSleep });
  assert.equal(r.ok, true);
  assert.equal(r.body, "recovered");
  assert.equal(calls, 3);
});

test("fetchWithRetry: a 200 carrying X-Surfaceome-Degraded is retried, then a healthy 200 is used", async () => {
  let calls = 0;
  const fetchImpl = async () => {
    calls += 1;
    if (calls <= 2) {
      return fakeResponse({
        status: 200,
        headers: { [DEGRADED_HEADER]: "triage_run_public" },
        textBody: "degraded-bytes-never-used",
      });
    }
    return fakeResponse({ status: 200, textBody: "healthy" });
  };
  const r = await fetchWithRetry("https://example.test/x", { fetchImpl, sleep: noopSleep });
  assert.equal(r.ok, true);
  assert.equal(r.body, "healthy", "must use the healthy body, never the degraded one");
  assert.equal(calls, 3);
});

test("fetchWithRetry: persistently degraded exhausts retries and is reported as a failure, not a success", async () => {
  let calls = 0;
  const fetchImpl = async () => {
    calls += 1;
    return fakeResponse({
      status: 200,
      headers: { [DEGRADED_HEADER]: "paper_metadata" },
      textBody: "degraded",
    });
  };
  const r = await fetchWithRetry("https://example.test/x", {
    fetchImpl,
    sleep: noopSleep,
    maxAttempts: 5,
  });
  assert.equal(r.ok, false);
  assert.equal(r.hardFailure, false, "a persistent degraded response is transient/availability, not deterministic");
  assert.equal(r.degraded, "paper_metadata");
  assert.equal(calls, 5, "must exhaust all attempts, not give up early or succeed");
});

test("fetchWithRetry: network errors are retried like 5xx", async () => {
  let calls = 0;
  const fetchImpl = async () => {
    calls += 1;
    if (calls === 1) throw new Error("ECONNRESET");
    return fakeResponse({ status: 200, textBody: "ok" });
  };
  const r = await fetchWithRetry("https://example.test/x", { fetchImpl, sleep: noopSleep });
  assert.equal(r.ok, true);
  assert.equal(calls, 2);
});

test("fetchWithRetry: honours Retry-After (seconds) for the computed delay", async () => {
  let calls = 0;
  const delays = [];
  const fetchImpl = async () => {
    calls += 1;
    if (calls === 1) {
      return fakeResponse({ status: 429, headers: { "Retry-After": "5" } });
    }
    return fakeResponse({ status: 200, textBody: "ok" });
  };
  const r = await fetchWithRetry("https://example.test/x", {
    fetchImpl,
    sleep: noopSleep,
    onRetry: (info) => delays.push(info.delay),
  });
  assert.equal(r.ok, true);
  assert.deepEqual(delays, [5000], "Retry-After: 5 should drive a 5000ms delay, not the default backoff");
});

test("fetchWithRetry: Retry-After is capped at maxDelayMs", async () => {
  let calls = 0;
  const delays = [];
  const fetchImpl = async () => {
    calls += 1;
    if (calls === 1) {
      return fakeResponse({ status: 429, headers: { "Retry-After": "9999" } });
    }
    return fakeResponse({ status: 200, textBody: "ok" });
  };
  await fetchWithRetry("https://example.test/x", {
    fetchImpl,
    sleep: noopSleep,
    maxDelayMs: 30_000,
    onRetry: (info) => delays.push(info.delay),
  });
  assert.deepEqual(delays, [30_000]);
});

test("fetchWithRetry: a non-429 4xx is a hard failure (no retry)", async () => {
  let calls = 0;
  const fetchImpl = async () => {
    calls += 1;
    return fakeResponse({ status: 403 });
  };
  const r = await fetchWithRetry("https://example.test/x", { fetchImpl, sleep: noopSleep });
  assert.equal(r.hardFailure, true);
  assert.equal(calls, 1);
});

test("fetchJsonWithRetry: parses a healthy body as JSON", async () => {
  const fetchImpl = async () => fakeResponse({ status: 200, jsonBody: { evidence: [] } });
  const r = await fetchJsonWithRetry("https://example.test/x", { fetchImpl, sleep: noopSleep });
  assert.equal(r.ok, true);
  assert.deepEqual(r.body, { evidence: [] });
});

test("fetchJsonWithRetry: malformed JSON on an otherwise-healthy response is a hard failure", async () => {
  let calls = 0;
  const fetchImpl = async () => {
    calls += 1;
    return fakeResponse({ status: 200 }); // jsonBody undefined -> json() throws
  };
  const r = await fetchJsonWithRetry("https://example.test/x", { fetchImpl, sleep: noopSleep });
  assert.equal(r.ok, false);
  assert.equal(r.hardFailure, true);
  assert.equal(calls, 1, "a parse error is deterministic — must not retry");
});

test("fetchWithRetry: a non-SyntaxError body-read failure (connection reset mid-read) is RETRIED, not a hard failure (I5)", async () => {
  let calls = 0;
  const readBody = async () => {
    calls += 1;
    if (calls === 1) {
      // Mirrors undici's "terminated" TypeError on a dropped connection —
      // the response headers arrived (2xx, ok) but the body stream never
      // finished. This is NOT the same as bad JSON content and must be
      // retried like any other transient/network failure.
      throw new TypeError("terminated");
    }
    return "recovered body";
  };
  const fetchImpl = async () => fakeResponse({ status: 200 });
  const r = await fetchWithRetry("https://example.test/x", { fetchImpl, readBody, sleep: noopSleep });
  assert.equal(r.ok, true);
  assert.equal(r.body, "recovered body");
  assert.equal(calls, 2, "must retry past the non-SyntaxError body-read failure");
});

test("fetchWithRetry: a SyntaxError body-read failure IS a hard failure, still not retried", async () => {
  let calls = 0;
  const readBody = async () => {
    calls += 1;
    throw new SyntaxError("Unexpected token");
  };
  const fetchImpl = async () => fakeResponse({ status: 200 });
  const r = await fetchWithRetry("https://example.test/x", { fetchImpl, readBody, sleep: noopSleep });
  assert.equal(r.ok, false);
  assert.equal(r.hardFailure, true);
  assert.equal(calls, 1);
});

test("fetchWithRetry: passes a per-attempt AbortSignal (M5)", async () => {
  const seenSignals = [];
  const fetchImpl = async (url, init) => {
    seenSignals.push(init?.signal ?? null);
    return fakeResponse({ status: 200, textBody: "ok" });
  };
  await fetchWithRetry("https://example.test/x", { fetchImpl, sleep: noopSleep });
  assert.equal(seenSignals.length, 1);
  assert.ok(seenSignals[0] instanceof AbortSignal, "expected an AbortSignal to be passed");
});

test("fetchWithRetry: a request that errors (simulating an aborted/timed-out attempt) is retried like any network error", async () => {
  // AbortSignal.timeout() firing surfaces to fetchImpl as a rejected
  // fetch() call (an AbortError) — exercised here via a fetchImpl stub
  // that rejects on its first call, standing in for that timeout path.
  // (The full 30s default timeout itself is not awaited in a unit test.)
  let calls = 0;
  const fetchImpl = async () => {
    calls += 1;
    if (calls === 1) {
      const err = new Error("The operation was aborted");
      err.name = "TimeoutError";
      throw err;
    }
    return fakeResponse({ status: 200, textBody: "ok" });
  };
  const r = await fetchWithRetry("https://example.test/x", {
    fetchImpl,
    sleep: noopSleep,
    requestTimeoutMs: 5, // small, just to confirm the option is threaded through without error
  });
  assert.equal(r.ok, true);
  assert.equal(calls, 2);
});

// ----------------------------------------------------------------
// parseRetryAfterMs / env-var resolvers
// ----------------------------------------------------------------

test("parseRetryAfterMs: seconds form", () => {
  const res = fakeResponse({ headers: { "Retry-After": "2" } });
  assert.equal(parseRetryAfterMs(res), 2000);
});

test("parseRetryAfterMs: absent header returns null", () => {
  const res = fakeResponse({});
  assert.equal(parseRetryAfterMs(res), null);
});

test("parseRetryAfterMs: a future HTTP-date returns the delta in ms (M7)", () => {
  const future = new Date(Date.now() + 10_000).toUTCString();
  const res = fakeResponse({ headers: { "Retry-After": future } });
  const ms = parseRetryAfterMs(res);
  assert.ok(ms != null && ms > 8000 && ms <= 10_000, `expected ~10000ms, got ${ms}`);
});

test("parseRetryAfterMs: a PAST HTTP-date returns null, not a negative/zero wait (M7)", () => {
  const past = new Date(Date.now() - 60_000).toUTCString();
  const res = fakeResponse({ headers: { "Retry-After": past } });
  assert.equal(
    parseRetryAfterMs(res),
    null,
    "a stale Retry-After date must fall back to the computed backoff, not drive an immediate-retry storm",
  );
});

test("fetchWithRetry: a past-date Retry-After falls back to the computed backoff, not 0ms (M7)", async () => {
  let calls = 0;
  const delays = [];
  const past = new Date(Date.now() - 60_000).toUTCString();
  const fetchImpl = async () => {
    calls += 1;
    if (calls === 1) return fakeResponse({ status: 429, headers: { "Retry-After": past } });
    return fakeResponse({ status: 200, textBody: "ok" });
  };
  await fetchWithRetry("https://example.test/x", {
    fetchImpl,
    sleep: noopSleep,
    onRetry: (info) => delays.push(info.delay),
  });
  assert.deepEqual(delays, [1000], "expected the default first-attempt backoff (1000ms), not 0");
});

// ----------------------------------------------------------------
// shouldAbortEarly (I1)
// ----------------------------------------------------------------

test("shouldAbortEarly: false while at or under the floor(frac × total) threshold", () => {
  // floor(0.01 * 1000) = 10 — 10 failures is still AT the threshold.
  assert.equal(shouldAbortEarly(10, 1000, 0.01), false);
});

test("shouldAbortEarly: true as soon as failures exceed the floor(frac × total) threshold", () => {
  assert.equal(shouldAbortEarly(11, 1000, 0.01), true);
});

test("shouldAbortEarly: a tiny total (floor == 0) trips on the very first failure", () => {
  assert.equal(shouldAbortEarly(0, 50, 0.01), false);
  assert.equal(shouldAbortEarly(1, 50, 0.01), true);
});

test("resolveBuildFetchTuning: defaults and env overrides", () => {
  const prevC = process.env.SURFACEOME_BUILD_FETCH_CONCURRENCY;
  const prevR = process.env.SURFACEOME_BUILD_FETCH_RPS;
  try {
    delete process.env.SURFACEOME_BUILD_FETCH_CONCURRENCY;
    delete process.env.SURFACEOME_BUILD_FETCH_RPS;
    assert.deepEqual(resolveBuildFetchTuning(), { concurrency: 8, rps: 8 });

    process.env.SURFACEOME_BUILD_FETCH_CONCURRENCY = "10";
    process.env.SURFACEOME_BUILD_FETCH_RPS = "20";
    assert.deepEqual(resolveBuildFetchTuning(), { concurrency: 10, rps: 20 });

    // Invalid values fall back to the default rather than throwing/NaN.
    process.env.SURFACEOME_BUILD_FETCH_CONCURRENCY = "not-a-number";
    process.env.SURFACEOME_BUILD_FETCH_RPS = "-5";
    assert.deepEqual(resolveBuildFetchTuning(), { concurrency: 8, rps: 8 });
  } finally {
    if (prevC === undefined) delete process.env.SURFACEOME_BUILD_FETCH_CONCURRENCY;
    else process.env.SURFACEOME_BUILD_FETCH_CONCURRENCY = prevC;
    if (prevR === undefined) delete process.env.SURFACEOME_BUILD_FETCH_RPS;
    else process.env.SURFACEOME_BUILD_FETCH_RPS = prevR;
  }
});

test("resolveMaxFailFrac: default, caller fallback, and env override", () => {
  const prev = process.env.SURFACEOME_BUILD_MAX_FAILED_FRAC;
  try {
    delete process.env.SURFACEOME_BUILD_MAX_FAILED_FRAC;
    assert.equal(resolveMaxFailFrac(), 0.01);
    assert.equal(resolveMaxFailFrac(0.02), 0.02, "caller-supplied fallback used when env unset");

    process.env.SURFACEOME_BUILD_MAX_FAILED_FRAC = "0.05";
    assert.equal(resolveMaxFailFrac(0.02), 0.05, "env var wins over the caller fallback");
  } finally {
    if (prev === undefined) delete process.env.SURFACEOME_BUILD_MAX_FAILED_FRAC;
    else process.env.SURFACEOME_BUILD_MAX_FAILED_FRAC = prev;
  }
});

test("parseGeneListEnv: parses, trims, filters empties; null when unset", () => {
  assert.equal(parseGeneListEnv(undefined), null);
  assert.equal(parseGeneListEnv(""), null);
  assert.equal(parseGeneListEnv("   "), null);
  assert.deepEqual(parseGeneListEnv("EGFR, PTEN ,,VWF"), new Set(["EGFR", "PTEN", "VWF"]));
});
