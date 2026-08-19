from accessible_surfaceome.agents.tag_site import literature_discovery as ld
from accessible_surfaceome.agents.tag_site.schema import VALIDATION_LEVELS, VALIDATION_RANK


def test_query_expands_aliases_and_phrase_quotes():
    q = ld.build_tag_site_query(["KCNH2", "hERG", "Kv11.1"])
    assert "KCNH2" in q and "hERG" in q and '"Kv11.1"' not in q  # single word: unquoted
    q2 = ld.build_tag_site_query(["TFRC", "transferrin receptor"])
    assert '"transferrin receptor"' in q2  # multi-word alias is phrase-quoted
    assert "epitope tag" in q2 and "ecto-tagged" in q2 and "HiBiT" in q2  # methods vocab present
    assert " AND " in q2  # (aliases) AND (methods)



def test_validation_levels_rank_surface_and_function_first():
    assert VALIDATION_LEVELS[0] == "surface_and_function"
    assert VALIDATION_LEVELS[-1] == "not_measured"
    assert VALIDATION_RANK["surface_and_function"] < VALIDATION_RANK["surface_only"]
    assert VALIDATION_RANK["surface_only"] < VALIDATION_RANK["not_measured"]


class _FakePaper:
    def __init__(self, pmid=None, doi=None, pmc_id=None, is_preprint=False):
        self.pmid = pmid
        self.doi = doi
        self.pmc_id = pmc_id
        self.is_retracted = False
        self.is_preprint = is_preprint


def test_discover_keys_on_source_id_keeps_preprints_and_dedupes(monkeypatch):
    # EuropePMC returns pmid 1, a DOI-anchored PREPRINT (now KEPT via the shared
    # include_preprints contract), and pmid 2; PubTator adds 2 (dup) + 3 (new).
    # The corpus is keyed on paper_source_id (PMC>PMID>DOI), not integer pmid.
    monkeypatch.setattr(
        ld, "europepmc_search",
        lambda **k: {"resultList": {"result": [{"pmid": "1"}, {"id": "PPR9"}, {"pmid": "2"}]}},
    )

    def fake_records(records, *, retraction_index, topic_tagger=None, context, include_preprints=False):
        out = []
        for rec in records:
            pid = rec.get("pmid")
            if pid and pid.isdigit():
                out.append(_FakePaper(pmid=int(pid)))
            elif include_preprints:  # the PPR record -> DOI-anchored preprint, kept
                out.append(_FakePaper(doi="10.1101/preprint9", is_preprint=True))
        return out

    monkeypatch.setattr(ld, "papers_from_europepmc_records", fake_records)

    class _Hits:
        hits = [type("H", (), {"pmid": 2})(), type("H", (), {"pmid": 3})()]

    monkeypatch.setattr(ld, "pubtator_search", lambda **k: _Hits())
    monkeypatch.setattr(ld, "build_gene_entity_query", lambda *a, **k: "q")
    monkeypatch.setattr(
        ld, "europepmc_bulk_by_pmid",
        lambda **k: [_FakePaper(pmid=p) for p in k["pmids"]],  # only pmid 3 (2 already seen)
    )

    out = ld.discover_tag_site_papers(http=object(), gene_symbol="X", aliases=["x protein"])
    assert set(out) == {"PMID:1", "PMID:2", "PMID:3", "DOI:10.1101/preprint9"}
    assert any(p.is_preprint for p in out.values())  # the preprint was KEPT, not skipped
