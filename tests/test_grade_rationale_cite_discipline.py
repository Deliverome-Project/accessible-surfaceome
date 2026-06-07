"""Tests for SurfaceEvidence.grade_rationale citation-discipline + the
new ExcludedClaim audit field.

Two validators backstop the citation discipline:

* ``_warn_grade_rationale_missing_cite`` (warn-only) — fires when
  grade_rationale is non-empty and carries no inline (aN_evi_NN) cite.
  Soft signal; the GPR75-class "VPS35-retromer claim with no cite"
  case is its motivating example.
* ``_fail_grade_rationale_structured_claims_uncited`` (raises
  ValueError) — refuses the record when grade_rationale contains
  structured-claim markers (numbered items OR named experimental
  methods) AND claim_stances has ≥2 attributions AND zero inline
  cites. Catches the unambiguous "wrote specific claims, has the
  attributions, didn't inline them" failure.

ExcludedClaim is the audit-trail row the methods builder's inclusion
filter populates (via the evidence-grade builder's wrapper output) for
ligand-engagement-as-soluble-partner evidence that doesn't establish
surface accessibility of THIS protein.
"""

from __future__ import annotations

import logging

import pytest
from pydantic import ValidationError

from accessible_surfaceome.tools._shared.models import (
    ClaimStanceRow,
    ExcludedClaim,
    SurfaceEvidence,
)


# ---- ExcludedClaim -----------------------------------------------------


def test_excluded_claim_round_trip():
    row = ExcludedClaim(
        evidence_id="a1_evi_13",
        reason=(
            "HMGB1 binding TREM-1 on monocytes — soluble ligand engagement, "
            "not surface anchoring of HMGB1"
        ),
    )
    assert row.evidence_id == "a1_evi_13"
    assert "TREM-1" in row.reason


def test_excluded_claim_reason_too_long_rejected():
    with pytest.raises(ValidationError):
        ExcludedClaim(evidence_id="a1_evi_01", reason="x" * 500)


def test_surface_evidence_has_excluded_default_empty():
    """Back-compat: pre-rollout records lack `excluded_as_ligand_engagement`;
    the field defaults to an empty list."""
    se = SurfaceEvidence(
        evidence_grade="weak",
        grade_rationale="—",
    )
    assert se.excluded_as_ligand_engagement == []


def test_surface_evidence_accepts_excluded():
    se = SurfaceEvidence(
        evidence_grade="weak",
        grade_rationale="—",
        excluded_as_ligand_engagement=[
            ExcludedClaim(
                evidence_id="a1_evi_13",
                reason=(
                    "Crosslinking captures protein bound to TREM-1; "
                    "TREM-1 is the membrane component, this protein is "
                    "the soluble ligand."
                ),
            ),
            ExcludedClaim(
                evidence_id="a1_evi_15",
                reason=(
                    "Antibody-neutralization blocks the secreted factor's "
                    "extracellular activity, not a surface-anchored form."
                ),
            ),
        ],
    )
    assert len(se.excluded_as_ligand_engagement) == 2


# ---- _warn_grade_rationale_missing_cite (warn-only) --------------------


def test_warn_fires_when_grade_rationale_has_no_inline_cite(caplog):
    """A non-empty rationale without any (aN_evi_NN) emits a warning."""
    with caplog.at_level(logging.WARNING):
        SurfaceEvidence(
            evidence_grade="supportive_but_indirect",
            grade_rationale=(
                "The picture is loosely supportive. No specific method "
                "calls; just a sketch of the evidence shape."
            ),
        )
    assert any(
        "grade_rationale lacks an inline" in r.message for r in caplog.records
    ), (
        f"expected cite-missing warn; got: "
        f"{[r.message for r in caplog.records]}"
    )


def test_warn_silent_when_grade_rationale_has_inline_cite(caplog):
    with caplog.at_level(logging.WARNING):
        SurfaceEvidence(
            evidence_grade="supportive_but_indirect",
            grade_rationale=(
                "Loose summary anchored by one cite (a1_evi_07)."
            ),
        )
    assert not any(
        "grade_rationale lacks an inline" in r.message for r in caplog.records
    )


def test_warn_silent_when_grade_rationale_empty(caplog):
    """Empty rationale doesn't warn (the required-field check covers that;
    the cite-warn is gated on non-empty content)."""
    with caplog.at_level(logging.WARNING):
        SurfaceEvidence(
            evidence_grade="weak",
            grade_rationale="—",
        )
    assert not any(
        "grade_rationale lacks an inline" in r.message for r in caplog.records
    )


# ---- _fail_grade_rationale_structured_claims_uncited (raises) ----------


