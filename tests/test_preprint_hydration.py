"""Unit tests for the shared bioRxiv/medRxiv DOI -> Paper hydration helper."""

from typing import Any, cast

from accessible_surfaceome.tools._shared import preprint as pp
from accessible_surfaceome.tools._shared.retraction_watch import RetractionIndex


class _FakeHTTP:
    """Fake CachedHTTP.get_json returning a canned bioRxiv details payload."""

    def __init__(self, by_server: dict[str, dict[str, Any]]):
        self.by_server = by_server
        self.calls: list[str] = []

    def get_json(self, url: str, *, source: str, ttl_days: int, **_: Any) -> Any:
        self.calls.append(url)
        # url shape: .../details/{server}/{doi}
        server = url.split("/details/")[1].split("/")[0]
        return self.by_server.get(server, {"collection": []})


_ENDO = {
    "collection": [
        {
            "title": "EndoNB: A general strategy to study the internalization of surface proteins.",
            "doi": "10.1101/2025.06.08.658482",
            "date": "2025-06-08",
            "category": "cell biology",
            "version": "1",
            "abstract": "We present a method to study surface protein turnover ...",
        }
    ]
}


def test_hydrates_biorxiv_doi_with_url_prefix():
    http = _FakeHTTP({"biorxiv": _ENDO})
    p = pp.paper_from_preprint_doi(
        "https://doi.org/10.1101/2025.06.08.658482", http=cast(Any, http)
    )
    assert p is not None
    assert p.doi == "10.1101/2025.06.08.658482"  # normalized (prefix stripped)
    assert p.is_preprint is True
    assert p.year == 2025
    assert p.title.endswith("surface proteins")  # trailing period stripped
    assert p.abstract and "surface protein turnover" in p.abstract
    assert p.is_retracted is False


def test_non_cshl_doi_returns_none_without_calling_api():
    http = _FakeHTTP({})
    assert (
        pp.paper_from_preprint_doi("10.1073/pnas.95.11.6290", http=cast(Any, http))
        is None
    )
    assert http.calls == []  # short-circuits before any network call


def test_falls_through_to_medrxiv_then_none_when_no_record():
    http = _FakeHTTP({})  # both servers return empty collection
    assert (
        pp.paper_from_preprint_doi("10.1101/2099.01.01.000000", http=cast(Any, http))
        is None
    )
    assert any("/biorxiv/" in u for u in http.calls)
    assert any("/medrxiv/" in u for u in http.calls)  # tried both


def test_flags_retracted_preprint():
    http = _FakeHTTP({"biorxiv": _ENDO})
    idx = RetractionIndex(
        pmids=frozenset(), dois=frozenset({"10.1101/2025.06.08.658482"})
    )
    p = pp.paper_from_preprint_doi(
        "10.1101/2025.06.08.658482", http=cast(Any, http), retraction_index=idx
    )
    assert p is not None and p.is_retracted is True
