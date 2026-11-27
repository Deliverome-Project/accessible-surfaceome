"""Tests for PR 1: dedicated tag-site abstract triage, scoped discovery,
alias hygiene, web-search cache, and Claude 5.x Haiku position verification."""

from __future__ import annotations

import types
from typing import cast

from accessible_surfaceome.agents.tag_site import literature_discovery as ld
from accessible_surfaceome.agents.tag_site import literature_triage as lt
from accessible_surfaceome.agents.tag_site import position_verify as pv
from accessible_surfaceome.tools._shared.http import CachedHTTP


class _FakeBlock:
    def __init__(self, text: str, btype: str = "text"):
        self.text = text
        self.type = btype


class _FakeResp:
    def __init__(self, text: str, *, stop_reason: str = "end_turn"):
        self.content = [_FakeBlock(text)]
        self.stop_reason = stop_reason
        self.usage = None


def _paper(
    *,
    pmid: int | None = 123,
    doi: str | None = None,
    pmc_id: str | None = None,
    title: str = "BLAP tag in ECL2",
    abstract: str = "We inserted a BLAP tag in extracellular loop 2.",
):
    return types.SimpleNamespace(
        pmid=pmid,
        doi=doi,
        pmc_id=pmc_id,
        title=title,
        abstract=abstract,
        is_retracted=False,
        is_preprint=False,
    )


def test_clean_tag_site_aliases_drops_noise_and_keeps_stems() -> None:
    cleaned = ld.clean_tag_site_aliases(
        "ADRB2",
        ["BAR", "B2AR", "p90", "T9", "beta-2 adrenergic receptor", "Asthma susceptibility"],
        primary_name="Beta-2 adrenergic receptor",
    )
    assert "ADRB2" in cleaned
    assert "B2AR" in cleaned
    assert "Beta-2 adrenergic receptor" in cleaned
    assert "BAR" not in cleaned
    assert "p90" not in cleaned
    assert "T9" not in cleaned
    assert "Asthma susceptibility" not in cleaned

    stemmed = ld.clean_tag_site_aliases(
        "ASGR1",
        ["Asialoglycoprotein receptor 1", "Transmembrane protein 12"],
    )
    assert "Asialoglycoprotein receptor" in stemmed
    assert "Transmembrane protein" not in stemmed


def test_queries_use_title_abs_scoping_and_internal_only_drops_generic_gfp() -> None:
    q = ld.build_tag_site_query(["KCNN3", "SK3"])
    assert "TITLE_ABS:(" in q
    assert "BLAP" in q and "alpha-bungarotoxin" in q

    qs_all = ld.build_tag_site_queries(["KCNN3", "SK3"], internal_only=False)
    qs_int = ld.build_tag_site_queries(["KCNN3", "SK3"], internal_only=True)
    assert all("TITLE_ABS:(" in x for x in qs_all)
    assert all("TITLE_ABS:(" in x for x in qs_int)
    assert any("GFP" in x for x in qs_all)
    assert not any("mCherry" in x or '"GFP fusion"' in x for x in qs_int)
    assert any("BLAP" in x for x in qs_int)
    assert any("S3-S4" in x and "loop C" in x for x in qs_int)

    pq = ld.build_tag_site_preprint_query(["KCNN3", "SK3"])
    assert pq.startswith("SRC:PPR AND ")
    assert "EndoNB" in pq


