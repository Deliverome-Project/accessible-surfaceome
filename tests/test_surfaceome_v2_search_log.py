"""Tests for the v2 orchestrator's plan-trim-select → SearchEntry translator.

The schema field ``SurfaceomeRecord.search_log`` is provenance: which
tools, with what params, returned how many papers. The v2 orchestrator
used to hardcode this to ``[]`` (silent provenance loss on every gene);
``_build_search_log`` is the fix. These tests pin the contract so a
regression flips them red instead of producing 5,500 records with no
provenance.
"""

from __future__ import annotations

from accessible_surfaceome.agents.plan_trim_select.runner import (
    PlanTrimSelectResult,
    SearchLogEntry,
)
from accessible_surfaceome.agents.surfaceome_v2.orchestrator import (
    _build_search_log,
    _search_log_entry_to_search_entry,
)
from datetime import UTC, datetime


def _dual_with(
    a1_entries: list[SearchLogEntry], a2_entries: list[SearchLogEntry]
):
    """Build the minimal DualPlanTrimSelectResult-shaped object the
    translator needs. The translator only touches ``.a1.search_log`` and
    ``.a2.search_log`` — anything else can be skipped.
    """
    class _StubDual:
        a1 = PlanTrimSelectResult(gene="STUB", bundle=None, plan=None,
                                  selection_response=None,
                                  search_log=a1_entries)
        a2 = PlanTrimSelectResult(gene="STUB", bundle=None, plan=None,
                                  selection_response=None,
                                  search_log=a2_entries)
    return _StubDual()


def test_translator_concatenates_a1_then_a2():
    a1 = [
        SearchLogEntry(
            tool="evidence_retrieval",
            params={"category": "surface_localization", "uniprot_acc": "P12345"},
            intent="seed surface evidence",
            n_drafts=4, n_papers=6, elapsed_s=2.1, error=None,
        ),
    ]
    a2 = [
        SearchLogEntry(
            tool="gene_literature",
            params={"mode": "topic_search"},
            intent="biological context",
            n_drafts=2, n_papers=3, elapsed_s=1.8, error=None,
        ),
    ]
    out = _build_search_log(_dual_with(a1, a2))
    assert [(e.tool, e.query["agent_focus"]) for e in out] == [
        ("evidence_retrieval", "a1"),
        ("gene_literature", "a2"),
    ]


def test_translator_extracts_mode_from_params():
    row = SearchLogEntry(
        tool="gene_literature",
        params={"mode": "gene2pubmed"},
        intent="seed",
        n_drafts=0, n_papers=12, elapsed_s=0.3, error=None,
    )
    entry = _search_log_entry_to_search_entry(row, "a1", datetime.now(UTC))
    assert entry.mode == "gene2pubmed"
    # mode is consumed; the rest of params survives in query
    assert "mode" not in entry.query
    assert entry.query["agent_focus"] == "a1"
    assert entry.query["intent"] == "seed"


def test_translator_synthesizes_mode_for_evidence_retrieval():
    """``evidence_retrieval`` has no explicit ``mode`` param — its
    ``category`` is the closest analog. The translator promotes it so the
    audit query "which categories did we look at" works on the SearchEntry
    shape too.
    """
    row = SearchLogEntry(
        tool="evidence_retrieval",
        params={"category": "shedding", "uniprot_acc": "P12345"},
        intent="shedding lit",
        n_drafts=1, n_papers=2, elapsed_s=0.5, error=None,
    )
    entry = _search_log_entry_to_search_entry(row, "a2", datetime.now(UTC))
    assert entry.mode == "shedding"
    # category survives in query because it's the canonical key for this tool
    assert entry.query["category"] == "shedding"


def test_translator_preserves_error_signal():
    row = SearchLogEntry(
        tool="gene_literature",
        params={"mode": "fetch_abstract", "pmid": "12345"},
        intent="abstract follow-up",
        n_drafts=0, n_papers=0, elapsed_s=5.0,
        error="HTTPError: 503 Service Unavailable",
    )
    entry = _search_log_entry_to_search_entry(row, "a1", datetime.now(UTC))
    assert entry.query["error"].startswith("HTTPError")
    assert entry.n_results == 0


def test_translator_maps_n_papers_to_n_results():
    row = SearchLogEntry(
        tool="gene_literature",
        params={"mode": "topic_search"},
        intent="x",
        n_drafts=99, n_papers=7, elapsed_s=0.0, error=None,
    )
    entry = _search_log_entry_to_search_entry(row, "a1", datetime.now(UTC))
    assert entry.n_results == 7  # n_papers, not n_drafts


def test_translator_handles_empty_logs():
    out = _build_search_log(_dual_with([], []))
    assert out == []
