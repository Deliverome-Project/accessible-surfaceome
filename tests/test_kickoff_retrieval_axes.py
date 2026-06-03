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
        assert _has_anchor(plan, "tox_normal_tissue")


def test_build_kickoff_dispatch_all_foci_have_tox_panel():
    for focus in ("a1", "a2", None):
        assert _has_anchor(build_kickoff(focus, 7, 89), "tox_normal_tissue")


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
    assert _has_anchor(build_kickoff("a1"), "tox_normal_tissue")


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
    terms = " ".join(_TOPIC_TERMS["tox_normal_tissue"]).lower()
    # The six high-consequence organs are present...
    for organ in ("liver", "lung", "kidney", "intestine", "heart", "brain"):
        assert organ in terms
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
