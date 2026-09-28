#!/usr/bin/env python3
"""Archive what the API serves for every annotated gene (dry-run by default).

Run after any bulk deterministic-table sync (enrichment-only changes are
not caught by publish-time archiving) and as step 1 of every release.

    uv run python scripts/cloud/sweep_record_history.py                 # list genes
    uv run python scripts/cloud/sweep_record_history.py --execute
    uv run python scripts/cloud/sweep_record_history.py --execute --genes EGFR,CD63
    uv run python scripts/cloud/sweep_record_history.py --check-stability
    uv run python scripts/cloud/sweep_record_history.py --check-stability --sample 200

``--check-stability`` is a separate, read-only mode: it fetches each gene
TWICE (needs ``ARCHIVE_BYPASS_TOKEN``, same as ``--execute``) and compares
the three content hashes across the two fetches, to catch a served part
that changes on every request without the underlying record changing
(e.g. a serve-time enrichment stamp the hasher doesn't yet strip — see
``VOLATILE_NESTED_KEYS`` in ``record_history/hashing.py``). It NEVER
touches the store, R2, or D1 — no revision is written and nothing is
purged. Defaults to a random sample of 50 genes (seeded, so the sample is
reproducible run to run); ``--genes`` overrides the sample with an exact
list, same as the archiving mode.

Two guardrails on top of the plain per-gene archive:

* ``--execute`` with no ``ARCHIVE_BYPASS_TOKEN`` exits immediately with a
  clear error instead of walking the whole cohort and recording ~5,000
  identical per-gene ``ArchiveError`` failures (``archive_gene`` itself
  would raise one per gene for a missing token).
* If ``ABORT_AFTER_N_CONSECUTIVE_FAILURES`` genes in a row raise ANY
  exception — ``ArchiveError`` (wrong token, or a Worker too old to echo
  the bypass-honoured header), a ``D1Error`` (public D1 down/misbehaving),
  an ``httpx.HTTPError`` (Worker unreachable or 5xx-ing), or anything else
  — the sweep stops calling the API for the rest of the cohort. A
  misconfiguration OR an outage should fail loud after a handful of genes,
  not grind through every remaining gene making the same doomed request.

The dry-run genes list (``/v1/genes``) is a public route, so it works
without any token; the bypass header is only sent when one is configured.

Worker fetches (both ``--execute`` and ``--check-stability``) are paced
independently of any D1 writes via ``--max-genes-per-second`` (default 2.0,
env ``RECORD_HISTORY_SWEEP_GPS``, ``0`` disables) — see 2026-09's incident
where a no-op sweep (nothing changed, so no D1 writes to pace against) made
8 threads fetch the bypass-header route as fast as possible, and each
uncached fetch costs ~17 D1 queries on the SAME public D1 that serves real
users, overloading it. On top of steady pacing, a 5xx from the Worker or an
exhausted-retries ``D1Error`` trips a growing pause (5s, 10s, 20s, ... capped
at 60s, reset on the next success) shared by every worker before it starts
its next gene — see ``_ServerErrorBackoff``.

Before archiving, ``--execute`` calls ``CloudRevisionStore.prefetch_latest()``
once — every gene's latest revision in a single D1 query instead of one
``latest()`` query per gene, which at cohort scale (~5,130 genes) is most of
this sweep's D1 call volume. Every D1 call made through the store (including
that prefetch) is paced via ``RECORD_HISTORY_D1_QPS`` (default 2.5 qps, ``0``
disables) so a sweep doesn't compete with concurrent sessions for the shared
Cloudflare account API budget (1,200 requests / 5 min across every
``api.cloudflare.com`` call — R2 REST ops and D1 queries both count).

Before that, ``--execute`` also builds (and caches) the R2 S3 client ONCE
in the main thread, ahead of the archiving pool, and exits non-zero with a
clear message if that fails — so a cold cache under the pool can't race
multiple workers into building their own clients (each with its own
credential-derivation call), and a missing/broken ``CLOUDFLARE_API_TOKEN``
fails loudly right away instead of ~5,130 individual failures. The store
is also constructed with ``require_s3=True``: if the S3 client somehow
becomes unavailable later, ``put_blob`` raises instead of silently
falling back to the REST ``r2_client`` path, which WOULD compete for the
shared budget this whole rewrite exists to protect.
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from accessible_surfaceome.cloud.d1_client import D1Error
from accessible_surfaceome.cloud.r2_s3 import R2S3CredentialError, r2_s3_client
from accessible_surfaceome.cloud.record_history.archive import (
    BYPASS_HEADER,
    PUBLIC_API_BASE,
    ArchiveResult,
    Served,
    archive_gene,
    fetch_served,
)
from accessible_surfaceome.cloud.record_history.hashing import (
    content_hash_evidence,
    content_hash_md,
    content_hash_record,
)
from accessible_surfaceome.cloud.record_history.rate_limit import (
    DEFAULT_SWEEP_GPS,
    SWEEP_GPS_ENV_VAR,
    RateLimiter,
    sweep_gps_from_env,
)
from accessible_surfaceome.cloud.record_history.store import (
    CloudRevisionStore,
    RevisionStore,
)
from accessible_surfaceome.cloud.surface_annotation import purge_paths
from accessible_surfaceome.env import load_env

logger = logging.getLogger(__name__)

ABORT_AFTER_N_CONSECUTIVE_FAILURES = 5
DEFAULT_STABILITY_SAMPLE = 50
STABILITY_SAMPLE_SEED = 0

# Server-error back-off: on a 5xx from the Worker or a (retries-exhausted)
# D1Error, every worker pauses before starting its NEXT gene, for a growing
# interval that resets to zero after any success. This is deliberately a
# second, independent guardrail alongside RateLimiter pacing (which paces
# steady-state traffic) and ABORT_AFTER_N_CONSECUTIVE_FAILURES (which stops
# the sweep entirely) — a handful of 5xxs under load should make the sweep
# back off and give the overloaded service room to recover, not just plow
# through at the same steady pace until the abort guard trips.
_BACKOFF_BASE_S = 5.0
_BACKOFF_CAP_S = 60.0


def annotated_genes(
    http: httpx.Client, token: str, base: str = PUBLIC_API_BASE
) -> list[str]:
    # /v1/genes is a public route — only attach the bypass header when a
    # token is actually configured, so the dry-run listing works tokenless.
    headers = {BYPASS_HEADER: token} if token else None
    resp = http.get(f"{base}/v1/genes", headers=headers)
    resp.raise_for_status()
    return [g["gene_symbol"] for g in resp.json()["genes"]]


class _ConsecutiveFailureGuard:
    """Trips once, after ``threshold`` consecutive failures of ANY kind.

    Deliberately not scoped to ``ArchiveError`` — a down public D1
    (``D1Error``) or an unreachable/5xx-ing Worker (``httpx.HTTPError``) is
    exactly the kind of systemic failure this guard exists to catch, same
    as a bad ``ARCHIVE_BYPASS_TOKEN``. Checked at the top of every submitted
    task rather than only observed after the fact from the orchestrating
    thread — so once it trips, every task still queued behind it skips its
    HTTP call deterministically, even with a single worker, instead of
    racing the main thread's bookkeeping loop to decide who gets there
    first.
    """

    def __init__(self, threshold: int) -> None:
        self._threshold = threshold
        self._streak = 0
        self._lock = threading.Lock()
        self._tripped = False
        self._trip_message: str | None = None

    @property
    def tripped(self) -> bool:
        with self._lock:
            return self._tripped

    def record_failure(self, exc: Exception) -> None:
        with self._lock:
            self._streak += 1
            if self._streak >= self._threshold and not self._tripped:
                self._tripped = True
                self._trip_message = (
                    f"{self._threshold} genes in a row failed — aborting the rest "
                    f"of the sweep instead of repeating the same failure across "
                    f"the cohort. Last error ({type(exc).__name__}): {exc}"
                )

    def record_success(self) -> None:
        with self._lock:
            self._streak = 0

    def pop_trip_message(self) -> str | None:
        with self._lock:
            msg, self._trip_message = self._trip_message, None
            return msg


def _is_server_error(exc: Exception) -> bool:
    """True for an httpx 5xx or a D1Error — the two "the service is
    struggling" signals worth backing off for, as opposed to a request-level
    failure (bad token, 4xx, malformed body) that retrying slower won't fix.

    ``D1Error`` already means public D1's own bounded retry budget (see
    ``d1_client.py``) was exhausted, so seeing one here means D1 was
    unhealthy for multiple consecutive attempts already — exactly the signal
    this back-off exists to react to.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, D1Error)


