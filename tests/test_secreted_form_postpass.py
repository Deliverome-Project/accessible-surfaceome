"""Tests for the deterministic secreted_form upgrade post-pass (Chunk 2 of
the PR #47 deep-dive redesign).

The synthesizer runs before isoform topology is fetched, so it can't see a
TM-less splice isoform implying a soluble species. The post-pass upgrades
secreted_form deterministically — and only ever UPGRADES.
"""

from __future__ import annotations

from datetime import UTC, datetime

from accessible_surfaceome.agents.surfaceome_v2.secreted_form_postpass import (
    apply_secreted_form_post_pass,
)
from accessible_surfaceome.tools._shared.models import (
    AccessibilityRisks,
    DeterministicFeatures,
    IsoformTopology,
    Orthologs,
    StructureFeatures,
)


def _iso(tm: int, ecd: int, isoform_id: str = "P00001-1") -> IsoformTopology:
    return IsoformTopology(
        isoform_id=isoform_id,
        uniprot_acc="P00001",
        tm_helix_count=tm,
        n_terminal_orientation="extracellular",
        c_terminal_orientation="cytoplasmic",
        signal_peptide_length=0,
        ecd_length_residues=ecd,
        icd_length_residues=10,
        per_residue_topology="o" * max(ecd, 1),
        tool_version="deeptmhmm-1.0.24",
        retrieved_at=datetime.now(UTC),
    )


def _features(isoforms: list[IsoformTopology]) -> DeterministicFeatures:
    return DeterministicFeatures(
        canonical_topology=isoforms[0],
        isoform_topologies=isoforms,
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


def _risks(
    *, secreted_present: bool, severity: str = "low", strength: str = "moderate"
) -> AccessibilityRisks:
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
                "present": secreted_present, "severity": severity,
                "evidence_strength": strength, "ratio_to_membrane": None,
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


def test_upgrades_when_tm_less_isoform_present():
    risks = _risks(secreted_present=False)
    # Canonical TM=7; an alternative isoform is TM=0 with a real ECD.
    feats = _features([_iso(7, 89), _iso(0, 89, "P00001-2")])
    changed = apply_secreted_form_post_pass(
        accessibility_risks=risks, deterministic_features=feats
    )
    assert changed is True
    assert risks.secreted_form.present is True
    assert risks.secreted_form.severity == "low"
    assert risks.secreted_form.evidence_strength == "weak"
    assert risks.secreted_form.source == "alternative_splicing"


def test_no_upgrade_when_every_isoform_has_a_tm():
    risks = _risks(secreted_present=False)
    feats = _features([_iso(7, 89), _iso(1, 200, "P00001-2")])
    changed = apply_secreted_form_post_pass(
        accessibility_risks=risks, deterministic_features=feats
    )
    assert changed is False
    assert risks.secreted_form.present is False


def test_no_upgrade_when_tm_less_isoform_has_tiny_ecd():
    risks = _risks(secreted_present=False)
    feats = _features([_iso(7, 89), _iso(0, 10, "P00001-2")])  # TM=0 but ECD<30
    changed = apply_secreted_form_post_pass(
        accessibility_risks=risks, deterministic_features=feats
    )
    assert changed is False


def test_never_downgrades_a_literature_backed_call():
    # Synthesizer set present=True / high / strong from the literature — the
    # weaker topology inference must not overwrite it.
    risks = _risks(secreted_present=True, severity="high", strength="strong")
    feats = _features([_iso(0, 89)])  # would otherwise trigger an upgrade
    changed = apply_secreted_form_post_pass(
        accessibility_risks=risks, deterministic_features=feats
    )
    assert changed is False
    assert risks.secreted_form.severity == "high"
    assert risks.secreted_form.evidence_strength == "strong"
