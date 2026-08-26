from collections import defaultdict
from types import SimpleNamespace
from typing import Any, cast

from accessible_surfaceome.agents._support import literature_clips as mod
from accessible_surfaceome.agents._support.literature_clips import (
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
        cast(Any, pool),
        papers_by_source_id=cast(Any, {"PMID:1": (paper, True)}),
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
        cast(Any, pool),
        papers_by_source_id=cast(Any, {"PMID:2": (paper, False)}),
        http=cast(Any, object()),
        retraction_index=cast(Any, object()),
    )
    st = store.get("PMID:2")
    assert st is not None and st.raw_text == "abstract body text"


def test_source_store_uses_draft_body_for_non_pmc_fetched(monkeypatch):
    # Regression (TMEM123/EndoNB): a FETCHED bioRxiv/medRxiv preprint has no PMC
    # id, so the PMC re-fetch yields nothing. The body-derived clip drafts must
    # supply the span-verify body text — otherwise every body clip from a preprint
    # fails verification against an abstract-only store and gets silently dropped.
    pool = {
        "c1": _real_draft(
            "c1",
            "TMEM123 internalized like the transferrin receptor",
            sid="DOI:10.1101/x",
        )
    }
    paper = SimpleNamespace(
        pmid=None, pmc_id=None, doi="10.1101/x", title="EndoNB",
        abstract="a general strategy for surface protein turnover",  # never names the protein
        publication_type="preprint", is_retracted=False,
        year=2025, journal="bioRxiv (preprint)", authors=[],
    )

    def _no_fetch(**kw):
        raise AssertionError("PMC fetch_fulltext must not run for a non-PMC preprint")

    monkeypatch.setattr(mod, "fetch_fulltext", _no_fetch)
    store = build_source_store(
        cast(Any, pool),
        papers_by_source_id=cast(Any, {"DOI:10.1101/x": (paper, True)}),
        http=cast(Any, object()),
        retraction_index=cast(Any, object()),
    )
    st = store.get("DOI:10.1101/x")
    assert st is not None
    assert "a general strategy" in st.raw_text  # abstract kept
    # the body clip (absent from the abstract) is now verifiable:
    assert "TMEM123 internalized like the transferrin receptor" in st.raw_text


def test_source_store_folds_drafts_for_pmc_paper_with_empty_jats(monkeypatch):
    # Robustness: a paper WITH a PMC id whose JATS comes back EMPTY (the
    # PMC-PDF-only case abstract_triage falls through to Unpaywall for) still has
    # body-derived drafts. The store must fold them in — the if/elif version only
    # folded drafts when pmc_id was absent, so these body clips were dropped.
    pool = {"c1": _real_draft("c1", "the receptor internalized via clathrin", sid="PMC:42")}
    paper = SimpleNamespace(
        pmid=42, pmc_id="PMC42", doi=None, title="t", abstract="abstract only text",
        publication_type="primary_research", is_retracted=False,
        year=2022, journal="J", authors=[],
    )
    # JATS returns NO sections (PMC-PDF-only) — the real body came via Unpaywall.
    monkeypatch.setattr(
        mod,
        "fetch_fulltext",
        lambda *, http, pmcid, retraction_index, topic_tagger=None: SimpleNamespace(sections=[]),
    )
    store = build_source_store(
        cast(Any, pool),
        papers_by_source_id=cast(Any, {"PMC:42": (paper, True)}),
        http=cast(Any, object()),
        retraction_index=cast(Any, object()),
    )
    st = store.get("PMC:42")
    assert st is not None
    assert "abstract only text" in st.raw_text
    # the body clip is verifiable even though JATS was empty and pmc_id is set:
    assert "the receptor internalized via clathrin" in st.raw_text


def test_fetched_store_body_still_contains_the_abstract(monkeypatch):
    # Regression: a fetched paper can contribute ABSTRACT-derived clips (e.g. a
    # worth_fetching body-fetch that fell back to abstract). The store body must
    # include the abstract, or those clips fail span verification and get
    # silently dropped at promotion.
    pool = {"c1": SimpleNamespace(source_id="PMID:3")}
    paper = SimpleNamespace(
        pmid=3, pmc_id="PMC9", title="t",
        abstract="ABSTRACT_SENTENCE_ONLY_IN_ABSTRACT",
        publication_type="primary_research", is_retracted=False,
        year=2021, journal="J", authors=[],
    )
    monkeypatch.setattr(
        mod,
        "fetch_fulltext",
        lambda *, http, pmcid, retraction_index, topic_tagger=None: SimpleNamespace(
            sections=[SimpleNamespace(name="results", text="BODY_SENTENCE_ONLY_IN_BODY")]
        ),
    )
    store = build_source_store(
        cast(Any, pool),
        papers_by_source_id=cast(Any, {"PMID:3": (paper, True)}),
        http=cast(Any, object()),
        retraction_index=cast(Any, object()),
    )
    st = store.get("PMID:3")
    assert st is not None
    assert "ABSTRACT_SENTENCE_ONLY_IN_ABSTRACT" in st.raw_text  # abstract kept
    assert "BODY_SENTENCE_ONLY_IN_BODY" in st.raw_text  # full text kept too
