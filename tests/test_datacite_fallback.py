"""Tests for the DataCite landing-page → citation_pdf_url body-fetch fallback.

Sits as tier-3 in ``_fetch_body_drafts`` after PMC JATS and Unpaywall: when a
paper's DOI is DataCite-registered (preprint platforms like Astera's Stacks,
institutional repos, etc.) and not in Unpaywall, we resolve the DOI through
DataCite, fetch the landing page, pull the Google-Scholar-standard
``<meta name="citation_pdf_url">`` tag, and parse the PDF through the same
pdfplumber path as Unpaywall. All network-free.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from accessible_surfaceome.agents.plan_trim_select import abstract_triage
from accessible_surfaceome.agents.plan_trim_select.abstract_triage import (
    _BodyFetch,
    _extract_citation_pdf_url,
    _fetch_body_drafts,
    _fetch_body_via_datacite_landing,
    _lookup_datacite_metadata,
)
from accessible_surfaceome.tools._shared.models import Paper, PaperSection

_BODY_SECTION = PaperSection(
    name="results",
    text="sampleworks integrates structure predictors with experimental "
    "guidance to refine biomolecular ensembles.",
)

_DATACITE_PAYLOAD = {
    "data": {
        "attributes": {
            "url": "https://thestacks.org/publications/sampleworks-release",
            "contentUrl": None,
            "rightsList": [
                {"rights": "Creative Commons Attribution 4.0", "rightsIdentifier": "cc-by-4.0"}
            ],
        }
    }
}

_LANDING_HTML = (
    '<html><head>'
    '<meta name="citation_title" content="sampleworks"/>'
    '<meta name="citation_pdf_url" content="https://thestacks-01.s3.amazonaws.com/x.pdf"/>'
    '</head><body>...</body></html>'
)


def _paper(doi: str | None = "10.82153/jkxj-tw08", pmid: int = 9991, pmc_id: str | None = None) -> Paper:
    return Paper(
        pmid=pmid,
        pmc_id=pmc_id,
        doi=doi,
        title="sampleworks",
        abstract="Experimentally guided biomolecular ensemble generation.",
        retraction_checked_at=datetime.now(UTC),
    )


class _RoutedHTTP:
    """Routes get_json / get_text / get_bytes by URL substring so DataCite,
    Unpaywall, the landing-page HTML, and the PDF blob can all be served from
    one fake without colliding."""

    def __init__(
        self,
        *,
        datacite_json: Any = None,
        unpaywall_json: Any = None,
        landing_html: str | None = None,
        pdf_bytes: bytes | None = None,
    ) -> None:
        self._datacite_json = datacite_json
        self._unpaywall_json = unpaywall_json
        self._landing_html = landing_html
        self._pdf_bytes = pdf_bytes
        self.calls: list[tuple[str, str]] = []  # (method, url)

    def get_json(self, url: str, **_: Any) -> Any:
        self.calls.append(("json", url))
        if "api.datacite.org" in url:
            if self._datacite_json is None:
                raise RuntimeError("DataCite 404")
            return self._datacite_json
        if "api.unpaywall.org" in url:
            if self._unpaywall_json is None:
                raise RuntimeError("Unpaywall 404")
            return self._unpaywall_json
        raise RuntimeError(f"unexpected json url: {url}")

    def get_text(self, url: str, **_: Any) -> str:
        self.calls.append(("text", url))
        if self._landing_html is None:
            raise RuntimeError("landing fetch failed")
        return self._landing_html

    def get_bytes(self, url: str, **_: Any) -> bytes:
        self.calls.append(("bytes", url))
        if self._pdf_bytes is None:
            raise RuntimeError("publisher 403")
        return self._pdf_bytes


# ---------------------------------------------------------------------------
# _extract_citation_pdf_url
# ---------------------------------------------------------------------------


def test_extract_citation_pdf_url_name_first() -> None:
    html = '<meta name="citation_pdf_url" content="https://x.example/a.pdf"/>'
    assert _extract_citation_pdf_url(html) == "https://x.example/a.pdf"


def test_extract_citation_pdf_url_single_quotes() -> None:
    html = "<meta name='citation_pdf_url' content='https://x.example/a.pdf'/>"
    assert _extract_citation_pdf_url(html) == "https://x.example/a.pdf"


def test_extract_citation_pdf_url_content_first() -> None:
    # Some templates emit attributes in opposite order; both should resolve.
    html = '<meta content="https://x.example/a.pdf" name="citation_pdf_url"/>'
    assert _extract_citation_pdf_url(html) == "https://x.example/a.pdf"


def test_extract_citation_pdf_url_missing_returns_none() -> None:
    html = '<html><head><meta name="citation_title" content="x"/></head></html>'
    assert _extract_citation_pdf_url(html) is None


# ---------------------------------------------------------------------------
# _lookup_datacite_metadata
# ---------------------------------------------------------------------------


def test_lookup_datacite_returns_landing_and_license() -> None:
    http = _RoutedHTTP(datacite_json=_DATACITE_PAYLOAD)
    meta = _lookup_datacite_metadata("10.82153/jkxj-tw08", http=cast(Any, http))
    assert meta is not None
    assert meta.landing_url == "https://thestacks.org/publications/sampleworks-release"
    assert meta.license == "cc-by-4.0"
    assert meta.content_urls == []


def test_lookup_datacite_handles_content_url_list() -> None:
    payload = {
        "data": {
            "attributes": {
                "url": "https://example/landing",
                "contentUrl": ["https://example/a.pdf", "https://example/b.pdf"],
            }
        }
    }
    http = _RoutedHTTP(datacite_json=payload)
    meta = _lookup_datacite_metadata("10.x/y", http=cast(Any, http))
    assert meta is not None
    assert meta.content_urls == ["https://example/a.pdf", "https://example/b.pdf"]


def test_lookup_datacite_404_returns_none() -> None:
    http = _RoutedHTTP(datacite_json=None)  # raises in get_json
    assert _lookup_datacite_metadata("10.crossref/only", http=cast(Any, http)) is None


def test_lookup_datacite_unexpected_shape_returns_none() -> None:
    # An Unpaywall-shaped JSON accidentally fed to the DataCite resolver
    # must not crash — it just isn't a DataCite record.
    http = _RoutedHTTP(datacite_json={"is_oa": False})
    assert _lookup_datacite_metadata("10.x/y", http=cast(Any, http)) is None


# ---------------------------------------------------------------------------
# _fetch_body_via_datacite_landing
# ---------------------------------------------------------------------------


def test_datacite_landing_happy_path(monkeypatch) -> None:
    monkeypatch.setattr(abstract_triage, "parse_pdf_to_sections", lambda _b: [_BODY_SECTION])
    http = _RoutedHTTP(
        datacite_json=_DATACITE_PAYLOAD,
        landing_html=_LANDING_HTML,
        pdf_bytes=b"%PDF-1.4 sampleworks body",
    )
    drafts, lic = _fetch_body_via_datacite_landing(_paper(), http=cast(Any, http))
    assert drafts
    assert lic == "cc-by-4.0"
    # Drafts keyed on PMID:9991 (clean id), not DOI:....
    assert all(d.source_id == "PMID:9991" for d in drafts)
    # We hit the DataCite API, then the landing page, then the PDF.
    methods = [m for m, _ in http.calls]
    assert methods == ["json", "text", "bytes"]


def test_datacite_landing_no_doi_returns_empty() -> None:
    http = _RoutedHTTP(datacite_json=_DATACITE_PAYLOAD)
    drafts, lic = _fetch_body_via_datacite_landing(_paper(doi=None), http=cast(Any, http))
    assert drafts == [] and lic is None
    assert http.calls == []  # never even queried DataCite


def test_datacite_landing_no_meta_tag_returns_empty() -> None:
    # Landing page resolves but has no citation_pdf_url → fall through cleanly.
    http = _RoutedHTTP(
        datacite_json=_DATACITE_PAYLOAD,
        landing_html="<html><head></head><body>no meta here</body></html>",
        pdf_bytes=b"%PDF",
    )
    drafts, _lic = _fetch_body_via_datacite_landing(_paper(), http=cast(Any, http))
    assert drafts == []
    # The PDF must NOT have been fetched — we had nothing to point to.
    assert not any(m == "bytes" for m, _ in http.calls)


def test_datacite_landing_uses_content_url_when_pdf_like(monkeypatch) -> None:
    # contentUrl is set to a direct .pdf — opportunistic short-circuit avoids
    # the extra landing-page hop.
    monkeypatch.setattr(abstract_triage, "parse_pdf_to_sections", lambda _b: [_BODY_SECTION])
    payload = {
        "data": {
            "attributes": {
                "url": "https://example/landing",
                "contentUrl": "https://example/direct.pdf",
                "rightsList": [{"rightsIdentifier": "cc-by-4.0"}],
            }
        }
    }
    http = _RoutedHTTP(
        datacite_json=payload, landing_html=_LANDING_HTML, pdf_bytes=b"%PDF-1.4 body"
    )
    drafts, lic = _fetch_body_via_datacite_landing(_paper(), http=cast(Any, http))
    assert drafts and lic == "cc-by-4.0"
    # First bytes call should target the contentUrl, not the landing-derived URL.
    bytes_urls = [u for m, u in http.calls if m == "bytes"]
    assert bytes_urls[0] == "https://example/direct.pdf"


def test_datacite_landing_html_interstitial_returns_empty(monkeypatch) -> None:
    # citation_pdf_url present but the server returns HTML at that URL —
    # magic-byte guard must reject.
    called = {"parsed": False}
    monkeypatch.setattr(
        abstract_triage,
        "parse_pdf_to_sections",
        lambda _b: called.__setitem__("parsed", True) or [_BODY_SECTION],
    )
    http = _RoutedHTTP(
        datacite_json=_DATACITE_PAYLOAD,
        landing_html=_LANDING_HTML,
        pdf_bytes=b"<html>not a pdf</html>",
    )
    drafts, _lic = _fetch_body_via_datacite_landing(_paper(), http=cast(Any, http))
    assert drafts == []
    assert called["parsed"] is False


# ---------------------------------------------------------------------------
# _fetch_body_drafts fall-through with DataCite as tier 3
# ---------------------------------------------------------------------------


def test_chain_falls_through_to_datacite_when_unpaywall_misses(monkeypatch) -> None:
    # No PMC id, Unpaywall says not-OA, but DataCite carries the DOI →
    # final source must be ``datacite_pdf`` with the DataCite license.
    monkeypatch.setattr(abstract_triage, "parse_pdf_to_sections", lambda _b: [_BODY_SECTION])
    monkeypatch.setattr(abstract_triage, "_lookup_pmcid_for_pmid", lambda *_a, **_k: None)
    http = _RoutedHTTP(
        datacite_json=_DATACITE_PAYLOAD,
        unpaywall_json={"is_oa": False},
        landing_html=_LANDING_HTML,
        pdf_bytes=b"%PDF-1.4 stacks body",
    )
    result = _fetch_body_drafts(
        _paper(pmc_id=None), http=cast(Any, http), retraction_index=cast(Any, None)
    )
    assert isinstance(result, _BodyFetch)
    assert result.source == "datacite_pdf"
    assert result.oa_license == "cc-by-4.0"
    assert result.drafts


# ---------------------------------------------------------------------------
# arXiv DOI shortcut
# ---------------------------------------------------------------------------


def test_arxiv_pdf_url_from_doi_canonical() -> None:
    from accessible_surfaceome.agents.plan_trim_select.abstract_triage import (
        _arxiv_pdf_url_from_doi,
    )
    assert _arxiv_pdf_url_from_doi(
        "10.48550/arxiv.2510.17752"
    ) == "https://arxiv.org/pdf/2510.17752"


def test_arxiv_pdf_url_from_doi_legacy_archive_format() -> None:
    from accessible_surfaceome.agents.plan_trim_select.abstract_triage import (
        _arxiv_pdf_url_from_doi,
    )
    # arXiv's pre-2015 IDs look like ``{archive}/{nnnnnnn}`` (e.g.
    # ``cs/0501001``) — the DOI keeps the slash; arxiv.org/pdf accepts it.
    assert _arxiv_pdf_url_from_doi(
        "10.48550/arxiv.cs/0501001"
    ) == "https://arxiv.org/pdf/cs/0501001"


def test_arxiv_pdf_url_from_doi_uppercase_normalizes() -> None:
    from accessible_surfaceome.agents.plan_trim_select.abstract_triage import (
        _arxiv_pdf_url_from_doi,
    )
    assert _arxiv_pdf_url_from_doi(
        "10.48550/ARXIV.2510.17752"
    ) == "https://arxiv.org/pdf/2510.17752"


def test_arxiv_pdf_url_from_doi_non_arxiv_returns_none() -> None:
    from accessible_surfaceome.agents.plan_trim_select.abstract_triage import (
        _arxiv_pdf_url_from_doi,
    )
    assert _arxiv_pdf_url_from_doi("10.5281/zenodo.6451649") is None
    assert _arxiv_pdf_url_from_doi("10.1038/nature12373") is None
    assert _arxiv_pdf_url_from_doi(None) is None
    assert _arxiv_pdf_url_from_doi("") is None


def test_arxiv_shortcut_skips_datacite_on_success(monkeypatch) -> None:
    """The arXiv shortcut must short-circuit before DataCite metadata
    + landing-page fetches when the deterministic URL works. Measured
    by ``_RoutedHTTP.calls``: only the PDF call, no datacite.org / no
    landing GET."""
    monkeypatch.setattr(abstract_triage, "parse_pdf_to_sections", lambda _b: [_BODY_SECTION])
    monkeypatch.setattr(abstract_triage, "_lookup_pmcid_for_pmid", lambda *_a, **_k: None)
    http = _RoutedHTTP(
        datacite_json=None,
        unpaywall_json=None,
        landing_html=None,
        pdf_bytes=b"%PDF-1.4 arxiv body",
    )
    paper = _paper(doi="10.48550/arxiv.2510.17752", pmid=0, pmc_id=None)
    result = _fetch_body_drafts(paper, http=cast(Any, http), retraction_index=cast(Any, None))
    assert isinstance(result, _BodyFetch)
    assert result.source == "datacite_pdf"
    assert result.drafts
    json_calls = [u for kind, u in http.calls if kind == "json"]
    text_calls = [u for kind, u in http.calls if kind == "text"]
    bytes_calls = [u for kind, u in http.calls if kind == "bytes"]
    assert not any("api.datacite.org" in u for u in json_calls), (
        f"DataCite should be skipped on arXiv success, got json calls: {json_calls}"
    )
    assert text_calls == [], (
        f"landing page should be skipped on arXiv success, got: {text_calls}"
    )
    assert bytes_calls == ["https://arxiv.org/pdf/2510.17752"], (
        f"expected single arxiv PDF call, got: {bytes_calls}"
    )


def test_arxiv_shortcut_falls_back_to_datacite_when_pdf_fails(monkeypatch) -> None:
    """If arxiv.org returns no usable PDF (404, transient outage, parser
    returns 0 sections), the chain must still try the standard DataCite
    path. Otherwise an arxiv.org hiccup would mask a perfectly-fetchable
    DataCite-routed copy."""
    call_count = {"n": 0}
    def _parse(_b: bytes) -> list[PaperSection]:
        call_count["n"] += 1
        # First parse (arxiv URL): pretend parse failed.
        # Second parse (DataCite-derived URL): success.
        return [] if call_count["n"] == 1 else [_BODY_SECTION]
    monkeypatch.setattr(abstract_triage, "parse_pdf_to_sections", _parse)
    monkeypatch.setattr(abstract_triage, "_lookup_pmcid_for_pmid", lambda *_a, **_k: None)
    http = _RoutedHTTP(
        datacite_json=_DATACITE_PAYLOAD,
        unpaywall_json=None,
        landing_html=_LANDING_HTML,
        pdf_bytes=b"%PDF-1.4 some body",
    )
    paper = _paper(doi="10.48550/arxiv.2510.17752", pmid=0, pmc_id=None)
    result = _fetch_body_drafts(paper, http=cast(Any, http), retraction_index=cast(Any, None))
    assert isinstance(result, _BodyFetch)
    assert result.source == "datacite_pdf"
    assert result.drafts
    json_calls = [u for kind, u in http.calls if kind == "json"]
    text_calls = [u for kind, u in http.calls if kind == "text"]
    bytes_calls = [u for kind, u in http.calls if kind == "bytes"]
    assert any("api.datacite.org" in u for u in json_calls), (
        f"DataCite must be tried as fallback when arXiv shortcut fails, got: {json_calls}"
    )
    assert text_calls, f"landing HTML must be fetched as fallback, got: {text_calls}"
    assert "https://arxiv.org/pdf/2510.17752" in bytes_calls
    assert len(bytes_calls) >= 2


def test_chain_resolves_arxiv_doi_with_no_pmid_no_pmcid(monkeypatch) -> None:
    """Regression for the ``source_id == "UNKNOWN"`` bail-out.

    A DataCite-routed arXiv preprint typically arrives as ``Paper(pmid=0,
    pmc_id=None, doi="10.48550/arxiv.X")``. Before the ``paper_source_id``
    DOI fallback, the resolver bailed out at its ``source_id !=
    "UNKNOWN"`` guard and the chain raised, silently masking arXiv as
    unreachable. Lock that in: a DOI-only paper now reaches the DataCite
    tier and returns ``source="datacite_pdf"``.
    """
    monkeypatch.setattr(abstract_triage, "parse_pdf_to_sections", lambda _b: [_BODY_SECTION])
    monkeypatch.setattr(abstract_triage, "_lookup_pmcid_for_pmid", lambda *_a, **_k: None)
    arxiv_doi = "10.48550/arxiv.2510.17752"
    arxiv_datacite = {
        "data": {
            "attributes": {
                "url": f"https://arxiv.org/abs/{arxiv_doi.removeprefix('10.48550/arxiv.')}",
                "contentUrl": None,
                "rightsList": [],
            }
        }
    }
    arxiv_landing = (
        '<html><head>'
        '<meta name="citation_pdf_url" '
        'content="https://arxiv.org/pdf/2510.17752"/>'
        '</head><body>...</body></html>'
    )
    http = _RoutedHTTP(
        datacite_json=arxiv_datacite,
        unpaywall_json=None,  # arXiv DOIs 404 in Unpaywall
        landing_html=arxiv_landing,
        pdf_bytes=b"%PDF-1.4 arxiv body",
    )
    paper = _paper(doi=arxiv_doi, pmid=0, pmc_id=None)
    assert abstract_triage.paper_source_id(paper) == f"DOI:{arxiv_doi}"
    result = _fetch_body_drafts(paper, http=cast(Any, http), retraction_index=cast(Any, None))
    assert isinstance(result, _BodyFetch)
    assert result.source == "datacite_pdf"
    assert result.drafts


def test_unpaywall_success_does_not_reach_datacite(monkeypatch) -> None:
    # When Unpaywall returns a workable PDF we must not also query DataCite
    # — order matters for both latency and DataCite politeness.
    monkeypatch.setattr(abstract_triage, "parse_pdf_to_sections", lambda _b: [_BODY_SECTION])
    monkeypatch.setattr(abstract_triage, "_lookup_pmcid_for_pmid", lambda *_a, **_k: None)
    http = _RoutedHTTP(
        datacite_json=_DATACITE_PAYLOAD,
        unpaywall_json={
            "is_oa": True,
            "oa_locations": [
                {"url": "u", "url_for_pdf": "https://pub.example/x.pdf",
                 "host_type": "publisher", "version": "publishedVersion",
                 "license": "cc-by"}
            ],
        },
        landing_html=_LANDING_HTML,
        pdf_bytes=b"%PDF-1.4 unpaywall body",
    )
    result = _fetch_body_drafts(
        _paper(pmc_id=None), http=cast(Any, http), retraction_index=cast(Any, None)
    )
    assert result.source == "unpaywall_pdf"
    # No DataCite probe should have happened.
    assert not any("api.datacite.org" in u for _, u in http.calls)
