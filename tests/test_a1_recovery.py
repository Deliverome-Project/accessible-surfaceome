"""Unit tests for the A1 evidence-recovery re-tag logic (no network / LLM).

Guards the permeabilization-aware, method-dependent rule and the A2->A1
re-tag mutation — the two pure-logic pieces the backfill + Modal run rely on.
"""
from __future__ import annotations

from accessible_surfaceome.agents.surfaceome_v2.a1_recovery import (
    claim_is_direct_surface,
    retag_a2_direct_into_a1,
)


def _claim(**kw):
    base = {
        "evidence_id": kw.pop("evidence_id", "a2_evi_01"),
        "claim": "c",
        "claim_type": kw.pop("claim_type", "tissue_expression"),
        "direction": kw.pop("direction", "supports"),
        "evidence_type": kw.pop("evidence_type", "flow_cytometry"),
        "evidence_tier": kw.pop("evidence_tier", "primary"),
        "assay_context": {
            "permeabilized": kw.pop("permeabilized", False),
            "species": kw.pop("species", None),
        },
        "source_id": kw.pop("source_id", "PMID:1"),
        "quote": "q",
    }
    base.update(kw)
    return base


def test_nonperm_flow_is_direct():
    assert claim_is_direct_surface(_claim(evidence_type="flow_cytometry", permeabilized=False))


def test_permeabilized_flow_is_not_direct():
    # permeabilized flow measures TOTAL protein, not surface
    assert not claim_is_direct_surface(_claim(evidence_type="flow_cytometry", permeabilized=True))


def test_unknown_perm_if_is_credited():
    # grader-matching: perm=None IF/flow IS credited (only explicit True is excluded)
    assert claim_is_direct_surface(_claim(evidence_type="immunofluorescence", permeabilized=None))
    assert claim_is_direct_surface(_claim(evidence_type="flow_cytometry", permeabilized=None))


def test_surface_biotinylation_is_direct_regardless_of_perm_flag():
    # surface-by-method: permeabilized flag is not load-bearing
    assert claim_is_direct_surface(_claim(evidence_type="surface_biotinylation", permeabilized=None))
    assert claim_is_direct_surface(_claim(evidence_type="mass_spec_surfaceome", permeabilized=False))


def test_permeabilized_biotinylation_still_credited():
    # you cannot biotinylate an intracellular lysine on an intact cell anyway
    assert claim_is_direct_surface(_claim(evidence_type="surface_biotinylation", permeabilized=False))


def test_refutes_and_secondary_excluded():
    assert not claim_is_direct_surface(_claim(direction="refutes", permeabilized=False))
    assert not claim_is_direct_surface(_claim(evidence_tier="secondary", permeabilized=False))


def test_nonhuman_species_excluded():
    # CD79A-class: a non-human assay can't anchor a human direct_* grade
    assert not claim_is_direct_surface(_claim(evidence_type="flow_cytometry", permeabilized=False, species="other"))
    assert not claim_is_direct_surface(_claim(evidence_type="flow_cytometry", permeabilized=False, species="mouse"))


def test_human_and_unspecified_species_credited():
    assert claim_is_direct_surface(_claim(evidence_type="flow_cytometry", permeabilized=False, species="human"))
    assert claim_is_direct_surface(_claim(evidence_type="flow_cytometry", permeabilized=False, species=None))
    assert claim_is_direct_surface(_claim(evidence_type="flow_cytometry", permeabilized=False, species="unspecified"))


def test_non_surface_assays_excluded():
    # review / RNA / IHC are not surface-localization assays in the credited set
    assert not claim_is_direct_surface(_claim(evidence_type="review_assertion", permeabilized=False))
    assert not claim_is_direct_surface(_claim(evidence_type="single_cell_rna_seq", permeabilized=False))
    assert not claim_is_direct_surface(_claim(evidence_type="immunohistochemistry", permeabilized=False))


def test_retag_moves_only_qualifying_and_renumbers():
    blob = {
        "plan_trim_select": {
            "a1": {"claims": []},
            "a2": {
                "claims": [
                    _claim(evidence_id="a2_evi_01", evidence_type="flow_cytometry", permeabilized=False),
                    _claim(evidence_id="a2_evi_02", evidence_type="immunofluorescence", permeabilized=True),  # perm -> stays
                    _claim(evidence_id="a2_evi_03", evidence_type="mass_spec_surfaceome", permeabilized=None),
                    _claim(evidence_id="a2_evi_04", evidence_type="review_assertion", permeabilized=None),      # not method -> stays
                ]
            },
        }
    }
    out = retag_a2_direct_into_a1(blob)
    assert out["n_moved"] == 2
    assert out["method_types"] == {"flow_cytometry": 1, "mass_spec_surfaceome": 1}
    a1 = blob["plan_trim_select"]["a1"]["claims"]
    a2 = blob["plan_trim_select"]["a2"]["claims"]
    assert len(a1) == 2 and len(a2) == 2
    # moved claims re-id'd into the a1_evi_ namespace + re-tagged surface_expression
    assert [c["evidence_id"] for c in a1] == ["a1_evi_01", "a1_evi_02"]
    assert all(c["claim_type"] == "surface_expression" for c in a1)
    # the permeabilized IF and the review assertion remain in A2
    assert {c["evidence_type"] for c in a2} == {"immunofluorescence", "review_assertion"}


def test_retag_empty_when_nothing_qualifies():
    blob = {"plan_trim_select": {"a1": {"claims": []}, "a2": {"claims": [
        _claim(evidence_type="review_assertion"), _claim(evidence_type="flow_cytometry", permeabilized=True),
    ]}}}
    out = retag_a2_direct_into_a1(blob)
    assert out["n_moved"] == 0
    assert blob["plan_trim_select"]["a1"]["claims"] == []
