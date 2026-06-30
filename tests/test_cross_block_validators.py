"""Schema-level cross-block validators (added v2.4.0).

The v2 block-builders each produce a typed slice of ``SurfaceomeRecord``;
the synthesizer then writes the executive_summary + accessibility_risks.
Before this set of validators landed, the synthesizer could emit a
record like ``surface_evidence.evidence_grade='direct_multi_method'``
with ``surface_evidence.methods=[]`` and nothing would catch the
incoherence — the validators below enforce that:

1. ``evidence_grade`` matches the methods cardinality it claims
   (``direct_multi_method`` ⇒ ≥2 direct methods from ≥2 sources;
   ``direct_single_method`` ⇒ ≥1 direct method).
2. ``accessibility_risks.secreted_form.present=True`` is backed by
   citation, subcellular_localization, or fractionation method.
3. ``executive_summary.headline_risks`` entries correspond to
   non-trivially-present ``accessibility_risks`` sub-blocks.

The tests below exercise both the happy path (valid records validate)
and each rejection path (specific incoherent records raise).
"""

from __future__ import annotations

import pytest

from accessible_surfaceome.tools._shared.models import (
    AccessibilityRisks,
    CoReceptorRequirements,
    DualLocalization,
    ECDSizeAssessment,
    EpitopeMasking,
    MethodObservation,
    RestrictedSubdomain,
    SecretedForm,
    ShedForm,
    SubcellularLocalization,
    _is_headline_risk_backed,
    _validate_evidence_grade_methods_cardinality,
    _validate_headline_risks_match_present_risks,
    _validate_secreted_form_corroboration,
)


# ---------- helpers ----------------------------------------------------------


def _method(
    *,
    relevance: str = "direct_surface_accessibility",
    cited_evidence_ids: list[str] | None = None,
) -> MethodObservation:
    """Build a minimal MethodObservation for the validators that only read
    ``accessibility_relevance`` + ``cited_evidence_ids``. Other fields use
    schema defaults / minimal values."""
    return MethodObservation.model_validate(
        {
            "method_family": "flow_cytometry",
            "method_subclass": "live_cell_flow",
            "permeabilization": "live_cell",
            "expression_system": "endogenous",
            "accessibility_relevance": relevance,
            "surface_claim_type": "surface_accessible",
            "cited_evidence_ids": cited_evidence_ids or ["a1_evi_01"],
        }
    )


def _secreted(
    *,
    present: bool,
    cited_evidence_ids: list[str] | None = None,
) -> SecretedForm:
    return SecretedForm.model_validate(
        {
            "present": present,
            "severity": "moderate" if present else "low",
            "evidence_strength": "strong" if present else "weak",
            "cited_evidence_ids": cited_evidence_ids or [],
        }
    )


def _subloc(
    *,
    primary: str = "plasma_membrane",
    dual_compartments: list[str] | None = None,
) -> SubcellularLocalization:
    return SubcellularLocalization.model_validate(
        {
            "primary_compartment": primary,
            "dual_localization": [
                DualLocalization.model_validate(
                    {"compartment": c, "fraction_estimate": None, "condition": None}
                ).model_dump()
                for c in (dual_compartments or [])
            ],
        }
    )


def _risks(
    *,
    shed_present: bool = False,
    secreted_present: bool = False,
    co_receptor_dep: str = "none",
    epitope_severity: str = "none",
) -> AccessibilityRisks:
    return AccessibilityRisks.model_validate(
        {
            "co_receptor_requirements": CoReceptorRequirements.model_validate(
                {
                    "surface_expression_dependency": co_receptor_dep,
                    "partners": [],
                    "evidence_basis": "co_expression_only",
                    "rationale": "n/a",
                    "cited_evidence_ids": [],
                }
            ).model_dump(),
            "shed_form": ShedForm.model_validate(
                {
                    "present": shed_present,
                    "severity": "moderate" if shed_present else "low",
                    "evidence_strength": "moderate" if shed_present else "weak",
                }
            ).model_dump(),
            "secreted_form": _secreted(
                present=secreted_present,
                cited_evidence_ids=["a1_evi_01"] if secreted_present else None,
            ).model_dump(),
            "restricted_subdomain": RestrictedSubdomain.model_validate(
                {
                    "present": False,
                    "domain": "unknown",
                    "severity": "low",
                    "evidence_strength": "weak",
                    "rationale": "n/a",
                }
            ).model_dump(),
            "ecd_size_assessment": ECDSizeAssessment.model_validate(
                {
                    "ecd_accessibility_class": "moderate",
                    "rationale": "n/a",
                }
            ).model_dump(),
            "epitope_masking": EpitopeMasking.model_validate(
                {
                    "mechanism": [],
                    "severity": epitope_severity,
                    "evidence_strength": "weak",
                    "rationale": "n/a",
                }
            ).model_dump(),
        }
    )


