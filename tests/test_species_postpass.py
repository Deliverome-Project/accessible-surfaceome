"""Tests for the deterministic species post-pass over BiologicalContext + SurfaceEvidence.

Three behaviors:

1. Rows with ``species="unspecified"`` get filled from cell-line tokens
   in their free-text fields.
2. Rows where the agent already set ``species`` to anything other than
   "unspecified" are NOT overwritten by the post-pass — the agent had
   paper context the post-pass doesn't.
3. ``species_inferred`` is set ``True`` exactly when the post-pass did
   the filling.
"""

from __future__ import annotations

from accessible_surfaceome.agents.surfaceome_v2.species_postpass import (
    apply_species_post_pass,
)
from accessible_surfaceome.tools._shared.models import (
    AccessibilityModulationObservation,
    AssayContext,
    BiologicalContext,
    Evidence,
    ExpressionObservation,
    ExpressionRow,
    MethodObservation,
    Species,
    SubcellularLocalization,
    SurfaceEvidence,
)


def _evidence(eid: str, species: Species) -> Evidence:
    return Evidence(
        evidence_id=eid,
        claim="test claim",
        claim_type="surface_expression",
        direction="supports",
        evidence_type="surface_biotinylation",
        evidence_tier="primary",
        confidence="moderate",
        assay_context=AssayContext(species=species),
        spans=[],
        entailment_verified=False,
    )


def _bio(
    expression: list[ExpressionRow] | None = None,
    modulation: list[AccessibilityModulationObservation] | None = None,
) -> BiologicalContext:
    return BiologicalContext(
        expression=expression or [],
        cell_states=[],
        subcellular_localization=SubcellularLocalization(
            primary_compartment="plasma_membrane",
        ),
        anatomical_accessibility=[],
        accessibility_modulation=modulation or [],
    )


def _surf(methods: list[MethodObservation] | None = None) -> SurfaceEvidence:
    return SurfaceEvidence(
        evidence_grade="supportive_but_indirect",
        grade_rationale="test stub",
        methods=methods or [],
        non_surface_expression=[],
        contradicting_evidence=[],
    )


def _method(observations: list[ExpressionObservation]) -> MethodObservation:
    return MethodObservation(
        method_family="flow_cytometry",
        method_subclass="live_cell_flow",
        permeabilization="live_cell",
        expression_system="endogenous",
        antibodies=[],
        accessibility_relevance="supports_surface_localization",
        surface_claim_type="surface_accessible",
        expression_observations=observations,
    )


def test_post_pass_fills_expression_species_from_cell_line() -> None:
    bio = _bio(
        expression=[
            ExpressionRow(
                tissue="bone",
                cell_type="osteoblast (MC3T3-E1)",
                present="moderate",
                disease_context="normal",
            ),
        ]
    )
    surf = _surf()
    stats = apply_species_post_pass(biological_context=bio, surface_evidence=surf)
    assert stats.expression_filled == 1
    assert bio.expression[0].species == "mouse"
    assert bio.expression[0].species_inferred is True


def test_post_pass_fills_expression_obs_from_context() -> None:
    surf = _surf(methods=[
        _method([
            ExpressionObservation(
                context="U251 MG glioblastoma cells; sulfo-NHS biotin labeling",
                sample_type="established_cell_line",
                level="moderate",
            ),
        ])
    ])
    stats = apply_species_post_pass(biological_context=_bio(), surface_evidence=surf)
    assert stats.expression_obs_filled == 1
    obs = surf.methods[0].expression_observations[0]
    assert obs.species == "human"
    assert obs.species_inferred is True


def test_post_pass_does_not_overwrite_agent_set_species() -> None:
    # Agent explicitly set species="human" — the post-pass must NOT touch
    # it even if the text contains a mouse-cell-line token.
    bio = _bio(
        expression=[
            ExpressionRow(
                cell_type="primary osteoblast (compared to NIH-3T3 mouse fibroblast)",
                present="moderate",
                disease_context="normal",
                species="human",  # agent's call: this is the human row
            ),
        ]
    )
    stats = apply_species_post_pass(biological_context=bio, surface_evidence=_surf())
    assert stats.expression_filled == 0
    assert bio.expression[0].species == "human"
    assert bio.expression[0].species_inferred is False


def test_post_pass_skips_row_with_no_cell_line_match() -> None:
    bio = _bio(
        expression=[
            ExpressionRow(
                tissue="solid tumor (primary)",
                present="moderate",
                disease_context="tumor",
            ),
        ]
    )
    stats = apply_species_post_pass(biological_context=bio, surface_evidence=_surf())
    assert stats.expression_filled == 0
    assert bio.expression[0].species == "unspecified"
    assert bio.expression[0].species_inferred is False


