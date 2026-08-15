from accessible_surfaceome.agents.tag_site import literature_discovery as ld
from accessible_surfaceome.agents.tag_site.schema import VALIDATION_LEVELS, VALIDATION_RANK


def test_query_expands_aliases_and_phrase_quotes():
    q = ld.build_tag_site_query(["KCNH2", "hERG", "Kv11.1"])
    assert "KCNH2" in q and "hERG" in q and '"Kv11.1"' not in q  # single word: unquoted
    q2 = ld.build_tag_site_query(["TFRC", "transferrin receptor"])
    assert '"transferrin receptor"' in q2  # multi-word alias is phrase-quoted
    assert "epitope tag" in q2 and "ecto-tagged" in q2 and "HiBiT" in q2  # methods vocab present
    assert " AND " in q2  # (aliases) AND (methods)


def test_source_tier_ranks_papers_over_patents_over_vendor():
    assert ld.source_tier("https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5603536/") == "paper"
    assert ld.source_tier("https://www.nature.com/articles/s41467-017-00646-w") == "paper"
    assert ld.source_tier("https://www.biorxiv.org/content/10.1101/2025.06.08.658482v1") == "paper"
    assert ld.source_tier("https://image-ppubs.uspto.gov/print/downloadPdf/9981047") == "patent"
    assert ld.source_tier("https://www.origene.com/catalog/cdna-clones/rc204499") == "vendor"
    assert ld.source_tier("https://www.alomone.com/p/anti-kv11-1-herg/APC-109") == "vendor"
    assert ld.source_tier("https://some-random-lab.edu/protocol") == "other"
    # rank order: paper best, vendor worst
    ranks = [ld.SOURCE_TIER_RANK[t] for t in ("paper", "patent", "other", "vendor")]
    assert ranks == sorted(ranks) and ranks[0] < ranks[-1]


def test_validation_levels_rank_surface_and_function_first():
    assert VALIDATION_LEVELS[0] == "surface_and_function"
    assert VALIDATION_LEVELS[-1] == "not_measured"
    assert VALIDATION_RANK["surface_and_function"] < VALIDATION_RANK["surface_only"]
    assert VALIDATION_RANK["surface_only"] < VALIDATION_RANK["not_measured"]


class _FakePaper:
    def __init__(self, pmid):
        self.pmid = pmid


def test_discover_unions_europepmc_and_pubtator_and_dedupes(monkeypatch):
    # EuropePMC returns pmids 1,2 (one non-integer preprint id that must be skipped);
    # PubTator returns 2 (dup) and 3 (new). Result must be {1,2,3}, deduped.
    monkeypatch.setattr(
        ld, "europepmc_search",
        lambda **k: {"resultList": {"result": [{"pmid": "1"}, {"pmid": "PPR9"}, {"pmid": "2"}]}},
    )

    def fake_paper_from_europepmc(rec, *, retraction_index, topic_tagger=None):
        pid = rec["pmid"]
        if not pid.isdigit():
            raise LookupError("preprint id")
        return _FakePaper(int(pid))

    monkeypatch.setattr(ld, "paper_from_europepmc", fake_paper_from_europepmc)

    class _Hits:
        hits = [type("H", (), {"pmid": 2})(), type("H", (), {"pmid": 3})()]

    monkeypatch.setattr(ld, "pubtator_search", lambda **k: _Hits())
    monkeypatch.setattr(ld, "build_gene_entity_query", lambda *a, **k: "q")
    monkeypatch.setattr(
        ld, "europepmc_bulk_by_pmid",
        lambda **k: [_FakePaper(p) for p in k["pmids"]],  # only pmid 3 passed (2 already seen)
    )

    out = ld.discover_tag_site_papers(http=object(), gene_symbol="X", aliases=["x protein"])
    assert set(out) == {1, 2, 3}
