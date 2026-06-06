"""Tests for the deterministic-kickoff retrieval axes (Chunk 1 of the
PR #47 deep-dive redesign).

Covers:

* the shared ``topology_gate`` predicates (single source of the membrane /
  secreted-isoform thresholds);
* the always-on tox-organ panel (A6.2) and the topology-gated
  surface-reachability axis (A6.1), recall-biased on unknown topology;
* "never RNA-atlas" (A6.3) — satisfied by construction: no RNA-atlas anchor
  exists, and the tox anchor routes through MED literature terms;
* OE/heterologous-host recall (A4.4 / C.1) and the soluble-in-circulation
  enrichment of the ``shedding`` anchor (A2.4).
"""

from __future__ import annotations

from typing import get_args

from accessible_surfaceome.agents._support.topology_gate import (
    MIN_ECD_RESIDUES,
    is_likely_membrane_with_ecd,
    is_secreted_isoform,
)
from accessible_surfaceome.agents.plan_trim_select.kickoff_templates import (
    build_a1_kickoff,
    build_a2_kickoff,
    build_kickoff,
    build_unified_kickoff,
)
from accessible_surfaceome.tools._shared.models import TopicAnchor
from accessible_surfaceome.tools.evidence_retrieval import _CATEGORY_SPECS
from accessible_surfaceome.tools.gene_literature import _TOPIC_TERMS

# get_args on the closed Literal gives the full anchor value set.
_ALL_ANCHORS = set(get_args(TopicAnchor))


# --------------------------------------------------------------------------
# topology_gate predicates
# --------------------------------------------------------------------------


def test_membrane_gate_true_for_tm_with_ecd():
    assert is_likely_membrane_with_ecd(1, MIN_ECD_RESIDUES) is True
    assert is_likely_membrane_with_ecd(7, 89) is True


def test_membrane_gate_false_for_no_tm_or_small_ecd():
    assert is_likely_membrane_with_ecd(0, 500) is False  # no TM
    assert is_likely_membrane_with_ecd(1, MIN_ECD_RESIDUES - 1) is False  # tiny ECD


def test_membrane_gate_false_on_unknown_topology():
    # The predicate itself is conservative; the kickoff supplies the
    # recall-biased "unknown fires the gate" behavior, not this helper.
    assert is_likely_membrane_with_ecd(None, None) is False


def test_secreted_isoform_predicate():
    assert is_secreted_isoform(0, MIN_ECD_RESIDUES) is True
    assert is_secreted_isoform(1, 500) is False  # has a TM → not soluble
    assert is_secreted_isoform(0, MIN_ECD_RESIDUES - 1) is False  # too short


# --------------------------------------------------------------------------
# kickoff helpers
# --------------------------------------------------------------------------


def _topic_anchor_sets(plan) -> list[list[TopicAnchor]]:
    return [
        list(s.anchors)
        for s in plan.searches
        if s.mode == "topic_search" and s.anchors
    ]


def _has_anchor(plan, anchor: str) -> bool:
    return any(s.anchors and anchor in s.anchors for s in plan.searches)


# --------------------------------------------------------------------------
# tox panel — always-on for every focus (A6.2)
# --------------------------------------------------------------------------


def test_tox_panel_always_emitted_every_focus():
    for plan in (
        build_a1_kickoff(7, 89),
        build_a2_kickoff(7, 89),
        build_unified_kickoff(7, 89),
        build_a1_kickoff(0, 0),  # even a known non-membrane gene
        build_a1_kickoff(None, None),  # even with unknown topology
    ):
        assert _has_anchor(plan, "normal_tissue_expression")


def test_build_kickoff_dispatch_all_foci_have_tox_panel():
    for focus in ("a1", "a2", None):
        assert _has_anchor(build_kickoff(focus, 7, 89), "normal_tissue_expression")


# --------------------------------------------------------------------------
# surface-reachability — gated on membrane+ECD, recall-biased (A6.1)
# --------------------------------------------------------------------------


def test_reachability_present_for_membrane_with_ecd():
    assert _has_anchor(build_a1_kickoff(7, 89), "surface_reachability")
    assert _has_anchor(build_a2_kickoff(1, 40), "surface_reachability")


