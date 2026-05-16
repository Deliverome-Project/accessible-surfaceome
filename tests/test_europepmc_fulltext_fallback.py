"""Tests for the NCBI -> EuropePMC -> abstract-only fallback chain in
``fetch_fulltext``.

NCBI was promoted to first-line on 2026-05-16 after a survey on the GPR75
A1 run found EuropePMC's ``fullTextXML`` endpoint 404'd on 58/58
fulltext attempts while NCBI succeeded on 40/40. EuropePMC remains in
the chain as Layer 2 to catch EuropePMC-only OAI ingestions NCBI hasn't
mirrored.

These tests stub out ``CachedHTTP.get_text`` / ``get_json`` so the
fallback paths are exercised without hitting the network. The pure-XML
parsing logic is already covered by other tests; what's exercised here
is the layer-selection contract:

1. NCBI succeeds -> ``fulltext_fetch_source == "ncbi"``; EuropePMC not called.
2. NCBI 404 -> EuropePMC succeeds -> ``fulltext_fetch_source == "europepmc"``.
3. Both 404 -> sections is empty, ``fulltext_fetch_source ==
   "abstract_only"``, abstract still present.
4. NCBI returns ``<pmc-articleset/>`` -> treated as 404-equivalent,
   falls through to Layer 2 (EuropePMC).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from accessible_surfaceome.tools._shared import retraction_watch as rw
from accessible_surfaceome.tools._shared.europepmc import (
    EUROPEPMC_FULLTEXT,
    NCBI_PMC_EFETCH,
    fetch_fulltext,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_METADATA_PAYLOAD: dict[str, Any] = {
    "resultList": {
        "result": [
            {
                "pmid": "11111",
                "pmcid": "PMC12462478",
                "doi": "10.1000/fake",
                "pubYear": "2023",
                "journalTitle": "J. Fakes",
                "title": "A test article.",
                "abstractText": "This is the abstract used when full text is unavailable.",
                "isOpenAccess": "Y",
                "pubTypeList": {"pubType": ["research-article"]},
                "authorList": {"author": [{"fullName": "Doe J"}]},
            }
        ]
    }
}


_GOOD_JATS_XML = """<?xml version="1.0"?>
<article>
  <body>
    <sec sec-type="intro">
      <title>Introduction</title>
      <p>Hello world. This is the introduction paragraph.</p>
    </sec>
    <sec sec-type="results">
      <title>Results</title>
      <p>We observed something noteworthy.</p>
    </sec>
  </body>
