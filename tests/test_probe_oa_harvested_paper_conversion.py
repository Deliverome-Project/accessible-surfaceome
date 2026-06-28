"""Tests for the probe → HarvestedPaper conversion helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

# scripts/probes/probe_oa_buckets.py isn't on a package path — load it as a
# module by path so we can exercise the helpers without invoking main().
_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "probes" / "probe_oa_buckets.py"
_spec = importlib.util.spec_from_file_location("_probe", _SCRIPT)
assert _spec is not None and _spec.loader is not None
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)


def test_paper_id_prefers_pmc_then_pmid_then_doi() -> None:
    """Canonical source key: PMC > PMID > DOI > None — must mirror
    ``paper_source_id`` in abstract_triage so D1 joins line up."""
    assert _probe._paper_id_from_row(
        {"pmc_id": "PMC123", "pmid": 7, "doi": "10.1/x"}
    ) == "PMC:PMC123"
    assert _probe._paper_id_from_row(
        {"pmc_id": None, "pmid": 7, "doi": "10.1/x"}
    ) == "PMID:7"
    assert _probe._paper_id_from_row(
        {"pmc_id": None, "pmid": 0, "doi": "10.48550/arxiv.2510.17752"}
    ) == "DOI:10.48550/arxiv.2510.17752"
    assert _probe._paper_id_from_row(
        {"pmc_id": None, "pmid": 0, "doi": None}
    ) is None


def test_harvested_papers_from_gene_row_threads_all_fields() -> None:
    gene_row = {
        "gene": "CD20",
        "papers": [
            {
                "pmid": 12345, "pmc_id": "PMC9999", "doi": "10.1101/2026.01.01",
                "year": 2026, "title": "CD20 surface biology", "bucket": "pmc",
            },
            {
                "pmid": 0, "pmc_id": None, "doi": "10.48550/arxiv.2510.17752",
                "year": 2025, "title": None, "bucket": "datacite_oa_repo",
            },
            # No ids → dropped from output.
            {"pmid": 0, "pmc_id": None, "doi": None, "year": 2024, "bucket": "no_oa"},
        ],
    }
    out = _probe._harvested_papers_from_gene_row(
        gene_row, run_id="probe_test", source="probe_production",
    )
    assert len(out) == 2  # id-less row dropped
    assert out[0].gene_symbol == "CD20"
    assert out[0].paper_id == "PMC:PMC9999"
    assert out[0].source == "probe_production"
    assert out[0].run_id == "probe_test"
    assert out[0].bucket == "pmc"
    assert out[0].doi == "10.1101/2026.01.01"
    assert out[1].paper_id == "DOI:10.48550/arxiv.2510.17752"
    assert out[1].bucket == "datacite_oa_repo"
    assert out[1].title is None


def test_harvested_papers_from_empty_gene_row() -> None:
    out = _probe._harvested_papers_from_gene_row(
        {"gene": "X", "papers": []}, run_id="r", source="s",
    )
    assert out == []
