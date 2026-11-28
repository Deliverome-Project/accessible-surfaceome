"""Tests for PR 2: loop-aware relevance & alternate-frame boosting,
worth_fetching / pool / synthesis caps, adaptive Haiku 5.5 web scout,
1-hop construct-citation follow-up, prompt decontamination, and Claude 5.5 wiring."""

from __future__ import annotations

import types
from typing import cast

from anthropic import Anthropic

from accessible_surfaceome.agents.plan_trim_select.abstract_triage import TriageOutcome
from accessible_surfaceome.agents.plan_trim_select.schemas import AbstractTriageResponse
from accessible_surfaceome.agents.tag_site import literature_discovery as ld
from accessible_surfaceome.agents.tag_site import reference_followup as rf
from accessible_surfaceome.agents.tag_site import runner as R
from accessible_surfaceome.agents.tag_site.frames import Frame
from accessible_surfaceome.agents.tag_site.schema import TagSiteResult
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import EvidenceClaimDraft


def _clip(quote: str, score: float = 1.0, source_id: str = "PMC:PMC1", context: str | None = None):
    return types.SimpleNamespace(
        quote=quote,
        context_excerpt=context,
        score=score,
        source_id=source_id,
        section="methods",
    )


def test_boost_lifts_alternate_frame_residue_and_named_loop_and_demotes_cyto_gfp() -> None:
    # Member sequence has a 10-aa N-terminal extension relative to canonical.
    # Canonical residue K25 maps to member residue 35 (in extracellular loop O).
    canonical = "M" * 24 + "K" + "G" * 25  # len 50, K at 25
    member = "A" * 10 + canonical           # len 60, K at 35
    topo = "I" * 10 + "M" * 15 + "O" * 20 + "M" * 15  # 26-45 is extracellular loop

    pool = {
        "alt_res": _clip("An HA epitope tag was inserted after Lys-25 in the loop", 0.5),
        "loop_only": _clip("An ALFA tag was inserted into extracellular loop 2 (ECL2)", 0.5),
        "cyto_gfp": _clip("A C-terminal GFP fusion was constructed to track expression", 5.0),
        "plain": _clip("Cells were grown in DMEM medium", 1.0),
    }
    frames = [
        Frame(label="member", sequence=member, offset=0),
        Frame(label="canonical", sequence=canonical, offset=10, expected=True),
    ]
    boosted = ld.boost_residue_clips(
        pool, sequence=member, topology=topo, alternate_frames=frames, internal_only=True
    )
    assert "alt_res" in boosted
    assert 35 in boosted["alt_res"]
    # Tier ordering: residue-pinned > loop-only > plain > demoted cytoplasmic GFP
    assert pool["alt_res"].score > pool["loop_only"].score > pool["plain"].score > pool["cyto_gfp"].score


def test_tag_site_relevance_penalizes_terminal_gfp_when_internal_only() -> None:
    rel = R.tag_site_relevance("M" * 50, internal_only=True)
    loop_s = rel("We inserted an HA tag into the second extracellular loop (ECL2).")
    gfp_s = rel("C-terminal GFP fusion was expressed in HEK293 cells.")
    assert loop_s > gfp_s


def test_cap_worth_fetching_ranks_by_relevance_and_citations_and_keeps_pinned() -> None:
    papers = {
        "PMID:1": types.SimpleNamespace(title="C-terminal GFP localization", abstract="C-terminal GFP fusion", pmc_id="PMC1"),
        "PMID:2": types.SimpleNamespace(title="HA tag in extracellular loop 2", abstract="inserted an HA tag into ECL2", pmc_id=None),
        "PMID:3": types.SimpleNamespace(title="Classic topology study", abstract="epitope tag study", pmc_id="PMC3"),
        "PMID:4": types.SimpleNamespace(title="User pinned paper", abstract="brief note", pmc_id=None),
    }
    outcomes = [
        TriageOutcome(
            paper_id=pid,
            response=AbstractTriageResponse(paper_id=pid, decision="worth_fetching", reason="r"),
            usage=None,
            elapsed_s=0.1,
        )
        for pid in papers
    ]
    capped = R._cap_worth_fetching(
        outcomes,
        papers,
        sequence="M" * 50,
        internal_only=True,
        max_fetch=2,
        pinned_ids={"PMID:4"},
        citation_counts={"PMID:3": 500, "PMID:1": 10, "PMID:2": 5, "PMID:4": 0},
    )
    decisions = {o.paper_id: o.response.decision for o in capped}
    assert decisions["PMID:4"] == "worth_fetching"  # pinned never downgraded
    assert decisions["PMID:2"] == "worth_fetching"  # loop insertion relevance wins
    assert decisions["PMID:1"] == "keep_abstract"   # downgraded
    assert decisions["PMID:3"] == "keep_abstract"


