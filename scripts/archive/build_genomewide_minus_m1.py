"""Build the "genome-wide minus M1" candidate list for genome-scale triage.

M1 is the candidate-universe of proteins already flagged surface by at
least one of the 5 surface databases (UniProt subcellular, GO CC, HPA,
SURFY, CSPA — see ``data/processed/candidate_universe/candidate_universe.tsv``).
Those proteins are already covered by classical methods; the triage agent's
job for the genome-wide sweep is to find what M1 *missed*.

This script:

1. Loads the NCBI-protein-coding-∩-HGNC catalog at
   ``data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv``
   (19,464 rows — the agreed `WHOLE_GENOME_N` per
   ``docs/data-sources/whole-genome-gene-catalogs.md``).
2. Loads M1 from ``data/processed/candidate_universe/candidate_universe.tsv``.
3. Subtracts M1 from the catalog by HGNC ID (primary) with a
   gene-symbol fallback for the rare row that lacks HGNC xref.
4. Writes the residual to
   ``data/processed/whole_genome_minus_m1.tsv`` with one row per gene.

The output schema matches the triage runner's input expectation
(``gene_symbol`` + ``uniprot_acc`` if known; the resolver fills the rest
at runtime).
"""

from __future__ import annotations

import csv
from pathlib import Path

from accessible_surfaceome.paths import REPO_ROOT

CATALOG_TSV = REPO_ROOT / "data" / "external" / "ncbi_gene_info" / "Homo_sapiens.protein_coding.with_hgnc.tsv"
M1_TSV = REPO_ROOT / "data" / "processed" / "candidate_universe" / "candidate_universe.tsv"
OUT_TSV = REPO_ROOT / "data" / "processed" / "whole_genome_minus_m1.tsv"


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


def main() -> int:
    catalog = _read_tsv(CATALOG_TSV)
    m1 = _read_tsv(M1_TSV)

    m1_hgnc_ids = {r["hgnc_id"].strip() for r in m1 if r.get("hgnc_id")}
    m1_symbols = {r["gene_symbol"].strip() for r in m1 if r.get("gene_symbol")}

    kept: list[dict[str, str]] = []
    skipped_in_m1 = 0
    for row in catalog:
        hgnc_id = (row.get("hgnc_id") or "").strip()
        symbol = (row.get("gene_symbol") or "").strip()
        # Two-key join: HGNC ID is canonical; symbol is the fallback.
        if (hgnc_id and hgnc_id in m1_hgnc_ids) or (symbol and symbol in m1_symbols):
            skipped_in_m1 += 1
            continue
        kept.append({
            "gene_symbol": symbol,
            "hgnc_id": hgnc_id,
            "ncbi_gene_id": row.get("ncbi_gene_id", ""),
            "ensembl_gene": row.get("ensembl_gene", ""),
            "description": (row.get("description") or "").strip(),
        })

    OUT_TSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["gene_symbol", "hgnc_id", "ncbi_gene_id", "ensembl_gene", "description"]
    with OUT_TSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for r in sorted(kept, key=lambda x: x["gene_symbol"]):
            w.writerow(r)

    print(f"Catalog (NCBI PC ∩ HGNC):        {len(catalog):>6}")
    print(f"M1 (≥1 surface DB):              {len(m1):>6}  ({len(m1_hgnc_ids)} unique HGNC IDs)")
    print(f"Subtracted (in M1):              {skipped_in_m1:>6}")
    print(f"Kept (genome-wide − M1):         {len(kept):>6}")
    print(f"Wrote {OUT_TSV.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
