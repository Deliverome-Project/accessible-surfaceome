"""Tests for the two new cross-bucket validators:

* ``SurfaceomeRecord._check_state_dependence_consistent_with_modulation`` —
  refuses ``executive_summary.state_dependence='low'`` when the A2 biology
  shows state-conditional upregulation of the surface form (the TROP2
  miscalibration: state_dependence='low' alongside 10 increases-direction
  modulation rows + induction_trigger='oncogenic').

* ``Filters._require_has_known_ligand_rationale_when_true`` and the
  ``SynthesizerLLMFilters`` mirror — refuse ``has_known_ligand=True``
  with empty rationale. If the ligand can't be named, the bool should
  be False (orphan-receptor case).

The state_dependence validator is tested by calling the function
directly on a duck-typed mock (SimpleNamespace) — building a full
``SurfaceomeRecord`` for each scenario means assembling 6+ required
sub-blocks, which obscures the bug surface. The validator only reads
four attributes; mocking those is clearer and the validator's logic
gets exercised either way.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from accessible_surfaceome.tools._shared.models import (
    Filters,
    SurfaceomeRecord,
    SynthesizerLLMFilters,
)


# ---- state_dependence validator (direct call on a mock) ----------------


def _make_mock(
    *,
    state_dependence: str = "low",
    surface_accessibility: str = "high",
    induction_trigger: str = "none",
    increases_rows: int = 0,
    oncogenic_increase: bool = False,
) -> SimpleNamespace:
    """Build a SimpleNamespace shaped like the slice of SurfaceomeRecord
    the state_dependence validator reads. Names + nesting mirror the
    Pydantic model so the validator runs unchanged."""
    rows: list[SimpleNamespace] = []
    for _ in range(increases_rows):
        rows.append(
            SimpleNamespace(
                direction="increases",
                cell_state_trigger=None,
            )
        )
    if oncogenic_increase:
        rows.append(
            SimpleNamespace(
                direction="increases",
                cell_state_trigger="oncogenic_transformation",
            )
        )
    return SimpleNamespace(
        executive_summary=SimpleNamespace(
            state_dependence=state_dependence,
            surface_accessibility=surface_accessibility,
        ),
        filters=SimpleNamespace(induction_trigger=induction_trigger),
        biological_context=SimpleNamespace(accessibility_modulation=rows),
    )


def _run(mock: SimpleNamespace) -> SimpleNamespace:
    """Invoke the validator function bound to mock as `self`. Returns
    the mock on success; raises on violation.

    The model_validator decorator wraps the underlying function in a
    PydanticDescriptorProxy; the proxy is callable at runtime but the
    static type checker sees it as a descriptor object. The ty:ignore
    suppresses the false positive on what is in fact a working call.
    """
    SurfaceomeRecord._check_state_dependence_consistent_with_modulation(  # ty:ignore[call-non-callable]
        mock
    )
    return mock


def test_state_dep_low_ok_when_biology_is_quiet():
    """No induction trigger, no increases rows → 'low' OK."""
    _run(_make_mock(state_dependence="low"))


def test_state_dep_low_rejected_when_induction_trigger_nonzero():
    with pytest.raises(ValueError) as excinfo:
        _run(_make_mock(state_dependence="low", induction_trigger="oncogenic"))
    msg = str(excinfo.value)
    assert "state_dependence='low'" in msg
    assert "induction_trigger" in msg


def test_state_dep_low_rejected_when_three_or_more_increases():
    with pytest.raises(ValueError) as excinfo:
        _run(_make_mock(state_dependence="low", increases_rows=3))
    assert "3 accessibility_modulation rows" in str(excinfo.value)


def test_state_dep_low_accepted_with_only_two_increases():
    """Threshold is ≥3 — two increases rows still allow 'low'."""
    _run(_make_mock(state_dependence="low", increases_rows=2))


def test_state_dep_low_rejected_with_oncogenic_increase_row():
    with pytest.raises(ValueError) as excinfo:
        _run(_make_mock(state_dependence="low", oncogenic_increase=True))
    assert "oncogenic_transformation" in str(excinfo.value)


def test_state_dep_low_accepted_with_oncogenic_row_when_sa_is_no():
    """The oncogenic-increase clause is gated on
    surface_accessibility != 'no' — a 'no' call doesn't carry a
    targetable state to erase, so 'low' is allowed even with an
    oncogenic increase row."""
    _run(
        _make_mock(
            state_dependence="low",
            oncogenic_increase=True,
            surface_accessibility="no",
        )
    )


def test_state_dep_moderate_accepted_under_all_conditions():
    """The validator only refuses 'low'; 'moderate' and 'high' always
    pass even when all conditions fire."""
    _run(
        _make_mock(
            state_dependence="moderate",
            induction_trigger="oncogenic",
            increases_rows=5,
            oncogenic_increase=True,
        )
    )


def test_state_dep_error_lists_all_violations():
    """When multiple conditions fire, all are surfaced in one error
    message (so the reader sees the full picture, not a single hit)."""
    with pytest.raises(ValueError) as excinfo:
        _run(
            _make_mock(
                state_dependence="low",
                induction_trigger="oncogenic",
                increases_rows=4,
                oncogenic_increase=True,
            )
        )
    msg = str(excinfo.value)
    assert "induction_trigger" in msg
    assert "5 accessibility_modulation rows" in msg
    assert "oncogenic_transformation" in msg


# ---- has_known_ligand_rationale on SynthesizerLLMFilters ---------------


def test_synth_filters_true_with_rationale_ok():
    f = SynthesizerLLMFilters(
        expression_level="moderate",
        expression_breadth="broad",
        surface_specificity="surface_dominant",
        has_known_ligand=True,
        has_known_ligand_rationale=(
            "EGF binds EGFR ECD with sub-nM affinity (a1_evi_03)."
        ),
    )
    assert f.has_known_ligand_rationale.strip() != ""


def test_synth_filters_true_with_empty_rationale_rejected():
    with pytest.raises(ValidationError) as excinfo:
        SynthesizerLLMFilters(
            expression_level="moderate",
            expression_breadth="broad",
            surface_specificity="surface_dominant",
            has_known_ligand=True,
            has_known_ligand_rationale="",
        )
    assert "non-empty has_known_ligand_rationale" in str(excinfo.value)


def test_synth_filters_true_with_whitespace_rationale_rejected():
    with pytest.raises(ValidationError):
        SynthesizerLLMFilters(
            expression_level="moderate",
            expression_breadth="broad",
            surface_specificity="surface_dominant",
            has_known_ligand=True,
            has_known_ligand_rationale="   \n\t",
        )


def test_synth_filters_false_with_empty_rationale_ok():
    """Orphan-receptor case: bool flipped to False, empty rationale OK."""
    f = SynthesizerLLMFilters(
        expression_level="moderate",
        expression_breadth="broad",
        surface_specificity="surface_dominant",
        has_known_ligand=False,
        has_known_ligand_rationale="",
    )
    assert f.has_known_ligand is False


# ---- has_known_ligand_rationale on Filters (persisted) -----------------


def _filters_payload(
    *,
    has_known_ligand: bool,
    has_known_ligand_rationale: str,
) -> dict:
    """Minimum-valid Filters payload — every required field, with the
    ligand fields exposed for the validator under test. Matches what
    the orchestrator produces from a deep-dive run."""
    return {
        "surface_accessibility": "high",
        "confidence": "moderate",
        "state_dependence": "moderate",
        "surface_call_reason": "classical_surface_receptor",
        "subcategory": "single_pass_T1",
        "llm_family": "receptor",
        "evidence_grade": "direct_multi_method",
        "evidence_density": "moderate",
        "ecd_accessibility_class": "large",
        "expression_level": "moderate",
        "expression_breadth": "broad",
        "surface_specificity": "surface_dominant",
        "co_receptor_dependency": "none",
        "has_known_ligand": has_known_ligand,
        "has_known_ligand_rationale": has_known_ligand_rationale,
        "n_term_extracellular": True,
        "c_term_extracellular": False,
        "has_shed_form": False,
        "has_secreted_form": False,
        "requires_coreceptor_for_expression": False,
        "has_epitope_masking": False,
        "has_restricted_subdomain": False,
    }


def test_filters_true_with_rationale_ok():
    payload = _filters_payload(
        has_known_ligand=True,
        has_known_ligand_rationale="endogenous agonist X (a1_evi_05).",
    )
    f = Filters.model_validate(payload)
    assert f.has_known_ligand


def test_filters_true_with_empty_rationale_rejected():
    payload = _filters_payload(
        has_known_ligand=True, has_known_ligand_rationale=""
    )
    with pytest.raises(ValidationError) as excinfo:
        Filters.model_validate(payload)
    assert "non-empty has_known_ligand_rationale" in str(excinfo.value)


def test_filters_false_with_empty_rationale_ok():
    payload = _filters_payload(
        has_known_ligand=False, has_known_ligand_rationale=""
    )
    f = Filters.model_validate(payload)
    assert f.has_known_ligand is False