def test_reachability_absent_for_known_non_membrane():
    # Known TM=0 with no ECD: a cytoplasmic/non-surface protein — the
    # barrier axis is moot and must be suppressed.
    assert not _has_anchor(build_a1_kickoff(0, 0), "surface_reachability")
    # Known membrane but sub-threshold ECD: also suppressed.
    assert not _has_anchor(build_a1_kickoff(1, 5), "surface_reachability")


def test_reachability_fires_recall_biased_on_unknown_topology():
    # D1 miss / placeholder → topology unknown → fire the axis anyway.
    assert _has_anchor(build_a1_kickoff(None, None), "surface_reachability")
    assert _has_anchor(build_kickoff("a2", None, None), "surface_reachability")


def test_kickoff_backwards_compatible_no_topology_args():
    # Default (no topology) must still build and fire the gated axis.
    assert _has_anchor(build_a1_kickoff(), "surface_reachability")
    assert _has_anchor(build_kickoff("a1"), "normal_tissue_expression")


# --------------------------------------------------------------------------
# partner-dependency + membrane-subdomain axes (feed co_receptor /
# restricted_subdomain) — gated like surface-reachability
# --------------------------------------------------------------------------


def test_partner_and_subdomain_axes_fire_for_membrane_with_ecd():
    p = build_a1_kickoff(7, 89)
    assert _has_anchor(p, "partner_dependency")
    assert _has_anchor(p, "membrane_subdomain")


def test_partner_and_subdomain_axes_suppressed_for_known_non_membrane():
    p = build_a1_kickoff(0, 0)
    assert not _has_anchor(p, "partner_dependency")
    assert not _has_anchor(p, "membrane_subdomain")


def test_subdomain_anchor_includes_lipid_rafts():
    terms = " ".join(_TOPIC_TERMS["membrane_subdomain"]).lower()
    assert "lipid raft" in terms
    assert "ciliary" in terms or "cilium" in terms


def test_partner_dependency_anchor_targets_coreceptor_evidence():
    terms = " ".join(_TOPIC_TERMS["partner_dependency"]).lower()
    assert "co-receptor" in terms or "coreceptor" in terms
    assert "heterodimer" in terms


# --------------------------------------------------------------------------
# never RNA-atlas (A6.3) — by construction
# --------------------------------------------------------------------------


def test_no_rna_atlas_anchor_exists():
    # The enum carries no transcript/RNA-atlas value, so a tox search can
    # never route through one. Guards against a future anchor reintroducing
    # the RNA-atlas-only retrieval path.
    for anchor in _ALL_ANCHORS:
        assert "rna" not in anchor.lower()
        assert "transcript" not in anchor.lower()


def test_every_kickoff_anchor_is_protein_level_and_resolvable():
    # Every topic_search anchor the kickoff emits must (a) be a valid
    # TopicAnchor and (b) resolve to a non-empty MED-literature term list,
    # so topic_search never raises "no known terms".
    for plan in (build_a1_kickoff(7, 89), build_a2_kickoff(7, 89)):
        for anchors in _topic_anchor_sets(plan):
            for anchor in anchors:
                assert anchor in _ALL_ANCHORS
                assert _TOPIC_TERMS.get(anchor)  # non-empty term list


def test_tox_anchor_terms_are_organ_literature_not_rna():
    terms = " ".join(_TOPIC_TERMS["normal_tissue_expression"]).lower()
    # The six high-consequence organs are present...
    for organ in ("liver", "lung", "kidney", "intestine", "heart", "brain"):
        assert organ in terms
    # ...anchored on SURFACE expression (not an RNA atlas / distribution survey)...
    assert "surface expression" in terms
    # ...with the atlas / microarray (RNA-flavored) qualifiers removed...
    assert "tissue distribution" not in terms
    assert "tissue microarray" not in terms
    assert "normal tissue" not in terms
    # ...and the anchor doesn't pull an RNA-atlas channel.
    assert "rna" not in terms
    assert "transcript" not in terms


# --------------------------------------------------------------------------
# OE host breadth (A4.4 / C.1) + soluble-in-circulation enrichment (A2.4)
# --------------------------------------------------------------------------


def test_oe_retrieval_hits_any_host_no_wild_type_gate():
    flow_query = " ".join(_CATEGORY_SPECS["flow_cytometry"].query_clauses).lower()
    # Host-agnostic heterologous-expression recall...
    assert "transfected" in flow_query
    assert "ectopic expression" in flow_query
    # ...and crucially NOT gated on the "wild-type" keyword (real
    # WT-transfectant papers rarely use it; gating suppresses recall).
    assert "wild-type" not in flow_query
    assert "wild type" not in flow_query


