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

export const DEFAULT_CONCURRENCY = 4;
export const DEFAULT_RPS = 8;
export const DEFAULT_MAX_ATTEMPTS = 5;
// 1s, 2s, 4s, 8s between the 5 attempts; capped at 30s (also the cap
// applied to an honoured `Retry-After`).
export const DEFAULT_BACKOFF_MS = [1000, 2000, 4000, 8000];
export const DEFAULT_MAX_DELAY_MS = 30_000;
export const DEFAULT_MAX_FAIL_FRAC = 0.01;

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

  function pump() {
    while (queue.length > 0 && active < concurrency) {
      const t = now();
      if (t < nextSlotAt) {
        const wait = nextSlotAt - t;
        sleep(wait).then(pump);
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

/** Honour `Retry-After` (seconds, or an HTTP-date) when present. */
export function parseRetryAfterMs(res) {
  const raw = res?.headers?.get?.("Retry-After") ?? res?.headers?.get?.("retry-after");
  if (raw == null) return null;
  const seconds = Number(raw);
  if (Number.isFinite(seconds)) return Math.max(0, seconds * 1000);
  const dateMs = Date.parse(raw);
  if (!Number.isNaN(dateMs)) return Math.max(0, dateMs - Date.now());
  return null;
}

export function computeBackoffMs(attempt, { baseDelaysMs = DEFAULT_BACKOFF_MS, maxDelayMs = DEFAULT_MAX_DELAY_MS } = {}) {
  const ms = baseDelaysMs[attempt] ?? baseDelaysMs[baseDelaysMs.length - 1];
  return Math.min(ms, maxDelayMs);
}

/**
 * Fetch `url`, retrying on 429 / 5xx / network error / a 200 response
 * carrying `X-Surfaceome-Degraded` (serve-time enrichment failed on the
 * Worker) — up to `maxAttempts` times with exponential backoff, honouring
 * `Retry-After` when the Worker sends one. A deterministic 4xx (404, or
 * any non-429 4xx) returns immediately without retrying.
 *
 * Resolves to a discriminated result — never throws on a fetch/HTTP
 * failure (network errors ARE caught and folded into the result):
 *   { ok: true, body, status }                          — success.
 *   { ok: false, hardFailure: true, status }             — deterministic
 *     4xx (or a malformed body on an otherwise-2xx response); don't retry.
 *   { ok: false, hardFailure: false, status, degraded, error } — retries
 *     exhausted on a transient (429/5xx/network) or persistently-degraded
 *     response. THIS is the signal the incident is about: an availability
 *     problem, not a per-gene data problem.
 *
 * `readBody(res)` decides how to consume the body of a healthy (ok,
 * non-degraded) response — defaults to `res.text()`; pass
 * `res => res.json()` (or use `fetchJsonWithRetry`) for JSON endpoints.
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
  } = {},
) {
  let lastStatus = null;
  let lastDegraded = null;
  let lastError = null;
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    let res = null;
    try {
      res = await fetchImpl(url, headers ? { headers } : undefined);
    } catch (err) {
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
          // Malformed body on an otherwise-healthy response — a
          // deterministic parse problem, not an availability/pacing
          // issue, so don't burn retries on it.
          return { ok: false, hardFailure: true, status: res.status, error: err };
        }
      }
      if (res.ok && degradedHeader) {
        lastDegraded = degradedHeader;
        // Drain the body so the connection can be reused/closed cleanly;
        // we never use degraded bytes.
        await Promise.resolve(res.text?.()).catch(() => {});
      } else if (res.status === 404 || (res.status !== 429 && res.status < 500)) {
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
