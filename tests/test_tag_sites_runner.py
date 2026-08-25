from accessible_surfaceome.agents.tag_site import runner as R
import types

from accessible_surfaceome.agents.tag_site.schema import TagSiteProposal, TagSiteResult
from typing import cast
from anthropic import Anthropic
from accessible_surfaceome.tools._shared.http import CachedHTTP


def _paper(*, pmid=None, doi=None, pmc_id=None, title="", abstract="", year=None, is_preprint=False):
    # Minimal Paper stand-in carrying the fields paper_source_id + discovery read.
    return types.SimpleNamespace(pmid=pmid, doi=doi, pmc_id=pmc_id, title=title,
                                 abstract=abstract, year=year, is_preprint=is_preprint)


def _evi(quote, *, source_id="PMID:11", claim="tag inserted at this site", verified=True):
    # Duck-typed Evidence stand-in: the runner only reads .spans[0].source.source_id,
    # .spans[0].quote, .claim, .entailment_verified (the real pydantic Evidence has
    # ~8 required fields, so a namespace keeps these tests focused on runner logic).
    span = types.SimpleNamespace(source=types.SimpleNamespace(source_id=source_id), quote=quote)
    return types.SimpleNamespace(
        evidence_id="tag_evi_1", claim=claim, spans=[span], entailment_verified=verified
    )


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


def test_format_evidence_ledger():
    # empty ledger -> instruction to return zero sites
    assert "EMPTY sites list" in R.format_evidence_ledger([])

    # a PMID-keyed clip surfaces the numeric PMID + its verbatim quote
    block = R.format_evidence_ledger([
        _evi("We inserted ALFA after G101 in the ectodomain.", source_id="PMID:28924207",
             claim="ALFA inserted after G101 displayed on the surface"),
    ])
    assert "PMID 28924207" in block
    assert "We inserted ALFA after G101 in the ectodomain." in block
    assert "ALFA inserted after G101 displayed on the surface" in block

    # a preprint (DOI source_id, no PMID) is cited by DOI so the model sets supporting_pmid=null
    pp = R.format_evidence_ledger([
        _evi("ALFA inserted after N100.", source_id="DOI:10.1101/2023.01.01"),
    ])
    assert "DOI:10.1101/2023.01.01" in pp


def test_run_tag_site_agent_composes_pipeline_and_synthesis(monkeypatch):
    # Discovery + web complement feed the shared clip pipeline; the span-verified
    # evidence ledger (NOT raw papers) reaches the synthesis prompt.
    monkeypatch.setattr(R, "discover_tag_site_papers",
                        lambda **k: {"PMID:55501": _paper(pmid=55501, title="Web ALFA knock-in")})
    monkeypatch.setattr(R, "web_discover_papers", lambda *a, **k: [])
    monkeypatch.setattr(R, "triage_abstracts", lambda *a, **k: [])
    monkeypatch.setattr(R, "build_pool", lambda *a, **k: ({}, []))
    monkeypatch.setattr(R, "build_source_store", lambda *a, **k: object())
    monkeypatch.setattr(R, "select_clips", lambda *a, **k: object())
    monkeypatch.setattr(
        R, "promote",
        lambda *a, **k: [_evi("ALFA inserted in the ectodomain after G101.", source_id="PMID:55501")],
    )
    captured = {}

    def fake_call_builder(client, **k):
        captured["label"] = k["label"]
        captured["prompt"] = k["user_prompt"]
        return _result([_site(2, val="surface_only"), _site(1, val="not_measured", res=200)])

    monkeypatch.setattr(R, "call_builder", fake_call_builder)
    out = R.run_tag_site_agent(
        gene_symbol="X", protein_name="X protein", uniprot_accession="Q0",
        aliases=["x protein"], sequence="A" * 300, topology="O" * 300,
        client=cast(Anthropic, object()), http=cast(CachedHTTP, object()),
    )
    assert captured["label"] == "tag_site:X"
    assert "EVIDENCE LEDGER" in captured["prompt"]
    assert "PMID 55501" in captured["prompt"]       # the span-verified clip's source
    assert out.sites[0].validation_level == "surface_only"  # ranks above not_measured


def test_run_returns_empty_when_no_evidence(monkeypatch):
    # No span-verified tag-insertion clip -> ZERO sites, WITHOUT a synthesis call.
    monkeypatch.setattr(R, "discover_tag_site_papers", lambda **k: {"PMID:1": _paper(pmid=1)})
    monkeypatch.setattr(R, "web_discover_papers", lambda *a, **k: [])
    monkeypatch.setattr(R, "triage_abstracts", lambda *a, **k: [])
    monkeypatch.setattr(R, "build_pool", lambda *a, **k: ({}, []))
    monkeypatch.setattr(R, "build_source_store", lambda *a, **k: object())
    monkeypatch.setattr(R, "select_clips", lambda *a, **k: object())
    monkeypatch.setattr(R, "promote", lambda *a, **k: [])

    def _boom(*a, **k):
        raise AssertionError("call_builder must not run with an empty ledger")

    monkeypatch.setattr(R, "call_builder", _boom)
    out = R.run_tag_site_agent(
        gene_symbol="X", protein_name="X", uniprot_accession="Q0", aliases=[],
        sequence="AAA", topology="OOO", client=cast(Anthropic, object()), http=cast(CachedHTTP, object()),
    )
    assert out.sites == [] and out.sequence_length == 3


