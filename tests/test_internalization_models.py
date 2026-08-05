from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from accessible_surfaceome.agents.internalization.models import (
    SCHEMA_VERSION,
    InternalizationRecord,
    IsoformPrior,
    ModelPriorLLMOut,
    ModelPriorTrack,
)


def _isoform_prior(**over):
    base: dict[str, Any] = dict(
        isoform_id="P00533-1",
        is_canonical=True,
        length_aa=1210,
        topology_summary="1 TM; N-term extracellular; cytoplasmic tail present",
        endocytic_motifs_noted="dileucine in cytoplasmic tail",
        grade="high",
        confidence="moderate",
        rationale="Cytoplasmic tail carries a canonical endocytic sorting motif.",
    )
    base.update(over)
    return IsoformPrior(**base)


def test_isoform_prior_rejects_bad_grade():
    with pytest.raises(ValidationError):
        _isoform_prior(grade="very_high")


def test_model_prior_track_defaults_scope_and_keeps_model():
    track = ModelPriorTrack(
        model="claude-opus-4-8",
        overall_grade="high",
        overall_confidence="moderate",
        model_reasoning="reasons",
        per_isoform=[_isoform_prior()],
    )
    assert track.scope == "intrinsic_propensity"
    assert track.model == "claude-opus-4-8"


def test_llm_out_has_no_model_or_scope_fields():
    # The LLM output schema must NOT carry model/scope (code sets those).
    fields = set(ModelPriorLLMOut.model_fields)
    assert "model" not in fields
    assert "scope" not in fields
    assert fields == {
        "overall_grade",
        "overall_confidence",
        "model_reasoning",
        "per_isoform",
    }


def test_record_round_trips_and_forbids_extra():
    rec = InternalizationRecord(
        schema_version=SCHEMA_VERSION,
        gene_symbol="EGFR",
        hgnc_id="HGNC:3236",
        uniprot_acc="P00533",
        model_priors=[
            ModelPriorTrack(
                model="claude-sonnet-4-6",
                overall_grade="low",
                overall_confidence="low",
                model_reasoning="reasons",
                per_isoform=[_isoform_prior()],
            )
        ],
        generated_at=datetime.now(UTC),
        runner_version="x",
    )
    dumped = rec.model_dump_json()
    again = InternalizationRecord.model_validate_json(dumped)
    assert again.model_priors[0].per_isoform[0].isoform_id == "P00533-1"
    with pytest.raises(ValidationError):
        InternalizationRecord.model_validate({**again.model_dump(), "junk": 1})
