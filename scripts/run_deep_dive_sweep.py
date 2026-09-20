"""Local in-process driver for a v2 deep-dive sweep over a gene list.

Why this exists: the obvious way to parallelise a cohort locally is
``xargs -P N`` over ``scripts/annotate_gene.py``, but that spawns N
independent processes, each with its **own** in-process
:class:`~accessible_surfaceome.tools._shared.ratelimit.RateLimiter` — so the
per-host courtesy interval is violated N-fold against NCBI / Europe PMC /
PubTator. ``ratelimit.py`` is explicit that the limiter "is intentionally
in-process by default" and that "local scripts leave [the cross-process gate]
unset"; Modal solves this with a single-container gate, and locally the
equivalent is simply to keep every gene in **one** process so they share the
limiter. Hence a ThreadPoolExecutor rather than a process fan-out.

Mirrors ``scripts/annotate_gene.py``'s publish sequence per gene so the two
paths can't drift: annotate → publish_record → deep_dive_run → harvested_paper
→ intermediates.

Usage::

    uv run python scripts/run_deep_dive_sweep.py \\
        --gene-list data/processed/intracellular_rescue_v1/deep_dive_cohort.tsv \\
        --cohort-run-id intracellular_rescue_v1_sonnet_2026_09 \\
        --concurrency 28

``--dry-run`` prints the resolved cohort and exits without calling the API.
``--no-publish`` keeps everything off public D1 (private sinks still run,
unlike ``annotate_gene.py`` where they share the ``--publish`` flag).
"""

from __future__ import annotations

import argparse
import csv
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from accessible_surfaceome.agents.surfaceome_v2 import annotate
from accessible_surfaceome.cloud.deep_dive_upload import D1DeepDiveSink
from accessible_surfaceome.cloud.harvested_paper import (
    ensure_schema as ensure_harvested_paper_schema,
    harvested_papers_from_dual,
    publish_harvested_papers,
)
from accessible_surfaceome.cloud.intermediates import publish_intermediates
from accessible_surfaceome.cloud.surface_annotation import publish_record
from accessible_surfaceome.env import load_env
from accessible_surfaceome.tools._shared.models import SurfaceomeRecord

logger = logging.getLogger("deep_dive_sweep")

# Per-gene identifier column preference. HGNC ID first, per the
# gene-identifier-resolution rule (bare symbols misroute ~0.2% of genes).
_ID_COLUMNS = ("hgnc_id", "uniprot_acc", "gene_symbol")


def _load_cohort(path: Path) -> list[tuple[str, str]]:
    """Return ``[(gene_symbol, resolvable_id), ...]`` from a TSV."""
    with path.open() as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    if not rows or "gene_symbol" not in rows[0]:
        raise SystemExit(f"{path}: missing required 'gene_symbol' column")
    out: list[tuple[str, str]] = []
    for r in rows:
        ident = next((r[c] for c in _ID_COLUMNS if r.get(c)), None)
        if ident is None:
            raise SystemExit(f"{path}: no usable identifier for {r['gene_symbol']}")
        out.append((r["gene_symbol"], ident))
    return out


class _Progress:
    """Thread-safe counters + a running cost total with an optional cap."""

    def __init__(self, total: int, max_total_cost_usd: float | None):
        self.total = total
        self.max_total_cost_usd = max_total_cost_usd
        self._lock = threading.Lock()
        self.done = 0
        self.valid = 0
        self.invalid = 0
        self.failed = 0
        self.cost = 0.0
        self.aborted = False

    def record(self, *, symbol: str, status: str, cost: float, elapsed: float) -> None:
        with self._lock:
            self.done += 1
            self.cost += cost
            if status == "VALID":
                self.valid += 1
            elif status == "INVALID":
                self.invalid += 1
            else:
                self.failed += 1
            if (
                self.max_total_cost_usd is not None
                and self.cost >= self.max_total_cost_usd
                and not self.aborted
            ):
                self.aborted = True
                logger.error(
                    "COST CAP $%.2f reached after %d genes — no new genes will start",
                    self.max_total_cost_usd, self.done,
                )
            logger.info(
                "[%4d/%d] %-12s %-8s %6.1fs $%.3f  (running $%.2f | ok=%d bad=%d err=%d)",
                self.done, self.total, symbol, status, elapsed, cost,
                self.cost, self.valid, self.invalid, self.failed,
            )