class _ServerErrorBackoff:
    """Shared, growing pause after a 5xx / D1-transient failure.

    ``before_gene()`` is called by every worker right before it starts
    fetching its next gene; it blocks until any currently pending pause has
    elapsed, so a burst of server errors stalls the WHOLE pool rather than
    one worker backing off while the others keep hammering an overloaded
    Worker/D1. The pause interval grows 5s -> 10s -> 20s -> ... capped at
    60s on each consecutive ``record_server_error()`` call, and resets to
    zero on the next ``record_success()``.

    ``clock``/``sleep`` are injectable (same contract as
    ``rate_limit.RateLimiter``) so tests can drive this without a real
    wall-clock wait.
    """

    def __init__(
        self,
        *,
        base_s: float = _BACKOFF_BASE_S,
        cap_s: float = _BACKOFF_CAP_S,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._base_s = base_s
        self._cap_s = cap_s
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._streak = 0
        self._resume_at = clock()

    def before_gene(self) -> None:
        with self._lock:
            resume_at = self._resume_at
        wait = resume_at - self._clock()
        if wait > 0:
            self._sleep(wait)

    def record_server_error(self) -> None:
        with self._lock:
            self._streak += 1
            interval = min(self._base_s * (2 ** (self._streak - 1)), self._cap_s)
            self._resume_at = self._clock() + interval
        logger.warning(
            "server error — pausing the sweep for %.0fs before the next gene "
            "(consecutive server-error streak: %d)",
            interval,
            self._streak,
        )
        print(f"server error — pausing {interval:.0f}s before the next gene")

    def record_success(self) -> None:
        with self._lock:
            self._streak = 0


def _archive_or_skip(
    symbol: str,
    *,
    http: httpx.Client,
    store: RevisionStore,
    token: str,
    guard: _ConsecutiveFailureGuard,
    limiter: RateLimiter,
    backoff: _ServerErrorBackoff,
) -> ArchiveResult | None:
    """Runs inside the pool. Returns ``None`` for a gene skipped post-abort."""
    if guard.tripped:
        return None
    backoff.before_gene()
    limiter.acquire()
    try:
        result = archive_gene(
            symbol, source="sweep", http=http, store=store, token=token
        )
    except Exception as exc:  # noqa: BLE001 — any failure counts toward the abort guard
        guard.record_failure(exc)
        if _is_server_error(exc):
            backoff.record_server_error()
        raise
    else:
        guard.record_success()
        backoff.record_success()
        return result


def sweep(
    genes: list[str] | None,
    *,
    execute: bool,
    workers: int,
    max_genes_per_second: float | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> Counter[str]:
    """``max_genes_per_second`` paces Worker fetches (see ``RateLimiter`` /
    ``SWEEP_GPS_ENV_VAR``), independent of D1 write pacing —
    ``None`` (the default) resolves ``RECORD_HISTORY_SWEEP_GPS`` /
    :data:`DEFAULT_SWEEP_GPS`; ``0`` disables it explicitly. ``clock``/
    ``sleep`` are injectable (tests only) so pacing/back-off can be driven
    without a real wall-clock wait."""
    load_env()
    token = os.environ.get("ARCHIVE_BYPASS_TOKEN", "").strip()
    if execute and not token:
        print(
            "ARCHIVE_BYPASS_TOKEN is unset — refusing to run --execute against "
            "the whole cohort only to fail on every gene; export it (or drop "
            "--execute for a dry-run) and try again.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    counts: Counter[str] = Counter()
    with httpx.Client(timeout=60) as http:
        todo = genes or annotated_genes(http, token)
        if not execute:
            print(f"[dry-run] would archive {len(todo)} genes; pass --execute.")
            return counts
        # Build (and cache) the S3 client ONCE, here in the main thread,
        # before the archiving pool starts below — so pooled workers find
        # it already built (one client, one credential-derivation call)
        # instead of racing a cold cache, and a broken/missing
        # CLOUDFLARE_API_TOKEN fails loudly right now instead of ~5,130
        # individual (require_s3=True) ArchiveError failures.
        try:
            r2_s3_client()
        except R2S3CredentialError as exc:
            print(
                f"R2 S3 client unavailable ({exc}) — the sweep refuses to fall "
                "back to the REST r2_client path at cohort scale (it would "
                "compete for the shared Cloudflare account API budget). Set "
                "CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_API_TOKEN (or "
                "R2_ACCESS_KEY_ID/R2_SECRET_ACCESS_KEY) and retry.",
                file=sys.stderr,
            )
            raise SystemExit(1) from exc
        gps = max_genes_per_second if max_genes_per_second is not None else sweep_gps_from_env()
        limiter = RateLimiter(gps, clock=clock, sleep=sleep)
        backoff = _ServerErrorBackoff(clock=clock, sleep=sleep)
        guard = _ConsecutiveFailureGuard(ABORT_AFTER_N_CONSECUTIVE_FAILURES)
        with (
            CloudRevisionStore.from_env(require_s3=True) as store,
            ThreadPoolExecutor(workers) as pool,
        ):
            # One query for every gene's latest revision instead of one
            # `latest()` query per gene — at cohort scale (~5,130 genes)
            # this alone is most of the sweep's D1 call volume. `latest()`
            # then serves from this in-memory cache for the rest of the
            # sweep; a successful `insert_revision` keeps it current.
            store.prefetch_latest()
            # Per-gene `/revisions` purges are skipped during a sweep (no
            # `purge=` passed through, so `archive_gene`'s default `None`
            # applies) to spare purge quota on the shared zone; those lists
            # are 60-second TTL and self-heal.
            futs = {
                pool.submit(
                    _archive_or_skip,
                    g,
                    http=http,
                    store=store,
                    token=token,
                    guard=guard,
                    limiter=limiter,
                    backoff=backoff,
                ): g
                for g in todo
            }
            for i, fut in enumerate(as_completed(futs), 1):
                g = futs[fut]
                try:
                    result = fut.result()
                except Exception as exc:  # noqa: BLE001 — report and keep sweeping
                    counts["failed"] += 1
                    print(f"FAILED {g}: {exc}")
                else:
                    if result is None:
                        # A gene skipped post-abort is a sweep failure, not
                        # merely a no-op — count it into "failed" explicitly
                        # (not just relying on the N real failures that
                        # tripped the guard already being >0) so a caller
                        # reading `counts["failed"]` alone sees the full
                        # blast radius of the abort, and so main()'s exit
                        # code reflects it without depending on that
                        # invariant either.
                        counts["skipped_after_abort"] += 1
                        counts["failed"] += 1
                    else:
                        counts[result.status] += 1
                msg = guard.pop_trip_message()
                if msg:
                    print(f"ABORTING: {msg}")
                if i % 250 == 0:
                    print(f"{i}/{len(todo)} {dict(counts)}")
    if counts["created"]:
        purge_paths(["/v1/releases"])
    print(dict(counts))
    return counts


def _served_hashes(served: Served) -> tuple[str, str | None, str | None]:
    """The three content hashes ``archive_gene`` would compute for ``served``."""
    json_hash = content_hash_record(served.record)
    evidence_hash = (
        content_hash_evidence(served.evidence) if served.evidence is not None else None
    )
    md_hash = (
        content_hash_md(served.md_bytes.decode("utf-8"))
        if served.md_bytes is not None
        else None
    )
    return json_hash, evidence_hash, md_hash


def _check_gene_stability(
    symbol: str,
    *,
    http: httpx.Client,
    token: str,
    base: str = PUBLIC_API_BASE,
    limiter: RateLimiter,
    backoff: _ServerErrorBackoff,
) -> list[str]:
    """Fetches ``symbol`` twice and returns the parts whose hash disagreed.

    Read-only: only calls ``fetch_served`` (a GET), never touches the
    store/R2/D1. An empty list means the two fetches hashed identically.

    Each of the two ``fetch_served`` calls counts as its own paced unit
    (``limiter.acquire()`` before each) — a stability check costs the public
    API/D1 exactly as much per gene as an ``--execute`` sweep costs per two
    genes, so it's paced at the same rate. ``backoff.before_gene()`` runs
    once per gene (not per fetch), matching the sweep's "pause before the
    next gene" contract.
    """
    backoff.before_gene()
    try:
        limiter.acquire()
        first = fetch_served(symbol, http=http, token=token, base=base)
        limiter.acquire()
        second = fetch_served(symbol, http=http, token=token, base=base)
    except Exception as exc:  # noqa: BLE001 — re-raised after recording back-off
        if _is_server_error(exc):
            backoff.record_server_error()
        raise
    else:
        backoff.record_success()
    if first is None and second is None:
        return []
    if first is None or second is None:
        # The gene flipped between annotated/not-annotated mid-check — a
        # real instability, just not one a hash-part name describes.
        return ["annotated_status"]
    diffs = []
    for part, a, b in zip(
        ("record", "evidence", "md"), _served_hashes(first), _served_hashes(second)
    ):
        if a != b:
            diffs.append(part)
    return diffs


def check_stability(
    genes: list[str] | None,
    *,
    sample: int,
    seed: int,
    http: httpx.Client,
    token: str,
    workers: int,
    base: str = PUBLIC_API_BASE,
    max_genes_per_second: float | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, list[str]]:
    """Read-only stability check: never touches the store/R2/D1.

    Fetches each of ``genes`` (or a seeded random sample of ``sample``
    annotated genes, if ``genes`` is ``None``) twice and compares content
    hashes. Returns ``{gene_symbol: [differing parts]}`` for every gene
    that was unstable; an empty dict means every checked gene was stable.

    ``max_genes_per_second`` / ``clock`` / ``sleep`` — see ``sweep()``'s
    docstring; both fetches per gene are paced (and count toward the same
    server-error back-off) at the same per-fetch rate a sweep uses.
    """
    if not token:
        print(
            "ARCHIVE_BYPASS_TOKEN is unset — --check-stability needs it to fetch "
            "the un-cached bypass response twice per gene; export it and try again.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if genes is not None:
        todo = genes
    else:
        all_genes = annotated_genes(http, token, base)
        if sample >= len(all_genes):
            todo = all_genes
        else:
            todo = random.Random(seed).sample(all_genes, sample)
    gps = max_genes_per_second if max_genes_per_second is not None else sweep_gps_from_env()
    limiter = RateLimiter(gps, clock=clock, sleep=sleep)
    backoff = _ServerErrorBackoff(clock=clock, sleep=sleep)
    unstable: dict[str, list[str]] = {}
    with ThreadPoolExecutor(workers) as pool:
        futs = {
            pool.submit(
                _check_gene_stability,
                g,
                http=http,
                token=token,
                base=base,
                limiter=limiter,
                backoff=backoff,
            ): g
            for g in todo
        }
        for fut in as_completed(futs):
            g = futs[fut]
            try:
                diffs = fut.result()
            except Exception as exc:  # noqa: BLE001 — report and keep checking
                print(f"ERROR {g}: {exc}")
                unstable[g] = ["error"]
                continue
            if diffs:
                unstable[g] = diffs
                print(f"UNSTABLE {g}: {', '.join(diffs)}")
    print(f"checked {len(todo)} genes, {len(unstable)} unstable")
    return unstable


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--genes", help="comma-separated symbols (default: all annotated)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument(
        "--check-stability",
        action="store_true",
        help=(
            "read-only: fetch each gene twice and diff content hashes; "
            "never touches the store/R2/D1 (see module docstring)"
        ),
    )
    ap.add_argument(
        "--sample",
        type=int,
        default=DEFAULT_STABILITY_SAMPLE,
        help="genes to sample for --check-stability (ignored when --genes is given)",
    )
    ap.add_argument(
        "--base",
        default=PUBLIC_API_BASE,
        help=(
            "API base for --check-stability only (e.g. a local `wrangler dev` of an "
            "undeployed Worker); a real sweep always archives the public API"
        ),
    )
    ap.add_argument(
        "--max-genes-per-second",
        type=float,
        default=None,
        help=(
            "cap how many genes --execute/--check-stability may START fetching "
            "per second through the public Worker's archive-bypass header — "
            "which skips the Worker's caches, so each fetch costs ~17 queries "
            "on the shared public D1 that serves real users. "
            f"Default {DEFAULT_SWEEP_GPS} (or ${SWEEP_GPS_ENV_VAR} if set); "
            "0 disables pacing entirely. Never raise this during business hours."
        ),
    )
    args = ap.parse_args()
    if args.base != PUBLIC_API_BASE and not args.check_stability:
        ap.error("--base is only allowed with --check-stability")
    genes = [g.strip() for g in args.genes.split(",")] if args.genes else None
    if args.check_stability:
        load_env()
        token = os.environ.get("ARCHIVE_BYPASS_TOKEN", "").strip()
        with httpx.Client(timeout=60) as http:
            unstable = check_stability(
                genes,
                sample=args.sample,
                seed=STABILITY_SAMPLE_SEED,
                http=http,
                token=token,
                workers=args.workers,
                base=args.base.rstrip("/"),
                max_genes_per_second=args.max_genes_per_second,
            )
        raise SystemExit(1 if unstable else 0)
    counts = sweep(
        genes,
        execute=args.execute,
        workers=args.workers,
        max_genes_per_second=args.max_genes_per_second,
    )
    raise SystemExit(1 if counts["failed"] else 0)


if __name__ == "__main__":
    main()
