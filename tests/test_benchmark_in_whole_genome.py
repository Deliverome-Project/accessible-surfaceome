"""Validate that every benchmark gene is present in the trimmed whole-genome list.

The whole-genome denominator used by the subbench cost extrapolation is
``data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv``
(NCBI protein-coding ∩ has-HGNC-xref, 19,464 rows). If a benchmark gene
is *not* in that list, either:

* the symbol in the benchmark TSV is stale (NCBI has renamed it; the
  test surfaces the canonical symbol via the synonym lookup), or
* the gene falls outside the protein-coding catalog entirely (real
  problem — benchmark/scope mismatch).

The test is lenient: it accepts either a primary-symbol or a synonym
match, but it reports any alias drift in the failure message so the
benchmark TSV can be refreshed.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from accessible_surfaceome.agents._eval.benchmark import load_benchmark

WHOLE_GENOME_TSV = (
    Path(__file__).resolve().parents[1]
    / "data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv"
)


@pytest.fixture(scope="module")
def whole_genome_index() -> tuple[set[str], dict[str, str]]:
    """Return (primary_symbols, synonym_to_primary)."""
    if not WHOLE_GENOME_TSV.exists():
        pytest.skip(f"{WHOLE_GENOME_TSV} missing; run fetch_ncbi_human_protein_coding.py")
    primary: set[str] = set()
    syn_to_primary: dict[str, str] = {}
    with WHOLE_GENOME_TSV.open() as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            sym = row["gene_symbol"]
            primary.add(sym)
            for syn in row["synonyms"].split("|"):
                syn = syn.strip()
                if syn and syn != "-":
                    syn_to_primary.setdefault(syn, sym)
    return primary, syn_to_primary


def test_every_benchmark_gene_resolves_to_whole_genome(
    whole_genome_index: tuple[set[str], dict[str, str]],
) -> None:
    primary, syn_to_primary = whole_genome_index
    missing: list[str] = []
    drift: list[str] = []
    for r in load_benchmark():
        sym = r.gene_symbol
        if sym in primary:
            continue
        if sym in syn_to_primary:
            drift.append(f"{sym} -> {syn_to_primary[sym]} (benchmark uses legacy alias)")
            continue
        missing.append(sym)

    # Hard fail only on true absences; drift is reported as a non-fatal
    # message so the benchmark TSV can be refreshed at the next sweep.
    if drift:
        print("\nAlias drift (benchmark symbol -> current NCBI symbol):")
        for line in drift:
            print(f"  {line}")
    assert not missing, (
        f"benchmark genes not present in trimmed whole-genome list: {missing}"
    )
