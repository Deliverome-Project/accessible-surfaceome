"""Schema additions for Chunk 8 of the PR #47 redesign: the
accessibility_context_summary headline (A1.7) and the SynthesizerLLMFilters
chip rationales + warn-only inline-cite validator (A1.6 / A8.2)."""

from __future__ import annotations

import logging

from accessible_surfaceome.tools._shared.models import SynthesizerLLMFilters


def _llm_filters(
    expression_level_rationale: str = "",
    expression_breadth_rationale: str = "",
    surface_specificity_rationale: str = "",
) -> SynthesizerLLMFilters:
    return SynthesizerLLMFilters(
        expression_level="moderate",
        expression_breadth="broad",
        surface_specificity="surface_dominant",
        # Default to orphan-receptor case so the empty rationale is
        # valid under the has_known_ligand=True-requires-rationale
        # validator. Tests that need a positive ligand override.
        has_known_ligand=False,
        expression_level_rationale=expression_level_rationale,
        expression_breadth_rationale=expression_breadth_rationale,
        surface_specificity_rationale=surface_specificity_rationale,
    )


def test_rationales_default_empty():
    f = _llm_filters()
    assert f.expression_level_rationale == ""
    assert f.surface_specificity_rationale == ""


def test_rationale_with_inline_cite_does_not_warn(caplog):
    with caplog.at_level(logging.WARNING):
        _llm_filters(expression_level_rationale="broadly high (a2_evi_03)")
    assert "lacks an inline" not in caplog.text


def test_rationale_without_cite_warns_but_does_not_raise(caplog):
    # Warn-only: the value is accepted (synth is a Managed Agent with no
    # in-process repair loop), but the missing cite is logged.
    with caplog.at_level(logging.WARNING):
        f = _llm_filters(expression_breadth_rationale="broad across many tissues")
    assert f.expression_breadth_rationale == "broad across many tissues"
    assert "lacks an inline" in caplog.text


def test_accessibility_context_summary_is_optional_str():
    from accessible_surfaceome.tools._shared.models import ExecutiveSummary

    # Additive default "" keeps pre-A1.7 records valid (the field is not
    # required, so v1 ExecutiveSummary output still validates).
    field = ExecutiveSummary.model_fields["accessibility_context_summary"]
    assert field.default == ""
    assert field.is_required() is False