def test_shedding_anchor_enriched_for_circulating_soluble_target():
    terms = " ".join(_TOPIC_TERMS["shedding"]).lower()
    assert "circulating" in terms
    assert "serum level" in terms
    assert "plasma level" in terms


# --------------------------------------------------------------------------
# surface_reachability retune + epitope_masking masking axis + A1/A2 mirror
# --------------------------------------------------------------------------


def test_surface_reachability_drops_vasculature_adds_qualified_accessibility():
    terms = " ".join(_TOPIC_TERMS["surface_reachability"]).lower()
    # Qualified binder-access vocabulary added...
    assert "surface accessibility" in terms
    assert "antibody accessibility" in terms
    # ...never the bare/ambiguous form (would pull chromatin-accessibility /
    # ATAC-seq + "data accessibility" noise)...
    assert "chromatin" not in terms
    # ...and the removed vasculature terms are gone.
    assert "tumor vasculature" not in terms
    assert "vascular permeability" not in terms


def test_epitope_masking_anchor_covers_homo_hetero_other():
    terms = " ".join(_TOPIC_TERMS["epitope_masking"]).lower()
    # HOMO — the target's own self-association
    assert "homodimer" in terms
    assert "oligomerization" in terms or "self-association" in terms
    # HETERO — a partner protein covering the epitope
    assert "heterodimer" in terms
    # OTHER — glycan / conformational occlusion
    assert "glycan shield" in terms or "conformational masking" in terms


def test_epitope_masking_axis_gated_like_other_membrane_axes():
    # Fires for membrane+ECD and (recall-biased) unknown topology...
    assert _has_anchor(build_a1_kickoff(7, 89), "epitope_masking")
    assert _has_anchor(build_a2_kickoff(1, 40), "epitope_masking")
    assert _has_anchor(build_a1_kickoff(None, None), "epitope_masking")
    # ...suppressed for a known non-membrane / sub-threshold-ECD protein.
    assert not _has_anchor(build_a1_kickoff(0, 0), "epitope_masking")


# Single-anchor standing searches that MUST be byte-identical between A1 and
# A2 — they come from the one shared ``_standing_axes()`` helper. Listed
# explicitly so a new shared axis has to be added here on purpose; the
# byte-for-byte mirror is asserted by
# test_shared_standing_searches_identical_across_a1_a2.
_MIRRORED_STANDING_ANCHORS = [
    "normal_tissue_expression",  # always-on
    "surface_reachability",      # gated on membrane+ECD
    "partner_dependency",        # gated
    "membrane_subdomain",        # gated
    "epitope_masking",           # gated
]


def _search_sig(plan, anchor):
    """Full signature (tool, mode, anchors, intent) of the single-anchor
    standing search carrying ``anchor`` in ``plan``, or None if absent."""
    for s in plan.searches:
        if s.anchors == [anchor]:
            return (s.tool, s.mode, tuple(s.anchors), s.intent)
    return None


def _topic_sigs(plan, *required):
    """Signatures (tool, mode, anchors, intent) of topic_searches whose anchor
    set contains all of ``required`` — used to locate a shared search and
    compare it byte-for-byte across A1 and A2."""
    req = set(required)
    return [
        (s.tool, s.mode, tuple(s.anchors), s.intent)
        for s in plan.searches
        if s.anchors and req <= set(s.anchors)
    ]


def test_surface_method_search_identical_across_a1_a2():
    # The combined surface-expression + surface-method topic_search
    # (surface_expression + flow_cytometry + surface_biotinylation +
    # mass_spec_surfaceome + ihc) must be BYTE-IDENTICAL in A1 and A2 — both
    # emit the single _surface_method_search() helper.
    from accessible_surfaceome.agents.plan_trim_select.kickoff_templates import (
        _SURFACE_METHOD_ANCHORS,
    )

    c1 = _topic_sigs(build_a1_kickoff(7, 89), "surface_expression", "flow_cytometry")
    c2 = _topic_sigs(build_a2_kickoff(7, 89), "surface_expression", "flow_cytometry")
    assert len(c1) == 1, f"A1 should emit the combined search exactly once: {c1}"
    assert len(c2) == 1, f"A2 should emit the combined search exactly once: {c2}"
    assert c1 == c2, f"combined surface-method search differs: A1={c1}, A2={c2}"
    assert set(c1[0][2]) == set(_SURFACE_METHOD_ANCHORS)


