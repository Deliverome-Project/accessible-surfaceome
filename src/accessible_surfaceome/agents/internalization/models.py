"""Pydantic models for the internalization record.

Schema 0.2.3 carries two tracks: ``model_priors`` (Plan 1 — per-isoform grade
from sequence + topology) and an optional ``literature`` track (Plan 2 —
PMID-anchored, span-verified). This record is a separate artifact from
``SurfaceomeRecord`` with its own schema version.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from accessible_surfaceome.tools._shared.models import Evidence

SCHEMA_VERSION = "0.2.4"
RUNNER_VERSION = "internalization-model-prior/0.1.0"

Grade = Literal["high", "moderate", "low", "no", "unknown"]
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


# --- Literature track (Plan 2): PMID-anchored, span-verified ---

InternalizationMode = Literal["basal", "native_ligand", "therapeutic", "unknown"]
AssayType = Literal[
    "antibody_uptake",
    "ligand_uptake",
    "adc_internalization",
    "nanoparticle_uptake",
    "oligonucleotide_uptake",
    "peptide_uptake",
    "viral_entry",
    "radioligand_immunopet",
    "ph_sensitive_dye",
    "acid_strip_flow",
    "surface_biotinylation",
    "live_imaging",
    "receptor_recycling",
    "endocytosis_inhibitor",
    "other",
    "unknown",
]
CellContext = Literal[
    "primary",
    "cell_line",
    "tumor_cell_line",
    "ipsc_or_stem",
    "in_vivo",
    "other",
    "unknown",
]
Mechanism = Literal[
    "clathrin",
    "caveolin",
    "macropinocytosis",
    "clathrin_independent",
    "receptor_mediated_unspecified",
    "other",
    "unknown",
]
Magnitude = Literal["high", "moderate", "low", "none", "unknown"]
RateMetric = Literal[
    "ke_h_inv", "percent_internalized", "half_life", "fold_change", "other"
]
# Where the receptor traffics after uptake / its intracellular fate.
TraffickingCompartment = Literal[
    "early_endosome",
    "recycling_endosome",
    "late_endosome",
    "lysosome",
    "golgi",
    "er",
    "degradation",
    "recycled_to_surface",
    "other",
    "unknown",
]
# Does a ligand or therapeutic binder CHANGE internalization relative to basal?
LigandEffect = Literal[
    "increases", "decreases", "no_change", "not_applicable", "unknown"
]
# How perturbing a DIFFERENT gene/protein changes the TARGET's internalization.
ModulatorEffect = Literal["increases", "decreases", "no_change", "unknown"]
# How the third-party modulator was perturbed in the experiment.
PerturbationType = Literal[
    "knockdown",
    "knockout",
    "overexpression",
    "inhibitor_or_drug",
    "mutation",
    "antibody_or_ligand_block",
    "other",
    "unknown",
]


class ModeGrade(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grade: Grade = "unknown"
    confidence: GradeConfidence = "low"
    rationale: str = ""
    cited_source_ids: list[str] = Field(default_factory=list)


class GradesByMode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    basal: ModeGrade = Field(default_factory=ModeGrade)
    native_ligand: ModeGrade = Field(default_factory=ModeGrade)
    therapeutic: ModeGrade = Field(default_factory=ModeGrade)


class InternalizationQuant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rate_metric: RateMetric | None = None
    rate_value: float | None = None
    rate_unit: str | None = None
    time_point: str | None = None
    quant_summary: str = ""


class InternalizationObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assay_type: AssayType
    assay_type_other_label: str | None = None
    cell_line: str | None = None
    cell_context: CellContext = "unknown"
    internalization_mode: InternalizationMode = "unknown"
    ligand_name: str | None = None
    ligand_effect: LigandEffect = "unknown"
    mechanism: Mechanism | None = None
    trafficking_compartment: TraffickingCompartment = "unknown"
    magnitude: Magnitude = "unknown"
    quant: InternalizationQuant = Field(default_factory=InternalizationQuant)
    controls_note: str | None = None
    condition_note: str = ""
    cited_source_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_other_label(self) -> InternalizationObservation:
        if self.assay_type == "other" and not self.assay_type_other_label:
            raise ValueError("assay_type='other' requires assay_type_other_label")
        if self.assay_type != "other" and self.assay_type_other_label is not None:
            raise ValueError(
                "assay_type_other_label must be None unless assay_type=='other'"
            )
        return self


class ModulatorObservation(BaseModel):
    """A finding where perturbing a DIFFERENT gene/protein changes the TARGET's
    internalization — recorded SEPARATELY from the target's own internalization
    (``observations``). This is genuinely different data: it measures what
    modulates the target's uptake (a family member, heterodimer partner,
    adaptor, or pathway gene), not the target's intrinsic / native-ligand /
    therapeutic internalization. It does NOT drive ``grades_by_mode`` /
    ``overall_grade``."""

    model_config = ConfigDict(extra="forbid")

    modulator: str = Field(
        ..., description="The DIFFERENT gene/protein that was perturbed."
    )
    perturbation: PerturbationType = "unknown"
    effect_on_target: ModulatorEffect = "unknown"
    cell_line: str | None = None
    cell_context: CellContext = "unknown"
    magnitude: Magnitude = "unknown"
    quant: InternalizationQuant = Field(default_factory=InternalizationQuant)
    note: str = ""
    cited_source_ids: list[str] = Field(default_factory=list)


class LiteratureLLMOut(BaseModel):
    """Exact shape the grader model emits — no ``sources`` (code attaches the
    promoted, span-verified evidence ledger)."""

    model_config = ConfigDict(extra="forbid")

    grades_by_mode: GradesByMode = Field(default_factory=GradesByMode)
    overall_grade: Grade = "unknown"
    overall_confidence: GradeConfidence = "low"
    rationale: str = ""
    cross_condition_note: str = ""
    trafficking_summary: str = ""
    observations: list[InternalizationObservation] = Field(default_factory=list)
    modulator_observations: list[ModulatorObservation] = Field(default_factory=list)


class LiteratureTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grades_by_mode: GradesByMode = Field(default_factory=GradesByMode)
    overall_grade: Grade = "unknown"
    overall_confidence: GradeConfidence = "low"
    rationale: str = ""
    cross_condition_note: str = ""
    trafficking_summary: str = ""
    species_scope: str = "unspecified"
    species_inferred: bool = False
    has_primary_or_invivo_evidence: bool = False
    observations: list[InternalizationObservation] = Field(default_factory=list)
    modulator_observations: list[ModulatorObservation] = Field(default_factory=list)
    sources: list[Evidence] = Field(default_factory=list)
    n_observations: int = 0
    n_modulator_observations: int = 0
    n_papers_discovered: int = 0
    n_papers_fetched: int = 0


class InternalizationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    gene_symbol: str
    hgnc_id: str
    uniprot_acc: str
    model_priors: list[ModelPriorTrack]
    literature: LiteratureTrack | None = None
    generated_at: datetime
    runner_version: str
