"""Tests for the PubTator3 client + its wiring into evidence_retrieval.

Three groups:

* **Query construction** — ``build_gene_entity_query`` produces the
  ``@GENE_<SYMBOL> <terms>`` form PubTator's entity operator expects.
* **Response parsing** — ``pubtator_search`` decodes the real PubTator3
  search-response shape (probed live) into typed hits, including the
  year-from-``date`` extraction.
* **Discovery wiring** — ``_union_by_pmid`` dedups across sources and
  ``_pubtator_discovery`` degrades gracefully when PubTator is down.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest

from accessible_surfaceome.tools import evidence_retrieval as er
from accessible_surfaceome.tools._shared import pubtator
from accessible_surfaceome.tools._shared import retraction_watch as rw
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import IdentifierBundle, Paper


# ---------------------------------------------------------------------------
# Fake HTTP — minimal CachedHTTP stand-in
# ---------------------------------------------------------------------------


class _FakeHTTP:
    """Returns a canned JSON payload for get_json; raises for everything else."""

    def __init__(self, json_payload: Any = None, *, raise_on_call: bool = False):
        self._payload = json_payload
        self._raise = raise_on_call
        self.calls: list[dict[str, Any]] = []

    def get_json(self, url: str, *, source: str, ttl_days: int, params: dict | None = None) -> Any:
        self.calls.append({"url": url, "source": source, "params": params})
        if self._raise:
            raise RuntimeError("simulated PubTator outage")
        return self._payload


# ---------------------------------------------------------------------------
# Query construction
# ---------------------------------------------------------------------------


def test_build_gene_entity_query_upcases_and_appends() -> None:
    assert (
        pubtator.build_gene_entity_query("erbb2", "immunohistochemistry surface")
        == "@GENE_ERBB2 immunohistochemistry surface"
    )


def test_build_gene_entity_query_bare_symbol() -> None:
    assert pubtator.build_gene_entity_query("ERBB2") == "@GENE_ERBB2"


def test_build_gene_entity_query_rejects_empty_symbol() -> None:
    with pytest.raises(ValueError, match="non-empty symbol"):
        pubtator.build_gene_entity_query("  ")


# ---------------------------------------------------------------------------
# Response parsing — fixture mirrors the live PubTator3 search shape
# ---------------------------------------------------------------------------


def _pubtator_payload() -> dict[str, Any]:
    """Mirror of a real PubTator3 /search/ response (fields pared down)."""
    return {
        "count": 40991,
        "current": 1,
        "total_pages": 4100,
        "page_size": 10,
        "results": [
            {
                "_id": "36980575",
                "pmid": 36980575,
                "pmcid": "PMC10046044",
                "doi": "10.3390/cancers15061688",
                "title": "Evaluation of ERBB2 mRNA Expression in HER2-Equivocal Cases.",
                "journal": "Cancers (Basel)",
                "authors": ["Carretero-Barrio I", "Palacios J"],
                "date": "2023-03-09T00:00:00Z",
                "meta_date_publication": "2023 Mar 9",
                "score": 281.8696,
            },
            {
                # pmcid absent, date absent — exercise the fallbacks
                "_id": "12345678",
                "pmid": 12345678,
                "pmcid": None,
                "doi": None,
                "title": "An older HER2 paper",
                "journal": "J Cell Biol",
                "authors": [],
                "meta_date_publication": "1999 Jan",
                "score": 99.5,
            },
        ],
    }


def test_pubtator_search_parses_hits() -> None:
    http = _FakeHTTP(_pubtator_payload())
    result = pubtator.pubtator_search(http=cast(CachedHTTP, http), query="@GENE_ERBB2 immunohistochemistry")

    assert result.total_count == 40991
    assert result.page == 1
    assert len(result.hits) == 2

    first = result.hits[0]
    assert first.pmid == 36980575
    assert first.pmcid == "PMC10046044"
    assert first.doi == "10.3390/cancers15061688"
    assert first.journal == "Cancers (Basel)"
    assert first.year == 2023  # from the ISO `date` field
    assert first.score == pytest.approx(281.8696)
    assert first.authors == ["Carretero-Barrio I", "Palacios J"]
    # Title's trailing period is stripped (consistency with Europe PMC papers).
    assert not first.title.endswith(".")


def test_pubtator_search_year_falls_back_to_meta_date() -> None:
    http = _FakeHTTP(_pubtator_payload())
    result = pubtator.pubtator_search(http=cast(CachedHTTP, http), query="q")
    second = result.hits[1]
    assert second.pmcid is None
    assert second.year == 1999  # no `date`, parsed from `meta_date_publication`


def test_pubtator_search_passes_query_through_to_http() -> None:
    http = _FakeHTTP(_pubtator_payload())
    pubtator.pubtator_search(http=cast(CachedHTTP, http), query="@GENE_ERBB2 flow cytometry", page=2)
    assert http.calls[0]["params"] == {
        "text": "@GENE_ERBB2 flow cytometry",
        "page": "2",
        "sort": "score desc",
    }
    assert http.calls[0]["source"] == "pubtator"


def test_pubtator_search_sort_date_desc_passes_through() -> None:
    http = _FakeHTTP(_pubtator_payload())
    pubtator.pubtator_search(
        http=cast(CachedHTTP, http), query="@GENE_SRC", sort="date desc"
    )
    assert http.calls[0]["params"]["sort"] == "date desc"


def test_pubtator_search_empty_results() -> None:
    http = _FakeHTTP({"count": 0, "current": 1, "results": []})
    result = pubtator.pubtator_search(http=cast(CachedHTTP, http), query="@GENE_NOPE foo")
    assert result.total_count == 0
    assert result.hits == []


# ---------------------------------------------------------------------------
# Discovery wiring in evidence_retrieval
# ---------------------------------------------------------------------------


def _paper(pmid: int, *, pmc_id: str | None = None) -> Paper:
    return Paper(
        pmid=pmid,
        pmc_id=pmc_id,
        title=f"paper {pmid}",
        is_pmc_oa=bool(pmc_id),
        retraction_checked_at=datetime.now(UTC),
    )


def test_union_by_pmid_dedups_first_wins() -> None:
    pubtator_papers = [_paper(1, pmc_id="PMC1"), _paper(2, pmc_id="PMC2")]
    epmc_papers = [_paper(2, pmc_id="PMC2"), _paper(3, pmc_id="PMC3")]
    union = er._union_by_pmid(pubtator_papers, epmc_papers)
    assert [p.pmid for p in union] == [1, 2, 3]
    # PMID 2 keeps the PubTator-sourced instance (first list wins).
    assert union[1] is pubtator_papers[1]


def test_union_by_pmid_preserves_order() -> None:
    a = [_paper(5), _paper(3)]
    b = [_paper(9), _paper(3), _paper(1)]
    assert [p.pmid for p in er._union_by_pmid(a, b)] == [5, 3, 9, 1]


def _bundle() -> IdentifierBundle:
    return IdentifierBundle(
        uniprot_acc="P04626",
        hgnc_id="HGNC:3430",
        hgnc_symbol="ERBB2",
        aliases=["HER2"],
        ncbi_gene_id=2064,
    )


def test_pubtator_discovery_degrades_gracefully_on_outage() -> None:
    """If PubTator errors, discovery returns [] rather than raising —
    Europe PMC keyword discovery remains the sole source for the call."""
    http = _FakeHTTP(raise_on_call=True)
    out = er._pubtator_discovery(
        bundle=_bundle(),
        spec=er._CATEGORY_SPECS["ihc"],
        max_papers=5,
        http=cast(CachedHTTP, http),
        retraction_index=rw.empty(),
    )
    assert out == []


def test_pubtator_discovery_skips_when_no_terms() -> None:
    """The hpa_ihc spec has empty pubtator_terms — no HTTP call is made."""
    http = _FakeHTTP(raise_on_call=True)  # would raise if called
    out = er._pubtator_discovery(
        bundle=_bundle(),
        spec=er._CATEGORY_SPECS["hpa_ihc"],
        max_papers=5,
        http=cast(CachedHTTP, http),
        retraction_index=rw.empty(),
    )
    assert out == []
    assert http.calls == []  # short-circuited before any request
