"""Fetch the HGNC complete-set TSV (every approved human gene symbol).

HGNC is the authoritative naming registry for human genes; their
"complete set" download is what most downstream pipelines treat as the
official gene catalogue. This script is the second of the pair that
populates ``data/external/<source>/`` — see also
``scripts/fetch_ncbi_human_protein_coding.py``. Both feed
``docs/data-sources/whole-genome-gene-catalogs.md`` and the
``WHOLE_GENOME_N`` constant in the triage bench cost projections.

Source: HGNC publishes the TSV via Google Cloud Storage. The
ebi.ac.uk path that used to host it returns HTTP 404 as of 2026-05;
the working URL is::

    https://storage.googleapis.com/public-download-files/hgnc/tsv/tsv/hgnc_complete_set.txt

Output: ``data/external/hgnc/hgnc_complete_set.tsv`` plus a small
summary JSON with row counts by ``locus_group`` and the fetch
timestamp.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.request
from collections import Counter
from pathlib import Path

URL = "https://storage.googleapis.com/public-download-files/hgnc/tsv/tsv/hgnc_complete_set.txt"
DEFAULT_OUT_DIR = Path("data/external/hgnc")


def fetch(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    tsv_path = out_dir / "hgnc_complete_set.tsv"
    summary_path = out_dir / "hgnc_complete_set.summary.json"

    print(f"fetching {URL} ...")
    with urllib.request.urlopen(URL) as resp, tsv_path.open("wb") as fh:
        fh.write(resp.read())
    print(f"saved {tsv_path}")

    locus_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    n_total = 0
    n_pc_approved = 0
    with tsv_path.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            n_total += 1
            locus_counts[r["locus_group"]] += 1
            status_counts[r["status"]] += 1
            if r["status"] == "Approved" and r["locus_group"] == "protein-coding gene":
                n_pc_approved += 1

    summary = {
        "source_url": URL,
        "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_rows": n_total,
        "approved_protein_coding": n_pc_approved,
        "locus_group_counts": dict(locus_counts.most_common()),
        "status_counts": dict(status_counts.most_common()),
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"summary -> {summary_path}")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = ap.parse_args()
    s = fetch(args.out_dir)
    print()
    print(f"Total HGNC rows:              {s['total_rows']:,}")
    print(f"Approved protein-coding:      {s['approved_protein_coding']:,}")


if __name__ == "__main__":
    main()
