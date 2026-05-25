"""Tests for the new Filter promotions (PR for the prompt/filter rethink):

1. ``Filters.state_dependence`` — copied from ``executive_summary.state_dependence``
2. ``Filters.co_receptor_dependency`` — full 4-value enum copied from
   ``accessibility_risks.co_receptor_requirements.surface_expression_dependency``
   (alongside the existing ``requires_coreceptor_for_expression`` bool)
3. ``ExecutiveSummary.surface_call_reason`` + ``Filters.surface_call_reason``
   — re-emitted by the synthesizer (NOT inherited from the triage's reason),
   uses the same TriageReason enum so the catalog can filter by the same
   vocabulary regardless of which agent produced the reason.

Plus prompt-content tripwires: synth prompt instructs the LLM to re-derive
the reason from A1+A2 evidence (not blindly copy triage), and treats
state-conditional high accessibility as ``surface_accessibility=high``
when the conditional state itself shows high accessibility.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from accessible_surfaceome.agents.surfaceome_synthesizer.runner import (
    SYSTEM_PROMPT_PATH as SYNTH_SYSTEM_PROMPT_PATH,
)
from accessible_surfaceome.agents.surfaceome_v1.orchestrator import (
    _derive_filters,
)
from accessible_surfaceome.tools._shared.models import (
    AccessibilityRisks,
    BiologicalContext,
    DeterministicFeatures,
    ExecutiveSummary,
    Filters,
    IsoformTopology,
    Orthologs,
    StructureFeatures,
    SubcellularLocalization,
    SurfaceEvidence,
    SynthesizerLLMFilters,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _risks(co_receptor_dependency: str = "none") -> AccessibilityRisks:
    return AccessibilityRisks.model_validate(
        {
            "co_receptor_requirements": {
                "surface_expression_dependency": co_receptor_dependency,
                "partners": [],
                "evidence_basis": "mixed",
                "rationale": "—",
                "cited_evidence_ids": [],
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
        }
    )


def _exec(
    *,
    state_dependence: str = "moderate",
    surface_call_reason: str = "classical_surface_receptor",
    surface_accessibility: str = "moderate",
) -> ExecutiveSummary:
    payload: dict[str, Any] = {
        "one_paragraph": "—",
        "state_dependence": state_dependence,
        "evidence_grade_summary": "weak",
        "surface_accessibility": surface_accessibility,
        "subcategory": "other",
        "confidence": "moderate",
        "headline_risks": [],
        "cited_evidence_ids": [],
        "surface_call_reason": surface_call_reason,
    }
    return ExecutiveSummary.model_validate(payload)


def _det() -> DeterministicFeatures:
    now = datetime.now(UTC)
    return DeterministicFeatures(
        canonical_topology=IsoformTopology(
            isoform_id="P00000-1",
            uniprot_acc="P00000",
            tm_helix_count=0,
            n_terminal_orientation="cytoplasmic",
            c_terminal_orientation="cytoplasmic",
            signal_peptide_length=0,
            ecd_length_residues=0,
            icd_length_residues=100,
            per_residue_topology="",
            tool_version="stub",
            retrieved_at=now,
        ),
        isoform_topologies=[],
        orthologs=Orthologs(),
        paralogs=[],
        structure=StructureFeatures(
            afdb_id="AF-P00000-F1-model_v4",
            afdb_version="v4",
            ecd_mean_plddt=0.0,
            ecd_disordered_fraction=0.0,
            source="stub",
            license="CC BY 4.0",
            attribution="© DeepMind / EMBL-EBI",
        ),
    )


def _llm_filters() -> SynthesizerLLMFilters:
    return SynthesizerLLMFilters(
        expression_level="moderate",
        expression_breadth="broad",
        surface_specificity="surface_dominant",
    )


def _surface_evidence() -> SurfaceEvidence:
    return SurfaceEvidence(
        evidence_grade="weak",
        grade_rationale="—",
        methods=[],
        non_surface_expression=[],
        contradicting_evidence=[],
        therapeutic_engagement=None,
    )


def _bio_ctx() -> BiologicalContext:
    return BiologicalContext(
        tissues=[], cell_types=[], cell_states=[],
        subcellular_localization=SubcellularLocalization(
            primary_compartment="plasma_membrane",
            dual_localization=[], membrane_subdomains=[],
        ),
        anatomical_accessibility=[],
        accessibility_modulation=[],
    )


# ---------------------------------------------------------------------------
# Schema additions
# ---------------------------------------------------------------------------


def test_filters_has_state_dependence_field():
    """Filters must accept state_dependence so the catalog can D1-filter
    on it without joining through executive_summary."""
    assert "state_dependence" in Filters.model_fields


def test_filters_has_co_receptor_dependency_enum_field():
    """Filters must expose the full 4-value CoreceptorDependency enum
    (required / modulatory / none / unknown), not just the
    'requires_coreceptor_for_expression' bool — the bool collapses
    'modulatory' into False, losing a real signal."""
    assert "co_receptor_dependency" in Filters.model_fields


def test_filters_has_surface_call_reason_field():
    assert "surface_call_reason" in Filters.model_fields


def test_executive_summary_has_surface_call_reason_field():
    """The synthesizer must emit its own reason for the surface call,
    re-derived from A1+A2 evidence (not inherited from the triage)."""
    assert "surface_call_reason" in ExecutiveSummary.model_fields


# ---------------------------------------------------------------------------
# _derive_filters propagation
# ---------------------------------------------------------------------------


def test_derive_filters_propagates_state_dependence():
    filters = _derive_filters(
        executive_summary=_exec(state_dependence="high"),
        surface_evidence=_surface_evidence(),
        biological_context=_bio_ctx(),
        accessibility_risks=_risks(),
        filters_llm=_llm_filters(),
        deterministic_features=_det(),
        n_evidence=1,
    )
    assert filters.state_dependence == "high"


def test_derive_filters_propagates_co_receptor_dependency_full_enum():
    """The new enum field must carry 'modulatory' through — that's the
    case the existing bool flattens incorrectly."""
    filters = _derive_filters(
        executive_summary=_exec(),
        surface_evidence=_surface_evidence(),
        biological_context=_bio_ctx(),
        accessibility_risks=_risks(co_receptor_dependency="modulatory"),
        filters_llm=_llm_filters(),
        deterministic_features=_det(),
        n_evidence=1,
    )
    assert filters.co_receptor_dependency == "modulatory"
    # And the legacy bool still reads correctly (False for modulatory)
    assert filters.requires_coreceptor_for_expression is False


def test_derive_filters_propagates_surface_call_reason():
    filters = _derive_filters(
        executive_summary=_exec(surface_call_reason="inner_leaflet_anchored"),
        surface_evidence=_surface_evidence(),
        biological_context=_bio_ctx(),
        accessibility_risks=_risks(),
        filters_llm=_llm_filters(),
        deterministic_features=_det(),
        n_evidence=1,
    )
    assert filters.surface_call_reason == "inner_leaflet_anchored"


# ---------------------------------------------------------------------------
# Prompt-content tripwires
# ---------------------------------------------------------------------------


def test_synth_prompt_explains_surface_call_reason_re_derivation():
    """The synth prompt must instruct the LLM to RE-DERIVE the reason
    from A1+A2 evidence rather than blindly copy the triage's reason —
    that's what makes the rolled-up reason a deep-dive signal, not just
    a triage echo."""
    body = SYNTH_SYSTEM_PROMPT_PATH.read_text().lower()
    assert "surface_call_reason" in body
    # Re-derivation guidance — accept either phrasing
    assert any(
        phrase in body
        for phrase in (
            "re-derive",
            "rederive",
            "your own reason",
            "do not inherit",
            "do not copy",
            "confirm or override",
        )
    )


def test_synth_prompt_explains_state_conditional_high_accessibility():
    """The synth prompt must say: if accessibility is high in some state,
    set surface_accessibility=high (with state_dependence flagging the
    conditionality) — don't pick the worst-case state as the headline.
    SRC is the canonical case: cancer-state high is the target-discovery
    signal; normal-cell low is the conditionality on top."""
    body = SYNTH_SYSTEM_PROMPT_PATH.read_text().lower()
    # Either phrasing acceptable
    assert any(
        phrase in body
        for phrase in (
            "high in any context",
            "high in some context",
            "high in a specific state",
            "state-conditional high",
            "best-case state",
            "pick the highest accessibility across states",
        )
    )
