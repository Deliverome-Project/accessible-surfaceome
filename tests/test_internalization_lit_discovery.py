from types import SimpleNamespace
from typing import Any, cast

from accessible_surfaceome.agents.internalization import literature_discovery as mod
from accessible_surfaceome.agents.internalization.literature_discovery import (
    build_internalization_query,
    build_kinetics_query,
    discover_internalization_papers,
)


def test_query_ors_aliases_and_ands_internalization_terms():
    q = build_internalization_query(["TFRC", "CD71", "TFR1"])
    assert "TFRC" in q and "CD71" in q
    assert "internali" in q.lower()
    assert "endocytos" in q.lower()


def test_kinetics_query_targets_quantitative_terms():
    q = build_kinetics_query(["TFRC", "CD71"])
    assert "TFRC" in q and "CD71" in q
    assert "rate constant" in q
    assert "half-time" in q or "half-life" in q


def test_multiword_aliases_are_phrase_quoted():
    # An unquoted multi-word alias parses as AND across fields and inflates the
    # match set ~50x, drowning the citation-sorted kinetics pass. Quote it.
    q = build_kinetics_query(["TFRC", "transferrin receptor"])
    assert '"transferrin receptor"' in q
    assert "TFRC" in q  # single-word alias stays unquoted


def test_discovery_runs_citation_sorted_kinetics_pass(monkeypatch):
    # The kinetics pass must query under CITATION sort — that's what surfaces the
    # heavily-cited classic rate-constant papers the recency-default misses.
    calls: list[tuple[str, object]] = []

    def _search(*, http, query, page_size=25, sort=None):
        calls.append((query, sort))
        return {"resultList": {"result": []}}

    monkeypatch.setattr(mod, "europepmc_search", _search)
    monkeypatch.setattr(
        mod, "paper_from_europepmc", lambda rec, **kw: _paper(int(rec["pmid"]))
    )
    monkeypatch.setattr(
        mod,
        "pubtator_search",
        lambda *, http, query, page=1, sort="score desc": SimpleNamespace(hits=[]),
    )
    monkeypatch.setattr(
        mod, "europepmc_bulk_by_pmid", lambda *, http, pmids, retraction_index, **kw: []
    )

    bundle = SimpleNamespace(hgnc_symbol="TFRC", aliases=[], previous_symbols=[],
        approved_name="transferrin receptor", alias_names=[])
    discover_internalization_papers(
        cast(Any, bundle), http=cast(Any, object()), retraction_index=cast(Any, object())
    )
    # exactly one europepmc_search call carries a CITED sort, and it's a kinetics query
    cited = [(q, s) for q, s in calls if s == "CITED desc"]
    assert len(cited) == 1
    assert "rate constant" in cited[0][0]


def test_kinetics_pass_uses_protein_name_not_noisy_short_symbols(monkeypatch):
    # The citation pass must query on the FULL name (what classic papers use) and
    # NOT the noisy short symbols (TR / T9 / p90) that drown it under CITED sort.
    calls: list[tuple[str, object]] = []

    def _search(*, http, query, page_size=25, sort=None):
        calls.append((query, sort))
        return {"resultList": {"result": []}}

    monkeypatch.setattr(mod, "europepmc_search", _search)
    monkeypatch.setattr(mod, "paper_from_europepmc", lambda rec, **kw: _paper(int(rec["pmid"])))
    monkeypatch.setattr(
        mod, "pubtator_search",
        lambda *, http, query, page=1, sort="score desc": SimpleNamespace(hits=[]),
    )
    monkeypatch.setattr(
        mod, "europepmc_bulk_by_pmid", lambda *, http, pmids, retraction_index, **kw: []
    )

    bundle = SimpleNamespace(
        hgnc_symbol="TFRC",
        aliases=["TR", "T9", "p90", "CD71"],  # noisy short symbols
        previous_symbols=[],
        approved_name="transferrin receptor",
        alias_names=[],
    )
    discover_internalization_papers(
        cast(Any, bundle), http=cast(Any, object()), retraction_index=cast(Any, object())
    )
    kinetics_q = next(q for q, s in calls if s == "CITED desc")
    assert '"transferrin receptor"' in kinetics_q  # full name drives the pass
    # noisy short symbols must NOT be in the citation-sorted query
    for noisy in (" TR ", " T9 ", " p90 "):
        assert noisy not in f" {kinetics_q} "
    # but the broad (recency) queries still use the full symbol set incl. noisy ones
    broad = " ".join(q for q, s in calls if s is None)
    assert "T9" in broad


def _paper(pmid):
    return SimpleNamespace(pmid=pmid)


def test_discovery_unions_and_dedupes_by_pmid(monkeypatch):
    monkeypatch.setattr(
        mod,
        "europepmc_search",
        lambda *, http, query, page_size=25, sort=None: {
            "resultList": {"result": [{"pmid": "1"}, {"pmid": "2"}]}
        },
    )
    monkeypatch.setattr(
        mod,
        "paper_from_europepmc",
        lambda rec, *, retraction_index, topic_tagger=None: _paper(int(rec["pmid"])),
    )
    monkeypatch.setattr(
        mod,
        "pubtator_search",
        lambda *, http, query, page=1, sort="score desc": SimpleNamespace(
            hits=[SimpleNamespace(pmid=2), SimpleNamespace(pmid=3)]
        ),
    )
    monkeypatch.setattr(
        mod,
        "europepmc_bulk_by_pmid",
        lambda *, http, pmids, retraction_index, topic_tagger=None: [
            _paper(p) for p in pmids
        ],
    )

    bundle = SimpleNamespace(hgnc_symbol="TFRC", aliases=["CD71"], previous_symbols=[],
        approved_name="transferrin receptor", alias_names=[])
    out = discover_internalization_papers(
        cast(Any, bundle), http=cast(Any, object()), retraction_index=cast(Any, object())
    )
    assert set(out) == {1, 2, 3}  # deduped: 2 came from both sources


def test_discovery_skips_records_with_non_integer_pmid(monkeypatch):
    # EuropePMC returns preprint records whose PMID is non-integer (e.g.
    # "PPR1220047"); paper_from_europepmc raises LookupError on those. One bad
    # record must be skipped, not abort the whole discovery.
    monkeypatch.setattr(
        mod,
        "europepmc_search",
        lambda *, http, query, page_size=25, sort=None: {
            "resultList": {"result": [{"pmid": "PPR1220047"}, {"pmid": "5"}]}
        },
    )

    def _coerce(rec, *, retraction_index, topic_tagger=None):
        if not rec["pmid"].isdigit():
            raise LookupError(f"non-integer PMID: {rec['pmid']!r}")
        return _paper(int(rec["pmid"]))

    monkeypatch.setattr(mod, "paper_from_europepmc", _coerce)
    monkeypatch.setattr(
        mod,
        "pubtator_search",
        lambda *, http, query, page=1, sort="score desc": SimpleNamespace(hits=[]),
    )
    monkeypatch.setattr(
        mod,
        "europepmc_bulk_by_pmid",
        lambda *, http, pmids, retraction_index, topic_tagger=None: [],
    )

    bundle = SimpleNamespace(hgnc_symbol="TFRC", aliases=[], previous_symbols=[],
        approved_name="transferrin receptor", alias_names=[])
    out = discover_internalization_papers(
        cast(Any, bundle), http=cast(Any, object()), retraction_index=cast(Any, object())
    )
    assert set(out) == {5}  # preprint record skipped, integer-PMID record kept
