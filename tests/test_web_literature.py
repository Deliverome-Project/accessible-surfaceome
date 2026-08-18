"""Unit tests for the shared web_search literature-discovery module."""

from typing import Any, cast

from accessible_surfaceome.agents._support import web_literature as wl
from accessible_surfaceome.tools._shared.models import Paper


def _paper(**kw: Any) -> Paper:
    base: dict[str, Any] = {"pmid": 1, "title": "t"}
    base.update(kw)
    return Paper(**base)


def test_source_tier_ranks_by_host():
    assert wl.source_tier("https://www.biorxiv.org/content/10.1101/x") == "preprint"
    assert wl.source_tier("https://www.medrxiv.org/content/10.1101/y") == "preprint"
    assert wl.source_tier("https://www.nature.com/articles/x") == "paper"
    assert wl.source_tier("https://pubmed.ncbi.nlm.nih.gov/123/") == "paper"
    assert wl.source_tier("https://www.abcam.com/x") == "vendor"
    assert wl.source_tier("https://some.random.blog/x") == "other"


def test_discovery_result_tolerates_model_envelope():
    """Regression: the web_search model wraps the list in a
    ``{"protein": ..., "topic": ..., "citations": [...]}`` envelope and decorates
    each citation with ``title`` / ``url`` / ``reason``. Under ``extra="forbid"``
    this failed validation after every repair and returned nothing (the TMEM123
    silent-zero bug). ``extra="ignore"`` must recover the citations."""
    payload = {
        "protein": {"gene_symbol": "EGFR", "aliases": ["ERBB1"]},
        "topic": "internalization / endocytosis measurements",
        "citations": [
            {
                "pmid": 12456789,
                "doi": "10.1/x",
                "title": "EGFR endocytosis kinetics",
                "url": "https://www.nature.com/x",
                "reason": "measures uptake",
                "note": "rate paper",
            },
            {"pmid": None, "doi": "10.1101/2026.01.01.123456", "note": "recent preprint"},
        ],
    }
    res = wl.WebDiscoveryResult.model_validate(payload)
    assert len(res.citations) == 2  # envelope keys ignored, list recovered
    assert res.citations[0].title == "EGFR endocytosis kinetics"
    assert res.citations[0].url == "https://www.nature.com/x"  # usable extras kept


def test_web_discover_hydrates_pmid_and_doi_and_dedups(monkeypatch):
    # Model surfaces one PMID hit, one DOI-only preprint, and a dup of the PMID.
    monkeypatch.setattr(
        wl,
        "call_builder",
        lambda *a, **k: wl.WebDiscoveryResult(
            citations=[
                wl.WebCitation(pmid=111),
                wl.WebCitation(doi="https://doi.org/10.1101/2025.06.08.658482"),
                wl.WebCitation(pmid=111, note="dup"),
            ]
        ),
    )
    # PMID hydration → a real Paper.
    monkeypatch.setattr(
        wl, "europepmc_bulk_by_pmid", lambda **k: [_paper(pmid=111, title="pmid paper")]
    )
    # DOI hydration → the EuropePMC search returns one PPR record...
    monkeypatch.setattr(
        wl,
        "europepmc_search",
        lambda **k: {"resultList": {"result": [{"id": "PPR1", "doi": "10.1101/2025.06.08.658482"}]}},
    )
    # ...which paper_from_europepmc (include_preprints=True) turns into a DOI-anchored preprint Paper.
    monkeypatch.setattr(
        wl,
        "paper_from_europepmc",
        lambda rec, **k: _paper(pmid=None, doi=rec["doi"], title="preprint", is_preprint=True),
    )

    out = wl.web_discover_papers(
        cast(Any, object()),
        intent="internalization",
        gene_names=["TMEM123", "porimin"],
        http=cast(Any, object()),
        retraction_index=cast(Any, object()),
    )
    # 2 unique papers (the dup PMID collapses on paper_source_id).
    assert len(out) == 2
    ids = {p.pmid for p in out}
    assert 111 in ids and None in ids  # the PMID paper + the DOI-only preprint
    assert any(p.is_preprint and p.doi for p in out)


def test_web_discover_returns_empty_when_tool_unavailable(monkeypatch):
    # call_builder returns None when web_search isn't enabled / JSON never validates.
    monkeypatch.setattr(wl, "call_builder", lambda *a, **k: None)
    out = wl.web_discover_papers(
        cast(Any, object()),
        intent="x",
        gene_names=["GENEX"],
        http=cast(Any, object()),
        retraction_index=cast(Any, object()),
    )
    assert out == []


def test_web_discover_drops_unresolvable_citations(monkeypatch):
    # A citation whose PMID/DOI don't resolve is dropped (integrity: nothing
    # unverifiable enters the pool).
    monkeypatch.setattr(
        wl,
        "call_builder",
        lambda *a, **k: wl.WebDiscoveryResult(citations=[wl.WebCitation(pmid=999)]),
    )
    monkeypatch.setattr(wl, "europepmc_bulk_by_pmid", lambda **k: [])  # no hit
    out = wl.web_discover_papers(
        cast(Any, object()),
        intent="x",
        gene_names=["GENEX"],
        http=cast(Any, object()),
        retraction_index=cast(Any, object()),
    )
    assert out == []