</article>"""


_EMPTY_NCBI_ARTICLESET = "<?xml version=\"1.0\"?><pmc-articleset/>"


def _make_http(
    *,
    ncbi_fulltext: str | int | Exception,
    europepmc_fulltext: str | int | Exception | None = None,
) -> Any:
    """Build a MagicMock that satisfies the subset of CachedHTTP the
    fallback chain uses: ``get_json`` (metadata search) and
    ``get_text`` (the two fulltext URLs).

    Layer 1 (NCBI) is always wired; Layer 2 (EuropePMC) is optional —
    tests that exercise the NCBI happy path can omit
    ``europepmc_fulltext`` because EuropePMC should never be called
    when NCBI succeeds. The assertion in ``_get_text`` enforces that
    contract: if a NCBI-happy-path test accidentally hits the EuropePMC
    branch, ``europepmc_fulltext is None`` raises a clear AssertionError.

    Each stub accepts:
    - ``str`` — returned verbatim from get_text.
    - ``int`` — interpreted as an HTTP status code; raises a synthetic
      ``HTTPStatusError`` so the helper sees the same exception shape
      it would in production.
    - ``Exception`` — raised as-is.
    """
    http = MagicMock()

    http.get_json.return_value = _METADATA_PAYLOAD

    def _get_text(url: str, *, source: str, ttl_days: int, **_: Any) -> str:
        if source == "ncbi_pmc_efetch":
            return _resolve(ncbi_fulltext, url)
        if source == "europepmc_fulltext":
            assert europepmc_fulltext is not None, (
                "EuropePMC fallback was invoked but the test didn't supply "
                "an europepmc_fulltext stub — this means an NCBI-only "
                "happy-path test accidentally fell through."
            )
            return _resolve(europepmc_fulltext, url)
        raise AssertionError(f"unexpected get_text source: {source}")

    http.get_text.side_effect = _get_text
    return http


def _resolve(stub: str | int | Exception, url: str) -> str:
    if isinstance(stub, str):
        return stub
    if isinstance(stub, int):
        request = httpx.Request("GET", url)
        response = httpx.Response(stub, request=request)
        raise httpx.HTTPStatusError(
            f"{stub} for url {url}", request=request, response=response
        )
    if isinstance(stub, Exception):
        raise stub
    raise TypeError(f"unsupported stub type: {type(stub)!r}")


# ---------------------------------------------------------------------------
# Layer 1: NCBI happy path (preferred — authoritative PMC source)
# ---------------------------------------------------------------------------


def test_layer1_ncbi_success_sets_source_ncbi() -> None:
    http = _make_http(ncbi_fulltext=_GOOD_JATS_XML)
    paper = fetch_fulltext(
        http=http,
        pmcid="PMC12462478",
        retraction_index=rw.empty(),
    )
    assert paper.fulltext_fetch_source == "ncbi"
    assert paper.sections, "NCBI layer should populate sections"
    # EuropePMC must not have been called when NCBI succeeded.
    epmc_calls = [
        c for c in http.get_text.call_args_list
        if c.kwargs.get("source") == "europepmc_fulltext"
    ]
    assert not epmc_calls


def test_layer1_ncbi_call_shape() -> None:
    """The NCBI efetch endpoint receives the numeric PMCID (no ``PMC``
    prefix), the ``db=pmc rettype=xml`` params, and the URL is the
    public efetch endpoint constant."""
    http = _make_http(ncbi_fulltext=_GOOD_JATS_XML)
    fetch_fulltext(
        http=http,
        pmcid="PMC12462478",
        retraction_index=rw.empty(),
    )
    ncbi_calls = [
        c for c in http.get_text.call_args_list
        if c.kwargs.get("source") == "ncbi_pmc_efetch"
    ]
    assert len(ncbi_calls) == 1
    params = ncbi_calls[0].kwargs["params"]
    assert params["id"] == "12462478"
    assert params["db"] == "pmc"
    assert params["rettype"] == "xml"
    assert ncbi_calls[0].args[0] == NCBI_PMC_EFETCH


def test_layer1_ncbi_api_key_in_params_when_env_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NCBI_API_KEY", "test-key-abc")
    http = _make_http(ncbi_fulltext=_GOOD_JATS_XML)
    fetch_fulltext(http=http, pmcid="PMC12462478", retraction_index=rw.empty())
    ncbi_call = [
        c for c in http.get_text.call_args_list
        if c.kwargs.get("source") == "ncbi_pmc_efetch"
    ][0]
    assert ncbi_call.kwargs["params"].get("api_key") == "test-key-abc"


def test_layer1_no_api_key_param_when_env_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    http = _make_http(ncbi_fulltext=_GOOD_JATS_XML)
    fetch_fulltext(http=http, pmcid="PMC12462478", retraction_index=rw.empty())
    ncbi_call = [
        c for c in http.get_text.call_args_list
        if c.kwargs.get("source") == "ncbi_pmc_efetch"
    ][0]
    assert "api_key" not in ncbi_call.kwargs["params"]


# ---------------------------------------------------------------------------
# Layer 2: EuropePMC fallback (when NCBI fails)
# ---------------------------------------------------------------------------


def test_layer2_europepmc_fallback_on_ncbi_404() -> None:
    http = _make_http(ncbi_fulltext=404, europepmc_fulltext=_GOOD_JATS_XML)
    paper = fetch_fulltext(
        http=http,
        pmcid="PMC12462478",
        retraction_index=rw.empty(),
    )
    assert paper.fulltext_fetch_source == "europepmc"
    assert paper.sections, "EuropePMC layer should populate sections"
    # EuropePMC was called exactly once.
    epmc_calls = [
        c for c in http.get_text.call_args_list
        if c.kwargs.get("source") == "europepmc_fulltext"
    ]
    assert len(epmc_calls) == 1
    # And the URL is the EuropePMC fullTextXML endpoint for this PMCID.
    assert epmc_calls[0].args[0] == EUROPEPMC_FULLTEXT.format(pmcid="PMC12462478")


def test_layer2_europepmc_fallback_on_ncbi_5xx() -> None:
    """5xx is also a recoverable status — should still fall through."""
    http = _make_http(ncbi_fulltext=503, europepmc_fulltext=_GOOD_JATS_XML)
    paper = fetch_fulltext(
        http=http,
        pmcid="PMC12462478",
        retraction_index=rw.empty(),
    )
    assert paper.fulltext_fetch_source == "europepmc"
    assert paper.sections


def test_layer2_europepmc_fallback_on_ncbi_empty_articleset() -> None:
    """NCBI's HTTP-200-with-empty-pmc-articleset means the article is
    not accessible via efetch — fall through to EuropePMC, not directly
    to abstract-only."""
    http = _make_http(
        ncbi_fulltext=_EMPTY_NCBI_ARTICLESET,
        europepmc_fulltext=_GOOD_JATS_XML,
    )
    paper = fetch_fulltext(
        http=http,
        pmcid="PMC12462478",
        retraction_index=rw.empty(),
    )
    assert paper.fulltext_fetch_source == "europepmc"
    assert paper.sections


def test_layer2_europepmc_fallback_on_ncbi_request_error() -> None:
    """Network failure against NCBI should not abort — try EuropePMC next."""
    http = _make_http(
        ncbi_fulltext=httpx.ConnectError("simulated network failure"),
        europepmc_fulltext=_GOOD_JATS_XML,
    )
    paper = fetch_fulltext(
        http=http,
        pmcid="PMC12462478",
        retraction_index=rw.empty(),
    )
    assert paper.fulltext_fetch_source == "europepmc"
    assert paper.sections


# ---------------------------------------------------------------------------
# Layer 3: abstract-only graceful degrade
# ---------------------------------------------------------------------------


def test_layer3_abstract_only_when_both_fulltexts_404() -> None:
    http = _make_http(ncbi_fulltext=404, europepmc_fulltext=404)
    paper = fetch_fulltext(
        http=http,
        pmcid="PMC12462478",
        retraction_index=rw.empty(),
    )
    assert paper.fulltext_fetch_source == "abstract_only"
    assert paper.sections == []
    assert paper.truncated_sections == []
    # Abstract still present — that's the whole point of the degrade.
    assert paper.abstract == _METADATA_PAYLOAD["resultList"]["result"][0]["abstractText"]
    # Other metadata still populated.
    assert paper.title == "A test article"  # trailing "." is stripped
    assert paper.pmc_id == "PMC12462478"


def test_layer3_abstract_only_when_ncbi_empty_and_europepmc_404() -> None:
    """If NCBI returns an empty articleset AND EuropePMC 404s, degrade."""
    http = _make_http(
        ncbi_fulltext=_EMPTY_NCBI_ARTICLESET,
        europepmc_fulltext=404,
    )
    paper = fetch_fulltext(
        http=http,
        pmcid="PMC12462478",
        retraction_index=rw.empty(),
    )
    assert paper.fulltext_fetch_source == "abstract_only"
    assert paper.sections == []


def test_layer3_abstract_only_when_europepmc_5xx() -> None:
    http = _make_http(ncbi_fulltext=404, europepmc_fulltext=503)
    paper = fetch_fulltext(
        http=http,
        pmcid="PMC12462478",
        retraction_index=rw.empty(),
    )
    assert paper.fulltext_fetch_source == "abstract_only"
    assert paper.sections == []


def test_layer3_abstract_only_when_europepmc_request_error() -> None:
    http = _make_http(
        ncbi_fulltext=404,
        europepmc_fulltext=httpx.ConnectError("simulated network failure"),
    )
    paper = fetch_fulltext(
        http=http,
        pmcid="PMC12462478",
        retraction_index=rw.empty(),
    )
    assert paper.fulltext_fetch_source == "abstract_only"
    assert paper.sections == []


# ---------------------------------------------------------------------------
# Metadata-search failure remains an error (not a degrade case)
# ---------------------------------------------------------------------------


def test_metadata_lookup_failure_still_raises() -> None:
    """If the EuropePMC SEARCH layer can't find the PMCID at all, we
    don't have abstract metadata to degrade to — keep the historical
    ``LookupError``. The metadata-search endpoint is independent of the
    fulltext-mirror promotion and remains EuropePMC-backed."""
    http = MagicMock()
    http.get_json.return_value = {"resultList": {"result": []}}

    with pytest.raises(LookupError):
        fetch_fulltext(
            http=http,
            pmcid="PMC99999999",
            retraction_index=rw.empty(),
        )


# ---------------------------------------------------------------------------
# PMCID normalization invariants
# ---------------------------------------------------------------------------


def test_url_normalization_lowercase_input() -> None:
    """``pmc12462478`` (no PMC prefix, lowercase) should still hit the
    upper-case-prefixed URLs / numeric NCBI id."""
    http = _make_http(ncbi_fulltext=_GOOD_JATS_XML)
    fetch_fulltext(
        http=http,
        pmcid="pmc12462478",
        retraction_index=rw.empty(),
    )
    ncbi_call = [
        c for c in http.get_text.call_args_list
        if c.kwargs.get("source") == "ncbi_pmc_efetch"
    ][0]
    # NCBI sees the numeric PMCID (PMC prefix stripped).
    assert ncbi_call.kwargs["params"]["id"] == "12462478"