# ---------- evidence_grade ↔ methods cardinality -----------------------------


class TestEvidenceGradeMethodsCardinality:
    def test_direct_multi_method_requires_two_direct_methods(self) -> None:
        with pytest.raises(ValueError, match="direct_multi_method"):
            _validate_evidence_grade_methods_cardinality(
                "direct_multi_method", [_method(cited_evidence_ids=["a1_evi_01"])]
            )

    def test_direct_multi_method_requires_two_distinct_sources(self) -> None:
        # Two methods, same source — fails source-diversity check
        with pytest.raises(ValueError, match="2 distinct sources"):
            _validate_evidence_grade_methods_cardinality(
                "direct_multi_method",
                [
                    _method(cited_evidence_ids=["a1_evi_01"]),
                    _method(cited_evidence_ids=["a1_evi_01"]),
                ],
            )

    def test_direct_multi_method_passes_with_two_methods_two_sources(self) -> None:
        _validate_evidence_grade_methods_cardinality(
            "direct_multi_method",
            [
                _method(cited_evidence_ids=["a1_evi_01"]),
                _method(cited_evidence_ids=["a1_evi_02"]),
            ],
        )

    def test_direct_single_method_requires_at_least_one_direct(self) -> None:
        with pytest.raises(ValueError, match="direct_single_method"):
            _validate_evidence_grade_methods_cardinality("direct_single_method", [])

    def test_direct_single_method_passes_with_one_direct(self) -> None:
        _validate_evidence_grade_methods_cardinality(
            "direct_single_method", [_method()]
        )

    def test_direct_single_method_rejects_only_indirect_methods(self) -> None:
        # A method labeled supports_membrane_association is NOT direct_surface_accessibility
        with pytest.raises(ValueError, match="direct_single_method"):
            _validate_evidence_grade_methods_cardinality(
                "direct_single_method",
                [_method(relevance="supports_membrane_association")],
            )

    def test_supportive_but_indirect_no_methods_constraint(self) -> None:
        # Empty methods is OK for indirect grades
        _validate_evidence_grade_methods_cardinality("supportive_but_indirect", [])
        _validate_evidence_grade_methods_cardinality("weak", [])
        _validate_evidence_grade_methods_cardinality("conflicting", [])


# ---------- secreted_form corroboration --------------------------------------


class TestSecretedFormCorroboration:
    def test_present_false_skips_validation(self) -> None:
        # When .present=False, no corroboration needed
        _validate_secreted_form_corroboration(
            _secreted(present=False),
            _subloc(),
            [],
        )

    def test_present_true_with_citation_passes(self) -> None:
        _validate_secreted_form_corroboration(
            _secreted(present=True, cited_evidence_ids=["a1_evi_05"]),
            _subloc(),
            [],
        )

    def test_present_true_with_secreted_primary_compartment_passes(self) -> None:
        _validate_secreted_form_corroboration(
            _secreted(present=True),
            _subloc(primary="secreted"),
            [],
        )

    def test_present_true_with_secreted_dual_localization_passes(self) -> None:
        _validate_secreted_form_corroboration(
            _secreted(present=True),
            _subloc(dual_compartments=["secreted"]),
            [],
        )

    def test_present_true_with_er_dual_localization_passes(self) -> None:
        _validate_secreted_form_corroboration(
            _secreted(present=True),
            _subloc(dual_compartments=["ER"]),
            [],
        )

    def test_present_true_with_fractionation_method_passes(self) -> None:
        _validate_secreted_form_corroboration(
            _secreted(present=True),
            _subloc(),
            [_method(relevance="supports_membrane_association")],
        )

    def test_present_true_with_no_corroboration_fails(self) -> None:
        with pytest.raises(ValueError, match="no corroboration"):
            _validate_secreted_form_corroboration(
                _secreted(present=True),
                _subloc(primary="plasma_membrane"),
                [_method(relevance="direct_surface_accessibility")],
            )

    def test_dual_localization_compartment_label_matches_case_insensitively(
        self,
    ) -> None:
        _validate_secreted_form_corroboration(
            _secreted(present=True),
            _subloc(dual_compartments=["Endoplasmic Reticulum"]),
            [],
        )


