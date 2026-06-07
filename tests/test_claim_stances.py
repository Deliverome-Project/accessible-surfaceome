"""Tests for the claim_stances structured per-claim accounting on
``evidence_grade`` (suggestion 5b.8).

Background: ``evidence_grade.grade_rationale`` is free-text prose. To
know WHICH claims contradicted vs supported a grade, downstream code
(synthesizer, catalog filters) had to re-parse the rationale. The
stance map adds a structured ``claim_stances: list[ClaimStanceRow]``
field so the per-claim accounting is auditable + filterable directly.

Validators + filters this enables:
* Every ``claim_stances[i].claim_id`` must resolve to an EvidenceClaim
  in the input ledger (same pattern as the other ``cited_evidence_ids``
  resolution checks).
* Filters expose ``n_supporting_claims_high_weight`` +
  ``n_contradicting_claims_high_weight`` so the catalog can filter
  "conflicting grade with only 1 high-weight contradiction → likely
  artifact" vs "≥3 contradictions → real disagreement".

Backward compat: ``claim_stances`` defaults to ``[]`` so old records
(no stance map emitted) still parse and the derived filter counts
read 0.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import get_args

import pytest
from pydantic import ValidationError

from accessible_surfaceome.agents.surfaceome_v1.orchestrator import (
    _derive_filters,
)
from accessible_surfaceome.tools._shared.models import (
    AccessibilityRisks,
    BiologicalContext,
    DeterministicFeatures,
    EvidenceClaim,
    ExecutiveSummary,
    Filters,
    IsoformTopology,
    Orthologs,
    StructureFeatures,
    SubcellularLocalization,
    SurfaceEvidence,
    SurfaceEvidenceDraft,
    SynthesizerLLMFilters,
)


# ---------------------------------------------------------------------------
# Schema additions
# ---------------------------------------------------------------------------


def test_claim_stance_literal_exists():
    from accessible_surfaceome.tools._shared.models import ClaimStance

    values = set(get_args(ClaimStance))
    assert values == {
        "supports_surface",
        "contradicts_surface",
        "tangential",
        "expression_only",
    }


def test_claim_weight_literal_exists():
    from accessible_surfaceome.tools._shared.models import ClaimWeight

    assert set(get_args(ClaimWeight)) == {"high", "moderate", "low"}


def test_claim_stance_row_model_exists():
    from accessible_surfaceome.tools._shared.models import ClaimStanceRow

    row = ClaimStanceRow(
        claim_id="a1_evi_01",
        stance="supports_surface",
        weight="high",
    )
    assert row.claim_id == "a1_evi_01"
    assert row.stance == "supports_surface"
    assert row.weight == "high"
    assert row.note is None  # optional


def test_claim_stance_row_optional_note():
    from accessible_surfaceome.tools._shared.models import ClaimStanceRow

    row = ClaimStanceRow(
        claim_id="a1_evi_02",
        stance="tangential",
        weight="moderate",
        note="informs the picture but doesn't commit either way",
    )
    assert row.note == "informs the picture but doesn't commit either way"


def test_surface_evidence_has_claim_stances_default_empty():
    """Backward compat: old SurfaceEvidence dicts without claim_stances
    must still parse, and the field defaults to an empty list."""
    se = SurfaceEvidence(
        evidence_grade="weak",
        grade_rationale="—",
        methods=[],
        non_surface_expression=[],
        contradicting_evidence=[],
    )
    assert se.claim_stances == []


def test_surface_evidence_accepts_claim_stances():
    from accessible_surfaceome.tools._shared.models import ClaimStanceRow

    se = SurfaceEvidence(
        evidence_grade="conflicting",
        grade_rationale="—",
        methods=[],
        non_surface_expression=[],
        contradicting_evidence=[],
        claim_stances=[
            ClaimStanceRow(
                claim_id="a1_evi_01", stance="supports_surface", weight="high"
            ),
            ClaimStanceRow(
                claim_id="a1_evi_05",
                stance="contradicts_surface",
                weight="high",
            ),
        ],
    )
    assert len(se.claim_stances) == 2


def test_evidence_grade_block_has_claim_stances_default_empty():
    from accessible_surfaceome.agents.surfaceome_v2.builders.evidence_grade import (
        EvidenceGradeBlock,
    )

    block = EvidenceGradeBlock(
        evidence_grade="weak",
        grade_rationale="—",
    )
    assert block.claim_stances == []


# ---------------------------------------------------------------------------
# Validator: claim_id resolution
# ---------------------------------------------------------------------------


def _claim(eid: str) -> EvidenceClaim:
    # model_validate accepts a dict for the AssayContext nested model;
    # the bare-kwarg path would require ty to narrow the dict to the
    # exact AssayContext shape, which is busywork for a test fixture.
    return EvidenceClaim.model_validate({
        "evidence_id": eid,
        "claim": "—",
        "claim_type": "surface_expression",
        "direction": "supports",
        "evidence_type": "flow_cytometry",
        "evidence_tier": "primary",
        "confidence": "moderate",
        "assay_context": {
            "species": "human",
            "cell_type_or_line": "HEK293",
            "permeabilized": False,
            "fixation": "live",
            "isoform": None,
            "cell_context": None,
        },
        "source_id": "PMID:1",
        "quote": "—",
        "section": "results",
    })


def test_surface_evidence_draft_validator_rejects_unknown_stance_claim_id():
    """Same pattern as the existing methods.cited_evidence_ids
    resolution check: a claim_stances entry whose claim_id isn't in
    the input ledger raises ValidationError."""
    from accessible_surfaceome.tools._shared.models import ClaimStanceRow

    se = SurfaceEvidence(
        evidence_grade="conflicting",
        grade_rationale="—",
        claim_stances=[
            ClaimStanceRow(
                claim_id="a1_evi_99",  # ← not in the claims list below
                stance="contradicts_surface",
                weight="high",
            ),
        ],
    )
    with pytest.raises(ValidationError, match="claim_stances|evidence_ids|absent"):
        SurfaceEvidenceDraft(
            surface_evidence=se,
            evidence_claims=[_claim("a1_evi_01")],
        )


def test_surface_evidence_draft_validator_accepts_resolved_stance_claim_ids():
    from accessible_surfaceome.tools._shared.models import ClaimStanceRow

    se = SurfaceEvidence(
        evidence_grade="conflicting",
        grade_rationale="—",
        claim_stances=[
            ClaimStanceRow(
                claim_id="a1_evi_01",
                stance="supports_surface",
                weight="high",
            ),
            ClaimStanceRow(
                claim_id="a1_evi_02",
                stance="contradicts_surface",
                weight="moderate",
            ),
        ],
    )
    # Should construct without raising
    draft = SurfaceEvidenceDraft(
        surface_evidence=se,
        evidence_claims=[_claim("a1_evi_01"), _claim("a1_evi_02")],
    )
    assert len(draft.surface_evidence.claim_stances) == 2


# ---------------------------------------------------------------------------
# Filter derivation
# ---------------------------------------------------------------------------


def _exec() -> ExecutiveSummary:
    return ExecutiveSummary(
        one_paragraph="—",
        surface_accessibility="high",
        evidence_grade_summary="conflicting",
        confidence="moderate",
        state_dependence="high",
        subcategory="other",
        llm_family="enzyme",
        surface_call_reason="lysosomal_exocytosis",
        headline_risks=[],
        cited_evidence_ids=[],
    )


def _risks() -> AccessibilityRisks:
    return AccessibilityRisks.model_validate({
        "co_receptor_requirements": {
            "surface_expression_dependency": "none", "partners": [],
            "evidence_basis": "mixed", "rationale": "—", "cited_evidence_ids": [],
        },
        "shed_form": {
            "present": False, "severity": "low",
            "evidence_strength": "moderate", "mechanism": None,
            "sheddase_if_known": None, "cited_evidence_ids": [],
        },
        "secreted_form": {
            "present": False, "severity": "low",
            "evidence_strength": "moderate", "ratio_to_membrane": None,
            "source": None, "cited_evidence_ids": [],
        },
        "restricted_subdomain": {
            "present": False, "domain": "raft", "severity": "low",
            "evidence_strength": "moderate", "rationale": "—",
            "cited_evidence_ids": [],
        },
        "ecd_size_assessment": {
            "ecd_accessibility_class": "moderate", "rationale": "—",
            "cited_evidence_ids": [],
        },
        "epitope_masking": {
            "mechanism": [], "severity": "none",
            "evidence_strength": "moderate", "rationale": "—",
            "cited_evidence_ids": [],
        },
    })


def _bio_ctx() -> BiologicalContext:
    return BiologicalContext(
        expression=[],
        subcellular_localization=SubcellularLocalization(
            primary_compartment="plasma_membrane",
            dual_localization=[], membrane_subdomains=[],
        ),
        anatomical_accessibility=[],
        accessibility_modulation=[],
    )


def _llm_filters() -> SynthesizerLLMFilters:
    return SynthesizerLLMFilters(
        expression_level="moderate",
        expression_level_rationale="moderate in epithelial tissues",
        expression_breadth="broad",
        expression_breadth_rationale="detected across several tissue families",
        surface_specificity="surface_dominant",
        surface_specificity_rationale="predominantly plasma-membrane localized",
        # Default to orphan-receptor case so the empty rationale is valid
        # under the has_known_ligand=True-requires-rationale validator.
        has_known_ligand=False,
    )


def _det() -> DeterministicFeatures:
    now = datetime.now(UTC)
    return DeterministicFeatures(
        canonical_topology=IsoformTopology(
            isoform_id="P00000-1", uniprot_acc="P00000",
            tm_helix_count=0, n_terminal_orientation="cytoplasmic",
            c_terminal_orientation="cytoplasmic", signal_peptide_length=0,
            ecd_length_residues=0, icd_length_residues=100,
            per_residue_topology="", tool_version="stub", retrieved_at=now,
        ),
        isoform_topologies=[], orthologs=Orthologs(), paralogs=[],
        structure=StructureFeatures(
            afdb_id="AF-P00000-F1-model_v4", afdb_version="v4",
            ecd_mean_plddt=0.0, ecd_disordered_fraction=0.0,
            source="stub", license="CC BY 4.0",
            attribution="© DeepMind / EMBL-EBI",
        ),
    )


def test_filters_derives_n_supporting_high_weight():
    """SRC's stance map: 3 supporting-high, 2 contradicting-high. The
    derived filter must count them correctly so the catalog can query
    "conflicting grade with ≥3 contradictions → real disagreement"."""
    from accessible_surfaceome.tools._shared.models import ClaimStanceRow

    se = SurfaceEvidence(
        evidence_grade="conflicting",
        grade_rationale="—",
        claim_stances=[
            ClaimStanceRow(claim_id="a1_evi_01", stance="supports_surface", weight="high"),
            ClaimStanceRow(claim_id="a1_evi_02", stance="supports_surface", weight="high"),
            ClaimStanceRow(claim_id="a1_evi_04", stance="supports_surface", weight="high"),
            ClaimStanceRow(claim_id="a1_evi_05", stance="contradicts_surface", weight="high"),
            ClaimStanceRow(claim_id="a1_evi_15", stance="contradicts_surface", weight="high"),
            # Low-weight support shouldn't be counted in the high bucket
            ClaimStanceRow(claim_id="a1_evi_06", stance="supports_surface", weight="low"),
            # Tangential shouldn't count either
            ClaimStanceRow(claim_id="a1_evi_07", stance="tangential", weight="moderate"),
        ],
    )
    filters = _derive_filters(
        executive_summary=_exec(),
        surface_evidence=se,
        biological_context=_bio_ctx(),
        accessibility_risks=_risks(),
        filters_llm=_llm_filters(),
        deterministic_features=_det(),
        n_evidence=7,
    )
    assert filters.n_supporting_claims_high_weight == 3
    assert filters.n_contradicting_claims_high_weight == 2


def test_filters_zero_counts_when_no_stances():
    """Backward-compat: SurfaceEvidence with empty claim_stances yields
    zero counts in the derived filters. Existing genes (no stance map
    emitted) get 0; the catalog reader can distinguish them via
    evidence_density or other signals."""
    se = SurfaceEvidence(
        evidence_grade="weak",
        grade_rationale="—",
        claim_stances=[],
    )
    filters = _derive_filters(
        executive_summary=_exec().model_copy(update={"surface_accessibility": "no",
                                                     "evidence_grade_summary": "weak",
                                                     "surface_call_reason": "cytoplasmic"}),
        surface_evidence=se,
        biological_context=_bio_ctx(),
        accessibility_risks=_risks(),
        filters_llm=_llm_filters(),
        deterministic_features=_det(),
        n_evidence=0,
    )
    assert filters.n_supporting_claims_high_weight == 0
    assert filters.n_contradicting_claims_high_weight == 0


# ---------------------------------------------------------------------------
# Filters schema additions
# ---------------------------------------------------------------------------


def test_filters_has_n_supporting_high_weight_field():
    assert "n_supporting_claims_high_weight" in Filters.model_fields


def test_filters_has_n_contradicting_high_weight_field():
    assert "n_contradicting_claims_high_weight" in Filters.model_fields


# ---------------------------------------------------------------------------
# Overexpression-with-surface-localization derived filter
# (separate from the stance map work but lives in the same Filters block)
# ---------------------------------------------------------------------------


def test_filters_has_overexpression_surface_localization_observed_field():
    assert "overexpression_surface_localization_observed" in Filters.model_fields


def _method(*, expression_system: str, accessibility_relevance: str):
    """Minimal MethodObservation for the OE-filter tests."""
    return {
        "method_family": "flow_cytometry",
        "method_subclass": "live_cell_flow",
        "permeabilization": "live_cell",
        "expression_system": expression_system,
        "overexpression": None,
        "antibodies": [],
        "accessibility_relevance": accessibility_relevance,
        "surface_claim_type": "surface_accessible",
        "expression_observations": [],
        "cited_evidence_ids": [],
    }


def test_overexpression_filter_true_when_oe_plus_direct_surface():
    """Canonical positive case: an OE-host flow paper that shows direct
    surface accessibility. Filter must flip True."""
    se = SurfaceEvidence.model_validate({
        "evidence_grade": "direct_single_method",
        "grade_rationale": "—",
        "methods": [_method(
            expression_system="overexpression",
            accessibility_relevance="direct_surface_accessibility",
        )],
        "non_surface_expression": [],
        "contradicting_evidence": [],
        "claim_stances": [],
    })
    filters = _derive_filters(
        executive_summary=_exec(),
        surface_evidence=se,
        biological_context=_bio_ctx(),
        accessibility_risks=_risks(),
        filters_llm=_llm_filters(),
        deterministic_features=_det(),
        n_evidence=1,
    )
    assert filters.overexpression_surface_localization_observed is True


def test_overexpression_filter_true_for_mixed_expression_system():
    """`mixed` expression_system (overexpression + endogenous in the
    same panel) also counts — the OE side of the panel is what matters
    for the filter."""
    # NB: ``direct_single_method`` is now enforced (v2.4.0) by the cross-
    # block validator to require ≥1 ``direct_surface_accessibility``
    # method. The OE filter we're exercising here doesn't care which
    # accessibility_relevance the method has — it keys off
    # ``expression_system='mixed'`` — so pin relevance to direct and the
    # filter logic still runs.
    se = SurfaceEvidence.model_validate({
        "evidence_grade": "direct_single_method",
        "grade_rationale": "—",
        "methods": [_method(
            expression_system="mixed",
            accessibility_relevance="direct_surface_accessibility",
        )],
        "non_surface_expression": [],
        "contradicting_evidence": [],
        "claim_stances": [],
    })
    filters = _derive_filters(
        executive_summary=_exec(),
        surface_evidence=se,
        biological_context=_bio_ctx(),
        accessibility_risks=_risks(),
        filters_llm=_llm_filters(),
        deterministic_features=_det(),
        n_evidence=1,
    )
    assert filters.overexpression_surface_localization_observed is True


def test_overexpression_filter_false_when_endogenous_only():
    """No OE method observed → filter stays False. (The protein may
    still be on the surface endogenously; this filter is about whether
    OE-based validation has been done.)"""
    se = SurfaceEvidence.model_validate({
        "evidence_grade": "direct_single_method",
        "grade_rationale": "—",
        "methods": [_method(
            expression_system="endogenous",
            accessibility_relevance="direct_surface_accessibility",
        )],
        "non_surface_expression": [],
        "contradicting_evidence": [],
        "claim_stances": [],
    })
    filters = _derive_filters(
        executive_summary=_exec(),
        surface_evidence=se,
        biological_context=_bio_ctx(),
        accessibility_risks=_risks(),
        filters_llm=_llm_filters(),
        deterministic_features=_det(),
        n_evidence=1,
    )
    assert filters.overexpression_surface_localization_observed is False


def test_overexpression_filter_false_when_oe_without_surface_localization():
    """OE observed but the method was indirect (membrane fractionation,
    not surface assay). The bool is specifically OE+surface, not just OE."""
    se = SurfaceEvidence.model_validate({
        "evidence_grade": "supportive_but_indirect",
        "grade_rationale": "—",
        "methods": [_method(
            expression_system="overexpression",
            accessibility_relevance="supports_membrane_association",
        )],
        "non_surface_expression": [],
        "contradicting_evidence": [],
        "claim_stances": [],
    })
    filters = _derive_filters(
        executive_summary=_exec(),
        surface_evidence=se,
        biological_context=_bio_ctx(),
        accessibility_risks=_risks(),
        filters_llm=_llm_filters(),
        deterministic_features=_det(),
        n_evidence=1,
    )
    assert filters.overexpression_surface_localization_observed is False


def test_overexpression_filter_false_when_no_methods():
    """Empty methods list (e.g. weak-grade record where the builder
    found no usable methods) → filter is False, never raises."""
    se = SurfaceEvidence.model_validate({
        "evidence_grade": "weak",
        "grade_rationale": "—",
        "methods": [],
        "non_surface_expression": [],
        "contradicting_evidence": [],
        "claim_stances": [],
    })
    filters = _derive_filters(
        executive_summary=_exec().model_copy(update={
            "surface_accessibility": "no",
            "evidence_grade_summary": "weak",
            "surface_call_reason": "cytoplasmic",
        }),
        surface_evidence=se,
        biological_context=_bio_ctx(),
        accessibility_risks=_risks(),
        filters_llm=_llm_filters(),
        deterministic_features=_det(),
        n_evidence=0,
    )
    assert filters.overexpression_surface_localization_observed is False


# ---------------------------------------------------------------------------
# Prompt tripwire — stance section + emit-order constraint
# ---------------------------------------------------------------------------


def test_evidence_grade_prompt_documents_claim_stances():
    """The evidence_grade_builder prompt must instruct the LLM on the
    new claim_stances field: what each stance value means, what each
    weight value means, and that stances must be emitted BEFORE the
    grade_rationale (so the structured per-claim call comes first;
    the rationale then summarizes the stances rather than the reverse)."""
    from pathlib import Path

    prompt_path = (
        Path(__file__).parent.parent
        / "src/accessible_surfaceome/agents/surfaceome_v2/prompts/evidence_grade_builder_system.md"
    )
    body = prompt_path.read_text().lower()
    assert "claim_stances" in body
    # All four stance values mentioned
    for stance in [
        "supports_surface",
        "contradicts_surface",
        "tangential",
        "expression_only",
    ]:
        assert stance in body, f"stance '{stance}' must be documented in the prompt"
    # All three weights mentioned
    for weight in ["high", "moderate", "low"]:
        assert weight in body
    # Emit-order constraint: stances before rationale
    assert any(
        phrase in body
        for phrase in [
            "before `grade_rationale`",
            "before grade_rationale",
            "before the rationale",
            "claim_stances first",
            "stances first",
            "stances before",
        ]
    )