def test_shedding_ptm_search_identical_across_a1_a2():
    # The shedding + PTM topic_search must be BYTE-IDENTICAL in A1 and A2 —
    # both emit the single _shedding_ptm_search() helper (PTM lives here, not
    # in A1's topology/structure search, so it stays mirrored).
    c1 = _topic_sigs(build_a1_kickoff(7, 89), "shedding", "ptm")
    c2 = _topic_sigs(build_a2_kickoff(7, 89), "shedding", "ptm")
    assert len(c1) == 1, f"A1 should emit the shedding+ptm search once: {c1}"
    assert len(c2) == 1, f"A2 should emit the shedding+ptm search once: {c2}"
    assert c1 == c2, f"shedding+ptm search differs: A1={c1}, A2={c2}"
    assert set(c1[0][2]) == {"shedding", "ptm"}
    # PTM must NOT also live in A1's topology/structure search (else it'd be
    # unmirrored again).
    a1_struct = _topic_sigs(build_a1_kickoff(7, 89), "topology")
    assert all("ptm" not in anchors for _, _, anchors, _ in a1_struct), (
        "ptm leaked back into A1's topology/structure search — keep it only in "
        "the shared _shedding_ptm_search()"
    )


def test_shared_standing_searches_identical_across_a1_a2():
    # Each shared standing/gated axis must be BYTE-IDENTICAL in A1 and A2 (same
    # tool, mode, anchors, intent) — they come from the single _standing_axes()
    # helper, so any divergence means someone bypassed it. Explicitly covers
    # membrane_subdomain, epitope_masking, surface_reachability,
    # partner_dependency, and normal_tissue_expression, at gated-on /
    # gated-off / unknown topology.
    for tmh, ecd in ((7, 89), (0, 0), (None, None)):
        a1 = build_a1_kickoff(tmh, ecd)
        a2 = build_a2_kickoff(tmh, ecd)
        for anchor in _MIRRORED_STANDING_ANCHORS:
            s1 = _search_sig(a1, anchor)
            s2 = _search_sig(a2, anchor)
            assert s1 == s2, (
                f"{anchor}: A1 vs A2 standing search differs "
                f"(A1={s1!r}, A2={s2!r}) at tmh={tmh}, ecd={ecd}"
            )
    # normal_tissue_expression is the always-on member (present even for a
    # known non-membrane gene); the gated axes are absent there in BOTH foci.
    assert _search_sig(build_a1_kickoff(0, 0), "normal_tissue_expression") is not None
    assert _search_sig(build_a2_kickoff(0, 0), "normal_tissue_expression") is not None
    assert _search_sig(build_a1_kickoff(0, 0), "epitope_masking") is None
    assert _search_sig(build_a2_kickoff(0, 0), "epitope_masking") is None


def _has_category(plan, category):
    return any(
        s.tool == "evidence_retrieval" and s.category == category
        for s in plan.searches
    )


def test_shedding_is_a_dedicated_evidence_retrieval_category():
    # shedding was reformulated from a topic-only anchor into a dedicated,
    # quote-grounded evidence_retrieval category (feeds shed_form/secreted_form
    # risks). It must: (1) have a spec with sheddase + serum/plasma decoy
    # signals, (2) be emitted by BOTH A1 and A2 (shared), (3) no longer be
    # double-covered by the catch-all `other`.
    from accessible_surfaceome.tools.evidence_retrieval import _CATEGORY_SPECS

    spec = _CATEGORY_SPECS.get("shedding")
    assert spec is not None, "shedding must be a dedicated evidence_retrieval category"
    clauses = " ".join(spec.query_clauses).lower()
    assert "shedding" in clauses or "sheddase" in clauses
    assert "serum level" in clauses and "plasma level" in clauses  # decoy signal
    hp = " ".join(p.pattern for p in spec.hallmark_patterns).lower()
    assert "ectodomain" in hp and "adam" in hp

    assert _has_category(build_a1_kickoff(7, 89), "shedding")
    assert _has_category(build_a2_kickoff(7, 89), "shedding")

    other = " ".join(_CATEGORY_SPECS["other"].query_clauses).lower()
    assert "shedding" not in other and "soluble form" not in other, (
        "shedding should live only in its dedicated category, not the `other` "
        "catch-all"
    )
