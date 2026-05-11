"""Fetch the canonical NCBI human gene catalog and filter to protein-coding.

Source: ``https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz``
— the authoritative whole-genome enumeration that drives the
``WHOLE_GENOME_N`` constant in ``scripts/triage_subbench_summary.py``.

Writes four artifacts under ``data/external/ncbi_gene_info/``:

* ``Homo_sapiens.gene_info.gz``  raw NCBI dump
* ``Homo_sapiens.protein_coding.tsv``  filtered to protein-coding biotype
  (20,624 rows as of 2026-05), with HGNC / Ensembl / MIM cross-references
  parsed out of the pipe-separated ``dbXrefs`` field
* ``Homo_sapiens.protein_coding.with_hgnc.tsv``  the further-trimmed
  subset that has a non-empty ``hgnc_id`` (19,464 rows). This is the
  canonical whole-genome denominator used by ``WHOLE_GENOME_N``. The
  ~1,160 rows dropped are dominated by ``LOC*`` machine-predicted ORFs,
  readthrough fusions, and ``uncharacterized protein`` placeholders that
  HGNC has not promoted to first-class symbols. See
  ``docs/data-sources/whole-genome-gene-catalogs.md``.
* ``Homo_sapiens.gene_info.summary.json``  biotype counts + fetch
  metadata (source URL, fetch timestamp)

Run again to refresh — NCBI updates the file daily and the protein-coding
count drifts by tens of genes per quarter as gene definitions are revised.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import time
import urllib.request
from collections import Counter
from pathlib import Path

URL = "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz"
DEFAULT_OUT_DIR = Path("data/external/ncbi_gene_info")


def _xref(dbxrefs: str, prefix: str) -> str:
    """Pull a single namespaced cross-reference out of NCBI's pipe-separated
    ``dbXrefs`` column. ``HGNC:HGNC:1234`` keeps the inner ``HGNC:1234`` slug.
    """
    for entry in dbxrefs.split("|"):
        if entry.startswith(prefix):
            return entry.split(":", 1)[1]
    return ""


def fetch_and_filter(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    gz_path = out_dir / "Homo_sapiens.gene_info.gz"
    tsv_path = out_dir / "Homo_sapiens.protein_coding.tsv"
    trimmed_path = out_dir / "Homo_sapiens.protein_coding.with_hgnc.tsv"
    summary_path = out_dir / "Homo_sapiens.gene_info.summary.json"

    print(f"fetching {URL} ...")
    with urllib.request.urlopen(URL) as resp, gz_path.open("wb") as fh:
        fh.write(resp.read())
    print(f"saved {gz_path}")

    biotype_counts: Counter[str] = Counter()
    pc_rows: list[dict[str, str]] = []
    with gzip.open(gz_path, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            biotype_counts[row["type_of_gene"]] += 1
            if row["type_of_gene"] != "protein-coding":
                continue
            pc_rows.append({
                "ncbi_gene_id": row["GeneID"],
                "gene_symbol": row["Symbol"],
                "synonyms": row["Synonyms"],
                "chromosome": row["chromosome"],
                "map_location": row["map_location"],
                "description": row["description"],
                "hgnc_id": _xref(row["dbXrefs"], "HGNC:HGNC:"),
                "ensembl_gene": _xref(row["dbXrefs"], "Ensembl:"),
                "mim": _xref(row["dbXrefs"], "MIM:"),
            })

    fieldnames = list(pc_rows[0].keys())
    with tsv_path.open("w") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(pc_rows)
    print(f"wrote {len(pc_rows):,} protein-coding rows to {tsv_path}")

    pc_with_hgnc = [r for r in pc_rows if r["hgnc_id"]]
    with trimmed_path.open("w") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(pc_with_hgnc)
    print(f"wrote {len(pc_with_hgnc):,} protein-coding-with-HGNC rows to {trimmed_path}")

    summary = {
        "source_url": URL,
        "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_human_gene_records": sum(biotype_counts.values()),
        "biotype_counts": dict(biotype_counts.most_common()),
        "protein_coding_n": len(pc_rows),
        "protein_coding_with_hgnc": len(pc_with_hgnc),
        "protein_coding_with_ensembl": sum(1 for r in pc_rows if r["ensembl_gene"]),
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"summary -> {summary_path}")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = ap.parse_args()
    summary = fetch_and_filter(args.out_dir)
    print()
    print(f"Total NCBI human gene records: {summary['total_human_gene_records']:,}")
    print(f"Protein-coding:                {summary['protein_coding_n']:,}")
    print(f"  with HGNC cross-ref:         {summary['protein_coding_with_hgnc']:,}")
    print(f"  with Ensembl cross-ref:      {summary['protein_coding_with_ensembl']:,}")


if __name__ == "__main__":
    main()
