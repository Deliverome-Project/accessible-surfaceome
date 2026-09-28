// Shared pacing + retry infrastructure for the build's bulk per-gene
// fetchers against the public Worker (api.deliverome.org/surfaceome).
//
// Background (2026-09-28 production incident): every merge to main
// triggers a Cloudflare Pages build that pre-fetches ~5.3k gene records
// (and related per-gene endpoints, e.g. the evidence ledger) from the
// Worker. The build fired these as a large unpaced burst, which drove
// 27k-62k Worker requests per 15 min (baseline 6-16k), pushed cache
// misses onto the shared public D1 (~17 queries per miss), and D1
// returned "internal error" 500s to REAL USERS during the build. The
// Worker also served some records "degraded" (serve-time enrichment
// failed; such 200 responses carry `X-Surfaceome-Degraded` and
// `Cache-Control: no-store`) — and the build accepted any `res.ok`, so a
// degraded record got baked into the materialized JSON / Markdown that
// ships to readers.
//
// This module provides:
//   - `createLimiter` — a concurrency- AND rate-capped task scheduler.
//   - `fetchWithRetry` / `fetchJsonWithRetry` — retry with exponential
//     backoff on 5xx / 429 / network errors AND on a 200 response that
//     carries `X-Surfaceome-Degraded`, honouring `Retry-After` when
//     present.
//   - `resolveBuildFetchTuning` / `resolveMaxFailFrac` — env-var
//     overrides shared by every bulk fetcher so operators tune pacing
//     in one place.
//
// Every bulk per-gene fetcher the build runs (build-data-snapshot.mjs's
// per-gene record pre-fetch, build-markdown-exports.mjs's record +
// evidence fetch) must route through a `createLimiter` instance and
// `fetchWithRetry`/`fetchJsonWithRetry` — that is the fix for the
// incident above.

export const DEGRADED_HEADER = "X-Surfaceome-Degraded";

// Concurrency default raised 4 → 8 (PR #275 review): the request-RATE cap
// (DEFAULT_RPS, still 8/s) is what actually protects D1 from a cache-miss
// burst, not the in-flight count — a higher concurrency just lets more
// requests overlap in flight while the rate limiter still paces how often
// a NEW one starts, so this halves wall-clock time on latency-bound runs
// without raising the request rate against the Worker/D1.
export const DEFAULT_CONCURRENCY = 8;
export const DEFAULT_RPS = 8;
export const DEFAULT_MAX_ATTEMPTS = 5;
// 1s, 2s, 4s, 8s between the 5 attempts; capped at 30s (also the cap
// applied to an honoured `Retry-After`).
export const DEFAULT_BACKOFF_MS = [1000, 2000, 4000, 8000];
export const DEFAULT_MAX_DELAY_MS = 30_000;
export const DEFAULT_MAX_FAIL_FRAC = 0.01;
// Per-request timeout (M5) — an individual fetch that hangs (rather than
// erroring or timing out at the transport level) must not stall a whole
// worker slot indefinitely; a timeout is folded into the same retryable
// "network error" path as a connection failure.
export const DEFAULT_REQUEST_TIMEOUT_MS = 30_000;