def _run_one(
    symbol: str,
    ident: str,
    *,
    publish: bool,
    cohort_run_id: str,
    sink: D1DeepDiveSink | None,
    progress: _Progress,
) -> None:
    if progress.aborted:
        return
    started = time.monotonic()
    status, cost = "ERROR", 0.0
    try:
        result = annotate(ident, persist=True, read_phase_checkpoint=True)
        cost = float(result.total_cost_usd or 0.0)
        elapsed = time.monotonic() - started
        status = "VALID" if result.record is not None else "INVALID"

        if publish and result.record is not None:
            publish_record(
                result.record,
                push_to_d1=True,
                write_snapshot=True,
                cohort_run_id=cohort_run_id,
            )

        # Private-D1 sinks. Deliberately NOT gated on --publish: a failed
        # annotate is the highest-value case for the diagnostic trail, and
        # annotate_gene.py's coupling of the two is a wart this driver avoids.
        if sink is not None and result.record is not None:
            sink.insert(result.record, cost_usd=cost, latency_s=elapsed)

        if result.dual is not None:
            try:
                harvested = harvested_papers_from_dual(
                    result.dual, run_id=cohort_run_id, gene_symbol=result.gene
                )
                if harvested:
                    publish_harvested_papers(harvested)
            except Exception as exc:  # noqa: BLE001
                logger.warning("harvested_paper failed (%s): %s", symbol, exc)

        if result.intermediates:
            sv = (
                result.record.schema_version
                if result.record is not None
                else SurfaceomeRecord.model_fields["schema_version"].default
            )
            try:
                publish_intermediates(
                    gene_symbol=result.gene,
                    intermediates=result.intermediates,
                    schema_version=sv,
                    record_valid=result.record is not None,
                    cohort_run_id=cohort_run_id,
                    failure_mode=result.failure_mode,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("intermediates failed (%s): %s", symbol, exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("annotate FAILED (%s): %s", symbol, exc)
    finally:
        progress.record(
            symbol=symbol,
            status=status,
            cost=cost,
            elapsed=time.monotonic() - started,
        )


def main(argv: list[str] | None = None) -> int:
    load_env()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s"
    )
    ap = argparse.ArgumentParser()
    ap.add_argument("--gene-list", required=True, type=Path)
    ap.add_argument("--cohort-run-id", required=True)
    ap.add_argument(
        "--concurrency",
        type=int,
        default=20,
        help=(
            "Concurrent genes in ONE process (shared RateLimiter). The OTPM-safe "
            "ceiling is ~66 (see agents/_support/concurrency.py), but a small "
            "cohort is bounded by the latency tail (p99 1428s), so past ~24-30 "
            "the wall clock stops improving."
        ),
    )
    ap.add_argument("--publish", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--max-total-cost-usd", type=float, default=None)
    ap.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True,
                    help="Skip genes already in deep_dive_run under this cohort-run-id.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    cohort = _load_cohort(args.gene_list)

    sink: D1DeepDiveSink | None = None
    try:
        sink = D1DeepDiveSink(run_id=args.cohort_run_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("D1DeepDiveSink unavailable (%s) — continuing without it", exc)

    if args.resume and sink is not None:
        before = len(cohort)
        cohort = [(s, i) for s, i in cohort if not sink.already_done(s)]
        if before != len(cohort):
            logger.info("resume: skipping %d gene(s) already done", before - len(cohort))

    print(f"cohort:      {len(cohort)} genes  ({args.gene_list})")
    print(f"run_id:      {args.cohort_run_id}")
    print(f"concurrency: {args.concurrency} (single process, shared RateLimiter)")
    print(f"publish:     {'public D1 + viewer snapshot' if args.publish else 'private sinks only'}")
    if args.dry_run:
        for s, i in cohort[:10]:
            print(f"  {s:12s} -> {i}")
        if len(cohort) > 10:
            print(f"  ... and {len(cohort) - 10} more")
        return 0

    if args.publish:
        try:
            ensure_harvested_paper_schema()
        except Exception as exc:  # noqa: BLE001
            logger.warning("harvested_paper schema ensure failed: %s", exc)

    progress = _Progress(len(cohort), args.max_total_cost_usd)
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [
            pool.submit(
                _run_one, s, i,
                publish=args.publish,
                cohort_run_id=args.cohort_run_id,
                sink=sink,
                progress=progress,
            )
            for s, i in cohort
        ]
        for f in as_completed(futures):
            f.result()
    wall = time.monotonic() - t0

    if sink is not None:
        sink.close()

    print()
    print(f"genes:       {progress.done}/{len(cohort)}")
    print(f"  VALID:     {progress.valid}")
    print(f"  INVALID:   {progress.invalid}")
    print(f"  ERROR:     {progress.failed}")
    print(f"cost:        ${progress.cost:.2f}")
    print(f"wall clock:  {wall / 60:.1f} min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
