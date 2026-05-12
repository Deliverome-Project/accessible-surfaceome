"""Build the 'triageable' input TSV — the canonical NCBI catalog minus
the gene symbols that produce unrecoverable null verdicts.

The 2026-05-12 Sonnet/ncbi sweep over 19,464 NCBI protein-coding ∩ HGNC
genes converged with 139 stable nulls. Every remaining null is a
structural catalog artifact where no UniProt protein entry exists:

  - readthrough / deletion-hybrid transcripts (~83): NCBI catalogs the
    fused transcript but UniProt annotates the individual genes only.
  - antisense / divergent RNAs (~13): non-coding annotations.
  - pseudogenes (~16): no protein product.
  - Ig loci (~5): IGH/IGK/IGL/TRD/TRG — collective locus symbols, not
    individual genes.
  - HGNC entries without UniProt cross-reference (~21): registry-level
    catalogue entries that haven't been deposited into UniProt.

These cells are not triageable in principle — there's no protein to
classify. Subtract them from the catalog to get the canonical input
size for cost projections + future sweeps.

Output: data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.triageable.tsv
        (~19,325 rows; ~$203 / Sonnet-ncbi sweep at $0.0105/call)

The null-symbol list is pulled live from D1 — re-run after any future
genome-wide sweep refresh to pick up resolver / runner improvements.
"""
from __future__ import annotations

import csv

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

load_env()

CATALOG_IN = REPO_ROOT / "data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv"
CATALOG_OUT = REPO_ROOT / "data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.triageable.tsv"
SONNET_RUN_ID = "genome_full_sonnet_ncbi_v1"

# Per-call mean cost for Sonnet/ncbi on the slim canonical prompt,
# observed across the 19,464-cell 2026-05-12 sweep. Update when the
# pricing or prompt changes substantially.
MEAN_COST_PER_CALL = 0.0105

# Catalog → canonical (HGNC/UniProt) symbol renames discovered during the
# 2026-05-12 sweep. The NCBI catalog ships some legacy symbols that the
# resolver canonicalises at runtime, so the row that survives the sweep
# lands in D1 under the canonical name. Re-emit the canonical name in the
# triageable input so future re-runs key against the same identifier the
# verdict was written under.
#
# COX3 (NCBI gene_id 4514) → MT-CO3 (HGNC:7422); mitochondrial cytochrome
# c oxidase subunit III. Resolver path: gene_lookup canonicalises via the
# HGNC ``mt-`` prefix convention.
CATALOG_TO_CANONICAL_RENAMES = {
    "COX3": "MT-CO3",
}


def main() -> int:
    with D1Client() as d1:
        null_rows = d1.query(
            "SELECT gene_symbol FROM triage_run "
            "WHERE run_id = ? "
            "  AND predicted_verdict IS NULL "
            "  AND api_stop_reason IS NULL;",  # exclude refusals (handled via naive fallback)
            [SONNET_RUN_ID],
        )
    unrecoverable = {r["gene_symbol"] for r in null_rows}

    kept = 0
    dropped = 0
    renamed = 0
    with CATALOG_IN.open() as fin, CATALOG_OUT.open("w", newline="") as fout:
        reader = csv.DictReader(fin, delimiter="\t")
        writer = csv.DictWriter(
            fout, fieldnames=reader.fieldnames or [],
            delimiter="\t", quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()
        for r in reader:
            if r["gene_symbol"] in unrecoverable:
                dropped += 1
                continue
            canonical = CATALOG_TO_CANONICAL_RENAMES.get(r["gene_symbol"])
            if canonical is not None:
                r["gene_symbol"] = canonical
                renamed += 1
            writer.writerow(r)
            kept += 1

    print(f"  input  : {kept + dropped:>6,} rows  ({CATALOG_IN.name})")
    print(f"  output : {kept:>6,} rows  ({CATALOG_OUT.name})")
    print(f"  dropped: {dropped:>6,}  (catalog-artifact symbols, pulled from D1)")
    print(f"  renamed: {renamed:>6,}  (catalog → canonical HGNC symbol)")
    print()
    print(f"Expected Sonnet/ncbi sweep cost: "
          f"{kept:,} × ${MEAN_COST_PER_CALL} = ${kept * MEAN_COST_PER_CALL:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
