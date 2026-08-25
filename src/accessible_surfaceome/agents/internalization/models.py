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

SCHEMA_VERSION = "0.3.0"
RUNNER_VERSION = "internalization-model-prior/0.1.0"
# Human-bumpable label for the model-prior *system prompt*. Bump whenever
# model_prior_system.md changes so a re-run is detectable as non-stale even when
# schema_version is unchanged. (Internalization prompts are deliberately outside
# the deep-dive prompt-corpus fingerprint, so this pass carries its own version.)
# 0.2.0: per-residue DeepTMHMM topology handed to the model + cytoplasmic-only
# motif gate + succinct-but-comprehensive directive.
MODEL_PRIOR_PROMPT_VERSION = "0.2.0"
# Human-bumpable label for the LITERATURE prompt corpus (triage + select + grade
# + the shared web-discovery system prompt, hashed together in lit_prompt_sha).
# Bump whenever any of those changes so a lit re-run is detectable as non-stale
# even when schema_version is unchanged.
# 0.1.0: initial provenance stamp (triage + select + grade + web_search discovery).
# 0.1.1: web_discover envelope-tolerance fix (extra="ignore") — folds the web
#        system prompt into lit_prompt_sha so buggy-pass records re-run.
# 0.1.2: web-discovery recall (multi-search prompt) + bioRxiv-DOI hydration
#        fallback so EuropePMC-unindexed preprints (e.g. a methods/screen paper
#        that studies the protein without naming it) are caught, not dropped.
# 0.1.3: generalized the shared web-scout prompt to be topic-driven — removed
#        internalization-specific topic examples that had leaked into the
#        tag_site-shared module (no behavior change for internalization; avoids
#        over-fitting the shared scout to one caller's topic).
# 0.1.4: grade prompt — native_ligand mode is `unknown`/NA for orphan receptors
#        with no soluble endogenous ligand; chimeric-receptor + heterodimer-
#        partner-ligand studies no longer count as native-ligand evidence.
LIT_PROMPT_VERSION = "0.1.4"

Grade = Literal["high", "moderate", "low", "no", "unknown"]
GradeConfidence = Literal["high", "moderate", "low"]

# Sequence-track-only ordinal grade — finer than the shared literature ``Grade``
# so the model can register genuine spread. 5 ordered levels + ``unknown`` (can't
# tell from sequence). ``very_low`` subsumes the old non-internalizing ``no``.
# Kept SEPARATE from ``Grade`` so the literature per-mode grades are unchanged.
SeqGrade = Literal["very_high", "high", "moderate", "low", "very_low", "unknown"]

# Structured endocytic-motif hit (complements the free-text summary). A motif is
# only functional in a CYTOPLASMIC region, so ``region`` + ``functional_context``
# carry the topology judgement, not just the match.
MotifType = Literal[
    "yxxphi",          # tyrosine-based YXX[hydrophobic]
    "npxy",            # NPXY / FxNPxY (PTB-recognized)
    "dileucine",       # [DE]XXXL[LI]
    "acidic_cluster",  # acidic / CK2-phospho cluster (often paired with dileucine)
    "other",
]


class MotifHit(BaseModel):
    """One endocytic sorting-motif match the model found in the sequence."""

    model_config = ConfigDict(extra="forbid")

    motif_type: MotifType
    sequence: str = Field(..., description="The matched residues, e.g. 'YTRF'.")
    region: Literal["cytoplasmic", "extracellular", "transmembrane", "unknown"] = (
        "unknown"
    )
    approx_position: str | None = None  # e.g. "~res20" or "aa 20-23"
    functional_context: bool = False  # True iff in a cytoplasmic region (can act)
    note: str = ""


class IsoformPrior(BaseModel):
    """Model's per-isoform intrinsic-endocytic-propensity grade."""

    model_config = ConfigDict(extra="forbid")

    isoform_id: str
    is_canonical: bool
    length_aa: int | None = None
    topology_summary: str
    # Raw DeepTMHMM per-residue topology over {S,I,O,M,B} (S=signal peptide,
    # I=cytoplasmic/inside, O=extracellular/outside, M=TM helix, B=β-barrel TM),
    # residue-aligned to the graded sequence. None when topology fell back to
    # UniProt features (no per-residue call). NOT emitted by the model — code
    # re-stamps it from the trusted input context, so the model never has to
    # echo the long string back.
    topology_per_residue: str | None = None
    endocytic_motifs_noted: str | None = None  # free-text human summary
    motifs: list[MotifHit] = Field(default_factory=list)  # structured hits
    grade: SeqGrade
    confidence: GradeConfidence
    rationale: str = Field(..., description="Why this isoform got this grade.")


class ModelPriorLLMOut(BaseModel):
    """Exact shape the model must emit. No model/scope fields — code sets those."""

    model_config = ConfigDict(extra="forbid")

    overall_grade: SeqGrade
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
    overall_grade: SeqGrade
    overall_confidence: GradeConfidence
    model_reasoning: str
    per_isoform: list[IsoformPrior]
    # Prompt provenance so a stale record is detectable: prompt_sha is the
    # content fingerprint of the exact system prompt this track ran under
    # (auto-catches any edit); prompt_version is the human-bumpable label.
    # Code sets both — the model never emits them.
    prompt_sha: str | None = None
    prompt_version: str | None = None


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
    # Prompt provenance (the mandate): content-sha of the triage+select+grade
    # prompt corpus this track ran under (auto-catches any edit), plus the
    # human-bumpable label. Code sets both; the sweep's resume treats a changed
    # prompt_sha as stale.
    prompt_sha: str | None = None
    prompt_version: str | None = None


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
