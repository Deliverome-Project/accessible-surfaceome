"""Unit tests for ``scrub_headline_risks`` + the cell_states viewer fix.

The scrub enforces structured-vs-prose coherence in the synthesizer's
output: every ``headline_risks`` entry must be backed by a structured
``accessibility_risks`` field that agrees. Caught on the CD81 review
where the synthesizer listed ``co_receptor`` in headline_risks even
though ``surface_expression_dependency = "modulatory"`` (not
``"required"``).

The cell_states viewer fix hides the perpetually-empty ``Cell states
(0)`` subsection on v2 records (v2's orchestrator hardcodes
``cell_states=[]``; the modulation block subsumes the legacy v1
field).
"""

from __future__ import annotations

from typing import Any

from accessible_surfaceome.agents.surfaceome_v1.orchestrator import (
    scrub_headline_risks,
)
from accessible_surfaceome.agents.surfaceome_v2.render_html import render_html
from accessible_surfaceome.tools._shared.models import (
    AccessibilityRisks,
    ExecutiveSummary,
)


def _risks(
    *,
    epitope_severity: str = "none",
    shed_present: bool = False,
    secreted_present: bool = False,
    restricted_present: bool = False,
    co_receptor_dependency: str = "none",
) -> AccessibilityRisks:
    """Build a valid AccessibilityRisks via model_validate on a dict —
    simpler than constructing each sub-model by hand. The dict shape
    mirrors what the synthesizer emits."""
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
                "present": shed_present,
                "severity": "moderate" if shed_present else "low",
                "evidence_strength": "moderate",
                "mechanism": None,
                "sheddase_if_known": None,
                "cited_evidence_ids": [],
            },
            "secreted_form": {
                "present": secreted_present,
                "severity": "moderate" if secreted_present else "low",
                "evidence_strength": "moderate",
                "ratio_to_membrane": None,
                "source": None,
                "cited_evidence_ids": [],
            },
            "restricted_subdomain": {
                "present": restricted_present,
                "domain": "raft",
                "severity": "moderate" if restricted_present else "low",
                "evidence_strength": "moderate",
                "rationale": "—",
                "cited_evidence_ids": [],
            },
            "ecd_size_assessment": {
                "ecd_accessibility_class": "moderate",
                "rationale": "—",
                "cited_evidence_ids": [],
            },
            "epitope_masking": {
                "mechanism": [],
                "severity": epitope_severity,
                "evidence_strength": "moderate",
                "rationale": "—",
                "cited_evidence_ids": [],
            },
        }
    )


def _exec(
    *,
    headline_risks: list[str],
    one_paragraph: str = "—",
    state_dependence: str = "moderate",
    evidence_grade_summary: str = "weak",
    surface_accessibility: str = "moderate",
    subcategory: str = "other",
    confidence: str = "moderate",
    surface_call_reason: str = "classical_surface_receptor",
) -> ExecutiveSummary:
    return ExecutiveSummary.model_validate(
        {
            "one_paragraph": one_paragraph,
            "state_dependence": state_dependence,
            "evidence_grade_summary": evidence_grade_summary,
            "surface_accessibility": surface_accessibility,
            "subcategory": subcategory,
            "confidence": confidence,
            "headline_risks": headline_risks,
            "cited_evidence_ids": [],
            "surface_call_reason": surface_call_reason,
        }
    )


# ---------------------------------------------------------------------------
# scrub_headline_risks
# ---------------------------------------------------------------------------


def test_scrub_drops_co_receptor_when_dependency_is_modulatory() -> None:
    """The exact CD81 case: synthesizer wrote ``co_receptor`` in
    headline_risks but set ``surface_expression_dependency=modulatory``
    (not ``required``). Scrub drops it."""
    es = _exec(headline_risks=["co_receptor", "isoform_decoy"])
    risks = _risks(co_receptor_dependency="modulatory", restricted_present=True)
    cleaned = scrub_headline_risks(es, risks)
    assert "co_receptor" not in cleaned.headline_risks
    assert "isoform_decoy" in cleaned.headline_risks


def test_scrub_keeps_co_receptor_when_dependency_is_required() -> None:
    es = _exec(headline_risks=["co_receptor"])
    risks = _risks(co_receptor_dependency="required")
    cleaned = scrub_headline_risks(es, risks)
    assert "co_receptor" in cleaned.headline_risks


