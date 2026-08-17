from accessible_surfaceome.agents.tag_site import runner as R
from accessible_surfaceome.agents.tag_site.schema import TagSiteProposal, TagSiteResult


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

    class P:
        title = "Ecto-tagged integrins"
        abstract = "We inserted ALFA after G101."
        year = 2017
    block = R.format_candidate_papers({28924207: P()})
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
