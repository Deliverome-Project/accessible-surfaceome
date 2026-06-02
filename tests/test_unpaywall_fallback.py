"""Tests for the Unpaywall + PDF body-fetch fallback in abstract_triage.

Covers ``_pick_best_pdf_url`` selection, the ``_fetch_body_via_unpaywall_pdf``
guard rails (no DOI / not OA / non-PDF body / fetch error → ``[]``), and the
3-step fall-through in ``_fetch_body_drafts`` (PMC JATS → PMC-empty →
Unpaywall PDF → raise). All network-free: a fake HTTP returns canned Unpaywall
JSON + PDF bytes, and ``parse_pdf_to_sections`` is monkeypatched so PDF parsing
(tested separately) is isolated out.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest

from accessible_surfaceome.agents.plan_trim_select import abstract_triage
from accessible_surfaceome.agents.plan_trim_select.abstract_triage import (
    UnpaywallLocation,
    _BodyFetch,
    _fetch_body_drafts,
    _fetch_body_via_unpaywall_pdf,
    _pick_best_pdf_url,
)
from accessible_surfaceome.tools._shared.models import Paper, PaperSection

_OA_PUBLISHER_PDF = {
    "is_oa": True,
    "oa_locations": [
        {
            "url": "https://pub.example/x",
            "url_for_pdf": "https://pub.example/x.pdf",
            "host_type": "publisher",
            "version": "publishedVersion",
        }
    ],
}
_BODY_SECTION = PaperSection(
    name="results",
    text="CD20 was biotinylated at the cell surface and quantified by flow "
    "cytometry in primary human B cells.",
)


def _loc(**kw: Any) -> UnpaywallLocation:
    base: dict[str, Any] = dict(
        url="u",
        url_for_pdf=None,
        url_for_landing_page=None,
        host_type=None,
        version=None,
        license=None,
        has_pdf=False,
    )
    base.update(kw)
    return UnpaywallLocation(**base)


def _paper(
    doi: str | None = "10.1000/x", pmid: int = 123, pmc_id: str | None = None
) -> Paper:
    return Paper(
        pmid=pmid,
        pmc_id=pmc_id,
        doi=doi,
        title="CD20 surface biology",
        abstract="CD20 sits at the B-cell surface.",
        retraction_checked_at=datetime.now(UTC),
    )


class _FakeHTTP:
    """Minimal CachedHTTP stand-in for get_json (Unpaywall) + get_bytes (PDF)."""

    def __init__(self, *, oa_json: Any, pdf_bytes: bytes | None) -> None:
        self._oa_json = oa_json
        self._pdf_bytes = pdf_bytes
        self.bytes_calls = 0

    def get_json(self, url: str, **_: Any) -> Any:
        return self._oa_json

    def get_bytes(self, url: str, **_: Any) -> bytes:
        self.bytes_calls += 1
        if self._pdf_bytes is None:
            raise RuntimeError("publisher 403")
        return self._pdf_bytes


# ---------------------------------------------------------------------------
# _pick_best_pdf_url
# ---------------------------------------------------------------------------


def test_pick_best_pdf_url_prefers_publisher_published() -> None:
    locs = [
        _loc(url_for_pdf="repo.pdf", host_type="repository", version="acceptedVersion"),
        _loc(url_for_pdf="pub.pdf", host_type="publisher", version="publishedVersion"),
    ]
    assert _pick_best_pdf_url(locs) == "pub.pdf"


def test_pick_best_pdf_url_falls_to_any_pdf() -> None:
    locs = [_loc(url_for_pdf="repo.pdf", host_type="repository", version="acceptedVersion")]
    assert _pick_best_pdf_url(locs) == "repo.pdf"


def test_pick_best_pdf_url_none_when_no_pdf() -> None:
    assert _pick_best_pdf_url([_loc(host_type="publisher")]) is None
    assert _pick_best_pdf_url([]) is None


# ---------------------------------------------------------------------------
# _fetch_body_via_unpaywall_pdf
# ---------------------------------------------------------------------------


def test_unpaywall_pdf_success_keys_on_paper_source_id(monkeypatch) -> None:
    monkeypatch.setattr(abstract_triage, "parse_pdf_to_sections", lambda _b: [_BODY_SECTION])
    http = _FakeHTTP(oa_json=_OA_PUBLISHER_PDF, pdf_bytes=b"%PDF-1.4 fake body")
    drafts = _fetch_body_via_unpaywall_pdf(_paper(), http=cast(Any, http))
    assert drafts
    # Keyed on PMID:123 (clean id), NOT DOI:..., per the design.
    assert all(d.source_id == "PMID:123" for d in drafts)


def test_unpaywall_no_doi_returns_empty() -> None:
    http = _FakeHTTP(oa_json=_OA_PUBLISHER_PDF, pdf_bytes=b"%PDF")
    assert _fetch_body_via_unpaywall_pdf(_paper(doi=None), http=cast(Any, http)) == []
    assert http.bytes_calls == 0


def test_unpaywall_not_oa_returns_empty() -> None:
    http = _FakeHTTP(oa_json={"is_oa": False}, pdf_bytes=b"%PDF")
    assert _fetch_body_via_unpaywall_pdf(_paper(), http=cast(Any, http)) == []
    assert http.bytes_calls == 0


def test_unpaywall_html_interstitial_returns_empty(monkeypatch) -> None:
    # 200 OK but HTML, not a PDF → magic-byte guard rejects it.
    called = {"parsed": False}
    monkeypatch.setattr(
        abstract_triage,
        "parse_pdf_to_sections",
        lambda _b: called.__setitem__("parsed", True) or [_BODY_SECTION],
    )
    http = _FakeHTTP(oa_json=_OA_PUBLISHER_PDF, pdf_bytes=b"<html>paywall</html>")
    assert _fetch_body_via_unpaywall_pdf(_paper(), http=cast(Any, http)) == []
    assert called["parsed"] is False  # never attempted to parse the HTML


def test_unpaywall_fetch_exception_returns_empty() -> None:
    http = _FakeHTTP(oa_json=_OA_PUBLISHER_PDF, pdf_bytes=None)  # get_bytes raises
    assert _fetch_body_via_unpaywall_pdf(_paper(), http=cast(Any, http)) == []


# ---------------------------------------------------------------------------
# _fetch_body_drafts fall-through
# ---------------------------------------------------------------------------


def test_pmc_success_does_not_reach_unpaywall(monkeypatch) -> None:
    monkeypatch.setattr(
        abstract_triage,
        "fetch_fulltext",
        lambda **_k: Paper(
            pmid=123,
            title="t",
            sections=[_BODY_SECTION],
            retraction_checked_at=datetime.now(UTC),
        ),
    )
    http = _FakeHTTP(oa_json=_OA_PUBLISHER_PDF, pdf_bytes=b"%PDF")
    result = _fetch_body_drafts(
        _paper(pmc_id="PMC9"), http=cast(Any, http), retraction_index=cast(Any, None)
    )
    assert isinstance(result, _BodyFetch)
    assert result.source == "pmc_xml"
    assert http.bytes_calls == 0  # Unpaywall never reached


def test_pmc_empty_falls_through_to_unpaywall_pdf(monkeypatch) -> None:
    monkeypatch.setattr(
        abstract_triage,
        "fetch_fulltext",
        lambda **_k: Paper(
            pmid=123, title="t", sections=[], retraction_checked_at=datetime.now(UTC)
        ),
    )
    monkeypatch.setattr(abstract_triage, "parse_pdf_to_sections", lambda _b: [_BODY_SECTION])
    http = _FakeHTTP(oa_json=_OA_PUBLISHER_PDF, pdf_bytes=b"%PDF-1.4 body")
    result = _fetch_body_drafts(
        _paper(pmc_id="PMC9"), http=cast(Any, http), retraction_index=cast(Any, None)
    )
    assert result.source == "unpaywall_pdf"
    assert result.drafts


def test_pmc_exception_falls_through_to_unpaywall(monkeypatch) -> None:
    # A PMC fetch that *raises* (network/parse error), not just empty, must
    # still fall through to the Unpaywall PDF path rather than abort.
    def _boom(**_k: object) -> Paper:
        raise RuntimeError("PMC network error")

    monkeypatch.setattr(abstract_triage, "fetch_fulltext", _boom)
    monkeypatch.setattr(abstract_triage, "parse_pdf_to_sections", lambda _b: [_BODY_SECTION])
    http = _FakeHTTP(oa_json=_OA_PUBLISHER_PDF, pdf_bytes=b"%PDF-1.4 body")
    result = _fetch_body_drafts(
        _paper(pmc_id="PMC9"), http=cast(Any, http), retraction_index=cast(Any, None)
    )
    assert result.source == "unpaywall_pdf"
    assert result.drafts


def test_all_paths_fail_raises(monkeypatch) -> None:
    monkeypatch.setattr(abstract_triage, "_lookup_pmcid_for_pmid", lambda *_a, **_k: None)
    http = _FakeHTTP(oa_json={"is_oa": False}, pdf_bytes=None)
    paper = _paper(pmc_id=None, pmid=123)
    with pytest.raises(ValueError):
        _fetch_body_drafts(paper, http=cast(Any, http), retraction_index=cast(Any, None))
