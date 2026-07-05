"""Guard: candidate_universe_v3 must not admit dangling/withdrawn HGNC rows.

A withdrawn (or symbol-reassigned) HGNC id resolves to no live record, so the
``gene_identifier_public`` join leaves every stable identifier empty
(uniprot_acc / ensembl_gene / ncbi_gene_id all blank) while still carrying the
hgnc_id. Such a row is a data-integrity hole: it silently misroutes any
downstream symbol-keyed lookup (the WAS -> MT-RNR1 reassignment-drift class the
resolver exists to avoid). The build script drops these before writing v3.

This is a *data-integrity* guard (did the gene resolve to anything?), not a
biology guard — a row that resolved to even one stable id is kept; whether to
additionally drop a resolved-but-inner-leaflet gene is a separate policy call.

Pure-function test: imports the script the way the repo's other script tests do
(sys.path), so it must not trigger the module's D1 query at import time.
"""
from __future__ import annotations

import sys
from pathlib import Path

# scripts/ isn't a package on PYTHONPATH; put it on sys.path so we import the
# build script the same way it's invoked (python scripts/build_candidate_universe_v3.py).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_candidate_universe_v3 as m  # noqa: E402  # ty: ignore[unresolved-import]


def test_resolves_predicate_true_when_any_stable_id_present():
    # All three present.
    assert m._resolves_to_stable_ids(
        {"uniprot_acc": "P12345", "ensembl_gene": "ENSG0", "ncbi_gene_id": "1"}
    )
    # Any single one present still counts as resolved.
    assert m._resolves_to_stable_ids({"uniprot_acc": "Q92681", "ensembl_gene": "", "ncbi_gene_id": ""})
    assert m._resolves_to_stable_ids({"uniprot_acc": "", "ensembl_gene": "ENSG1", "ncbi_gene_id": ""})
    assert m._resolves_to_stable_ids({"uniprot_acc": "", "ensembl_gene": "", "ncbi_gene_id": "42"})


def test_resolves_predicate_false_when_all_empty_or_whitespace():
    assert not m._resolves_to_stable_ids({"uniprot_acc": "", "ensembl_gene": "", "ncbi_gene_id": ""})
    # Whitespace-only fields are empty.
    assert not m._resolves_to_stable_ids(
        {"uniprot_acc": "   ", "ensembl_gene": "\t", "ncbi_gene_id": " "}
    )
    # Missing keys entirely are empty.
    assert not m._resolves_to_stable_ids({})


def test_partition_unresolved_drops_only_all_empty_rows():
    rows = [
        {"gene_symbol": "GOODA", "uniprot_acc": "P12345", "ensembl_gene": "ENSG1", "ncbi_gene_id": "1"},
        {"gene_symbol": "DANGLE", "uniprot_acc": "", "ensembl_gene": "", "ncbi_gene_id": ""},
        {"gene_symbol": "ENSONLY", "uniprot_acc": "", "ensembl_gene": "ENSG2", "ncbi_gene_id": ""},
        {"gene_symbol": "NCBIONLY", "uniprot_acc": "", "ensembl_gene": "", "ncbi_gene_id": "42"},
        {"gene_symbol": "WS", "uniprot_acc": "  ", "ensembl_gene": " ", "ncbi_gene_id": "\t"},
    ]
    resolved, dropped = m.partition_unresolved(rows)
    assert [r["gene_symbol"] for r in dropped] == ["DANGLE", "WS"]
    assert [r["gene_symbol"] for r in resolved] == ["GOODA", "ENSONLY", "NCBIONLY"]


def test_partition_unresolved_empty_input():
    resolved, dropped = m.partition_unresolved([])
    assert resolved == []
    assert dropped == []
