import pytest
from pydantic import ValidationError

from accessible_surfaceome.agents.internalization.models import (
    SCHEMA_VERSION,
    GradesByMode,
    InternalizationObservation,
    InternalizationRecord,
    LiteratureLLMOut,
    LiteratureTrack,
    ModeGrade,
)


def test_schema_version_bumped_to_0_2_0():
    assert SCHEMA_VERSION == "0.2.0"


def test_observation_requires_other_label_when_other():
    with pytest.raises(ValidationError):
        InternalizationObservation(assay_type="other")  # missing other_label
    ok = InternalizationObservation(
        assay_type="other", assay_type_other_label="split-GFP uptake"
    )
    assert ok.assay_type_other_label == "split-GFP uptake"


def test_observation_defaults_are_safe():
    o = InternalizationObservation(assay_type="antibody_uptake")
    assert o.internalization_mode == "unknown"
    assert o.magnitude == "unknown"
    assert o.quant.quant_summary == ""
    assert o.cited_source_ids == []


def test_llm_out_excludes_sources_field():
    # The grader model must not fabricate the promoted-evidence ledger.
    assert "sources" not in set(LiteratureLLMOut.model_fields)
    assert {
        "grades_by_mode",
        "overall_grade",
        "overall_confidence",
        "rationale",
        "cross_condition_note",
        "observations",
    } <= set(LiteratureLLMOut.model_fields)


def test_record_accepts_optional_literature_track():
    from datetime import UTC, datetime

    rec = InternalizationRecord(
        schema_version=SCHEMA_VERSION,
        gene_symbol="TFRC",
        hgnc_id="HGNC:11763",
        uniprot_acc="P02786",
        model_priors=[],
        literature=LiteratureTrack(
            grades_by_mode=GradesByMode(
                therapeutic=ModeGrade(grade="high", confidence="moderate")
            ),
            overall_grade="high",
            overall_confidence="moderate",
            observations=[InternalizationObservation(assay_type="antibody_uptake")],
            n_observations=1,
        ),
        generated_at=datetime.now(UTC),
        runner_version="x",
    )
    assert rec.literature is not None
    assert rec.literature.grades_by_mode.therapeutic.grade == "high"
    # literature is optional (model-prior-only records still validate)
    assert (
        InternalizationRecord.model_validate(
            {**rec.model_dump(), "literature": None}
        ).literature
        is None
    )
