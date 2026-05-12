"""Tests for the v0.4.0 deep-dive pack loader (Compara identity-only).

The pack used to join DeepTMHMM cohorts; in the v0.4.0 refocus we
dropped DeepTMHMM as a separate signal and the pack is now an
identity-only Ensembl Compara reader (D1 in production, CSV
fallback). These tests exercise the CSV-fallback path with on-disk
fixtures — D1 is mocked out for the test suite.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from accessible_surfaceome.agents.surface_annotator import deep_dive_pack as ddp_module
from accessible_surfaceome.agents.surface_annotator.deep_dive_pack import (
    DeepDivePack,
    DeepDivePackLoader,
    OrthologIdentity,
    render_markdown,
)


COMPARA_COLS = [
    "human_ensembl_gene",
    "human_uniprot_acc",
    "human_gene_symbol",
    "species",
    "ortholog_ensembl_gene",
    "ortholog_uniprot_acc",
    "ortholog_gene_symbol",
    "orthology_type",
    "percent_identity",
    "is_high_confidence",
]


@pytest.fixture
def compara_csv(tmp_path: Path) -> Path:
    """Write a tiny Compara CSV fixture covering ERBB2 (mouse + cyno)."""
    csv_path = tmp_path / "compara.csv"
    rows = [
        {
            "human_ensembl_gene": "ENSG00000141736",
            "human_uniprot_acc": "P04626",
            "human_gene_symbol": "ERBB2",
            "species": "mouse",
            "ortholog_ensembl_gene": "ENSMUSG00000062312",
            "ortholog_uniprot_acc": "P70424",
            "ortholog_gene_symbol": "Erbb2",
            "orthology_type": "one_to_one",
            "percent_identity": "94.5",
            "is_high_confidence": "1",
        },
        {
            "human_ensembl_gene": "ENSG00000141736",
            "human_uniprot_acc": "P04626",
            "human_gene_symbol": "ERBB2",
            "species": "cynomolgus",
            "ortholog_ensembl_gene": "ENSMFAG00000040123",
            "ortholog_uniprot_acc": "",
            "ortholog_gene_symbol": "ERBB2",
            "orthology_type": "one_to_one",
            "percent_identity": "98.1",
            "is_high_confidence": "1",
        },
    ]
    with csv_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COMPARA_COLS)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    return csv_path


def _disable_d1(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the loader to skip the D1 path by stubbing _from_d1."""
    monkeypatch.setattr(
        ddp_module,
        "_from_d1",
        lambda *, hgnc_symbol, uniprot_acc: (None, None, None),
    )


def test_for_gene_returns_mouse_and_cyno_orthologs_from_csv(
    compara_csv: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _disable_d1(monkeypatch)
    monkeypatch.setattr(ddp_module, "COMPARA_QUERY_CSV", compara_csv)

    loader = DeepDivePackLoader()
    pack = loader.for_gene(hgnc_symbol="ERBB2", uniprot_acc="P04626")

    assert pack.source == "csv"
    assert pack.mouse_ortholog is not None
    assert pack.mouse_ortholog.ortholog_uniprot_acc == "P70424"
    assert pack.mouse_ortholog.orthology_type == "one_to_one"
    assert pack.mouse_ortholog.percent_identity == pytest.approx(94.5)
    assert pack.mouse_ortholog.is_high_confidence is True

    assert pack.cyno_ortholog is not None
    assert pack.cyno_ortholog.ortholog_uniprot_acc is None  # blank in fixture
    assert pack.cyno_ortholog.percent_identity == pytest.approx(98.1)


def test_for_gene_returns_empty_pack_when_no_match(
    compara_csv: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _disable_d1(monkeypatch)
    monkeypatch.setattr(ddp_module, "COMPARA_QUERY_CSV", compara_csv)

    pack = DeepDivePackLoader().for_gene(hgnc_symbol="NOT_A_GENE")
    assert pack.mouse_ortholog is None
    assert pack.cyno_ortholog is None
    assert pack.source == "unknown"


def test_for_gene_returns_empty_pack_when_csv_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _disable_d1(monkeypatch)
    monkeypatch.setattr(ddp_module, "COMPARA_QUERY_CSV", tmp_path / "missing.csv")
    pack = DeepDivePackLoader().for_gene(hgnc_symbol="ERBB2")
    assert pack.mouse_ortholog is None and pack.cyno_ortholog is None


def test_render_markdown_lists_orthologs() -> None:
    pack = DeepDivePack(
        hgnc_symbol="ERBB2",
        uniprot_acc="P04626",
        mouse_ortholog=OrthologIdentity(
            species="mouse",
            ortholog_uniprot_acc="P70424",
            ortholog_gene_symbol="Erbb2",
            ortholog_ensembl_gene_id="ENSMUSG00000062312",
            orthology_type="one_to_one",
            percent_identity=94.5,
            is_high_confidence=True,
        ),
        cyno_ortholog=None,
        release_version="ensembl_compara_2026_05_11",
        source="csv",
    )
    md = render_markdown(pack)
    assert "Mouse ortholog" in md
    assert "P70424" in md
    assert "94.50%" in md
    assert "ensembl_compara_2026_05_11" in md


def test_render_markdown_renders_empty_placeholder() -> None:
    pack = DeepDivePack(hgnc_symbol="UNKNOWN", uniprot_acc=None)
    md = render_markdown(pack)
    assert "No Ensembl Compara" in md
    assert "Emit `orthology` as an empty list" in md
