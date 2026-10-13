"""Restore ``filters.n_papers_found`` from the run's own private-D1 intermediates.

A builders replay rebuilds the plan-trim-select result from the cached
``agent_run_intermediates`` blob via ``a1_recovery.reconstruct_dual_from_blob``.
Until that helper carried ``n_papers_discovered`` it defaulted the count to 0,
which the orchestrator reduces to ``None``, so every replayed record went out
with an unknown discovery corpus. 19 records replayed on 2026-09-21 (after the
topology backfill) were published that way.

The discovery count those records were built on is still in the intermediates
blob, so this copies it back rather than re-running discovery the way
``backfill_n_papers_found.py --from-d1`` does. Re-discovery would query today's
literature and could drift from the corpus the agent actually saw; the copy is
exact and makes no network calls beyond D1. Same reducer as the orchestrator:
``max(a1, a2)`` over the two sides.

The replay's publish also stamped every row with the replay batch's
``cohort_run_id``, so it republishes under the intermediates row's own
``cohort_run_id`` — the join key ``publish_record`` documents — which
returns seven ``cu_v3_sonnet_2026_06`` genes to their original cohort.

Each patched record is revalidated against ``SurfaceomeRecord`` and published
through ``publish_record`` (D1 write, edge-cache purge, record-history archive).
Dry-run by default; ``--execute`` publishes.

    uv run python scripts/build/restore_n_papers_found_from_intermediates.py
    uv run python scripts/build/restore_n_papers_found_from_intermediates.py --execute
"""

from __future__ import annotations

import argparse
import json

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.cloud.n_papers_found_backfill import (
    NEEDS_BACKFILL_SQL,
    patch_n_papers_found,
)
from accessible_surfaceome.cloud.surface_annotation import publish_record
from accessible_surfaceome.env import load_env
from accessible_surfaceome.tools._shared.models import SurfaceomeRecord

# Latest intermediates row per gene, projected to the two counts + cohort tag so
# the ~MB intermediates blob never crosses the wire.
_INTERMEDIATES_SQL = (
    "SELECT cohort_run_id, created_at, "
    "json_extract(intermediates_json, '$.plan_trim_select.a1.n_papers_discovered') AS a1, "
    "json_extract(intermediates_json, '$.plan_trim_select.a2.n_papers_discovered') AS a2 "
    "FROM agent_run_intermediates WHERE gene_symbol = ? "
    "ORDER BY created_at DESC LIMIT 1;"
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true", help="Publish (default: dry-run).")
    args = ap.parse_args()
    load_env()

    with D1Client(D1Config.from_env_public()) as pub, D1Client(D1Config.from_env()) as prv:
        targets = [r["gene_symbol"] for r in pub.query(NEEDS_BACKFILL_SQL, [])]
        print(f"{len(targets)} published records have a null n_papers_found")
        failed: list[str] = []
        for sym in targets:
            inter = prv.query(_INTERMEDIATES_SQL, [sym])
            counts = [c for c in (inter[0]["a1"], inter[0]["a2"]) if c] if inter else []
            if not counts:
                print(f"  {sym}: no discovery count in intermediates — skipped")
                failed.append(sym)
                continue
            n_found, cohort = max(counts), inter[0]["cohort_run_id"]
            row = pub.query(
                "SELECT annotation_json FROM surface_annotation WHERE gene_symbol = ?;", [sym]
            )
            record = SurfaceomeRecord.model_validate(
                patch_n_papers_found(json.loads(row[0]["annotation_json"]), n_found)
            )
            print(f"  {sym}: n_papers_found={n_found} cohort={cohort}")
            if args.execute:
                result = publish_record(record, cohort_run_id=cohort)
                if not result.d1_written:
                    print(f"    NOT written: {result.skipped_reason}")
                    failed.append(sym)
    if failed:
        print(f"{len(failed)} not restored: {', '.join(failed)}")
    if not args.execute:
        print("dry-run — pass --execute to publish")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
