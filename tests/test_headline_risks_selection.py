"""Tripwire tests for the synthesizer's headline_risks selection
discipline (PR #38 follow-up after content audit found 3/6 samples
using ``other`` to dodge and GPR75 missing the orphan-class enum
values the design added specifically for it).

These tests assert the prompt CONTENT carries the discipline rules —
they don't run the synthesizer (that's exercised in the end-to-end
re-runs on CD81 / HSPA5 / GPR75 listed in the plan).
"""

from __future__ import annotations

from accessible_surfaceome.agents.surfaceome_synthesizer.runner import (
    SYSTEM_PROMPT_PATH as SYNTH_SYSTEM_PROMPT_PATH,
)


def test_synthesizer_prompt_has_headline_risks_section() -> None:
    body = SYNTH_SYSTEM_PROMPT_PATH.read_text()
    # Must have a dedicated section so the discipline is locatable, not
    # buried in a sub-bullet inside "The judgment that matters".
    assert "## Headline-risks selection discipline" in body


def test_synthesizer_prompt_warns_against_other_as_dodge() -> None:
    body = SYNTH_SYSTEM_PROMPT_PATH.read_text().lower()
    assert "last-resort escape hatch" in body
    # Specific anti-pattern callouts the audit found in committed samples
    # (HSPA5 had "other" for EV decoys; should be `secreted_form`).
    assert "ev-associated decoy pool" in body
    assert "intracellular pool with stress-induced surface" in body


def test_synthesizer_prompt_names_all_three_orphan_class_signals() -> None:
    """The audit found GPR75 missing `low_endogenous_expression` +
    `ligand_unknown` in its headline_risks. The prompt must call out
    all three orphan-class signals explicitly."""
    body = SYNTH_SYSTEM_PROMPT_PATH.read_text()
    for token in (
        "low_endogenous_expression",
        "antibody_validation_weak",
        "ligand_unknown",
    ):
        assert token in body, (
            f"synthesizer prompt must name {token!r} as an orphan-class "
            "signal so the catalog can filter on it"
        )


def test_synthesizer_prompt_has_weak_evidence_audit_guard() -> None:
    """When evidence_grade is weak, at least one orphan-class signal
    must appear in headline_risks. The audit guard tells the model so."""
    body = SYNTH_SYSTEM_PROMPT_PATH.read_text().lower()
    assert "audit guard" in body
    assert "weak" in body
    assert "must appear in" in body or "must appear" in body