export const defaultSleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function envNumber(name, fallback) {
  const raw = process.env[name];
  if (raw == null || raw.trim() === "") return fallback;
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

/**
 * Read the shared build-fetch pacing knobs from the environment.
 *   SURFACEOME_BUILD_FETCH_CONCURRENCY — max in-flight requests (default 4).
 *   SURFACEOME_BUILD_FETCH_RPS         — max request STARTS per second (default 8).
 * Invalid / non-positive values fall back to the default rather than
 * throwing, so a typo'd env var degrades to the safe default instead of
 * crashing the build.
 */
export function resolveBuildFetchTuning() {
  return {
    concurrency: envNumber("SURFACEOME_BUILD_FETCH_CONCURRENCY", DEFAULT_CONCURRENCY),
    rps: envNumber("SURFACEOME_BUILD_FETCH_RPS", DEFAULT_RPS),
  };
}

/**
 * Read the shared failure-fraction exit threshold.
 *   SURFACEOME_BUILD_MAX_FAILED_FRAC — fraction (0-1) of genes that may
 *   fail/skip before the script exits non-zero (default 0.01 = 1%).
 * `fallback` lets a caller keep a pre-existing, script-specific default
 * when the env var isn't set.
 */
export function resolveMaxFailFrac(fallback = DEFAULT_MAX_FAIL_FRAC) {
  const raw = process.env.SURFACEOME_BUILD_MAX_FAILED_FRAC;
  if (raw == null || raw.trim() === "") return fallback;
  const n = Number(raw);
  return Number.isFinite(n) && n >= 0 ? n : fallback;
}

/**
 * Early-abort circuit breaker (PR #275 review, I1): true once
 * `failedCount` exceeds `floor(maxFailFrac × total)`. Both bulk fetchers
 * check this INSIDE their worker loop, after every completed gene, so a
 * real outage is caught mid-fetch — aborting the remaining planned
 * requests — instead of only being detected after every one of ~5.3k
 * genes has been attempted (which, for the MD job, also means the abort
 * happens before the fetch phase ever hands anything to the R2 upload
 * phase). This is the SAME threshold shape the end-of-run
 * failure-fraction gate uses, just evaluated continuously rather than
 * once at the end.
 */
export function shouldAbortEarly(failedCount, total, maxFailFrac) {
  return failedCount > Math.floor(maxFailFrac * total);
}

/**
 * Parse a comma-separated gene list from an env var (e.g.
 * SURFACEOME_MD_GENES=A,B,C) into a Set of trimmed, non-empty symbols.
 * Returns `null` when the env var is unset/empty, so callers can
 * distinguish "no filter" from "filter to nothing".
 */
export function parseGeneListEnv(raw) {
  if (raw == null || raw.trim() === "") return null;
  const syms = raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return syms.length > 0 ? new Set(syms) : null;
}

/**
 * Concurrency- AND rate-capped task scheduler. `schedule(fn)` queues
 * `fn` (a zero-arg function returning a Promise) and resolves/rejects
 * with its outcome once it has actually run.
 *
 * Both caps are enforced together: a queued task starts only once BOTH
 * (a) fewer than `concurrency` tasks are currently in flight and (b) at
 * least `1000/rps` ms have elapsed since the last task started. With
 * fast tasks (network latency well under the pacing interval), (b) is
 * the binding constraint — which is the point: it bounds the Worker
 * request RATE, not just how many requests are outstanding at once.
 *
 * `now`/`sleep` are injectable so tests can drive the scheduler with a
 * virtual clock instead of waiting on real timers.
 */
export function createLimiter({
  concurrency = DEFAULT_CONCURRENCY,
  rps = DEFAULT_RPS,
  now = Date.now,
  sleep = defaultSleep,
} = {}) {
  if (!(concurrency >= 1)) throw new Error("createLimiter: concurrency must be >= 1");
  if (!(rps > 0)) throw new Error("createLimiter: rps must be > 0");
  const minIntervalMs = 1000 / rps;
  let active = 0;
  let nextSlotAt = 0;
  const queue = [];
  // At most ONE pacing timer pending at a time (I4). `schedule()` calls
  // `pump()` synchronously on every enqueue, and `pump()` is also called
  // whenever a task finishes — without this guard, every one of those
  // calls that lands while rate-limited would independently schedule its
  // OWN `sleep(wait).then(pump)`, so queuing N tasks up front (the common
  // `Promise.all(tasks.map(...))` shape) created O(n) redundant pending
  // timers all waking at ~the same instant instead of one wakeup per
  // actual pacing interval.
  let waitingForSlot = false;

  function pump() {
    while (queue.length > 0 && active < concurrency) {
      const t = now();
      if (t < nextSlotAt) {
        if (!waitingForSlot) {
          waitingForSlot = true;
          const wait = nextSlotAt - t;
          sleep(wait).then(() => {
            waitingForSlot = false;
            pump();
          });
        }
        return;
      }
      const job = queue.shift();
      active += 1;
      nextSlotAt = Math.max(nextSlotAt, t) + minIntervalMs;
      Promise.resolve()
        .then(job.fn)
        .then(
          (value) => {
            active -= 1;
            job.resolve(value);
            pump();
          },
          (err) => {
            active -= 1;
            job.reject(err);
            pump();
          },
        );
    }
  }

  return function schedule(fn) {
    return new Promise((resolve, reject) => {
      queue.push({ fn, resolve, reject });
      pump();
    });
  };
}

/**
 * Honour `Retry-After` (seconds, or an HTTP-date) when present. Returns
 * `null` when absent OR when an HTTP-date form is already in the past
 * (M7) — a past/now date would otherwise floor to a 0ms wait via the old
 * `Math.max(0, …)` clamp, turning a single slow response into an
 * immediate-retry storm against an already-struggling Worker. `null`
 * lets the caller fall back to the normal computed backoff instead. The
 * numeric-seconds form is NOT floored this way: `Retry-After: 0` is a
 * legitimate "retry immediately" signal from the server, not a stale
 * clock artifact.
 */
export function parseRetryAfterMs(res) {
  const raw = res?.headers?.get?.("Retry-After") ?? res?.headers?.get?.("retry-after");
  if (raw == null) return null;
  const seconds = Number(raw);
  if (Number.isFinite(seconds)) return Math.max(0, seconds * 1000);
  const dateMs = Date.parse(raw);
  if (!Number.isNaN(dateMs)) {
    const delta = dateMs - Date.now();
    return delta > 0 ? delta : null;
  }
  return null;
}

export function computeBackoffMs(attempt, { baseDelaysMs = DEFAULT_BACKOFF_MS, maxDelayMs = DEFAULT_MAX_DELAY_MS } = {}) {
  const ms = baseDelaysMs[attempt] ?? baseDelaysMs[baseDelaysMs.length - 1];
  return Math.min(ms, maxDelayMs);
}

/**
 * Fetch `url`, retrying on 429 / 5xx / network error / request timeout /
 * a 200 response carrying `X-Surfaceome-Degraded` (serve-time enrichment
 * failed on the Worker) — up to `maxAttempts` times with exponential
 * backoff, honouring `Retry-After` when the Worker sends one. A
 * deterministic 4xx (404, or any non-429 4xx) returns immediately without
 * retrying.
 *
 * Resolves to a discriminated result — never throws on a fetch/HTTP
 * failure (network errors, including a timeout, ARE caught and folded
 * into the result):
 *   { ok: true, body, status }                          — success.
 *   { ok: false, hardFailure: true, status }             — deterministic:
 *     a 4xx status, OR malformed JSON (a `SyntaxError` from `readBody`) on
 *     an otherwise-healthy response — don't retry either.
 *   { ok: false, hardFailure: false, status, degraded, error } — retries
 *     exhausted on a transient (429/5xx/network/timeout/a non-SyntaxError
 *     body-read failure such as a connection reset mid-stream) or
 *     persistently-degraded response. THIS is the signal the incident is
 *     about: an availability problem, not a per-gene data problem.
 *
 * `readBody(res)` decides how to consume the body of a healthy (ok,
 * non-degraded) response — defaults to `res.text()`; pass
 * `res => res.json()` (or use `fetchJsonWithRetry`) for JSON endpoints.
 * Only a `SyntaxError` out of `readBody` (bad JSON — the bytes themselves
 * are wrong, retrying won't fix them) is treated as a hard failure; any
 * OTHER error reading the body (the connection dropping mid-read, an
 * aborted stream, etc.) is exactly as retryable as a network error at the
 * `fetchImpl` layer, since it means the bytes never fully arrived.
 *
 * `requestTimeoutMs` (default 30s) bounds a single attempt via
 * `AbortSignal.timeout` — a hang is folded into the same retryable
 * network-error path as a connection failure, not left to stall a worker
 * slot forever.
 */
export async function fetchWithRetry(
  url,
  {
    fetchImpl = fetch,
    headers,
    maxAttempts = DEFAULT_MAX_ATTEMPTS,
    baseDelaysMs = DEFAULT_BACKOFF_MS,
    maxDelayMs = DEFAULT_MAX_DELAY_MS,
    sleep = defaultSleep,
    onRetry,
    readBody = (res) => res.text(),
    requestTimeoutMs = DEFAULT_REQUEST_TIMEOUT_MS,
  } = {},
) {
  let lastStatus = null;
  let lastDegraded = null;
  let lastError = null;
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    let res = null;
    let bodyOutcome = null; // set only when a body-read was attempted on a healthy response
    try {
      const init = {};
      if (headers) init.headers = headers;
      if (requestTimeoutMs != null) init.signal = AbortSignal.timeout(requestTimeoutMs);
      res = await fetchImpl(url, Object.keys(init).length ? init : undefined);
    } catch (err) {
      // Network error OR AbortSignal.timeout firing — both transient.
      lastError = err;
      res = null;
    }
    if (res) {
      lastStatus = res.status;
      const degradedHeader = res.headers?.get?.(DEGRADED_HEADER) ?? null;
      if (res.ok && !degradedHeader) {
        try {
          const body = await readBody(res);
          return { ok: true, body, status: res.status };
        } catch (err) {
          if (err instanceof SyntaxError) {
            // Malformed JSON on an otherwise-healthy response — the bytes
            // themselves are wrong, a deterministic parse problem, not an
            // availability/pacing issue, so don't burn retries on it.
            return { ok: false, hardFailure: true, status: res.status, error: err };
          }
          // Any OTHER body-read error (connection reset mid-stream, an
          // aborted read, "terminated", …) is a network/transient problem
          // masquerading as a successful response header — retry it like
          // a network error rather than giving up immediately.
          bodyOutcome = err;
        }
      }
      if (bodyOutcome) {
        lastError = bodyOutcome;
        // fall through to the retry/backoff logic below
      } else if (res.ok && degradedHeader) {
        lastDegraded = degradedHeader;
        // Drain the body so the connection can be reused/closed cleanly;
        // we never use degraded bytes.
        await Promise.resolve(res.text?.()).catch(() => {});
      } else if (!res.ok && (res.status === 404 || (res.status !== 429 && res.status < 500))) {
        return { ok: false, hardFailure: true, status: res.status };
      }
      // else: 429 or 5xx — fall through to retry.
    }
    if (attempt < maxAttempts - 1) {
      const retryAfterMs = parseRetryAfterMs(res);
      const delay =
        retryAfterMs != null
          ? Math.min(retryAfterMs, maxDelayMs)
          : computeBackoffMs(attempt, { baseDelaysMs, maxDelayMs });
      if (onRetry) {
        onRetry({ attempt, delay, status: lastStatus, degraded: lastDegraded, error: lastError, url });
      }
      await sleep(delay);
    }
  }
  return {
    ok: false,
    hardFailure: false,
    status: lastStatus,
    degraded: lastDegraded,
    error: lastError,
  };
}

/** `fetchWithRetry`, parsing the healthy-response body as JSON. */
export function fetchJsonWithRetry(url, opts = {}) {
  return fetchWithRetry(url, { ...opts, readBody: (res) => res.json() });
}