def test_discover_records_citation_counts_and_preprint_pass(monkeypatch) -> None:
    seen_queries: list[str] = []

    def fake_search(*, http, query, page_size, sort=None):
        seen_queries.append(query)
        return {
            "resultList": {
                "result": [
                    {"pmid": "1001", "citedByCount": 42},
                    {"pmid": "1002", "pmcid": "PMC99", "citedByCount": "17"},
                ]
            }
        }

    monkeypatch.setattr(ld, "europepmc_search", fake_search)
    monkeypatch.setattr(
        ld,
        "papers_from_europepmc_records",
        lambda recs, **k: [
            _paper(pmid=1001),
            _paper(pmid=1002, pmc_id="PMC99"),
        ],
    )
    monkeypatch.setattr(ld, "pubtator_search", lambda **k: types.SimpleNamespace(hits=[]))
    monkeypatch.setattr(ld, "europepmc_bulk_by_pmid", lambda **k: [])

    cites: dict[str, int] = {}
    out = ld.discover_tag_site_papers(
        http=cast(CachedHTTP, object()),
        gene_symbol="KCNN3",
        aliases=["SK3", "BAR"],
        include_preprint_pass=True,
        citation_counts_out=cites,
    )
    assert set(out) == {"PMID:1001", "PMC:PMC99"}
    assert cites["PMID:1001"] == 42
    assert cites["PMC:PMC99"] == 17
    assert any(q.startswith("SRC:PPR") for q in seen_queries)
    assert all("BAR" not in q for q in seen_queries)


def test_web_search_cache_roundtrip_and_intent_invalidation(tmp_path) -> None:
    assert (
        ld.load_web_search_cache(
            "KCNN3", model="claude-haiku-5-5", max_uses=6, intent="loop", cache_dir=tmp_path
        )
        is None
    )
    ld.save_web_search_cache(
        "KCNN3",
        ["PMID:1", "DOI:10.1101/x"],
        model="claude-haiku-5-5",
        max_uses=6,
        intent="loop",
        cache_dir=tmp_path,
    )
    hit = ld.load_web_search_cache(
        "KCNN3", model="claude-haiku-5-5", max_uses=6, intent="loop", cache_dir=tmp_path
    )
    assert hit == ["DOI:10.1101/x", "PMID:1"]
    assert (
        ld.load_web_search_cache(
            "KCNN3", model="claude-haiku-5-5", max_uses=6, intent="other", cache_dir=tmp_path
        )
        is None
    )
    assert (
        ld.load_web_search_cache(
            "KCNN3", model="claude-sonnet-5-5", max_uses=6, intent="loop", cache_dir=tmp_path
        )
        is None
    )


def test_triage_passes_synonyms_scope_and_disables_thinking_on_haiku55(monkeypatch) -> None:
    captured: list[dict] = []

    def fake_call(client, **kwargs):
        captured.append(kwargs)
        return _FakeResp('```json\n{"paper_id": "PMID:123", "decision": "worth_fetching", "reason": "BLAP in ECL2"}\n```')

    monkeypatch.setattr(lt, "messages_create_with_backoff", fake_call)
    outcomes = lt.triage_tag_site_abstracts(
        object(),
        papers=[_paper(pmid=123, abstract="")],  # missing abstract still triaged via title
        gene="KCNN3",
        synonyms=["SK3", "KCa2.3"],
        internal_only=True,
        model="claude-haiku-5-5",
    )
    assert len(outcomes) == 1
    assert outcomes[0].error is None
    assert outcomes[0].response is not None
    assert outcomes[0].response.decision == "worth_fetching"
    assert captured[0]["thinking"] == {"type": "disabled"}
    user_text = captured[0]["messages"][0]["content"]
    assert "Also known as: SK3, KCa2.3" in user_text
    assert "SCOPE: internal extracellular loops ONLY" in user_text


def test_triage_handles_refusal_cleanly(monkeypatch) -> None:
    monkeypatch.setattr(
        lt,
        "messages_create_with_backoff",
        lambda client, **kw: _FakeResp("", stop_reason="refusal"),
    )
    outcomes = lt.triage_tag_site_abstracts(
        object(), papers=[_paper(pmid=55)], gene="KCNN3"
    )
    assert len(outcomes) == 1
    assert outcomes[0].response is None
    assert outcomes[0].error == "refusal"


