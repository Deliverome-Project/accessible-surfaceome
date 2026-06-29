"""Read-only post-run census across the deep-dive persistence surfaces.

Single command to answer "is this run trustworthy?" after a Modal sweep. For
every gene in the intended cohort it reconciles three surfaces — Volume JSON,
private D1 (``deep_dive_run`` + children), public D1 (``surface_annotation``) —
and classifies each gene (``ok`` / ``missing`` / a named drift class). It never
mutates anything; each drift class names the point tool that repairs it.

    uv run python scripts/deep_dive_census.py \\
        --run-id candidate_universe_v1_sonnet_2026_05 \\
        --gene-list data/processed/candidate_universe/candidate_universe.tsv \\
        --annotations-dir data/annotations

Exit codes (for runbook / CI gating):

* 0 — every cohort gene is ``ok`` on all surfaces.
* 1 — at least one gene drifted (uneven across surfaces / stale public schema /
  orphaned children). Must repair before trusting the run.
* 2 — no drift, but some genes never completed (``missing``) or appear on a
  surface without being in the gene-list (``unexpected``). Resume the sweep.

``--json`` emits the full per-gene matrix as JSON for downstream tooling.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

logger = logging.getLogger("deep_dive_census")


def main(argv: list[str] | None = None) -> int:
    from accessible_surfaceome.cloud.d1_client import D1Client, D1Error
    from accessible_surfaceome.cloud.deep_dive_census import (
        REPAIR_HINT,
        build_census,
        exit_code,
        load_cohort_symbols,
        orphan_symbols,
        private_parents,
        public_schema_versions,
        scan_volume_json,
        summarize,
    )
    from accessible_surfaceome.cloud.deep_dive_json_backfill import run_dir
    from accessible_surfaceome.env import load_env

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="deep_dive_run.run_id")
    parser.add_argument(
        "--cohort-run-id",
        default=None,
        help=(
            "Cohort tag for the quarantine lookup (agent_run_intermediates."
            "cohort_run_id). Defaults to --run-id, matching the sweep's "
            "cohort_run_id = (cohort_run_id or run_id). Set this only if the "
            "sweep used a distinct --cohort-run-id, else quarantined genes "
            "would be misreported as 'missing'."
        ),
    )
    parser.add_argument(
        "--gene-list",
        required=True,
        type=Path,
        help="cohort TSV (hgnc_id + hgnc_symbol/gene_symbol columns)",
    )
    parser.add_argument(
        "--annotations-dir",
        type=Path,
        default=Path("data/annotations"),
        help="root holding <run_id>/<symbol>.json (default: data/annotations)",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit the full per-gene matrix as JSON"
    )
    parser.add_argument(
        "--show",
        choices=["drift", "all", "none"],
        default="drift",
        help="which genes to list in the table (default: drift only)",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    load_env()

    cohort = load_cohort_symbols(args.gene_list)

    volume = scan_volume_json(run_dir(args.annotations_dir, args.run_id))

    # Private D1 is the census's core surface — if we can't reach it there is
    # no audit to run. Fail with a clean, distinct code (3 = infra, vs the
    # 0/1/2 data verdicts) rather than dumping a traceback in a runbook.
    from accessible_surfaceome.cloud.intermediates import fetch_quarantined_genes

    try:
        with D1Client() as d1:
            private = private_parents(d1, args.run_id)
            orphans = orphan_symbols(d1, args.run_id)
            # Over-cap genes parked for manual review (same signal the sweep
            # uses to skip them). Scope to the same cohort tag the sweep wrote
            # under: cohort_run_id = (cohort_run_id or run_id).
            quarantined = fetch_quarantined_genes(
                d1, cohort_run_id=args.cohort_run_id or args.run_id
            )
    except D1Error as exc:
        logger.error("cannot reach private D1 — census not run: %s", exc)
        return 3

    # Public D1 is a separate database; skip (don't fail) when creds absent.
    public: dict[str, str] | None
    public_cfg = _public_config()
    if public_cfg is None:
        logger.warning(
            "public D1 creds absent — skipping surface_annotation checks "
            "(public_missing / public_stale not evaluated)"
        )
        public = None
    else:
        with D1Client(public_cfg) as d1_pub:
            public = public_schema_versions(d1_pub, cohort)

    rows = build_census(
        cohort_symbols=cohort,
        volume=volume,
        private=private,
        orphan_symbols=orphans,
        public=public,
        quarantined=quarantined,
    )

    if args.json:
        print(json.dumps([asdict(r) | {"status": r.status} for r in rows], indent=2))
        return exit_code(rows)

    counts = summarize(rows)
    code = exit_code(rows)
    print(f"\ndeep-dive census — run_id={args.run_id}  cohort={len(cohort)} genes")
    print(f"  volume_json={len(volume)}  private={len(private)}  "
          f"public={'(skipped)' if public is None else len(public)}\n")
    for status, n in counts.most_common():
        hint = REPAIR_HINT.get(status)
        suffix = f"   → {hint}" if hint else ""
        print(f"  {status:18s} {n:6d}{suffix}")

    if args.show != "none":
        listed = [
            r for r in rows
            if args.show == "all" or (not r.is_ok and r.status != "ok")
        ]
        if listed:
            print(f"\n  {'gene':14s} {'status':18s} json  priv  pub  schema(json/priv/pub)")
            for r in sorted(listed, key=lambda x: (x.status, x.gene_symbol)):
                print(
                    f"  {r.gene_symbol:14s} {r.status:18s} "
                    f"{_b(r.in_volume_json)}    {_b(r.in_private)}    {_b(r.in_public)}   "
                    f"{r.json_schema_version or '-'}/"
                    f"{r.private_schema_version or '-'}/"
                    f"{r.public_schema_version or '-'}"
                )

    print(f"\nexit {code} "
          f"({'all ok' if code == 0 else 'drift — repair' if code == 1 else 'incomplete — resume'})")
    return code


def _b(flag: bool) -> str:
    return "Y" if flag else "."


def _public_config():
    from accessible_surfaceome.cloud.d1_env import public_d1_config_or_warn

    return public_d1_config_or_warn(operation="deep_dive_census", symbol=None)


if __name__ == "__main__":
    sys.exit(main())
