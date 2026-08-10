from collections import defaultdict
from types import SimpleNamespace
from typing import Any, cast

from accessible_surfaceome.agents.internalization import literature_pool as mod
from accessible_surfaceome.agents.internalization.literature_pool import (
    _add_to_pool,
    build_source_store,
)
from accessible_surfaceome.tools._shared.models import EvidenceClaimDraft


def _real_draft(clip, quote, sid="PMID:1"):
    return EvidenceClaimDraft(
        suggested_evidence_id=clip,
        quote=quote,
        source_id=sid,
        section="results",
        hallmark_phrase="h",
        score=1.0,
    )


def test_add_to_pool_dedups_same_quote_within_source():
    pool: dict[str, Any] = {}
    by_source: dict[str, list[Any]] = defaultdict(list)
    _add_to_pool(_real_draft("c1", "the receptor internalized"), pool, by_source)
    _add_to_pool(_real_draft("c2", "the receptor internalized"), pool, by_source)
    assert len(pool) == 1  # identical normalized quote within source -> deduped


def test_source_store_registers_real_body_for_fetched(monkeypatch):
    pool = {"c1": SimpleNamespace(source_id="PMID:1")}
    paper = SimpleNamespace(
        pmid=1, pmc_id="PMC9", title="t", abstract="abs",
        publication_type="primary_research", is_retracted=False,
        year=2020, journal="J", authors=["A B"],
    )
    monkeypatch.setattr(
        mod,
        "fetch_fulltext",
        lambda *, http, pmcid, retraction_index, topic_tagger=None: SimpleNamespace(
            sections=[SimpleNamespace(name="results", text="the receptor internalized rapidly in SKBR3")]
        ),
    )
    store = build_source_store(
        pool,
        papers_by_source_id={"PMID:1": (paper, True)},
        http=cast(Any, object()),
        retraction_index=cast(Any, object()),
    )
    st = store.get("PMID:1")
    assert st is not None
    assert "internalized rapidly" in st.raw_text
    assert st.normalized_text
    assert st.source_type == "pubmed"
    assert st.url == "https://pubmed.ncbi.nlm.nih.gov/1/"


def test_source_store_uses_abstract_when_not_fetched(monkeypatch):
    pool = {"c1": SimpleNamespace(source_id="PMID:2")}
    paper = SimpleNamespace(
        pmid=2, pmc_id=None, title="t", abstract="abstract body text",
        publication_type="review", is_retracted=False, year=None, journal=None, authors=[],
    )

    def _no_fetch(**kw):
        raise AssertionError("fetch_fulltext must not run for a non-fetched paper")

    monkeypatch.setattr(mod, "fetch_fulltext", _no_fetch)
    store = build_source_store(
        pool,
        papers_by_source_id={"PMID:2": (paper, False)},
        http=cast(Any, object()),
        retraction_index=cast(Any, object()),
    )
    st = store.get("PMID:2")
    assert st is not None and st.raw_text == "abstract body text"