# ---------- headline_risks ↔ accessibility_risks -----------------------------


class TestHeadlineRisksMatchPresentRisks:
    def test_empty_headline_risks_passes(self) -> None:
        _validate_headline_risks_match_present_risks([], _risks())

    def test_shed_form_headline_requires_shed_form_present(self) -> None:
        with pytest.raises(ValueError, match="shed_form"):
            _validate_headline_risks_match_present_risks(
                ["shed_form"], _risks(shed_present=False)
            )
        _validate_headline_risks_match_present_risks(
            ["shed_form"], _risks(shed_present=True)
        )

    def test_secreted_form_headline_requires_secreted_present(self) -> None:
        with pytest.raises(ValueError, match="secreted_form"):
            _validate_headline_risks_match_present_risks(
                ["secreted_form"], _risks(secreted_present=False)
            )
        _validate_headline_risks_match_present_risks(
            ["secreted_form"], _risks(secreted_present=True)
        )

    def test_co_receptor_headline_requires_non_independent_dependency(self) -> None:
        with pytest.raises(ValueError, match="co_receptor"):
            _validate_headline_risks_match_present_risks(
                ["co_receptor"], _risks(co_receptor_dep="none")
            )
        _validate_headline_risks_match_present_risks(
            ["co_receptor"], _risks(co_receptor_dep="required")
        )
        _validate_headline_risks_match_present_risks(
            ["co_receptor"], _risks(co_receptor_dep="modulatory")
        )

    def test_epitope_masked_headline_requires_non_none_severity(self) -> None:
        with pytest.raises(ValueError, match="epitope_masked"):
            _validate_headline_risks_match_present_risks(
                ["epitope_masked"], _risks(epitope_severity="none")
            )
        _validate_headline_risks_match_present_risks(
            ["epitope_masked"], _risks(epitope_severity="moderate")
        )

    def test_isoform_decoy_headline_always_passes(self) -> None:
        # No dedicated sub-block; prose carries it.
        _validate_headline_risks_match_present_risks(["isoform_decoy"], _risks())

    def test_multiple_unbacked_headlines_listed_in_error(self) -> None:
        with pytest.raises(ValueError, match="shed_form") as exc:
            _validate_headline_risks_match_present_risks(
                ["shed_form", "secreted_form"],
                _risks(shed_present=False, secreted_present=False),
            )
        # Both unbacked entries should be in the message
        assert "shed_form" in str(exc.value)
        assert "secreted_form" in str(exc.value)

    def test_is_headline_risk_backed_unknown_value_passes(self) -> None:
        """Forward-compat: an unknown HeadlineRisk value falls through to
        True so a future enum addition doesn't break old records."""
        assert _is_headline_risk_backed("some_future_value", _risks()) is True


def test_demote_multimethod_mirrors_cardinality_validator() -> None:
    """The orchestrator's in-process demotion must catch exactly the cases the
    SurfaceEvidence cardinality validator rejects. Otherwise the ValidationError
    bubbles out of the Modal worker and forces a full-gene retry (~$1.5 re-spend)
    — or a hard failure if the model keeps over-grading.
    """
    from accessible_surfaceome.agents.surfaceome_v2.orchestrator import (
        _demote_multimethod_if_unsupported as demote,
    )

    # 1 direct method → demote (multi needs ≥2 rows). [GPR75 case]
    assert (
        demote("direct_multi_method", [_method(cited_evidence_ids=["a1_evi_01"])])
        == "direct_single_method"
    )

    # 2 direct methods citing the SAME source → demote (multi needs ≥2 distinct
    # sources). This is the exact case that hard-failed a canary gene.
    two_same = [
        _method(cited_evidence_ids=["a1_evi_13"]),
        _method(cited_evidence_ids=["a1_evi_13"]),
    ]
    assert demote("direct_multi_method", two_same) == "direct_single_method"

    # 2 direct methods, 2 distinct sources → valid multi, left unchanged.
    two_diff = [
        _method(cited_evidence_ids=["a1_evi_01"]),
        _method(cited_evidence_ids=["a1_evi_02"]),
    ]
    assert demote("direct_multi_method", two_diff) == "direct_multi_method"

    # No direct rows at all → NOT demoted (single requires ≥1; the n_direct==0
    # case is handled by the re-LLM retry in _annotate, not by demotion).
    assert demote("direct_multi_method", []) == "direct_multi_method"

    # Any other grade passes through untouched.
    assert demote("direct_single_method", two_same) == "direct_single_method"
    assert demote("supportive_but_indirect", two_diff) == "supportive_but_indirect"