def test_position_verify_disables_thinking_on_haiku55_and_falls_back_on_refusal(monkeypatch) -> None:
    captured: list[dict] = []

    def fake_call(client, **kwargs):
        captured.append(kwargs)
        return _FakeResp("141")

    monkeypatch.setattr(pv, "messages_create_with_backoff", fake_call)
    assert pv.verify_position_blind("An HA tag was inserted after Val-141.", client=object()) == 141
    assert captured[0]["thinking"] == {"type": "disabled"}

    # Refusal on Haiku 5.5 falls back once to Haiku 4.5.
    models_seen: list[str] = []

    def fake_refusal_then_ok(client, **kw):
        models_seen.append(kw["model"])
        if kw["model"] == pv.HAIKU_MODEL:
            return _FakeResp("", stop_reason="refusal")
        return _FakeResp("60")

    monkeypatch.setattr(pv, "messages_create_with_backoff", fake_refusal_then_ok)
    assert (
        pv.verify_position_blind("A myc tag was introduced at position G 60.", client=object())
        == 60
    )
    assert models_seen == [pv.HAIKU_MODEL, pv.FALLBACK_HAIKU_MODEL]

    # Refusal on both models returns None cleanly.
    monkeypatch.setattr(
        pv,
        "messages_create_with_backoff",
        lambda client, **kw: _FakeResp("141", stop_reason="refusal"),
    )
    assert pv.verify_position_blind("An HA tag was inserted after Val-141.", client=object()) is None


def test_residue_mentions_handles_jats_spaced_single_letter_codes() -> None:
    seq = "A" * 59 + "G" + "A" * 80 + "V" + "A" * 10
    text = "A myc sequence was introduced at position G 60 and at position V 141."
    assert ld.residue_mentions(text, sequence=seq) == {60, 141}
    # Lowercase English 'a 60' is not a residue code.
    assert ld.residue_mentions("after a 60 min incubation", sequence=seq) == set()


def test_europepmc_retry_backoff_ratelimit_and_fail_loud_guard(monkeypatch) -> None:
    import pytest

    from accessible_surfaceome.agents._support import web_literature as wl
    from accessible_surfaceome.tools._shared.http import DEFAULT_TIMEOUT, _retry_delay_s
    from accessible_surfaceome.tools._shared.ratelimit import default_limiter

    assert DEFAULT_TIMEOUT.read == 25.0
    assert default_limiter()._intervals_ms["www.ebi.ac.uk"] == 350.0
    d0 = _retry_delay_s(0)
    assert 1.0 <= d0 <= 1.75
    d_cap = _retry_delay_s(10)
    assert 8.0 <= d_cap <= 8.75
    d_ra = _retry_delay_s(0, retry_after="60")
    assert 15.0 <= d_ra <= 15.5

    # Single EuropePMC query failure degrades gracefully; >= half fails loudly.
    calls = {"n": 0}

    def flaky_once(*, http, query, page_size, sort=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient 503")
        return {"resultList": {"result": []}}

    monkeypatch.setattr(ld, "europepmc_search", flaky_once)
    monkeypatch.setattr(ld, "papers_from_europepmc_records", lambda recs, **k: [])
    monkeypatch.setattr(ld, "pubtator_search", lambda **k: types.SimpleNamespace(hits=[]))
    monkeypatch.setattr(ld, "europepmc_bulk_by_pmid", lambda **k: [])
    ld.discover_tag_site_papers(
        http=cast(CachedHTTP, object()),
        gene_symbol="KCNN3",
        aliases=["SK3"],
        faceted=True,
        internal_only=True,
    )

    def always_fail(*, http, query, page_size, sort=None):
        raise RuntimeError("Connection reset by peer")

    monkeypatch.setattr(ld, "europepmc_search", always_fail)
    with pytest.raises(RuntimeError, match="EuropePMC discovery degraded"):
        ld.discover_tag_site_papers(
            http=cast(CachedHTTP, object()),
            gene_symbol="KCNN3",
            aliases=["SK3"],
            faceted=True,
            internal_only=True,
        )

    # web_literature._hydrate_one survives a transient EuropePMC DOI error.
    from accessible_surfaceome.tools._shared.retraction_watch import empty as empty_retraction

    monkeypatch.setattr(wl, "europepmc_search", always_fail)
    monkeypatch.setattr(wl, "paper_from_preprint_doi", lambda *a, **k: None)
    cit = wl.WebCitation(doi="10.1101/2026.01.01.000001")
    assert (
        wl._hydrate_one(
            cit,
            http=cast(CachedHTTP, object()),
            retraction_index=empty_retraction(),
            include_preprints=True,
        )
        is None
    )
