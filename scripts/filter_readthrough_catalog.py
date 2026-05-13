"""Filter readthrough / deletion-hybrid rows out of the NCBI catalog.

The upstream ``Homo_sapiens.protein_coding.with_hgnc.tsv`` (19,464 rows)
includes NCBI catalog entries for read-through transcripts and
deletion hybrids (e.g. ``ABCF2-H2BK1``, ``APOBEC3A_B``). These don't
correspond to single canonical proteins and have no separate UniProt
entry — they're genome-annotation artifacts that fail the resolver
during a sweep.

This script reads the canonical catalog and writes a cleaned version
to ``data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.cleaned.tsv``
with those rows removed. The 2026-05-12 sweep observed 83 of 89
catalog rows matching this filter trigger resolver failures; the
remaining 6 happen to have UniProt entries and would resolve, but
sweeping them adds no value (they re-trigger the readthrough
ambiguity at downstream-analysis time).

Forward-only change. Existing D1 records reference the unfiltered
catalog's content SHA — they're unaffected.
"""

from __future__ import annotations

import csv

from accessible_surfaceome.paths import REPO_ROOT

INPUT = REPO_ROOT / "data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv"
OUTPUT = REPO_ROOT / "data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.cleaned.tsv"

# Filter triggers — NCBI's description phrases for non-canonical entries.
DROP_PHRASES = ("readthrough", "deletion hybrid")


def is_dropable(row: dict) -> bool:
    desc = (row.get("description") or "").lower()
    return any(phrase in desc for phrase in DROP_PHRASES)


def main() -> int:
    kept: list[dict] = []
    dropped: list[dict] = []
    with INPUT.open() as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        fieldnames = list(reader.fieldnames or [])
        for r in reader:
            (dropped if is_dropable(r) else kept).append(r)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for r in kept:
            w.writerow(r)

    print(f"input:   {INPUT.relative_to(REPO_ROOT)}  ({len(kept) + len(dropped):,} rows)")
    print(f"output:  {OUTPUT.relative_to(REPO_ROOT)}  ({len(kept):,} rows)")
    print(f"dropped: {len(dropped)}  (readthrough / deletion-hybrid)")
    print("\nSample of dropped rows:")
    for r in dropped[:5]:
        print(f"  {r['gene_symbol']:<25s} {r.get('description', '')[:60]}")
    if len(dropped) > 5:
        print(f"  ... + {len(dropped) - 5} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