def test_run_returns_empty_on_no_papers(monkeypatch):
    # Nothing discovered -> empty result without touching the pipeline.
    monkeypatch.setattr(R, "discover_tag_site_papers", lambda **k: {})
    monkeypatch.setattr(R, "web_discover_papers", lambda *a, **k: [])

    def _boom(*a, **k):
        raise AssertionError("pipeline must not run with no papers")

    monkeypatch.setattr(R, "triage_abstracts", _boom)
    out = R.run_tag_site_agent(
        gene_symbol="X", protein_name="X", uniprot_accession="Q0", aliases=[],
        sequence="AAAA", topology="OOOO", client=cast(Anthropic, object()), http=cast(CachedHTTP, object()),
    )
    assert out.sites == [] and out.sequence_length == 4


def test_run_returns_empty_on_builder_failure(monkeypatch):
    monkeypatch.setattr(R, "discover_tag_site_papers", lambda **k: {"PMID:1": _paper(pmid=1)})
    monkeypatch.setattr(R, "web_discover_papers", lambda *a, **k: [])
    monkeypatch.setattr(R, "triage_abstracts", lambda *a, **k: [])
    monkeypatch.setattr(R, "build_pool", lambda *a, **k: ({}, []))
    monkeypatch.setattr(R, "build_source_store", lambda *a, **k: object())
    monkeypatch.setattr(R, "select_clips", lambda *a, **k: object())
    monkeypatch.setattr(R, "promote", lambda *a, **k: [_evi("ALFA after G101.", source_id="PMID:1")])
    monkeypatch.setattr(R, "call_builder", lambda client, **k: None)
    out = R.run_tag_site_agent(
        gene_symbol="X", protein_name="X", uniprot_accession="Q0", aliases=[],
        sequence="AAA", topology="OOO", client=cast(Anthropic, object()), http=cast(CachedHTTP, object()),
    )
    assert out.sites == [] and out.sequence_length == 3


def test_to_viewer_sites_shape():
    out = R.to_viewer_sites(_result([_site(1, val="surface_and_function")]), uniprot_acc="Q0")
    s = out[0]
    assert s["provenance"] == "literature_retrieved"
    assert s["site_id"].endswith("-lit") and s["det_path"] is None
    assert s["topology_state"] == "O" and s["extracellular"] is True
    assert "validation: surface_and_function" in s["rationale"]
    assert s["sources"] == [{"pmid": 123, "citation": "PMID 123", "claim": None}]
    # supporting_quote rides in the source's claim (drives the drawer quote)
    q = _site(1, val="surface_and_function")
    q.supporting_quote = "We inserted an ALFA tag after G100"
    qs = R.to_viewer_sites(_result([q]), uniprot_acc="Q0")[0]
    assert qs["sources"][0]["claim"] == "We inserted an ALFA tag after G100"
    assert s["residue_label"] == "A100"   # residue_before 'A' + insert_after 100


def test_residue_label_after_convention():
    # 'after N': residue immediately N-terminal to the junction (tag inserted AFTER it)
    p = _site(1, res=101)
    p.residue_before = "G"
    assert p.residue_label == "G101"
    from accessible_surfaceome.tag_sites.model import residue_label
    assert residue_label("G", 101) == "G101"
    assert residue_label(None, 101) is None   # before-residue-1 N-terminal tag


def test_quote_supported_entailment():
    from accessible_surfaceome.agents.tag_site.literature_discovery import quote_supported
    src = "Methods: we inserted an ALFA tag after residue G101 in the extracellular loop."
    assert quote_supported("We inserted an ALFA tag after residue G101", src) is True
    assert quote_supported("a fabricated sentence that is nowhere in the source", src) is False
    assert quote_supported(None, src) is False
    assert quote_supported("too short", src) is False   # < 12 normalized chars


def test_verify_entailment_flags_hallucinated_quotes():
    # The ledger is the span-verified source: a site whose quote is IN the ledger
    # passes; a hallucinated quote (nowhere in the ledger) is flagged.
    evidence = [_evi("We inserted an HA epitope after residue D298 in the ectodomain.",
                     source_id="PMID:11")]
    good = _site(1, val="surface_only", res=298)
    good.supporting_quote = "We inserted an HA epitope after residue D298"
    bad = _site(2, val="surface_and_function", res=147)
    bad.supporting_quote = "This exact sentence never appears in any fetched source text"
    res = _result([good, bad])
    R.verify_entailment(res, evidence=evidence)
    by_res = {s.insert_after_residue: s.entailment_verified for s in res.sites}
    assert by_res[298] is True and by_res[147] is False


def test_verify_entailment_tiebreak_in_ranking():
    # same validation+tier: the source-verified site ranks ahead of the unverified one.
    a = _site(1, val="surface_only", res=10)
    a.entailment_verified = False
    b = _site(2, val="surface_only", res=20)
    b.entailment_verified = True
    out = R.rank_sites(_result([a, b]))
    assert [s.insert_after_residue for s in out.sites] == [20, 10]
