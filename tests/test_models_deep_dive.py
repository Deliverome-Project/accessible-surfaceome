"""Tests for the deep-dive model additions (isoform / co-receptor / orthology)
plus the v0.5.0 sub-record + paralog + contradiction additions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from accessible_surfaceome.tools._shared.models import (
    SCHEMA_VERSION,
    AntibodyReference,
    CellTypeContext,
    ContradictionRecord,
    CoreceptorRequirement,
    IsoformAccessibility,
    MassSpecDetail,
    MicrodomainAssignment,
    OrthologRecord,
    ParalogRecord,
    RiskFlag,
    SheddingContext,
    SurfaceLocalizationAssay,
    SurfaceomeRecord,
)


def test_isoform_accessibility_minimal_roundtrip() -> None:
    iso = IsoformAccessibility(isoform_id="P04626-1", is_canonical=True)
    dumped = iso.model_dump()
    assert dumped["isoform_id"] == "P04626-1"
    assert dumped["surface_status"] is None
    assert dumped["differential_from_canonical"] is False
    assert dumped["uniprot_isoform_specific_locations"] == []
    assert dumped["cited_evidence_ids"] == []


def test_isoform_accessibility_rejects_oversize_rationale() -> None:
    with pytest.raises(ValidationError):
        IsoformAccessibility(isoform_id="P04626-1", rationale="x" * 501)


def test_coreceptor_requirement_other_label_required() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CoreceptorRequirement(
            partner_symbol="CD247",
            requirement_kind="other",
            description="needs CD247 for ER exit",
        )
    assert "requirement_kind_other_label" in str(exc_info.value)


def test_coreceptor_requirement_other_label_forbidden_when_closed() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CoreceptorRequirement(
            partner_symbol="CD247",
            requirement_kind="obligate_heterodimer",
            requirement_kind_other_label="extra label",
            description="needs CD247 for ER exit",
        )
    assert "requirement_kind_other_label" in str(exc_info.value)


def test_coreceptor_requirement_obligate_heterodimer_ok() -> None:
    cr = CoreceptorRequirement(
        partner_symbol="CD247",
        partner_uniprot_acc="P20963",
        requirement_kind="obligate_heterodimer",
        description="CD3 chain TCR complex requires CD247 (ζ-chain) for ER exit.",
        cited_evidence_ids=["evi_001"],
    )
    assert cr.requirement_kind_other_label is None
    assert cr.partner_uniprot_acc == "P20963"


def test_ortholog_record_concordance_is_tri_state() -> None:
    ortho = OrthologRecord(
        species="mouse",
        ortholog_uniprot_acc="P70424",
        ortholog_gene_symbol="Erbb2",
        ensembl_gene_id="ENSMUSG00000062312",
        orthology_type="one_to_one",
        percent_identity=94.5,
        surface_concordant_with_human=True,
    )
    assert ortho.surface_concordant_with_human is True
    assert ortho.surface_status is None  # default when not asserted

    unknown = OrthologRecord(species="cynomolgus")
    assert unknown.ortholog_uniprot_acc is None
    assert unknown.surface_concordant_with_human is None


def test_ortholog_record_rejects_unknown_species() -> None:
    with pytest.raises(ValidationError):
        # Bypass static type checks: feed an invalid species via model_validate
        # so the Literal["mouse","cynomolgus"] is enforced at runtime, not
        # parse time.
        OrthologRecord.model_validate({"species": "rat"})


# ---------------------------------------------------------------------------
# v0.5.0 additions
# ---------------------------------------------------------------------------


def test_schema_version_is_v0_5_0() -> None:
    assert SCHEMA_VERSION == "v0.5.0"


def test_mass_spec_detail_roundtrip() -> None:
    detail = MassSpecDetail(
        method="cell_surface_capture",
        enrichment_strategy="periodate-oxidized sialic acid biotinylation",
        peptide_count=2,
    )
    assert detail.method == "cell_surface_capture"
    assert detail.method_other_label is None


def test_mass_spec_detail_other_label_required() -> None:
    with pytest.raises(ValidationError) as exc_info:
        MassSpecDetail(method="other")
    assert "method_other_label" in str(exc_info.value)


def test_mass_spec_detail_other_label_forbidden_when_closed() -> None:
    with pytest.raises(ValidationError) as exc_info:
        MassSpecDetail(method="tmt_quantitative", method_other_label="extra")
    assert "method_other_label" in str(exc_info.value)


def test_antibody_reference_minimal_all_nullable() -> None:
    ab = AntibodyReference()
    assert ab.clone is None
    assert ab.url is None


def test_antibody_reference_rejects_invalid_url() -> None:
    with pytest.raises(ValidationError):
        AntibodyReference.model_validate({"url": "not-a-url"})


def test_cell_type_context_other_label_required() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CellTypeContext(material_kind="other")
    assert "material_kind_other_label" in str(exc_info.value)


def test_cell_type_context_primary_cell_ok() -> None:
    ctx = CellTypeContext(
        material_kind="primary_cell",
        cell_type="CD4+ T cell",
        tissue="peripheral blood",
        activation_state="PMA-stimulated 24h",
    )
    assert ctx.material_kind == "primary_cell"
    assert ctx.material_kind_other_label is None


def test_surface_assay_mass_spec_sub_record() -> None:
    assay = SurfaceLocalizationAssay(
        assay_type="mass_spec_surfaceome",
        species="human",
        cell_type_or_line="A431",
        direction="supports_surface",
        strength="strong",
        cited_evidence_ids=["evi_001"],
        mass_spec_detail=MassSpecDetail(method="cell_surface_capture"),
    )
    assert assay.antibody is None
    assert assay.mass_spec_detail is not None
    assert assay.mass_spec_detail.method == "cell_surface_capture"


def test_surface_assay_rejects_antibody_on_mass_spec() -> None:
    with pytest.raises(ValidationError) as exc_info:
        SurfaceLocalizationAssay(
            assay_type="mass_spec_surfaceome",
            species="human",
            cell_type_or_line="A431",
            direction="supports_surface",
            strength="strong",
            cited_evidence_ids=["evi_001"],
            antibody=AntibodyReference(clone="trastuzumab"),
        )
    assert "antibody is not valid for assay_type='mass_spec_surfaceome'" in str(
        exc_info.value
    )


def test_surface_assay_flow_cytometry_antibody_sub_record() -> None:
    assay = SurfaceLocalizationAssay(
        assay_type="flow_cytometry",
        species="human",
        cell_type_or_line="BT-474",
        direction="supports_surface",
        strength="strong",
        cited_evidence_ids=["evi_001"],
        antibody=AntibodyReference(
            clone="trastuzumab",
            vendor="Genentech",
            target_epitope="HER2 ECD domain IV",
        ),
    )
    assert assay.mass_spec_detail is None
    assert assay.antibody is not None
    assert assay.antibody.clone == "trastuzumab"


def test_surface_assay_rejects_mass_spec_detail_on_flow() -> None:
    with pytest.raises(ValidationError) as exc_info:
        SurfaceLocalizationAssay(
            assay_type="flow_cytometry",
            species="human",
            cell_type_or_line="BT-474",
            direction="supports_surface",
            strength="strong",
            cited_evidence_ids=["evi_001"],
            mass_spec_detail=MassSpecDetail(method="tmt_quantitative"),
        )
    assert "mass_spec_detail is not valid for assay_type='flow_cytometry'" in str(
        exc_info.value
    )


def test_microdomain_assignment_requires_citation() -> None:
    with pytest.raises(ValidationError) as exc_info:
        MicrodomainAssignment(microdomain="lipid_raft")
    assert "cited_evidence_ids" in str(exc_info.value)


def test_microdomain_assignment_other_label_required() -> None:
    with pytest.raises(ValidationError) as exc_info:
        MicrodomainAssignment(microdomain="other", cited_evidence_ids=["evi_001"])
    assert "microdomain_other_label" in str(exc_info.value)


def test_microdomain_assignment_roundtrip() -> None:
    md = MicrodomainAssignment(
        microdomain="lipid_raft",
        notes="HSP70 outer-leaflet attachment runs through cholesterol-rich microdomains.",
        cited_evidence_ids=["evi_005"],
    )
    assert md.microdomain == "lipid_raft"
    assert md.microdomain_other_label is None


def test_shedding_context_on_risk_flag() -> None:
    flag = RiskFlag(
        kind="soluble_shedding",
        severity="medium",
        description="HER2 ECD is shed by ADAM10/17 into circulation.",
        cited_evidence_ids=["evi_010"],
        shedding_context=SheddingContext(
            proteases=["adam10", "adam17"],
            cleavage_site="His-Cys-Leu cleavage in juxtamembrane domain",
            regulation="constitutive",
            serum_pool_documented=True,
        ),
    )
    assert flag.shedding_context is not None
    assert "adam10" in flag.shedding_context.proteases


def test_shedding_context_rejected_on_other_kind() -> None:
    with pytest.raises(ValidationError) as exc_info:
        RiskFlag(
            kind="other",
            kind_other_label="weird_thing",
            severity="medium",
            description="some other risk",
            shedding_context=SheddingContext(proteases=["adam10"]),
        )
    assert "shedding_context" in str(exc_info.value)


def test_paralog_record_minimal() -> None:
    p = ParalogRecord(paralog_symbol="HSPA1B")
    assert p.paralog_uniprot_acc is None
    assert p.paralog_surface_status == "unknown"
    assert p.cross_reactivity_risk == "unknown"


def test_paralog_record_validates_identity_range() -> None:
    with pytest.raises(ValidationError):
        ParalogRecord(paralog_symbol="HSPA1B", percent_identity=120.0)
    with pytest.raises(ValidationError):
        ParalogRecord(paralog_symbol="HSPA1B", ecd_percent_identity=-1.0)


def test_contradiction_record_minimal() -> None:
    c = ContradictionRecord(
        topic="HSP70 surface staining in unstressed cells",
        supporting_claim_ids=["evi_001"],
        refuting_claim_ids=["evi_002"],
        resolution="context_dependent",
        resolution_rationale=(
            "Surface staining is detectable on stressed but not resting cells."
        ),
    )
    assert c.resolution == "context_dependent"


def test_contradiction_record_requires_both_id_lists() -> None:
    with pytest.raises(ValidationError):
        ContradictionRecord(
            topic="topic",
            supporting_claim_ids=[],
            refuting_claim_ids=["evi_002"],
            resolution="unresolved",
            resolution_rationale="needs supporting evidence",
        )


# ---------------------------------------------------------------------------
# Backward-compat smoke + flag/list cross-validator
# ---------------------------------------------------------------------------


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_v0_4_records_load_under_v0_5_0() -> None:
    """Every persisted v0.4.0 annotation must parse cleanly under v0.5.0
    models (additive change — new fields default to empty)."""
    annotations_dir = REPO_ROOT / "data" / "annotations"
    files = sorted(annotations_dir.glob("*.json"))
    assert files, f"no annotation files found under {annotations_dir}"
    for path in files:
        record = SurfaceomeRecord.model_validate_json(path.read_text())
        assert record.paralogs == []
        assert record.contradictions == []
        assert record.contradiction_flag is False


def test_contradiction_flag_must_mirror_list() -> None:
    """A non-empty ``contradictions`` requires ``contradiction_flag=True``."""
    base = _minimal_record_payload()
    base["contradictions"] = [
        {
            "topic": "surface expression in resting cells",
            "supporting_claim_ids": ["evi_001"],
            "refuting_claim_ids": ["evi_002"],
            "resolution": "unresolved",
            "resolution_rationale": "needs more data",
        }
    ]
    base["contradiction_flag"] = False
    with pytest.raises(ValidationError) as exc_info:
        SurfaceomeRecord.model_validate(base)
    assert "contradiction_flag" in str(exc_info.value)


def test_contradiction_flag_consistent_when_both_empty() -> None:
    base = _minimal_record_payload()
    assert base["contradiction_flag"] is False
    record = SurfaceomeRecord.model_validate(base)
    assert record.contradictions == []


def _minimal_record_payload() -> dict:
    """Load HSPA1A as a v0.5.0-compatible payload base and strip any
    contradictions/paralogs so callers can re-populate them for tests.
    """
    raw = (REPO_ROOT / "data" / "annotations" / "HSPA1A.json").read_text()
    data = json.loads(raw)
    data["contradictions"] = []
    data["paralogs"] = []
    data["contradiction_flag"] = False
    return data
