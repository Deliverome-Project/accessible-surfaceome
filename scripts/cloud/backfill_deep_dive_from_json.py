"""Backfill missing private ``deep_dive_run`` rows from JSON artifacts.

Use this after pulling the Modal Volume when a sweep may have written
``<run_id>/<symbol>.json`` but failed to mirror the private D1 parent row.
The command is dry-run by default; pass ``--execute`` to mutate D1.

Examples:

    uv run modal volume get surfaceome-annotations / data/annotations/

    uv run python scripts/backfill_deep_dive_from_json.py \\
        --run-id candidate_universe_v3_sonnet_2026_06_stage1

    uv run python scripts/backfill_deep_dive_from_json.py \\
        --run-id candidate_universe_v3_sonnet_2026_06_stage1 \\
        --annotations-dir /tmp/modal_snapshot \\
        --execute

Cost note: the canonical JSON does not carry the original spend/latency. Rows
inserted without ``--metadata-tsv`` use zero for ``cost_usd``, ``latency_s``,
and ``n_tool_calls``. That preserves resume correctness but undercounts cost.
If you captured run metadata, provide a TSV with ``gene_symbol`` plus optional
``cost_usd``, ``latency_s``, and ``n_tool_calls`` columns.

Prompt note: the private D1 row records the composite prompt SHA from the
current checkout. Run this recovery before changing prompts, or from the same
commit/image used for the sweep, so prompt provenance stays aligned.

Exit codes:

* 0 — no missing rows, or every missing row was backfilled under ``--execute``
* 1 — dry-run found rows that would be backfilled
* 2 — argument / input error
* 3 — invalid JSON or D1 backfill failures
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.cloud.deep_dive_json_backfill import (
    JsonBackfillOutcome,
    execute_json_backfill,
    existing_private_genes,
    load_candidates,
    load_metadata_tsv,
    plan_json_backfill,
    run_dir,
)
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import DATA_DIR


def _print_summary(outcomes: list[JsonBackfillOutcome], *, execute: bool) -> None:
    by_action: dict[str, int] = {}
    for outcome in outcomes:
        by_action[outcome.action] = by_action.get(outcome.action, 0) + 1
    total = len(outcomes)
    print(f"scanned {total} JSON candidate(s)")
    for action, count in sorted(by_action.items()):
        print(f"  {action}: {count}")
    missing = by_action.get("would_backfill", 0)
    if missing and not execute:
        print(
            "\nDry run only. Re-run with --execute to insert the missing private "
            "D1 rows. Existing parent rows are intentionally skipped; run "
            "scripts/audit_deep_dive_orphans.py for incomplete child rows."
        )
    if execute and by_action.get("backfilled", 0):
        print(
            "\nBackfilled missing private parent rows. Run "
            "scripts/audit_deep_dive_orphans.py next to verify child counts."
        )


def _write_tsv(outcomes: list[JsonBackfillOutcome], path: Path) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["path", "gene_symbol", "action", "error"])
        for outcome in outcomes:
            writer.writerow(
                [
                    str(outcome.path),
                    outcome.gene_symbol or "",
                    outcome.action,
                    outcome.error or "",
                ]
            )
    print(f"wrote report to {path}")


def main(argv: list[str] | None = None) -> int:
    load_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="deep_dive_run.run_id")
    parser.add_argument(
        "--annotations-dir",
        type=Path,
        default=DATA_DIR / "annotations",
        help="Directory containing <run_id>/<symbol>.json artifacts",
    )
    parser.add_argument(
        "--metadata-tsv",
        type=Path,
        default=None,
        help=(
            "Optional TSV with gene_symbol and any of cost_usd, latency_s, "
            "n_tool_calls. Without it, inserted rows use zero metadata."
        ),
    )
    parser.add_argument(
        "--output-tsv",
        type=Path,
        default=None,
        help="Optional TSV report path",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Mutate private D1. Omit for dry-run report only.",
    )
    args = parser.parse_args(argv)

    source_dir = run_dir(args.annotations_dir, args.run_id)
    candidates = load_candidates(source_dir)
    if len(candidates) == 1 and candidates[0].action == "run_dir_missing":
        print(candidates[0].error)
        return 2

    try:
        metadata = load_metadata_tsv(args.metadata_tsv)
    except Exception as exc:  # noqa: BLE001
        print(f"metadata TSV error: {exc}")
        return 2

    with D1Client() as d1:
        existing = existing_private_genes(d1, args.run_id)
        if args.execute:
            outcomes = execute_json_backfill(
                run_id=args.run_id,
                candidates=candidates,
                existing=existing,
                metadata=metadata,
                d1=d1,
            )
        else:
            outcomes = plan_json_backfill(candidates, existing)

    _print_summary(outcomes, execute=args.execute)
    if args.output_tsv is not None:
        _write_tsv(outcomes, args.output_tsv)

    bad = [
        o
        for o in outcomes
        if o.action in {"json_invalid", "backfill_failed", "run_dir_missing"}
    ]
    if bad:
        return 3
    if not args.execute and any(o.action == "would_backfill" for o in outcomes):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