def test_post_pass_skips_ambiguous_multi_species_row() -> None:
    # Both a human and a mouse cell line mentioned → ambiguous, leave alone.
    bio = _bio(
        expression=[
            ExpressionRow(
                cell_type="osteoblast (HeLa control vs MC3T3-E1)",
                present="moderate",
                disease_context="normal",
            ),
        ]
    )
    stats = apply_species_post_pass(biological_context=bio, surface_evidence=_surf())
    assert stats.expression_filled == 0
    assert bio.expression[0].species == "unspecified"


def test_cite_aggregation_fills_abstract_row_when_all_cites_agree() -> None:
    # "bone" doesn't contain a cell-line token, but its cited evidence
    # (a single mouse-tagged paper) populates assay_context.species=mouse
    # → cite-aggregation pass fills the row.
    bio = _bio(
        expression=[
            ExpressionRow(
                tissue="bone",
                cell_type="osteoblast",
                present="moderate",
                disease_context="normal",
                cited_evidence_ids=["e_mouse_1"],
            ),
        ]
    )
    evidence = [_evidence("e_mouse_1", "mouse")]
    stats = apply_species_post_pass(
        biological_context=bio, surface_evidence=_surf(), evidence=evidence
    )
    assert stats.expression_filled == 1
    assert stats.filled_by_cite_aggregation == 1
    assert stats.filled_by_gazetteer == 0
    assert bio.expression[0].species == "mouse"
    assert bio.expression[0].species_inferred is True


def test_cite_aggregation_skips_row_when_cites_disagree() -> None:
    # Two cited evidence rows with different species → ambiguous, leave alone.
    bio = _bio(
        expression=[
            ExpressionRow(
                tissue="bone",
                present="moderate",
                disease_context="normal",
                cited_evidence_ids=["e_mouse_1", "e_human_1"],
            ),
        ]
    )
    evidence = [
        _evidence("e_mouse_1", "mouse"),
        _evidence("e_human_1", "human"),
    ]
    stats = apply_species_post_pass(
        biological_context=bio, surface_evidence=_surf(), evidence=evidence
    )
    assert stats.expression_filled == 0
    assert bio.expression[0].species == "unspecified"


def test_cite_aggregation_ignores_unspecified_cites() -> None:
    # Two cited rows, one unspecified + one mouse → the unspecified gets
    # filtered, mouse wins, row fills with mouse.
    bio = _bio(
        expression=[
            ExpressionRow(
                tissue="bone",
                present="moderate",
                disease_context="normal",
                cited_evidence_ids=["e_unspec_1", "e_mouse_1"],
            ),
        ]
    )
    evidence = [
        _evidence("e_unspec_1", "unspecified"),
        _evidence("e_mouse_1", "mouse"),
    ]
    stats = apply_species_post_pass(
        biological_context=bio, surface_evidence=_surf(), evidence=evidence
    )
    assert stats.expression_filled == 1
    assert bio.expression[0].species == "mouse"


def test_cite_aggregation_skipped_when_evidence_is_none() -> None:
    # No evidence arg → pass 2 doesn't run, row stays unspecified.
    bio = _bio(
        expression=[
            ExpressionRow(
                tissue="bone",
                present="moderate",
                disease_context="normal",
                cited_evidence_ids=["e_mouse_1"],
            ),
        ]
    )
    stats = apply_species_post_pass(
        biological_context=bio, surface_evidence=_surf(), evidence=None
    )
    assert stats.expression_filled == 0
    assert bio.expression[0].species == "unspecified"


def test_gazetteer_pass_runs_before_cite_aggregation() -> None:
    # Row has a cell-line token in cell_type AND cited evidence with
    # a different species. The gazetteer pass fires first; pass 2
    # skips the row because species is no longer unspecified.
    bio = _bio(
        expression=[
            ExpressionRow(
                tissue="bone",
                cell_type="MC3T3-E1 osteoblast",
                present="moderate",
                disease_context="normal",
                cited_evidence_ids=["e_human_1"],  # different species
            ),
        ]
    )
    evidence = [_evidence("e_human_1", "human")]
    stats = apply_species_post_pass(
        biological_context=bio, surface_evidence=_surf(), evidence=evidence
    )
    assert stats.expression_filled == 1
    assert stats.filled_by_gazetteer == 1
    assert stats.filled_by_cite_aggregation == 0
    assert bio.expression[0].species == "mouse"  # gazetteer won
