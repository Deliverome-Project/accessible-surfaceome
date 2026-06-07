"""Tests for the deterministic ``ecd_accessibility_class``.

``ecd_accessibility_class`` is the single source of truth for ECD size: the
classifier applies fixed thresholds to the deterministic ECD residue count,
and the v2 orchestrator post-pass overwrites whatever the synthesizer emitted.
There is no LLM judgment and no literature override on this field anymore.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from accessible_surfaceome.agents.surfaceome_v2.orchestrator import (
    _attach_deterministic_ecd_size_assessment,
)
from accessible_surfaceome.tools._shared.models import (
    AccessibilityRisks,
    DeterministicFeatures,
    ECDSizeAssessment,
    IsoformTopology,
    Orthologs,
    StructureFeatures,
    classify_ecd_accessibility_class,
)


# --------------------------------------------------------------------------
# 1. classifier threshold table
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("ecd_len", "expected"),
    [
        (None, "none"),
        (0, "none"),
        (1, "minimal"),
        (29, "minimal"),
        (30, "small"),
        (59, "small"),
        (60, "moderate"),
        (199, "moderate"),
        (200, "large"),
        (5000, "large"),
    ],
)
def test_classify_ecd_accessibility_class_thresholds(ecd_len, expected):
    assert classify_ecd_accessibility_class(ecd_len) == expected


def test_classifier_exposed_as_staticmethod():
    # The model exposes the same function as ``ECDSizeAssessment.classify`` so
    # callers holding the model can reach the canonical thresholds directly.
    assert ECDSizeAssessment.classify(247) == "large"
    assert ECDSizeAssessment.classify(0) == "none"


# --------------------------------------------------------------------------
# 2. orchestrator deterministic overwrite
# --------------------------------------------------------------------------
def _iso(ecd: int) -> IsoformTopology:
    return IsoformTopology(
        isoform_id="P00001-1",
        uniprot_acc="P00001",
        tm_helix_count=1,
        n_terminal_orientation="extracellular",
        c_terminal_orientation="cytoplasmic",
        signal_peptide_length=0,
        ecd_length_residues=ecd,
        icd_length_residues=10,
        per_residue_topology="o" * max(ecd, 1),
        tool_version="deeptmhmm-1.0.24",
        retrieved_at=datetime.now(UTC),
    )


def _features(ecd: int) -> DeterministicFeatures:
    canonical = _iso(ecd)
    return DeterministicFeatures(
        canonical_topology=canonical,
        isoform_topologies=[],
        paralogs=[],
        orthologs=Orthologs(),
        structure=StructureFeatures(
            afdb_id="AF-P00001-F1-model_v4",
            afdb_version="v4",
            ecd_mean_plddt=0.0,
            ecd_disordered_fraction=0.0,
            source="stub",
            license="CC BY 4.0",
            attribution="© DeepMind / EMBL-EBI",
        ),
    )


def _risks(*, ecd_class: str) -> AccessibilityRisks:
    return AccessibilityRisks.model_validate(
        {
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
                "ecd_accessibility_class": ecd_class,
                "rationale": "the literature says this is a huge ectodomain",
                "cited_evidence_ids": ["a1_evi_03"],
            },
            "epitope_masking": {
                "mechanism": [], "severity": "none",
                "evidence_strength": "moderate", "rationale": "—",
                "cited_evidence_ids": [],
            },
        }
    )


def test_overwrite_corrects_a_contradicting_synthesizer_draft():
    # Synthesizer (wrongly) emitted "large" with a literature rationale, but
    # the deterministic ECD is only 12 residues → must become "minimal".
    risks = _risks(ecd_class="large")
    feats = _features(12)
    out = _attach_deterministic_ecd_size_assessment(risks, feats)
    assert out.ecd_size_assessment.ecd_accessibility_class == "minimal"
    # rationale is the deterministic string, NOT the synthesizer's literature prose
    assert "12 residues" in out.ecd_size_assessment.rationale
    assert "deterministically" in out.ecd_size_assessment.rationale
    assert out.ecd_size_assessment.cited_evidence_ids == []
    # input left untouched (model_copy returns a new object)
    assert risks.ecd_size_assessment.ecd_accessibility_class == "large"


def test_overwrite_matches_residue_count_across_bands():
    for ecd_len, expected in [(0, "none"), (12, "minimal"), (45, "small"),
                              (100, "moderate"), (247, "large")]:
        # Seed with a deliberately wrong class to prove the overwrite ignores it.
        risks = _risks(ecd_class="none" if expected != "none" else "large")
        out = _attach_deterministic_ecd_size_assessment(risks, _features(ecd_len))
        assert out.ecd_size_assessment.ecd_accessibility_class == expected


def test_overwrite_handles_none_ecd_length():
    feats = _features(0)
    # Force ecd_length_residues to None via model_copy on the canonical block.
    feats = feats.model_copy(
        update={
            "canonical_topology": feats.canonical_topology.model_copy(
                update={"ecd_length_residues": None}
            )
        }
    )
    risks = _risks(ecd_class="large")
    out = _attach_deterministic_ecd_size_assessment(risks, feats)
    assert out.ecd_size_assessment.ecd_accessibility_class == "none"
    assert "deterministically" in out.ecd_size_assessment.rationale
