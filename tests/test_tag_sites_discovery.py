"""Discovery: several narrow queries, unioned, and remembered across runs.

One monolithic `(aliases) AND (every method term OR'd together)` query gets a
single relevance ranking and a single top-N cut, so a paper matching one narrow
facet competes against everything. Splitting by facet gives each its own top-N.

And discovery is non-deterministic where it matters: the EndoNB preprint was
retrieved on one run of TMEM123 and absent from the next, with identical code
and a warm cache. Its abstract names none of the five genes it tags, so only the
web-search leg can reach it at all. Caching the per-gene union means a paper
found once is never lost again.
"""
from typing import cast

from accessible_surfaceome.agents.tag_site.literature_discovery import (
    build_tag_site_queries,
    merge_discovery_cache,
)
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import Paper


def test_several_distinct_queries_are_built():
    qs = build_tag_site_queries(["TFRC", "transferrin receptor"])
    assert len(qs) >= 4
    assert len(set(qs)) == len(qs)          # no duplicates


def test_every_query_scopes_to_the_gene_aliases():
    for q in build_tag_site_queries(["TFRC", "transferrin receptor"]):
        assert "TFRC" in q
        assert '"transferrin receptor"' in q   # multi-word aliases stay phrases


def test_the_facets_cover_distinct_tagging_modalities():
    """A paper is findable by the modality it used, not only by the word 'tag'."""
    joined = " ".join(build_tag_site_queries(["X"])).lower()
    for modality in ("epitope", "knock-in", "fluorescent", "surface", "insertion"):
        assert modality in joined, modality


def test_cache_merge_keeps_a_paper_a_later_run_missed():
    """The EndoNB case: present one run, gone the next."""
    cached = {"PMID:1": {"pmid": 1}, "DOI:10.1101/x": {"doi": "10.1101/x"}}
    fresh = {"PMID:1": {"pmid": 1}, "PMID:2": {"pmid": 2}}
    merged = merge_discovery_cache(cached=cached, fresh=fresh)
    assert set(merged) == {"PMID:1", "PMID:2", "DOI:10.1101/x"}


def test_fresh_results_win_on_collision():
    """A re-fetched record may be richer (a preprint that since got a PMCID)."""
    merged = merge_discovery_cache(
        cached={"PMID:1": {"pmid": 1, "pmc_id": None}},
        fresh={"PMID:1": {"pmid": 1, "pmc_id": "PMC9"}},
    )
    assert merged["PMID:1"]["pmc_id"] == "PMC9"


def test_merging_an_empty_cache_is_just_the_fresh_set():
    fresh = {"PMID:2": {"pmid": 2}}
    assert merge_discovery_cache(cached={}, fresh=fresh) == fresh


# --- wiring: several queries per gene, and the cache is unioned ---------------

def test_discovery_issues_one_query_per_facet_plus_the_broad_pass(monkeypatch):
    from accessible_surfaceome.agents.tag_site import literature_discovery as LD
    seen = []

    def fake_search(*, http, query, page_size, sort=None):
        seen.append((query, sort))
        return {"resultList": {"result": []}}

    monkeypatch.setattr(LD, "europepmc_search", fake_search)
    monkeypatch.setattr(LD, "papers_from_europepmc_records", lambda *a, **k: [])
    monkeypatch.setattr(LD, "pubtator_search",
                        lambda **k: type("R", (), {"hits": []})())
    monkeypatch.setattr(LD, "europepmc_bulk_by_pmid", lambda **k: [])

    LD.discover_tag_site_papers(http=cast(CachedHTTP, object()),
                                gene_symbol="TFRC", aliases=["TfR1"])

    assert len(seen) >= 6, seen                       # broad x2 sorts + per-facet
    assert any(s == "CITED desc" for _, s in seen)    # the citation pass survives
    assert len({q for q, _ in seen}) >= 5             # genuinely distinct queries


def test_discovery_unions_a_supplied_cache(monkeypatch):
    """A paper the cache remembers is returned even when this run misses it."""
    from accessible_surfaceome.agents.tag_site import literature_discovery as LD
    monkeypatch.setattr(LD, "europepmc_search",
                        lambda **k: {"resultList": {"result": []}})
    monkeypatch.setattr(LD, "papers_from_europepmc_records", lambda *a, **k: [])
    monkeypatch.setattr(LD, "pubtator_search",
                        lambda **k: type("R", (), {"hits": []})())
    monkeypatch.setattr(LD, "europepmc_bulk_by_pmid", lambda **k: [])

    remembered = {"DOI:10.1101/2025.06.08.658482": cast(Paper, object())}
    out = LD.discover_tag_site_papers(
        http=cast(CachedHTTP, object()), gene_symbol="TMEM123", aliases=["Porimin"],
        cached=remembered,
    )
    assert "DOI:10.1101/2025.06.08.658482" in out


# --- persistence --------------------------------------------------------------

def test_cache_round_trips_through_disk(tmp_path):
    from accessible_surfaceome.agents.tag_site.literature_discovery import (
        load_discovery_cache, save_discovery_cache,
    )
    from accessible_surfaceome.tools._shared.models import Paper
    papers = {
        "DOI:10.1101/2025.06.08.658482": Paper(
            pmid=None, doi="10.1101/2025.06.08.658482", pmc_id=None,
            title="EndoNB", abstract="", year=2025, is_preprint=True),
    }
    save_discovery_cache("TMEM123", papers, cache_dir=tmp_path)
    back = load_discovery_cache("TMEM123", cache_dir=tmp_path)
    assert set(back) == set(papers)
    assert back["DOI:10.1101/2025.06.08.658482"].doi == "10.1101/2025.06.08.658482"


def test_loading_a_cache_that_does_not_exist_is_empty_not_an_error(tmp_path):
    from accessible_surfaceome.agents.tag_site.literature_discovery import load_discovery_cache
    assert load_discovery_cache("NOSUCHGENE", cache_dir=tmp_path) == {}


def test_a_corrupt_cache_file_is_ignored_rather_than_crashing_the_run(tmp_path):
    from accessible_surfaceome.agents.tag_site.literature_discovery import load_discovery_cache
    (tmp_path / "TMEM123.json").write_text("{not json")
    assert load_discovery_cache("TMEM123", cache_dir=tmp_path) == {}
