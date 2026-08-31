#!/usr/bin/env python3
"""Time-to-first-byte (TTFB) budget check for the surfaceome site + public API.

Measures TTFB for a set of URLs and fails if any median TTFB exceeds its
budget. The default budget is **800 ms** — the web.dev "good" TTFB threshold
(https://web.dev/articles/ttfb). Public API endpoints are warmed once before
timing so the check reflects steady-state Cloudflare edge-cache performance
rather than a one-off cold miss (a cold miss on a rarely-requested gene is
expected to be slower and is not what this monitors).

TTFB here = wall-clock from request send to response headers received, taken
as the median of a few samples over a reused (keep-alive) connection, which is
what a returning visitor experiences.

Usage:
    uv run python scripts/ttfb_check.py            # default targets
    uv run python scripts/ttfb_check.py --budget-ms 800
    uv run python scripts/ttfb_check.py --samples 5 --json

Exit code: 0 if every target is within budget, 1 otherwise (for CI).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass

import httpx

SITE = "https://surfaceome.deliverome.org"
API = "https://api.deliverome.org/surfaceome"

# A representative, low-cardinality gene used for the per-gene endpoints. Any
# deep-dived symbol works; KLK2 is a stable member of the cohort.
_GENE = "KLK2"


@dataclass(frozen=True)
class Target:
    label: str
    url: str
    warm_first: bool  # warm the edge cache once before timing (API endpoints)


def default_targets() -> list[Target]:
    return [
        # Static site documents (served from Cloudflare Pages' edge).
        Target("site: home", f"{SITE}/", False),
        Target("site: gene page shell", f"{SITE}/{_GENE}/", False),
        Target("site: api docs", f"{SITE}/api/", False),
        Target("site: reproducibility", f"{SITE}/reproducibility/", False),
        # Public Worker API (D1-backed; warmed so we measure the edge-cache
        # steady state, which is what the gene page hits in practice).
        Target("api: gene record", f"{API}/v1/genes/{_GENE}", True),
        Target("api: triage", f"{API}/v1/triage/{_GENE}", True),
        Target("api: catalog row", f"{API}/v1/catalog/{_GENE}", True),
    ]


def _ttfb_ms(client: httpx.Client, url: str) -> tuple[float, int]:
    """One TTFB sample: ms from request send to response headers received."""
    t0 = time.perf_counter()
    with client.stream("GET", url) as resp:
        # Entering the stream context blocks until status + headers arrive =
        # time to first byte. We deliberately don't read the body.
        ttfb = (time.perf_counter() - t0) * 1000.0
        status = resp.status_code
    return ttfb, status


def measure(client: httpx.Client, target: Target, samples: int) -> dict:
    if target.warm_first:
        # Warm the edge cache + the connection (ignore this timing).
        try:
            client.get(target.url)
        except httpx.HTTPError:
            pass
    times: list[float] = []
    status = 0
    error: str | None = None
    for _ in range(samples):
        try:
            ttfb, status = _ttfb_ms(client, target.url)
            times.append(ttfb)
        except httpx.HTTPError as exc:  # network / timeout
            error = f"{type(exc).__name__}: {exc}"
            break
    median = statistics.median(times) if times else float("inf")
    return {
        "label": target.label,
        "url": target.url,
        "status": status,
        "median_ms": round(median, 1),
        "samples_ms": [round(t, 1) for t in times],
        "error": error,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--budget-ms",
        type=float,
        default=800.0,
        help="TTFB budget in milliseconds (default: 800 = web.dev 'good').",
    )
    ap.add_argument(
        "--samples",
        type=int,
        default=3,
        help="Timed samples per target; the median is compared to the budget.",
    )
    ap.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Per-request timeout in seconds.",
    )
    ap.add_argument("--json", action="store_true", help="Emit JSON results.")
    args = ap.parse_args()

    targets = default_targets()
    results: list[dict] = []
    # A real browser reuses connections + supports HTTP/2; mirror that so the
    # measurement reflects a returning visitor, not a cold TLS handshake.
    # HTTP/2 needs the optional `h2` package; fall back to HTTP/1.1 keep-alive
    # if it isn't installed (Cloudflare serves both; timing is comparable).
    try:
        import h2  # noqa: F401

        use_http2 = True
    except ImportError:
        use_http2 = False
    with httpx.Client(
        http2=use_http2,
        timeout=args.timeout,
        headers={"User-Agent": "surfaceome-ttfb-check/1.0"},
        follow_redirects=True,
    ) as client:
        for t in targets:
            results.append(measure(client, t, args.samples))

    def failed(r: dict) -> bool:
        # A non-2xx status is a failure even if fast — e.g. a gene URL that
        # soft-404s (renders client-side but returns HTTP 404) is a real
        # correctness bug, not a passing "fast" page.
        return bool(r["error"]) or r["status"] >= 400 or r["median_ms"] > args.budget_ms

    failures = [r for r in results if failed(r)]

    if args.json:
        print(json.dumps(
            {"budget_ms": args.budget_ms, "results": results,
             "passed": not failures}, indent=2))
    else:
        print(f"TTFB budget: {args.budget_ms:.0f} ms  "
              f"(median of {args.samples} samples/target)\n")
        width = max(len(r["label"]) for r in results)
        for r in results:
            ok = (
                not r["error"]
                and r["status"] < 400
                and r["median_ms"] <= args.budget_ms
            )
            mark = "PASS" if ok else "FAIL"
            detail = r["error"] if r["error"] else (
                f'{r["median_ms"]:7.1f} ms  (HTTP {r["status"]})')
            print(f"  [{mark}] {r['label']:<{width}}  {detail}")
        print()
        if failures:
            print(f"{len(failures)} target(s) over the {args.budget_ms:.0f} ms "
                  f"TTFB budget.")
        else:
            print(f"All {len(results)} targets within the "
                  f"{args.budget_ms:.0f} ms TTFB budget.")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