def test_cap_pool_per_paper_and_evidence_diversity() -> None:
    pool = {
        f"p1_{i}": EvidenceClaimDraft(
            suggested_evidence_id=f"p1_{i}",
            quote=f"clip {i}",
            source_id="PMC:PMC1",
            section="methods",
            hallmark_phrase="x",
            score=10.0 - i * 0.1,
        )
        for i in range(12)
    }
    pool["p2_0"] = EvidenceClaimDraft(
        suggested_evidence_id="p2_0",
        quote="second paper clip",
        source_id="PMC:PMC2",
        section="methods",
        hallmark_phrase="x",
        score=2.0,
    )
    capped = R._cap_pool_per_paper(pool, max_per_paper=4, keep_ids={"p1_11"})
    assert "p2_0" in capped
    assert "p1_11" in capped  # keep_ids preserved
    assert sum(1 for d in capped.values() if d.source_id == "PMC:PMC1") == 4


def test_reference_followup_extracts_cues_and_parses_jats() -> None:
    nums, ays = rf.extract_citation_cues(
        "BLAP-KCNN3 was generated as previously described [ 18 ], [ 25 ] and (Gao et al., 2008)."
    )
    assert {18, 25}.issubset(nums)
    assert ("gao", "2008") in ays

    xml = """<article><back><ref-list>
      <ref id="B18"><label>18</label><element-citation>
        <person-group><name><surname>Gao</surname></name></person-group>
        <year>2008</year>
        <article-title>Insertion of a biotin acceptor peptide into the extracellular loop of SK3</article-title>
        <pub-id pub-id-type="pmid">18234567</pub-id>
      </element-citation></ref>
    </ref-list></back></article>"""
    refs = rf.parse_jats_references(xml)
    assert len(refs) == 1
    assert refs[0]["num"] == 18
    assert refs[0]["pmid"] == "18234567"


