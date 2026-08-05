"""Pydantic models for the internalization record.

Schema 0.1.0 carries ONLY the model-prior track. Plan 2 (literature track)
bumps the version and adds a ``literature`` field. This record is a separate
artifact from ``SurfaceomeRecord`` with its own schema version.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "0.1.0"
RUNNER_VERSION = "internalization-model-prior/0.1.0"

Grade = Literal["high", "low", "no", "unknown"]
GradeConfidence = Literal["high", "moderate", "low"]


class IsoformPrior(BaseModel):
    """Model's per-isoform intrinsic-endocytic-propensity grade."""

    model_config = ConfigDict(extra="forbid")

    isoform_id: str
    is_canonical: bool
    length_aa: int | None = None
    topology_summary: str
    endocytic_motifs_noted: str | None = None
    grade: Grade
    confidence: GradeConfidence
    rationale: str = Field(..., description="Why this isoform got this grade.")


class ModelPriorLLMOut(BaseModel):
    """Exact shape the model must emit. No model/scope fields — code sets those."""

    model_config = ConfigDict(extra="forbid")

    overall_grade: Grade
    overall_confidence: GradeConfidence
    model_reasoning: str
    per_isoform: list[IsoformPrior]


class ModelPriorTrack(BaseModel):
    """One model's grade (e.g. Opus or Sonnet). ``scope`` is fixed: a model
    cannot know therapeutic/antibody-induced internalization from sequence, so
    this track speaks only to intrinsic/basal endocytic propensity."""

    model_config = ConfigDict(extra="forbid")

    model: str
    scope: Literal["intrinsic_propensity"] = "intrinsic_propensity"
    overall_grade: Grade
    overall_confidence: GradeConfidence
    model_reasoning: str
    per_isoform: list[IsoformPrior]


class InternalizationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    gene_symbol: str
    hgnc_id: str
    uniprot_acc: str
    model_priors: list[ModelPriorTrack]
    generated_at: datetime
    runner_version: str
