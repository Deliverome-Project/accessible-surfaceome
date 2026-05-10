"""Tests for the surface-annotator deep-dive pack loader + markdown renderer."""

from __future__ import annotations

from pathlib import Path

import pytest

from accessible_surfaceome.agents.surface_annotator.deep_dive_pack import (
    DeepDivePackLoader,
    render_markdown,
)


# Column orders kept aligned with the real precompute schemas so the loader
# parses fixtures the same way it parses live data.
_ISOFORM_COLS = [
    "uniprot_accession",
    "uniprot_accession_full",
    "uniprot_entry_name",
    "deeptmhmm_label",
    "protein_length",
    "tm_helix_count",
    "beta_strand_count",
    "has_signal_peptide",
    "signal_peptide_length",
    "n_term_side",
    "c_term_side",
    "n_term_extracellular",
    "c_term_extracellular",
    "n_term_intracellular",
    "c_term_intracellular",
    "predicted_surface_membrane",
    "predicted_secreted",
]

_METADATA_COLS = [
    "cohort",
    "error",
    "n_candidates",
    "query_ensembl_gene_id",
    "query_input_gene_symbols",
    "search_url",
    "selected_length",
    "selected_reviewed",
    "selected_uniprot_accession",
    "selected_uniprot_entry_name",
    "sequence_length",
    "source_url",
    "species",
    "status",
    "target_ensembl_gene_id",
    "target_gene_symbol",
    "taxid",
]

_COMPARA_COLS = [
    "query_ensembl_gene_id",
    "query_input_gene_symbols",
    "n_input_genes_for_query_id",
    "n_biomart_rows_for_query_id",
    "mouse_has_one2one_high_confidence",
    "mouse_target_ensembl_gene_id",
    "mouse_target_gene_symbol",
    "mouse_target_percent_identity",
    "mouse_orthology_type",
    "mouse_orthology_confidence",
    "cyno_has_one2one_high_confidence",
    "cyno_target_ensembl_gene_id",
    "cyno_target_gene_symbol",
    "cyno_target_percent_identity",
    "cyno_orthology_type",
    "cyno_orthology_confidence",
    "has_one_or_both_species_pass",
    "has_both_species_pass",
]

_CANDIDATE_UNIVERSE_COLS = [
    "uniprot_accession",
    "gene_symbol_input",
    "gene_symbol",
    "gene_symbol_mapping_status",
    "gene_symbol_resolved",
]