def test_runner_adaptive_web_search_uses_internal_intent_and_claude55(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(R, "DISCOVERY_CACHE_DIR", tmp_path / "disc")
    seen_web: list[dict] = []
    seen_triage: list[dict] = []
    seen_builder: list[dict] = []

    monkeypatch.setattr(
        R,
        "discover_tag_site_papers",
        lambda **k: {"PMID:1": types.SimpleNamespace(pmid=1, doi=None, pmc_id=None, title="t", abstract="a", year=2024, is_preprint=False)},
    )

    def fake_web(client, **kw):
        seen_web.append(kw)
        return []

    def fake_triage(client, **kw):
        seen_triage.append(kw)
        return []

    def fake_builder(client, **kw):
        seen_builder.append(kw)
        return TagSiteResult(gene_symbol="KCNN3", sites=[])

    monkeypatch.setattr(R, "web_discover_papers", fake_web)
    monkeypatch.setattr(R, "triage_abstracts", fake_triage)
    monkeypatch.setattr(
        R,
        "build_pool",
        lambda *a, **k: (
            {
                "c1": EvidenceClaimDraft(
                    suggested_evidence_id="c1",
                    quote="BLAP inserted in ECL2",
                    source_id="PMID:1",
                    section="methods",
                    hallmark_phrase="x",
                    score=1.0,
                )
            },
            [],
        ),
    )
    monkeypatch.setattr(R, "build_source_store", lambda *a, **k: object())
    monkeypatch.setattr(R, "select_clips", lambda *a, **k: object())
    span = types.SimpleNamespace(
        source=types.SimpleNamespace(source_id="PMID:1"), quote="BLAP inserted in ECL2"
    )
    monkeypatch.setattr(
        R,
        "promote",
        lambda *a, **k: [
            types.SimpleNamespace(
                evidence_id="tag_evi_1",
                claim="BLAP in ECL2",
                spans=[span],
                entailment_verified=True,
                evidence_tier="primary",
                confidence="moderate",
            )
        ],
    )
    monkeypatch.setattr(R, "call_builder", fake_builder)

    inter: dict = {}
    out = R.run_tag_site_agent(
        gene_symbol="KCNN3",
        protein_name="Small conductance calcium-activated potassium channel protein 3",
        uniprot_accession="Q9UGI6",
        aliases=["SK3", "KCa2.3"],
        sequence="M" * 60,
        topology="I" * 10 + "M" * 15 + "O" * 20 + "M" * 15,
        loop_inventory="NO extracellular terminus. Loops: 26-45 (20 aa).",
        client=cast(Anthropic, object()),
        http=cast(CachedHTTP, object()),
        intermediates=inter,
    )
    assert out.model == "claude-sonnet-5-5"
    assert seen_triage[0]["internal_only"] is True
    assert "SK3" in seen_triage[0]["synonyms"]
    assert seen_web[0]["model"] == "claude-haiku-5-5"
    assert seen_web[0]["gene_names"][0] == "KCNN3"
    assert "EXCLUDING N-terminal or C-terminal" in seen_web[0]["intent"]
    assert seen_builder[0]["model"] == "claude-sonnet-5-5"
    assert inter["web_search_used"] is True


def test_runner_adaptive_web_search_force_fetches_previously_discarded_hit(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(R, "DISCOVERY_CACHE_DIR", tmp_path / "disc")
    paper = types.SimpleNamespace(
        pmid=28602638,
        doi="10.1000/test",
        pmc_id="PMC3679034",
        title="ATM regulates GLUT1",
        abstract="GLUT1 S490 phosphorylation study",
        year=2013,
        is_preprint=False,
    )
    monkeypatch.setattr(R, "discover_tag_site_papers", lambda **k: {"PMC:PMC3679034": paper})
    # Initial abstract triage discards the paper (tag only in Methods).
    monkeypatch.setattr(
        R,
        "triage_abstracts",
        lambda client, **kw: [
            types.SimpleNamespace(
                paper_id="PMC:PMC3679034",
                response=types.SimpleNamespace(decision="discard", reason="no tag in abstract"),
                error=None,
                usage=None,
            )
        ],
    )
    # Adaptive web_search surfaces the same paper from full text.
    monkeypatch.setattr(R, "web_discover_papers", lambda client, **kw: [paper])

    seen_build_decisions: list[list[str]] = []

    def fake_build_pool(outcomes, papers_by_id, **kw):
        seen_build_decisions.append(
            [o.response.decision for o in outcomes if getattr(o, "response", None)]
        )
        return ({}, [])

    monkeypatch.setattr(R, "build_pool", fake_build_pool)
    monkeypatch.setattr(R, "call_builder", lambda *a, **k: TagSiteResult(gene_symbol="SLC2A1", sites=[]))

    R.run_tag_site_agent(
        gene_symbol="SLC2A1",
        protein_name="GLUT1",
        uniprot_accession="P11166",
        aliases=["GLUT1"],
        sequence="M" * 60,
        topology="I" * 10 + "M" * 15 + "O" * 20 + "M" * 15,
        loop_inventory="NO extracellular terminus. Loops: 26-45 (20 aa).",
        client=cast(Anthropic, object()),
        http=cast(CachedHTTP, object()),
    )
    # First build_pool saw only 'discard'; second build_pool force-fetched 'worth_fetching'.
    assert seen_build_decisions == [["discard"], ["worth_fetching"]]