def _gpr75_style_uncited_rationale() -> str:
    """The GPR75-shaped failure: three numbered claims, named methods,
    no inline cites — and claim_stances has ≥2 attributions, so the
    cites are AVAILABLE; the writer just didn't inline them."""
    return (
        "Three direct lines of evidence support surface exposure: "
        "(1) endogenous 3xFlag-GPR75 knockin mice showing ciliary PM "
        "localization in hypothalamic neurons by IF; "
        "(2) photoaffinity crosslinking of a 20-HETE analogue on "
        "membrane fractions; "
        "(3) VPS35-mediated retromer recycling to the hepatocyte PM. "
        "Graded supportive_but_indirect."
    )


def test_fail_on_structured_claims_without_cites():
    """The GPR75-shaped record: enumerated claims + named methods +
    two attributions in claim_stances + zero inline cites → reject."""
    with pytest.raises(ValidationError) as excinfo:
        SurfaceEvidence(
            evidence_grade="supportive_but_indirect",
            grade_rationale=_gpr75_style_uncited_rationale(),
            claim_stances=[
                ClaimStanceRow(
                    claim_id="a1_evi_07",
                    stance="supports_surface",
                    weight="high",
                ),
                ClaimStanceRow(
                    claim_id="a1_evi_11",
                    stance="supports_surface",
                    weight="moderate",
                ),
                ClaimStanceRow(
                    claim_id="a1_evi_12",
                    stance="supports_surface",
                    weight="moderate",
                ),
            ],
        )
    assert "no inline (aN_evi_NN) cites" in str(excinfo.value)


def test_pass_when_structured_claims_are_cited():
    """Same shape as the failing case, but with inline cites → accepted."""
    cited = (
        "Three lines: (1) knockin mice with PM localization (a1_evi_07); "
        "(2) photoaffinity crosslinking (a1_evi_12); "
        "(3) VPS35-mediated retromer recycling (a1_evi_11)."
    )
    se = SurfaceEvidence(
        evidence_grade="supportive_but_indirect",
        grade_rationale=cited,
        claim_stances=[
            ClaimStanceRow(
                claim_id="a1_evi_07",
                stance="supports_surface",
                weight="high",
            ),
            ClaimStanceRow(
                claim_id="a1_evi_11",
                stance="supports_surface",
                weight="moderate",
            ),
            ClaimStanceRow(
                claim_id="a1_evi_12",
                stance="supports_surface",
                weight="moderate",
            ),
        ],
    )
    # Round-trips; only warn-fires (which it shouldn't, since cites are
    # present) would happen here.
    assert se.evidence_grade == "supportive_but_indirect"


def test_pass_when_loose_prose_has_no_structured_claims():
    """Loose summarizing prose without numbered items or named methods
    still passes — the fail validator is intentionally narrow so
    genuinely narrative rationales aren't blocked."""
    se = SurfaceEvidence(
        evidence_grade="supportive_but_indirect",
        grade_rationale=(
            "The surface evidence is moderate overall — a mix of indirect "
            "fractionation reads and one localization sketch. The picture "
            "leans positive but doesn't quite clear the direct bar."
        ),
        claim_stances=[
            ClaimStanceRow(
                claim_id="a1_evi_01",
                stance="supports_surface",
                weight="moderate",
            ),
            ClaimStanceRow(
                claim_id="a1_evi_03",
                stance="supports_surface",
                weight="low",
            ),
        ],
    )
    # Validation passes — no specific claim tokens to require cites for.
    assert se.evidence_grade == "supportive_but_indirect"


def test_pass_when_only_one_claim_stance_row():
    """With only one stance row, the structured-claim fail validator
    short-circuits — citation discipline kicks in when there's a real
    attribution map to draw from. Using `supportive_but_indirect` here
    because `direct_*` carries an unrelated methods-cardinality check."""
    se = SurfaceEvidence(
        evidence_grade="supportive_but_indirect",
        # Specific method name but only one claim stance — passes the
        # fail gate; the warn gate still fires (covered above).
        grade_rationale=(
            "One live-cell flow study confirms surface staining."
        ),
        claim_stances=[
            ClaimStanceRow(
                claim_id="a1_evi_07",
                stance="supports_surface",
                weight="high",
            ),
        ],
    )
    assert se.evidence_grade == "supportive_but_indirect"


def test_pass_when_structured_claims_have_one_cite_among_them():
    """At least one inline cite is enough to satisfy the fail gate.
    Per-claim cite discipline is the prompt's job; the schema only
    catches the "wrote claims, has the map, zero cites" failure."""
    se = SurfaceEvidence(
        evidence_grade="supportive_but_indirect",
        grade_rationale=(
            "Three lines: (1) knockin mouse PM localization (a1_evi_07); "
            "(2) photoaffinity crosslinking; "
            "(3) VPS35 retromer recycling."
        ),
        claim_stances=[
            ClaimStanceRow(
                claim_id="a1_evi_07",
                stance="supports_surface",
                weight="high",
            ),
            ClaimStanceRow(
                claim_id="a1_evi_11",
                stance="supports_surface",
                weight="moderate",
            ),
        ],
    )
    # The fail gate allows it; the warn gate is silent (one cite present).
    assert se.evidence_grade == "supportive_but_indirect"
