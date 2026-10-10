"""Offline tests for the literature-refresh stages (no network, no LLM)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx

from accessible_surfaceome.agents.literature_refresh.dates import (
    parse_ncbi_date,
    resolve_publication_dates,
)
from accessible_surfaceome.agents.literature_refresh.discover import (
    filter_new,
    gene_name_patterns,
    mentions_gene,
)
from accessible_surfaceome.tools._shared.cache import Cache
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import IdentifierBundle, Paper
from accessible_surfaceome.tools._shared.ratelimit import RateLimiter


def _http(tmp_path: Path, handler, fresh: frozenset[str] = frozenset()) -> CachedHTTP:
    http = CachedHTTP(Cache(tmp_path / "cache.sqlite"), RateLimiter({}), fresh_sources=fresh)
    http._client = httpx.Client(transport=httpx.MockTransport(handler))
    return http


def _bundle(**kw) -> IdentifierBundle:
    base = {"hgnc_id": "HGNC:1", "hgnc_symbol": "IL24", "uniprot_acc": "Q13007",
            "aliases": [], "previous_symbols": []}
    base.update(kw)
    return IdentifierBundle.model_validate(base)


def _paper(pmid: int, title: str, abstract: str = "", year: int = 2026, pmc: str | None = None):
    return Paper(pmid=pmid, pmc_id=pmc, title=title, abstract=abstract, year=year)


# --- CachedHTTP.fresh_sources -------------------------------------------------


def test_fresh_source_skips_cache_read_but_other_sources_still_cache(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"n": len(calls)})

    http = _http(tmp_path, handler, fresh=frozenset({"europepmc"}))
    url = "https://api.example.test/search"
    assert http.get_json(url, source="europepmc", ttl_days=30)["n"] == 1
    assert http.get_json(url, source="europepmc", ttl_days=30)["n"] == 2  # re-queried
    assert http.get_json(url, source="europepmc_fulltext", ttl_days=365)["n"] == 3
    assert http.get_json(url, source="europepmc_fulltext", ttl_days=365)["n"] == 3  # cached


# --- dates ---------------------------------------------------------------------


def test_parse_ncbi_date_handles_partial_dates() -> None:
    assert parse_ncbi_date("2026 Aug 14") == date(2026, 8, 14)
    assert parse_ncbi_date("2026 Aug") == date(2026, 8, 1)
    assert parse_ncbi_date("2026") == date(2026, 1, 1)
    assert parse_ncbi_date("2026/08/14") == date(2026, 8, 14)
    assert parse_ncbi_date("") is None
    assert parse_ncbi_date(None) is None


def test_resolve_dates_routes_pmid_to_ncbi_and_pmc_only_to_europepmc(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "eutils" in request.url.host:
            return httpx.Response(200, json={"result": {"42": {"epubdate": "2026 Aug 2"}}})
        return httpx.Response(
            200,
            json={"resultList": {"result": [
                {"pmcid": "PMC9", "firstPublicationDate": "2026-09-10"}
            ]}},
        )

    http = _http(tmp_path, handler)
    papers = {
        "PMID:42": _paper(42, "a"),
        "PMC:PMC9": _paper(0, "b", pmc="PMC9"),
        "PMC:PMC7": None,  # body-clip source with no Paper, undatable here
    }
    got = resolve_publication_dates(papers, http)
    assert got == {"PMID:42": date(2026, 8, 2), "PMC:PMC9": date(2026, 9, 10)}


# --- gene-name patterns ----------------------------------------------------------


def test_symbol_match_tolerates_hyphen_and_rejects_substrings() -> None:
    pats = gene_name_patterns(_bundle(approved_name="interleukin 24"))
    assert mentions_gene(_paper(1, "IL-24 induces dormancy"), pats)
    assert mentions_gene(_paper(1, "x", "levels of interleukin-24 rose"), pats)
    assert not mentions_gene(_paper(1, "IL-240 and IL24X"), pats)


def test_short_aliases_do_not_count_on_their_own() -> None:
    pats = gene_name_patterns(_bundle(aliases=["ST16", "MDA7", "MELANOMA7"]))
    assert not mentions_gene(_paper(1, "Spread of C. pneumoniae ST16 in 2025"), pats)
    assert mentions_gene(_paper(1, "MELANOMA7 is induced"), pats)


# --- filter_new ------------------------------------------------------------------


def test_filter_new_applies_cutoff_citation_and_gene_mention() -> None:
    pats = gene_name_patterns(_bundle())
    papers = {
        "PMID:1": _paper(1, "IL24 new"),            # kept
        "PMID:2": _paper(2, "IL24 old"),            # before cutoff
        "PMID:3": _paper(3, "IL24 cited"),          # already cited
        "PMID:4": _paper(4, "unrelated protein"),   # no gene mention
        "PMC:PMC5": None,                           # body clip → kept without mention
        "PMID:6": _paper(6, "IL24 undated", year=2026),   # undated, cutoff year → kept
        "PMID:7": _paper(7, "IL24 undated", year=2025),   # undated, earlier → dropped
    }
    published = {
        "PMID:1": date(2026, 8, 1),
        "PMID:2": date(2026, 6, 1),
        "PMID:3": date(2026, 8, 1),
        "PMID:4": date(2026, 8, 1),
        "PMC:PMC5": date(2026, 8, 1),
    }
    kept, excluded = filter_new(
        papers,
        published=published,
        cutoff=date(2026, 7, 6),
        cited_ids={"PMID:3"},
        body_clip_ids={"PMC:PMC5"},
        patterns=pats,
    )
    assert kept == ["PMID:1", "PMC:PMC5", "PMID:6"]
    assert excluded == {
        "before_cutoff": 1, "already_cited": 1, "no_gene_mention": 1, "undated": 1
    }
