"""Historical repair must change only malformed URLs and be idempotent."""

import importlib.util
from pathlib import Path

import pytest

_path = Path(__file__).resolve().parents[1] / "scripts/repair_internalization_citation_urls.py"
_spec = importlib.util.spec_from_file_location("repair_citations", _path)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def test_repair_preserves_evidence_and_grade():
    source = {"source_id": "DOI:10.1234/paper", "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/None/"}
    record = {"literature": {"overall_grade": "moderate", "sources": [{
        "claim": "Measured uptake", "spans": [{"quote": "Exact quote", "source": source}],
    }]}}
    assert _mod.repair_record(record) == 1
    assert source["url"] == "https://doi.org/10.1234/paper"
    assert record["literature"]["overall_grade"] == "moderate"
    assert record["literature"]["sources"][0]["spans"][0]["quote"] == "Exact quote"
    assert _mod.repair_record(record) == 0


def test_repair_refuses_to_guess_a_source():
    record = {"literature": {"sources": [{"spans": [{"source": {
        "source_id": "unknown", "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/None/",
    }}]}]}}
    with pytest.raises(ValueError, match="without a DOI"):
        _mod.repair_record(record)
