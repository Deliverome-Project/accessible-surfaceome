import pytest

from accessible_surfaceome.agents.internalization.ids import resolve_hgnc_id


def _write_cohort(tmp_path):
    # Header uses `gene_symbol` to match the real cohort TSV
    # (data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv).
    p = tmp_path / "cohort.tsv"
    p.write_text(
        "gene_symbol\thgnc_id\tother\n"
        "TFRC\tHGNC:11763\tx\n"
        "EGFR\tHGNC:3236\ty\n"
    )
    return p


def test_passthrough_when_already_hgnc_id(tmp_path):
    assert resolve_hgnc_id("HGNC:11763", cohort_tsv=_write_cohort(tmp_path)) == "HGNC:11763"


def test_maps_symbol_case_insensitively(tmp_path):
    cohort = _write_cohort(tmp_path)
    assert resolve_hgnc_id("tfrc", cohort_tsv=cohort) == "HGNC:11763"
    assert resolve_hgnc_id("EGFR", cohort_tsv=cohort) == "HGNC:3236"


def test_unknown_symbol_raises(tmp_path):
    with pytest.raises(LookupError):
        resolve_hgnc_id("NOTAGENE", cohort_tsv=_write_cohort(tmp_path))
