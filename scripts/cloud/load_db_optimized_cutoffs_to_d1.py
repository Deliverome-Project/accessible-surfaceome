"""Load the SurfaceBench-recalibrated DB cutoffs into public D1.

The optimized rules — UniProt expanded to TM>0 / signal-peptide>0 / strict
subcellular term, CSPA tightened to high-confidence only — are computed
repo-side from the raw source dumps and written to
``data/processed/triage_bench/db_optimized_cutoffs.tsv``. They had never
been materialized in D1, so the Worker could not reproduce an optimized
call and the viewer's low-literature badge gated on the native UniProt
flag while every figure beside it used the recalibrated one.

POSITIVE LIST semantics, preserved end to end: an accession absent from
the file is (0, 0), never "fall back to the native flag". A fallback
resurrects the low-confidence CSPA-only proteins the tightening exists to
drop. Because absence means zero, **run this before deploying a Worker
that reads the table** — against an empty table every gene reads 0 and
the badge vanishes site-wide.

Idempotent: INSERT OR REPLACE keyed on accession, so re-running after a
cutoff refresh overwrites in place.

    uv run python scripts/cloud/load_db_optimized_cutoffs_to_d1.py            # dry run
    uv run python scripts/cloud/load_db_optimized_cutoffs_to_d1.py --execute
"""

from __future__ import annotations

import argparse
import csv

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

SRC = REPO_ROOT / "data/processed/triage_bench/db_optimized_cutoffs.tsv"
TABLE = "db_optimized_cutoff_public"

DDL = f"""CREATE TABLE IF NOT EXISTS {TABLE} (
  accession          TEXT PRIMARY KEY,
  uniprot_optimized  INTEGER NOT NULL DEFAULT 0,
  cspa_optimized     INTEGER NOT NULL DEFAULT 0
);"""

# D1 caps a statement at 100 bound parameters; 3 columns -> 33 rows per call.
COLUMNS = 3
BATCH = 100 // COLUMNS


def _flag(v: object) -> int:
    return 1 if str(v).strip() in ("1", "1.0") else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true",
                    help="write to D1 (otherwise dry-run)")
    args = ap.parse_args()
    load_env()

    with SRC.open(newline="", encoding="utf-8") as fh:
        rows = [
            (r["accession"].strip(), _flag(r["uniprot_optimized"]), _flag(r["cspa_optimized"]))
            for r in csv.DictReader(fh, delimiter="\t")
            if (r.get("accession") or "").strip()
        ]
    n_up = sum(1 for _, u, _ in rows if u)
    n_cspa = sum(1 for _, _, c in rows if c)
    print(f"{SRC.relative_to(REPO_ROOT)}: {len(rows):,} accessions "
          f"({n_up:,} uniprot_optimized, {n_cspa:,} cspa_optimized)")
    print(f"batches of {BATCH} -> {(len(rows) + BATCH - 1) // BATCH:,} statements")

    if not args.execute:
        print("\ndry run — nothing written. Re-run with --execute.")
        return 0

    with D1Client.public() as d1:
        d1.query(DDL, [])
        written = 0
        for i in range(0, len(rows), BATCH):
            chunk = rows[i:i + BATCH]
            values = ", ".join("(?, ?, ?)" for _ in chunk)
            params: list[object] = []
            for acc, up, cspa in chunk:
                params += [acc, up, cspa]
            d1.query(
                f"INSERT OR REPLACE INTO {TABLE} "
                f"(accession, uniprot_optimized, cspa_optimized) VALUES {values};",
                params,
            )
            written += len(chunk)
            if written % 1000 < BATCH:
                print(f"  {written:,}/{len(rows):,}")
        total = d1.query(f"SELECT COUNT(*) AS n FROM {TABLE};", [])
        print(f"\nloaded; {TABLE} now holds {total[0]['n']:,} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
