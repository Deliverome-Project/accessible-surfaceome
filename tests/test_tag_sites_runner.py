from accessible_surfaceome.agents.tag_site import runner as R
import types

from accessible_surfaceome.agents.tag_site.schema import TagSiteProposal, TagSiteResult


def _paper(*, pmid=None, doi=None, pmc_id=None, title="", abstract="", year=None, is_preprint=False):
    # Minimal Paper stand-in carrying the fields paper_source_id + the prompt render read.
    return types.SimpleNamespace(pmid=pmid, doi=doi, pmc_id=pmc_id, title=title,
                                 abstract=abstract, year=year, is_preprint=is_preprint)


def _site(rank, *, ev="published tag insertion at this exact site",
          val="not_measured", tier="paper", res=100):
    return TagSiteProposal(
        rank=rank, site_type="internal", insert_after_residue=res,
        residue_before="A", residue_after="B", topology_state="extracellular",
        tag_type="ALFA", evidence_type=ev, position_evidence="validated",
        cited_tag_residue=res, evidence_detail="d",
        functional_or_expression_impact_measured="x",
        validation_level=val, source_tier=tier, supporting_pmid=123,
        rationale="r", confidence="high",
    )


def _result(sites):
    return TagSiteResult(gene_symbol="X", uniprot_accession="Q0", sequence_length=300, sites=sites)


def test_function_perturbed_ranks_below_surface_only():
    # a perturbed/confounded function (SLC6A4-style Vmax cut, ANO1-style confound) must
    # NOT outrank a clean surface_only display.
    from accessible_surfaceome.agents.tag_site.schema import VALIDATION_RANK
    assert VALIDATION_RANK["function_perturbed"] > VALIDATION_RANK["surface_only"]
    assert VALIDATION_RANK["function_perturbed"] < VALIDATION_RANK["not_measured"]
    out = R.rank_sites(_result([_site(1, val="function_perturbed", res=10),
                                _site(2, val="surface_only", res=20)]))
    assert [s.insert_after_residue for s in out.sites] == [20, 10]  # surface_only first


def test_rank_sites_drops_unvalidated_and_orders_by_validation_then_tier():
    a = _site(1, val="not_measured", tier="paper", res=10)
    b = _site(2, val="surface_and_function", tier="vendor", res=20)
    c = _site(3, ev="structural inference", res=30)          # dropped (not validated)
    d = _site(4, val="surface_and_function", tier="paper", res=40)
    out = R.rank_sites(_result([a, b, c, d]))
    residues = [s.insert_after_residue for s in out.sites]
    assert residues == [40, 20, 10]          # D (val+paper), B (val+vendor), A (not_measured)
    assert [s.rank for s in out.sites] == [1, 2, 3]   # renumbered
    assert 30 not in residues                # the structural-inference site is gone


def test_format_candidate_papers():
    assert "rely on web_search" in R.format_candidate_papers({})

    p = _paper(pmid=28924207, title="Ecto-tagged integrins",
               abstract="We inserted ALFA after G101.", year=2017)
    block = R.format_candidate_papers({"PMID:28924207": p})
    assert "PMID 28924207" in block and "Ecto-tagged integrins" in block


def test_run_tag_site_agent_composes_discovery_and_builder(monkeypatch):
    monkeypatch.setattr(R, "discover_tag_site_papers", lambda **k: {})
    captured = {}

    def fake_call_builder(client, **k):
        captured["label"] = k["label"]
        captured["has_web_tool"] = any(t.get("name") == "web_search" for t in k["tools"])
        captured["prompt"] = k["user_prompt"]
        return _result([_site(2, val="surface_only"), _site(1, val="not_measured", res=200)])

    monkeypatch.setattr(R, "call_builder", fake_call_builder)
    out = R.run_tag_site_agent(
        gene_symbol="X", protein_name="X protein", uniprot_accession="Q0",
        aliases=["x protein"], sequence="A" * 300, topology="O" * 300,
        client=object(), http=object(),
    )
    assert captured["label"] == "tag_site:X"
    assert captured["has_web_tool"] is True
    assert "CANDIDATE PAPERS" in captured["prompt"]
    # surface_only ranks above not_measured
    assert out.sites[0].validation_level == "surface_only"


def test_run_returns_empty_on_builder_failure(monkeypatch):
    monkeypatch.setattr(R, "discover_tag_site_papers", lambda **k: {})
    monkeypatch.setattr(R, "call_builder", lambda client, **k: None)
    out = R.run_tag_site_agent(
        gene_symbol="X", protein_name="X", uniprot_accession="Q0", aliases=[],
        sequence="AAA", topology="OOO", client=object(), http=object(),
    )
    assert out.sites == [] and out.sequence_length == 3


