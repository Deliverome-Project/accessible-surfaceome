"""Audit ``deep_dive_run`` rows for orphaned children and (optionally)
backfill from the canonical JSON.

The Modal sweep streams a parent + its evidence + its search-log
children into D1 across separate HTTP calls. A child-insert failure
between the parent insert and the child inserts leaves the parent
orphaned: the next retry hits ``ON CONFLICT (run_id, gene_symbol) DO
NOTHING``, gets no ``dd_id`` back, and silently skips re-inserting
children. This script detects those parents and repairs them.

Usage::

    # Report only (default — no D1 mutations).
    uv run python scripts/audit/audit_deep_dive_orphans.py \\
        --run-id candidate_universe_v1_sonnet_2026_05

    # Backfill children from the on-disk JSON for every orphan.
    uv run python scripts/audit/audit_deep_dive_orphans.py \\
        --run-id candidate_universe_v1_sonnet_2026_05 \\
        --execute

    # Pull JSON from a Modal volume snapshot pulled to a custom path.
    uv run python scripts/audit/audit_deep_dive_orphans.py \\
        --run-id candidate_universe_v1_sonnet_2026_05 \\
        --annotations-dir /tmp/modal_snapshot \\
        --execute

Exit codes:

* ``0`` — no orphans, or every orphan was successfully backfilled
* ``1`` — orphans detected, run is incomplete (report mode)
* ``2`` — argument error
* ``3`` — partial backfill (some succeeded, some failed)
"""

from __future__ import annotations

import argparse
import csv
import logging
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.cloud.deep_dive_audit import (
    OrphanRow,
    backfill_from_record,
    find_orphans,
)
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import DATA_DIR
from accessible_surfaceome.tools._shared.models import SurfaceomeRecord

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuditOutcome:
    orphan: OrphanRow
    json_present: bool
    action: str  # "reported" | "backfilled" | "backfill_failed" | "json_missing" | "json_invalid"
    error: str | None = None


def _json_path(annotations_dir: Path, run_id: str, gene_symbol: str) -> Path:
    return annotations_dir / run_id / f"{gene_symbol}.json"


def _load_record(json_path: Path) -> SurfaceomeRecord | None:
    if not json_path.exists():
        return None
    try:
        return SurfaceomeRecord.model_validate_json(json_path.read_text())
    except ValidationError as exc:
        logger.warning("invalid record at %s: %s", json_path, exc)
        return None


def _process_orphan(
    d1: D1Client,
    orphan: OrphanRow,
    annotations_dir: Path,
    execute: bool,
) -> AuditOutcome:
    json_path = _json_path(annotations_dir, orphan.run_id, orphan.gene_symbol)
    if not json_path.exists():
        return AuditOutcome(orphan=orphan, json_present=False, action="json_missing")
    record = _load_record(json_path)
    if record is None:
        return AuditOutcome(
            orphan=orphan, json_present=True, action="json_invalid",
            error="record failed Pydantic validation",
        )
    if not execute:
        return AuditOutcome(orphan=orphan, json_present=True, action="reported")
    try:
        backfill_from_record(d1, parent_id=orphan.parent_id, record=record)
    except Exception as exc:  # noqa: BLE001 — report and continue
        return AuditOutcome(
            orphan=orphan, json_present=True, action="backfill_failed",
            error=str(exc),
        )
    return AuditOutcome(orphan=orphan, json_present=True, action="backfilled")


def _print_summary(outcomes: list[AuditOutcome], *, execute: bool) -> None:
    total = len(outcomes)
    if total == 0:
        print("no orphans found — every parent's children match its denormalized counts.")
        return
    missing_ev = sum(o.orphan.missing_evidence for o in outcomes)
    missing_sl = sum(o.orphan.missing_search_log for o in outcomes)
    print(
        f"orphans: {total} parents with incomplete children "
        f"(missing {missing_ev} evidence rows, {missing_sl} search_log rows)"
    )
    by_action: dict[str, int] = {}
    for o in outcomes:
        by_action[o.action] = by_action.get(o.action, 0) + 1
    for action, count in sorted(by_action.items()):
        print(f"  {action}: {count}")
    if not execute and any(o.json_present for o in outcomes):
        recoverable = sum(1 for o in outcomes if o.json_present)
        print(
            f"\n{recoverable}/{total} orphans have JSON on disk and can be "
            "backfilled. Re-run with --execute to repair."
        )


def _write_tsv(outcomes: list[AuditOutcome], path: Path) -> None:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow([
            "run_id", "gene_symbol", "parent_id",
            "expected_evidence", "actual_evidence", "missing_evidence",
            "expected_search_log", "actual_search_log", "missing_search_log",
            "json_present", "action", "error",
        ])
        for o in outcomes:
            w.writerow([
                o.orphan.run_id, o.orphan.gene_symbol, o.orphan.parent_id,
                o.orphan.expected_evidence, o.orphan.actual_evidence,
                o.orphan.missing_evidence,
                o.orphan.expected_search_log, o.orphan.actual_search_log,
                o.orphan.missing_search_log,
                int(o.json_present), o.action, o.error or "",
            ])
    print(f"wrote orphan report to {path}")


def main(argv: list[str] | None = None) -> int:
    load_env()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--run-id",
        required=True,
        help="Sweep tag to audit (matches deep_dive_run.run_id)",
    )
    p.add_argument(
        "--execute",
        action="store_true",
        help="Backfill children from the on-disk JSON. Without this flag, the "
        "script only reports; D1 is not mutated.",
    )
    p.add_argument(
        "--annotations-dir",
        type=Path,
        default=DATA_DIR / "annotations",
        help="Where per-gene JSON lives (canonical artifact). Expected layout "
        "is <dir>/<run_id>/<symbol>.json, matching the path scheme from PR #43.",
    )
    p.add_argument(
        "--output-tsv",
        type=Path,
        default=None,
        help="Optional path for a TSV report of every orphan + action taken.",
    )
    args = p.parse_args(argv)

    with D1Client() as d1:
        orphans = find_orphans(d1, args.run_id)
        print(
            f"scanned run_id={args.run_id}: found {len(orphans)} orphan parent(s) "
            f"in deep_dive_run.",
            flush=True,
        )
        outcomes: list[AuditOutcome] = []
        for orphan in orphans:
            outcomes.append(_process_orphan(d1, orphan, args.annotations_dir, args.execute))

    _print_summary(outcomes, execute=args.execute)
    if args.output_tsv is not None:
        _write_tsv(outcomes, args.output_tsv)

    if not outcomes:
        return 0
    failed = [o for o in outcomes if o.action in {"backfill_failed", "json_missing", "json_invalid"}]
    if args.execute:
        return 3 if failed else 0
    return 1  # report mode: orphans present ⇒ non-zero so CI can gate on this


if __name__ == "__main__":
    raise SystemExit(main())
