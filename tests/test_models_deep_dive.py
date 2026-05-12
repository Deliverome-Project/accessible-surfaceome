"""Tests for the deep-dive model additions (isoform / co-receptor / orthology)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from accessible_surfaceome.tools._shared.models import (
    CoreceptorRequirement,
    IsoformAccessibility,
    OrthologRecord,
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
