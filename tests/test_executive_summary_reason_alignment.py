"""Tests for the (surface_accessibility, state_dependence, surface_call_reason) cross-check on ExecutiveSummary.

The triage side has ``_check_reason_matches_verdict`` to ensure
(verdict, reason) pairs are internally consistent. The synth side was
missing the analogous validator until this fix — meaning the synth could
emit nonsensical combinations like ``surface_accessibility="high",
state_dependence="low", surface_call_reason="cytoplasmic"`` (a high
canonical surface call with a NO-bucket reason) and nothing in the
schema would catch it.

The validator added to ExecutiveSummary enforces bucket alignment:

* ``surface_accessibility ∈ {high, moderate}`` + ``state_dependence ∈ {low, unclear}``
  → reason must be from the YES-bucket (canonical surface mechanisms).
* ``surface_accessibility ∈ {high, moderate}`` + ``state_dependence ∈ {moderate, high}``
  → reason can be YES OR CONTEXTUAL (state-gated surface).
* ``surface_accessibility = no`` → reason must be from the NO-bucket.
* ``surface_accessibility = low`` → reason from NO or CONTEXTUAL bucket
  (a marginal-yes state may justify a low overall accessibility call).
* ``surface_accessibility = uncertain`` → any reason is allowed
  (by definition the synth wasn't sure).
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from accessible_surfaceome.tools._shared.models import ExecutiveSummary


def _es(**overrides: Any) -> ExecutiveSummary:
    """Build a minimal ExecutiveSummary kwargs dict with sane defaults.

    ``dict[str, Any]`` suppresses ty's Literal narrowing on the splat —
    Pydantic accepts the str values at runtime and validates them
    against the Literal enums itself.
    """
    base: dict[str, Any] = dict(
        one_paragraph="...",
        surface_accessibility="high",
        evidence_grade_summary="direct_multi_method",
        confidence="high",
        state_dependence="low",
        subcategory="single_pass_T1",
        protein_family="receptor",
        surface_call_reason="classical_surface_receptor",
        headline_risks=[],
        cited_evidence_ids=[],
    )
    base.update(overrides)
    return ExecutiveSummary(**base)


# ---------------------------------------------------------------------------
# YES-bucket alignment: canonical-surface call must use YES-bucket reason
# ---------------------------------------------------------------------------


def test_high_low_statedep_rejects_no_bucket_reason():
    """surface_accessibility=high with state_dependence=low requires a
    YES-bucket reason. Pairing high canonical accessibility with
    `cytoplasmic` (NO-bucket) is a synth confusion to catch."""
    with pytest.raises(ValidationError, match="surface_call_reason"):
        _es(
            surface_accessibility="high",
            state_dependence="low",
            surface_call_reason="cytoplasmic",
        )


def test_moderate_low_statedep_rejects_no_bucket_reason():
    """Same rule applies to moderate accessibility."""
    with pytest.raises(ValidationError, match="surface_call_reason"):
        _es(
            surface_accessibility="moderate",
            state_dependence="low",
            surface_call_reason="inner_leaflet_anchored",
        )


def test_high_low_statedep_accepts_yes_bucket():
    """Sanity: the canonical valid case for a high canonical-surface call."""
    es = _es(
        surface_accessibility="high",
        state_dependence="low",
        surface_call_reason="classical_surface_receptor",
    )
    assert es.surface_call_reason == "classical_surface_receptor"


# ---------------------------------------------------------------------------
# State-conditional: high + state_dep=high allows YES or CONTEXTUAL
# ---------------------------------------------------------------------------


def test_high_high_statedep_accepts_contextual_bucket():
    """SRC's actual emitted combo: surface_accessibility=high (cancer
    state), state_dependence=high, surface_call_reason=lysosomal_exocytosis
    (CONTEXTUAL bucket). This is the design-intent valid combo for
    cancer-state surface evidence."""
    es = _es(
        surface_accessibility="high",
        state_dependence="high",
        surface_call_reason="lysosomal_exocytosis",
    )
    assert es.surface_call_reason == "lysosomal_exocytosis"


def test_moderate_high_statedep_accepts_yes_bucket():
    """When state-dependent, the synth may still pick a YES-bucket
    reason (e.g., classical_surface_receptor for a constitutive surface
    protein whose level varies). Allowed."""
    es = _es(
        surface_accessibility="moderate",
        state_dependence="moderate",
        surface_call_reason="classical_surface_receptor",
    )
    assert es.surface_call_reason == "classical_surface_receptor"


def test_high_high_statedep_rejects_no_bucket():
    """Even with state-dependence, a NO-bucket reason is incompatible
    with a high accessibility call — that would say "the protein is
    canonically not at the surface AND also high accessibility" which
    contradicts itself."""
    with pytest.raises(ValidationError, match="surface_call_reason"):
        _es(
            surface_accessibility="high",
            state_dependence="high",
            surface_call_reason="nuclear",
        )


# ---------------------------------------------------------------------------
# NO accessibility: reason must be NO-bucket
# ---------------------------------------------------------------------------


def test_no_accessibility_requires_no_bucket():
    """surface_accessibility=no requires a NO-bucket reason — anything
    else contradicts the headline call."""
    with pytest.raises(ValidationError, match="surface_call_reason"):
        _es(
            surface_accessibility="no",
            surface_call_reason="classical_surface_receptor",
        )


def test_no_accessibility_accepts_no_bucket():
    es = _es(
        surface_accessibility="no",
        surface_call_reason="cytoplasmic",
    )
    assert es.surface_accessibility == "no"


# ---------------------------------------------------------------------------
# Low accessibility: NO or CONTEXTUAL bucket
# ---------------------------------------------------------------------------


def test_low_accessibility_accepts_contextual_bucket():
    """low accessibility with a CONTEXTUAL reason: the protein has a
    state-gated surface but the headline call is low because the
    state-gate is rare / niche. Valid."""
    es = _es(
        surface_accessibility="low",
        state_dependence="moderate",
        surface_call_reason="lysosomal_exocytosis",
    )
    assert es.surface_accessibility == "low"


def test_low_accessibility_rejects_yes_bucket():
    """low accessibility with a canonical YES-bucket reason contradicts
    itself."""
    with pytest.raises(ValidationError, match="surface_call_reason"):
        _es(
            surface_accessibility="low",
            surface_call_reason="classical_surface_receptor",
        )


# ---------------------------------------------------------------------------
# Uncertain: anything allowed
# ---------------------------------------------------------------------------


def test_uncertain_accepts_any_reason():
    """uncertain accessibility means the synth couldn't tell — any
    reason is allowed since by definition the synth wasn't confident
    enough to constrain the explanation."""
    # All three buckets should pass under uncertain
    for reason in ["classical_surface_receptor", "cell_state_induced", "cytoplasmic"]:
        es = _es(
            surface_accessibility="uncertain",
            surface_call_reason=reason,
        )
        assert es.surface_call_reason == reason


# ---------------------------------------------------------------------------
# `other` reason is always allowed (escape hatch in each bucket)
# ---------------------------------------------------------------------------


def test_other_reason_always_allowed():
    """`other` is in all three buckets (YES, CONTEXTUAL, NO) — the
    synth can always fall back to `other` when no specific reason fits."""
    for sa in ["high", "moderate", "low", "no", "uncertain"]:
        es = _es(surface_accessibility=sa, surface_call_reason="other")
        assert es.surface_call_reason == "other"
