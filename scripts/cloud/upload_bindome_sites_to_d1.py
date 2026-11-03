"""Load the derived Bindome binding sites into public D1.

Mirrors scripts/cloud/sync_surface_bind_to_d1.py: the committed TSV is the
source of truth, the table is a mirror, and the load is idempotent on
(uniprot_acc, site_id).

D1 caps a statement at 100 bound parameters, so with 11 columns the batch is
floor(100/11) = 9 rows per call.

    uv run python scripts/cloud/upload_bindome_sites_to_d1.py            # dry run
    uv run python scripts/cloud/upload_bindome_sites_to_d1.py --execute
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env

TSV = Path(__file__).resolve().parents[2] / "data/external/bindome/bindome_sites.tsv"
COLS = [
    "uniprot_acc",
    "gene_symbol",
    "site_id",
    "anchor_residue",
    "compartment",
    "n_residues",
    "n_designs_supporting",
    "n_designs_total",
    "mean_design_fraction",
    "residues",
    "bindome_release",
]
ROWS_PER_CALL = 100 // len(COLS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--release", default="2026-05-23", help="Bindome data release")
    ap.add_argument("--tsv", default=str(TSV))
    args = ap.parse_args()
    load_env()

    rows = list(csv.DictReader(open(args.tsv), delimiter="\t"))
    for r in rows:
        r["bindome_release"] = args.release
    print(f"{len(rows)} sites from {args.tsv}")
    if not args.execute:
        print("dry run -- pass --execute to write")
        return

    ins = "INSERT OR REPLACE INTO bindome_site_public (" + ",".join(COLS) + ") VALUES "
    with D1Client.public() as d1:
        written = 0
        for i in range(0, len(rows), ROWS_PER_CALL):
            chunk = rows[i : i + ROWS_PER_CALL]
            sql = (
                ins
                + ",".join(["(" + ",".join("?" * len(COLS)) + ")"] * len(chunk))
                + ";"
            )
            params: list[object] = []
            for r in chunk:
                params += [r[c] for c in COLS]
            d1.query(sql, params)
            written += len(chunk)
            if written % 180 == 0:
                print(f"  {written}/{len(rows)}")
        print(f"wrote {written} rows")
        n = d1.query("SELECT COUNT(*) n FROM bindome_site_public;", [])[0]["n"]
        print(f"bindome_site_public now holds {n} rows")


if __name__ == "__main__":
    main()
