from types import SimpleNamespace
from typing import Any, cast

from accessible_surfaceome.agents.internalization import literature_discovery as mod
from accessible_surfaceome.agents.internalization.literature_discovery import (
    build_internalization_query,
    discover_internalization_papers,
)


def test_query_ors_aliases_and_ands_internalization_terms():
    q = build_internalization_query(["TFRC", "CD71", "TFR1"])
    assert "TFRC" in q and "CD71" in q
    assert "internali" in q.lower()
    assert "endocytos" in q.lower()


def _paper(pmid):
    return SimpleNamespace(pmid=pmid)


def test_discovery_unions_and_dedupes_by_pmid(monkeypatch):
    monkeypatch.setattr(
        mod,
        "europepmc_search",
        lambda *, http, query, page_size=25: {
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

    bundle = SimpleNamespace(hgnc_symbol="TFRC", aliases=["CD71"], previous_symbols=[])
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
        lambda *, http, query, page_size=25: {
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

    bundle = SimpleNamespace(hgnc_symbol="TFRC", aliases=[], previous_symbols=[])
    out = discover_internalization_papers(
        cast(Any, bundle), http=cast(Any, object()), retraction_index=cast(Any, object())
    )
    assert set(out) == {5}  # preprint record skipped, integer-PMID record kept
