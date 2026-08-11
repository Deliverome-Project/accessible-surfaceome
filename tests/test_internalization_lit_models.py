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


def test_schema_version_is_0_2_1():
    assert SCHEMA_VERSION == "0.2.1"


def test_moderate_is_a_valid_grade():
    # `moderate` was added to the shared Grade enum so genuine middle cases
    # aren't forced to high/low, in both tracks.
    assert ModeGrade(grade="moderate").grade == "moderate"
    from accessible_surfaceome.agents.internalization.models import IsoformPrior

    iso = IsoformPrior(
        isoform_id="P0-1",
        is_canonical=True,
        topology_summary="t",
        grade="moderate",
        confidence="moderate",
        rationale="partial/slow uptake",
    )
    assert iso.grade == "moderate"


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