def test_scrub_drops_epitope_masked_when_severity_is_none_or_low() -> None:
    # ``isoform_decoy`` here is just a passive value the scrub doesn't
    # touch — used to assert that the scrub drops ONLY the offending
    # entry, not unrelated companions. Replaces the historical
    # ``"other"`` use, which is no longer a valid HeadlineRisk value
    # post-redundancy-audit.
    for sev in ("none", "low"):
        es = _exec(headline_risks=["epitope_masked", "isoform_decoy"])
        risks = _risks(epitope_severity=sev)
        cleaned = scrub_headline_risks(es, risks)
        assert "epitope_masked" not in cleaned.headline_risks, f"severity={sev!r}"
        assert "isoform_decoy" in cleaned.headline_risks


def test_scrub_keeps_epitope_masked_when_severity_is_moderate_or_high() -> None:
    for sev in ("moderate", "high"):
        es = _exec(headline_risks=["epitope_masked"])
        risks = _risks(epitope_severity=sev)
        cleaned = scrub_headline_risks(es, risks)
        assert "epitope_masked" in cleaned.headline_risks, f"severity={sev!r}"


def test_scrub_drops_shed_form_when_present_false() -> None:
    es = _exec(headline_risks=["shed_form", "secreted_form"])
    risks = _risks(shed_present=False, secreted_present=True)
    cleaned = scrub_headline_risks(es, risks)
    assert "shed_form" not in cleaned.headline_risks
    assert "secreted_form" in cleaned.headline_risks


# NOTE: the historical ``test_scrub_drops_restricted_subdomain_when_present_false``
# was removed when ``restricted_subdomain`` was dropped from the
# HeadlineRisk enum in the post-design-review slim. Pydantic now
# rejects the value at validation time, so the orchestrator scrub
# never sees it — no test needed.


def test_scrub_returns_same_object_when_no_drops_needed() -> None:
    """Optimization: when nothing changes, return the input unchanged
    (saves a model_copy + lets pydantic equality short-circuit).
    ``isoform_decoy`` is a value the scrub doesn't touch — picked
    here as the inert no-op value (replaced the historical ``other``
    after the enum slim)."""
    es = _exec(headline_risks=["isoform_decoy"])
    risks = _risks()
    cleaned = scrub_headline_risks(es, risks)
    assert cleaned is es


def test_scrub_preserves_other_executive_summary_fields() -> None:
    es = _exec(
        headline_risks=["co_receptor", "isoform_decoy"],
        one_paragraph="Important context paragraph.",
        state_dependence="high",
        evidence_grade_summary="direct_multi_method",
        surface_accessibility="high",
    )
    risks = _risks(co_receptor_dependency="modulatory", restricted_present=True)
    cleaned = scrub_headline_risks(es, risks)
    assert cleaned.one_paragraph == "Important context paragraph."
    assert cleaned.state_dependence == "high"
    assert cleaned.evidence_grade_summary == "direct_multi_method"
    assert cleaned.surface_accessibility == "high"


# ---------------------------------------------------------------------------
# Viewer: empty cell_states section is hidden
# ---------------------------------------------------------------------------


def _minimal_v2_record(
    *, cell_states: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Bare-minimum record dict the renderer accepts. Most fields can be
    None / empty since the renderer is defensive."""
    return {
        "schema_version": "1.0.0",
        "gene": {"hgnc_symbol": "X", "uniprot_acc": "Q1", "hgnc_id": "HGNC:1"},
        "executive_summary": None,
        "confidence": "moderate",
        "confidence_reasoning": "—",
        "surface_evidence": None,
        "biological_context": {
            "tissues": [],
            "cell_types": [],
            "cell_states": cell_states or [],
            "subcellular_localization": None,
            "anatomical_accessibility": [],
            "accessibility_modulation": [],
        },
        "deterministic_features": None,
        "accessibility_risks": None,
        "filters": None,
        "evidence": [],
        "evidence_count": 0,
        "primary_evidence_count": 0,
        "secondary_evidence_count": 0,
        "model_path": "claude-sonnet-4-6",
        "record_generated_at": "2026-05-16T00:00:00Z",
    }


def test_viewer_never_renders_cell_states_section() -> None:
    """Schema 2.5.0 retired cell_states[] — modulation block subsumes it.
    The viewer must never render a 'Cell states' subsection (the v1
    CD81 ghost-section complaint that prompted hiding-when-empty is
    now resolved structurally — the field doesn't exist)."""
    html = render_html(_minimal_v2_record())
    assert "Cell states" not in html
    assert "no cell-state rows" not in html
