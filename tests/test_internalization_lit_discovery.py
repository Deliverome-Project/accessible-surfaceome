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
    # pmc_id/doi present (None) so paper_source_id() can read them.
    return SimpleNamespace(pmid=pmid, pmc_id=None, doi=None, is_preprint=False)


def _preprint(doi):
    # A DOI-only preprint: no PMID, anchored on its DOI.
    return SimpleNamespace(pmid=None, pmc_id=None, doi=doi, is_preprint=True)


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
        lambda rec, **kw: _paper(int(rec["pmid"])),
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
    # Keyed on paper_source_id (PMC>PMID>DOI); 2 came from both sources → deduped.
    assert set(out) == {"PMID:1", "PMID:2", "PMID:3"}


def test_discovery_keeps_doi_anchored_preprints(monkeypatch):
    # EuropePMC returns preprint (SRC:PPR) records with a non-integer id and a
    # DOI. The internalization discovery opts into preprints
    # (include_preprints=True), so a DOI-anchored preprint is KEPT (keyed on its
    # DOI), alongside the integer-PMID record. A no-DOI record still raises
    # LookupError and is skipped without aborting the batch.
    monkeypatch.setattr(
        mod,
        "europepmc_search",
        lambda *, http, query, page_size=25, sort=None: {
            "resultList": {
                "result": [
                    {"pmid": "PPR1220047", "doi": "10.1101/2025.06.08.658482"},
                    {"pmid": None},  # no id, no doi → skipped
                    {"pmid": "5"},
                ]
            }
        },
    )

    def _coerce(rec, *, retraction_index, include_preprints=False, topic_tagger=None):
        raw = rec.get("pmid")
        if raw is not None and str(raw).isdigit():
            return _paper(int(raw))
        # non-integer / missing id: keep only as a DOI-anchored preprint when
        # the caller opted in (mirrors the real paper_from_europepmc gate).
        if include_preprints and rec.get("doi"):
            return _preprint(rec["doi"])
        raise LookupError(f"no numeric PMID: {raw!r}")

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
    # Preprint kept (DOI key), integer-PMID kept, no-DOI record skipped.
    assert set(out) == {"DOI:10.1101/2025.06.08.658482", "PMID:5"}
