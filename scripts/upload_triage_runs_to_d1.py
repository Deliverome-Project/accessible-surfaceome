"""Upload triage agent runs to the Cloudflare D1 ``deliverome_agent_runs`` database.

Run AFTER provisioning the D1 database (see cloudflare/README.md) and
setting the env vars CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_D1_DELIVEROME_ID,
CLOUDFLARE_API_TOKEN.

Examples
--------

    # Upload every persisted sub-bench run with a fresh run_id (default).
    uv run python scripts/upload_triage_runs_to_d1.py

    # Tag the upload with a known run_id (e.g. 2026-05-10_hard_cases).
    uv run python scripts/upload_triage_runs_to_d1.py --run-id 2026-05-10_hard_cases

    # Dry run — print what would be uploaded but make no API calls.
    uv run python scripts/upload_triage_runs_to_d1.py --dry-run
"""

from __future__ import annotations

import argparse
import logging

from accessible_surfaceome.cloud.triage_upload import (
    SUBBENCH_RUNS,
    SUBBENCH_TSV,
    upload_subbench_runs,
)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", default=None,
                    help="Tag for this upload (groups runs in D1). Default: a fresh uuid.")
    ap.add_argument("--bench-tsv", default=str(SUBBENCH_TSV),
                    help="Benchmark TSV to snapshot into benchmark_version.")
    ap.add_argument("--runs-root", default=str(SUBBENCH_RUNS),
                    help="Directory containing <model>/<variant>/*_run*.json records.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print what would be uploaded; make no API calls.")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    from pathlib import Path
    counters = upload_subbench_runs(
        bench_tsv=Path(args.bench_tsv),
        runs_root=Path(args.runs_root),
        run_id=args.run_id,
        dry_run=args.dry_run,
    )

    print()
    print("=== upload summary ===")
    for k, v in counters.items():
        print(f"  {k:20s} {v}")


if __name__ == "__main__":
    main()
