"""Unit tests for the deterministic UniProt family extractor.

UniProt records curator-assigned family membership as a free-text
SIMILARITY comment ("Belongs to the <family> family."). We surface that
as a deterministic family tag alongside the LLM's high-level functional
class. These tests are pure (no live API) — they exercise the parse +
normalization on hand-built entry dicts shaped like the UniProtKB JSON.
"""
from __future__ import annotations

from accessible_surfaceome.tools.gene_lookup import _uniprot_family


def _entry_with_similarity(value: str) -> dict:
    """Minimal UniProtKB entry carrying a single SIMILARITY comment."""
    return {
        "comments": [
            {"commentType": "FUNCTION", "texts": [{"value": "Some function."}]},
            {"commentType": "SIMILARITY", "texts": [{"value": value}]},
        ]
    }


def test_extracts_and_strips_boilerplate_gpcr():
    # GPR75 O95800's real SIMILARITY text.
    entry = _entry_with_similarity("Belongs to the G-protein coupled receptor 1 family")
    assert _uniprot_family(entry) == "G-protein coupled receptor 1 family"


def test_strips_trailing_period():
    entry = _entry_with_similarity("Belongs to the peptidase S1 family.")
    assert _uniprot_family(entry) == "peptidase S1 family"


def test_preserves_subfamily_detail():
    entry = _entry_with_similarity(
        "Belongs to the G-protein coupled receptor 1 family. Adenosine receptor subfamily."
    )
    assert (
        _uniprot_family(entry)
        == "G-protein coupled receptor 1 family. Adenosine receptor subfamily"
    )


def test_returns_none_when_no_similarity_comment():
    entry = {"comments": [{"commentType": "FUNCTION", "texts": [{"value": "x"}]}]}
    assert _uniprot_family(entry) is None


def test_returns_none_when_no_comments():
    assert _uniprot_family({}) is None


def test_passes_through_text_without_boilerplate():
    # Defensive: if UniProt ever omits the "Belongs to the" prefix, keep the text.
    entry = _entry_with_similarity("Tetraspanin (TM4SF) family")
    assert _uniprot_family(entry) == "Tetraspanin (TM4SF) family"