def _write_tsv(path: Path, columns: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["\t".join(columns)]
    lines.extend("\t".join(row) for row in rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_csv(path: Path, columns: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [",".join(columns)]
    lines.extend(",".join(row) for row in rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def fixture_paths(tmp_path: Path) -> dict[str, Path]:
    iso_tsv = tmp_path / "iso.tsv"
    mouse_tsv = tmp_path / "mouse.tsv"
    cyno_tsv = tmp_path / "cyno.tsv"
    mouse_meta = tmp_path / "mouse_meta.csv"
    cyno_meta = tmp_path / "cyno_meta.csv"
    compara = tmp_path / "compara.csv"
    universe = tmp_path / "universe.tsv"

    # ERBB2 has two isoforms with different topology (canonical TM, alt GLOB).
    _write_tsv(
        iso_tsv,
        _ISOFORM_COLS,
        [
            [
                "P04626", "P04626-1", "ERBB2_HUMAN", "TM", "1255", "1", "0",
                "1", "22", "O", "I", "1", "0", "0", "1", "1", "0",
            ],
            [
                "P04626", "P04626-2", "ERBB2_HUMAN", "GLOB", "979", "0", "0",
                "0", "0", "", "", "0", "0", "0", "0", "0", "0",
            ],
            [
                "Q01234", "Q01234-1", "OTHER_HUMAN", "TM", "300", "1", "0",
                "0", "0", "O", "I", "1", "0", "0", "1", "1", "0",
            ],
        ],
    )

    _write_tsv(
        mouse_tsv,
        _ISOFORM_COLS,
        [
            [
                "P70424", "P70424", "ERBB2_MOUSE", "TM", "1256", "1", "0",
                "1", "22", "O", "I", "1", "0", "0", "1", "1", "0",
            ],
        ],
    )

    _write_tsv(
        cyno_tsv,
        _ISOFORM_COLS,
        [],
    )

    _write_csv(
        mouse_meta,
        _METADATA_COLS,
        [
            [
                "mouse_ortholog_one2one_highconf_non_hla", "", "1",
                "ENSG00000141736", "ERBB2", "", "1256", "reviewed",
                "P70424", "ERBB2_MOUSE", "1256", "", "mouse", "ok",
                "ENSMUSG00000062312", "Erbb2", "10090",
            ],
        ],
    )

    _write_csv(
        cyno_meta,
        _METADATA_COLS,
        [],
    )

    _write_csv(
        compara,
        _COMPARA_COLS,
        [
            [
                "ENSG00000141736", "ERBB2", "1", "1",
                "1", "ENSMUSG00000062312", "Erbb2", "94.5",
                "ortholog_one2one", "1",
                "0", "", "", "",
                "", "",
                "1", "0",
            ],
        ],
    )

    _write_tsv(
        universe,
        _CANDIDATE_UNIVERSE_COLS,
        [
            ["P04626", "ERBB2", "ERBB2", "exact", "ERBB2"],
        ],
    )

    return {
        "isoform_tsv": iso_tsv,
        "mouse_ortholog_tsv": mouse_tsv,
        "cyno_ortholog_tsv": cyno_tsv,
        "mouse_metadata_csv": mouse_meta,
        "cyno_metadata_csv": cyno_meta,
        "compara_query_csv": compara,
        "candidate_universe_tsv": universe,
    }


def test_for_gene_returns_isoforms_and_mouse_ortholog(fixture_paths: dict[str, Path]) -> None:
    loader = DeepDivePackLoader(**fixture_paths)

    pack = loader.for_gene(hgnc_symbol="ERBB2", uniprot_acc="P04626")

    assert pack.hgnc_symbol == "ERBB2"
    assert pack.uniprot_acc == "P04626"
    assert [iso.isoform_id for iso in pack.isoforms] == ["P04626-1", "P04626-2"]
    assert pack.isoforms[0].deeptmhmm_label == "TM"
    assert pack.isoforms[0].predicted_surface_membrane is True
    assert pack.isoforms[1].deeptmhmm_label == "GLOB"
    assert pack.isoforms[1].predicted_surface_membrane is False

    assert pack.mouse_ortholog is not None
    assert pack.mouse_ortholog.ortholog_uniprot_acc == "P70424"
    assert pack.mouse_ortholog.ortholog_gene_symbol == "Erbb2"
    assert pack.mouse_ortholog.ortholog_ensembl_gene_id == "ENSMUSG00000062312"
    assert pack.mouse_ortholog.percent_identity == pytest.approx(94.5)
    assert pack.mouse_ortholog.deeptmhmm_label == "TM"

    assert pack.cyno_ortholog is None


def test_for_gene_resolves_uniprot_from_symbol(fixture_paths: dict[str, Path]) -> None:
    loader = DeepDivePackLoader(**fixture_paths)

    pack = loader.for_gene(hgnc_symbol="ERBB2")

    assert pack.uniprot_acc == "P04626"
    assert len(pack.isoforms) == 2


def test_render_markdown_includes_isoform_table(fixture_paths: dict[str, Path]) -> None:
    loader = DeepDivePackLoader(**fixture_paths)
    pack = loader.for_gene(hgnc_symbol="ERBB2", uniprot_acc="P04626")

    rendered = render_markdown(pack)

    assert "## Pre-loaded deep-dive context" in rendered
    assert "### Human isoform topology (DeepTMHMM)" in rendered
    assert "P04626-1" in rendered
    assert "P04626-2" in rendered
    assert "### Mouse ortholog" in rendered
    assert "P70424" in rendered
    assert "94.5%" in rendered
    assert "No one-to-one high-confidence ortholog" in rendered  # cyno empty


def test_render_markdown_empty_pack_explains_absence(tmp_path: Path) -> None:
    iso_tsv = tmp_path / "iso.tsv"
    mouse_tsv = tmp_path / "mouse.tsv"
    cyno_tsv = tmp_path / "cyno.tsv"
    mouse_meta = tmp_path / "mouse_meta.csv"
    cyno_meta = tmp_path / "cyno_meta.csv"
    compara = tmp_path / "compara.csv"
    universe = tmp_path / "universe.tsv"
    for path in (iso_tsv, mouse_tsv, cyno_tsv):
        _write_tsv(path, _ISOFORM_COLS, [])
    for path in (mouse_meta, cyno_meta):
        _write_csv(path, _METADATA_COLS, [])
    _write_csv(compara, _COMPARA_COLS, [])
    _write_tsv(universe, _CANDIDATE_UNIVERSE_COLS, [])

    loader = DeepDivePackLoader(
        isoform_tsv=iso_tsv,
        mouse_ortholog_tsv=mouse_tsv,
        cyno_ortholog_tsv=cyno_tsv,
        mouse_metadata_csv=mouse_meta,
        cyno_metadata_csv=cyno_meta,
        compara_query_csv=compara,
        candidate_universe_tsv=universe,
    )
    pack = loader.for_gene(hgnc_symbol="MISSING", uniprot_acc="Q99999")

    rendered = render_markdown(pack)

    assert "No precomputed isoform or ortholog topology data was available" in rendered
    assert "MISSING" in rendered


def test_loader_handles_missing_files(tmp_path: Path) -> None:
    # All paths point at non-existent files. The loader should not raise; per-gene
    # queries return empty packs.
    loader = DeepDivePackLoader(
        isoform_tsv=tmp_path / "missing_iso.tsv",
        mouse_ortholog_tsv=tmp_path / "missing_mouse.tsv",
        cyno_ortholog_tsv=tmp_path / "missing_cyno.tsv",
        mouse_metadata_csv=tmp_path / "missing_mouse_meta.csv",
        cyno_metadata_csv=tmp_path / "missing_cyno_meta.csv",
        compara_query_csv=tmp_path / "missing_compara.csv",
        candidate_universe_tsv=tmp_path / "missing_universe.tsv",
    )
    pack = loader.for_gene(hgnc_symbol="ERBB2", uniprot_acc="P04626")

    assert pack.isoforms == []
    assert pack.mouse_ortholog is None
    assert pack.cyno_ortholog is None
