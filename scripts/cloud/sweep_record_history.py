#!/usr/bin/env python3
"""Archive what the API serves for every annotated gene (dry-run by default).

Run after any bulk deterministic-table sync (enrichment-only changes are
not caught by publish-time archiving) and as step 1 of every release.

    uv run python scripts/cloud/sweep_record_history.py                 # list genes
    uv run python scripts/cloud/sweep_record_history.py --execute
    uv run python scripts/cloud/sweep_record_history.py --execute --genes EGFR,CD63

Two guardrails on top of the plain per-gene archive:

* ``--execute`` with no ``ARCHIVE_BYPASS_TOKEN`` exits immediately with a
  clear error instead of walking the whole cohort and recording ~5,000
  identical per-gene ``ArchiveError`` failures (``archive_gene`` itself
  would raise one per gene for a missing token).
* If ``ABORT_AFTER_N_CONSECUTIVE_ARCHIVE_ERRORS`` genes in a row come back
  with ``ArchiveError`` (wrong token, or a Worker too old to echo the
  bypass-honoured header), the sweep stops calling the API for the rest of
  the cohort — a misconfiguration should fail loud after a handful of
  genes, not grind through every gene making the same doomed request.

The dry-run genes list (``/v1/genes``) is a public route, so it works
without any token; the bypass header is only sent when one is configured.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from accessible_surfaceome.cloud.record_history.archive import (
    BYPASS_HEADER,
    PUBLIC_API_BASE,
    ArchiveResult,
    archive_gene,
)
from accessible_surfaceome.cloud.record_history.store import (
    ArchiveError,
    CloudRevisionStore,
    RevisionStore,
)
from accessible_surfaceome.cloud.surface_annotation import purge_paths
from accessible_surfaceome.env import load_env

ABORT_AFTER_N_CONSECUTIVE_ARCHIVE_ERRORS = 5


def annotated_genes(http: httpx.Client, token: str) -> list[str]:
    # /v1/genes is a public route — only attach the bypass header when a
    # token is actually configured, so the dry-run listing works tokenless.
    headers = {BYPASS_HEADER: token} if token else None
    resp = http.get(f"{PUBLIC_API_BASE}/v1/genes", headers=headers)
    resp.raise_for_status()
    return [g["gene_symbol"] for g in resp.json()["genes"]]


class _ConsecutiveArchiveErrorGuard:
    """Trips once, after ``threshold`` consecutive ``ArchiveError``s.

    Checked at the top of every submitted task rather than only observed
    after the fact from the orchestrating thread — so once it trips, every
    task still queued behind it skips its HTTP call deterministically, even
    with a single worker, instead of racing the main thread's bookkeeping
    loop to decide who gets there first.
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

    def record_archive_error(self, exc: Exception) -> None:
        with self._lock:
            self._streak += 1
            if self._streak >= self._threshold and not self._tripped:
                self._tripped = True
                self._trip_message = (
                    f"{self._threshold} genes in a row failed with ArchiveError — "
                    f"aborting the rest of the sweep instead of repeating the same "
                    f"failure across the cohort. Last error: {exc}"
                )

    def record_other(self) -> None:
        with self._lock:
            self._streak = 0

    def pop_trip_message(self) -> str | None:
        with self._lock:
            msg, self._trip_message = self._trip_message, None
            return msg


def _archive_or_skip(
    symbol: str,
    *,
    http: httpx.Client,
    store: RevisionStore,
    token: str,
    guard: _ConsecutiveArchiveErrorGuard,
) -> ArchiveResult | None:
    """Runs inside the pool. Returns ``None`` for a gene skipped post-abort."""
    if guard.tripped:
        return None
    try:
        result = archive_gene(
            symbol, source="sweep", http=http, store=store, token=token
        )
    except ArchiveError as exc:
        guard.record_archive_error(exc)
        raise
    else:
        guard.record_other()
        return result


def sweep(genes: list[str] | None, *, execute: bool, workers: int) -> Counter[str]:
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
        guard = _ConsecutiveArchiveErrorGuard(ABORT_AFTER_N_CONSECUTIVE_ARCHIVE_ERRORS)
        with (
            CloudRevisionStore.from_env() as store,
            ThreadPoolExecutor(workers) as pool,
        ):
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
                        counts["skipped_after_abort"] += 1
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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--genes", help="comma-separated symbols (default: all annotated)")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    genes = [g.strip() for g in args.genes.split(",")] if args.genes else None
    counts = sweep(genes, execute=args.execute, workers=args.workers)
    raise SystemExit(1 if counts["failed"] else 0)


if __name__ == "__main__":
    main()