def test_to_viewer_sites_shape():
    out = R.to_viewer_sites(_result([_site(1, val="surface_and_function")]), uniprot_acc="Q0")
    s = out[0]
    assert s["provenance"] == "literature_retrieved"
    assert s["site_id"].endswith("-lit") and s["det_path"] is None
    assert s["topology_state"] == "O" and s["extracellular"] is True
    assert "validation: surface_and_function" in s["rationale"]
    assert s["sources"] == [{"pmid": 123, "citation": "PMID 123"}]
    assert s["residue_label"] == "A100"   # residue_before 'A' + insert_after 100


def test_residue_label_after_convention():
    # 'after N': residue immediately N-terminal to the junction (tag inserted AFTER it)
    p = _site(1, res=101)
    p.residue_before = "G"
    assert p.residue_label == "G101"
    from accessible_surfaceome.tag_sites.model import residue_label
    assert residue_label("G", 101) == "G101"
    assert residue_label(None, 101) is None   # before-residue-1 N-terminal tag


def test_format_candidate_papers_includes_fulltext():
    p = _paper(pmid=32996060, title="ASIC1a surface HA",
               abstract="We inserted HA into the ectodomain.", year=2020)
    block = R.format_candidate_papers(
        {"PMID:32996060": p},
        fulltext={"PMID:32996060": {"methods": "HA between D298 and L299.",
                                    "results": "acid-evoked current was reduced vs WT."}},
    )
    assert "METHODS: HA between D298 and L299." in block
    assert "RESULTS: acid-evoked current was reduced vs WT." in block
    assert "REDUCED/CONFOUNDED" in block  # the extraction instruction is present


def test_quote_supported_entailment():
    from accessible_surfaceome.agents.tag_site.literature_discovery import quote_supported
    src = "Methods: we inserted an ALFA tag after residue G101 in the extracellular loop."
    assert quote_supported("We inserted an ALFA tag after residue G101", src) is True
    assert quote_supported("a fabricated sentence that is nowhere in the source", src) is False
    assert quote_supported(None, src) is False
    assert quote_supported("too short", src) is False   # < 12 normalized chars


def test_verify_entailment_flags_hallucinated_quotes():
    p = _paper(pmid=11, abstract="We inserted an HA epitope after residue D298 in the ectodomain.")
    good = _site(1, val="surface_only", res=298)
    good.supporting_pmid = 11
    good.supporting_quote = "We inserted an HA epitope after residue D298"
    bad = _site(2, val="surface_and_function", res=147)
    bad.supporting_pmid = 11
    bad.supporting_quote = "This exact sentence never appears in any fetched source text"
    res = _result([good, bad])
    R.verify_entailment(res, papers={"PMID:11": p}, fulltext={})
    by_res = {s.insert_after_residue: s.entailment_verified for s in res.sites}
    assert by_res[298] is True and by_res[147] is False


def test_verify_entailment_tiebreak_in_ranking():
    # same validation+tier: the source-verified site ranks ahead of the unverified one.
    a = _site(1, val="surface_only", res=10); a.entailment_verified = False
    b = _site(2, val="surface_only", res=20); b.entailment_verified = True
    out = R.rank_sites(_result([a, b]))
    assert [s.insert_after_residue for s in out.sites] == [20, 10]


def test_format_candidate_papers_includes_preprint_papers():
    # Preprints are now IN the papers dict (DOI-anchored, is_preprint=True), keyed
    # on paper_source_id — no separate list. They render as DOI + [preprint].
    pp = _paper(doi="10.1101/2023.01.01", title="EndoNB ALFA knock-in",
                abstract="ALFA inserted after N100.", year=2023, is_preprint=True)
    block = R.format_candidate_papers({"DOI:10.1101/2023.01.01": pp})
    assert "DOI 10.1101/2023.01.01" in block
    assert "[preprint]" in block
    assert "EndoNB ALFA knock-in" in block


def test_verify_entailment_hydrates_web_cited_pmid(monkeypatch):
    # A site cites a PMID the candidate set never contained (agent found it via
    # web_search). With http given, verify_entailment hydrates that PMID on demand
    # and confirms the quote, instead of flagging a real citation unverified.
    hp = _paper(pmid=999,
                abstract="We introduced an HA tag in extracellular loop 2 of the serotonin transporter.")

    monkeypatch.setattr(R, "europepmc_bulk_by_pmid", lambda **k: [hp])
    monkeypatch.setattr(R, "fetch_fulltext_sections", lambda **k: {})

    site = _site(1, val="function_perturbed", res=243)
    site.supporting_pmid = 999
    site.supporting_quote = "We introduced an HA tag in extracellular loop 2"
    res = _result([site])
    R.verify_entailment(res, papers={}, fulltext={}, http=object())
    assert res.sites[0].entailment_verified is True

    # Without http, the same web-cited PMID cannot be fetched -> stays unverified.
    site2 = _site(1, res=243); site2.supporting_pmid = 999
    site2.supporting_quote = "We introduced an HA tag in extracellular loop 2"
    res2 = _result([site2])
    R.verify_entailment(res2, papers={}, fulltext={})
    assert res2.sites[0].entailment_verified is False
