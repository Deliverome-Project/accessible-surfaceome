"""Pydantic return shapes for the surface-proteome custom tools and per-gene output.

Two families live here:

1. **Custom-tool returns** — what `gene_lookup`, `gene_literature`, and `patent_lookup`
   hand back to the orchestrator (and, after JSON-stringification, to the agent).
   See ``docs/tools-design.md``.

2. **Per-gene output** — ``Evidence``, ``GeneAnnotation``, and supporting types that
   describe what the agent emits for each gene and what the orchestrator persists to
   ``data/annotations/{gene}.json``. See the M3 plan in
   ``docs/plans/2026-04-16-surface-proteome-annotation.md``.

The two families share the ``SourceRef`` / ``EvidenceSpan`` / ``Evidence`` chain so a
quote produced by ``gene_literature.fetch_abstract`` can flow directly into a
persisted ``Evidence`` record after deterministic validation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

# ---------------------------------------------------------------------------
# Shared identifiers
# ---------------------------------------------------------------------------


class GeneIdentifier(BaseModel):
    """Persistent identifiers carried into a per-gene annotation header.

    Subset of ``IdentifierBundle`` — the bundle is what the resolve tool returns;
    this is what the annotation file itself stores so downstream consumers can
    join without re-resolving.
    """

    model_config = ConfigDict(extra="forbid")

    hgnc_symbol: str
    hgnc_id: str
    uniprot_acc: str  # primary identifier for this study; required everywhere
    ncbi_gene_id: int | None = None
    ensembl_gene: str | None = None


# ---------------------------------------------------------------------------
# gene_lookup return shapes
# ---------------------------------------------------------------------------


UniProtStatus = Literal["active", "obsolete", "merged", "demerged", "deleted", "unknown"]
AliasCollisionRisk = Literal["low", "medium", "high"]


class IdentifierBundle(BaseModel):
    """Return shape of ``gene_lookup(mode="resolve")``.

    The first call the agent makes for any new gene. Canonicalizes identifiers across
    HGNC / UniProt / NCBI / Ensembl / Open Targets so every later tool call uses the
    same anchors.

    UniProt is the study's primary identifier — ``resolve`` must produce one, and a
    symbol that cannot be mapped to a UniProt accession is out-of-scope. Surface this
    upstream by raising rather than returning a record with a null acc.
    """

    model_config = ConfigDict(extra="forbid")

    hgnc_symbol: str
    hgnc_id: str
    approved_name: str | None = None  # HGNC's current full name (e.g. "kidney associated DCDC2 antisense RNA 1")
    aliases: list[str] = Field(default_factory=list)  # current alternate symbols, union(HGNC, NCBI), deduped
    alias_names: list[str] = Field(default_factory=list)  # current alternate full names (HGNC.alias_name)
    previous_symbols: list[str] = Field(default_factory=list)  # deprecated symbols (HGNC.prev_symbol)
    previous_names: list[str] = Field(default_factory=list)  # deprecated full names (HGNC.prev_name)
    uniprot_acc: str
    uniprot_status: UniProtStatus = "unknown"
    uniprot_merged_into: str | None = None  # set when uniprot_status == "merged"
    ncbi_gene_id: int | None = None
    ensembl_gene: str | None = None
    ensembl_canonical_protein: str | None = None
    length_aa: int | None = None
    isoform_count: int | None = None
    alias_collision_risk: AliasCollisionRisk = "low"
    open_targets_status: str | None = None  # e.g. "approved", "uniprot_obsolete"
    ncbi_summary: str | None = None


SourceName = Literal[
    "surfy",
    "cspa",
    "uniprot_query",
    "go",
    "hpa",
    "deeptmhmm",
    "compartments",
    "patent_handle",
]


class SourceVote(BaseModel):
    """One source's vote on whether a gene is surface, with source-specific evidence.

    ``evidence`` is intentionally a free-form dict — each source's loader emits a
    different shape (GO returns ``[{go_id, evidence_code, term}]``; COMPARTMENTS
    returns ``top3_terms`` with stars; SURFY returns the ML class; etc.). Locking
    these down before the loaders settle would be premature.
    """

    model_config = ConfigDict(extra="forbid")

    source: SourceName
    vote: bool
    evidence: dict[str, Any] = Field(default_factory=dict)


class DBVotePanel(BaseModel):
    """Return shape of ``gene_lookup(mode="db_panel")``.

    Side-by-side per-source surface votes from the M1 candidate-universe processed
    data. Read directly from local Parquet/TSV; no upstream calls.
    """

    model_config = ConfigDict(extra="forbid")

    hgnc_symbol: str
    uniprot_acc: str
    sources: list[SourceVote]
    n_sources_voting_surface: int
    in_db_union: bool
    in_patent_handles: bool


SubcellularReliability = Literal["enhanced", "supported", "approved", "uncertain", "unknown"]


class TopologyFeature(BaseModel):
    """One UniProt topology feature: signal peptide, TM helix, topo_dom, lipidation, GPI."""

    model_config = ConfigDict(extra="forbid")

    feature_type: Literal[
        "signal_peptide",
        "transmembrane",
        "topological_domain",
        "intramembrane",
        "lipidation",
        "gpi_anchor",
        "glycosylation",
        "disulfide_bond",
    ]
    description: str | None = None
    start: int | None = None
    end: int | None = None


class SubcellularLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: str
    is_isoform_specific: bool = False
    isoform: str | None = None
    reliability: SubcellularReliability = "unknown"


class PTMRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ptm_type: str  # e.g. "phosphorylation", "glycosylation", "lipidation"
    description: str | None = None
    position: int | None = None


class CrossReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    db: Literal["pdb", "interpro", "pfam", "antibodypedia", "alphafold", "ensembl", "other"]
    identifier: str
    description: str | None = None


class IsoformRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    isoform_id: str
    name: str | None = None
    is_canonical: bool = False
    length_aa: int | None = None


class PublicationStub(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pmid: int
    title: str
    year: int | None = None


class UniProtSummary(BaseModel):
    """Return shape of ``gene_lookup(mode="uniprot_summary")``.

    Distilled UniProt entry — subcellular locations, topology features, PTMs,
    function/tissue prose, top-N publications, and key cross-refs. The agent should
    call this rather than ``web_fetch`` against UniProt directly: the tool is faster,
    cached, and Pydantic-validated.
    """

    model_config = ConfigDict(extra="forbid")

    uniprot_acc: str
    entry_name: str | None = None
    protein_name: str | None = None
    subcellular_locations: list[SubcellularLocation] = Field(default_factory=list)
    topology_features: list[TopologyFeature] = Field(default_factory=list)
    ptms: list[PTMRecord] = Field(default_factory=list)
    function_text: str | None = None
    tissue_specificity_text: str | None = None
    isoforms: list[IsoformRecord] = Field(default_factory=list)
    n_publications: int = 0
    top_publications: list[PublicationStub] = Field(default_factory=list)
    cross_references: list[CrossReference] = Field(default_factory=list)


class SourceRuleResult(BaseModel):
    """Per-source diagnosis of why the M1 rule fired or didn't for a given gene."""

    model_config = ConfigDict(extra="forbid")

    source: SourceName
    rule_fired: bool
    missing_features: list[str] = Field(default_factory=list)
    rule_explanation: str


class MissDiagnosis(BaseModel):
    """Return shape of ``gene_lookup(mode="miss_diagnosis")``.

    Returned only when a gene is in the controls panel but absent from the candidate
    universe. Per-source explanation of why each rule failed to fire, plus which
    "lane" (e.g. patent-handle, MHC-presentation edge case) might catch it instead.
    """

    model_config = ConfigDict(extra="forbid")

    hgnc_symbol: str
    uniprot_acc: str
    in_candidate_universe: bool
    per_source: list[SourceRuleResult]
    candidate_lanes: list[str] = Field(default_factory=list)
    summary: str


# ---------------------------------------------------------------------------
# gene_literature return shapes
# ---------------------------------------------------------------------------


TopicAnchor = Literal[
    "surface_expression",
    "topology",
    "ihc",
    "flow_cytometry",
    "surface_biotinylation",
    "mass_spec_surfaceome",
    "structure",
    "ptm",
    "shedding",
]

PublicationType = Literal[
    "primary_research",
    "review",
    "preprint",
    "meta_analysis",
    "db_entry",
    "structure",
    "other",
]


class PaperSection(BaseModel):
    """One section of a full-text paper.

    Used by ``fetch_fulltext``; references are deliberately omitted. If the section
    was truncated to fit the per-tool token ceiling, ``truncated`` is True and the
    caller can re-fetch with a narrower section selection.
    """

    model_config = ConfigDict(extra="forbid")

    name: Literal["intro", "methods", "results", "discussion", "figure_legends"]
    text: str
    truncated: bool = False


class Paper(BaseModel):
    """One paper record returned by gene_literature.

    Same shape across all four modes — ``abstract`` is populated by all modes,
    ``sections`` only by ``fetch_fulltext``. Tags and flags (``topic_tags``,
    ``is_review``, ``is_retracted``, ``is_pmc_oa``) are computed by the tool *before*
    tokens reach the agent, so the agent can prioritize without re-reading.
    """

    model_config = ConfigDict(extra="forbid")

    pmid: int
    pmc_id: str | None = None
    doi: str | None = None
    year: int | None = None
    journal: str | None = None
    title: str
    abstract: str | None = None
    publication_type: PublicationType = "other"
    is_review: bool = False
    is_retracted: bool = False
    retraction_checked_at: datetime | None = None
    is_pmc_oa: bool = False
    topic_tags: list[TopicAnchor] = Field(default_factory=list)
    sections: list[PaperSection] = Field(default_factory=list)
    truncated_sections: list[str] = Field(default_factory=list)


LiteratureMode = Literal["gene2pubmed", "topic_search", "fetch_abstract", "fetch_fulltext"]


class LiteraturePack(BaseModel):
    """Return shape of ``gene_literature(mode="gene2pubmed" | "topic_search")``.

    Ordered list of papers (gene2pubmed-curated first, topic-search fill second).
    Topic-search results are dedup'd against any prior gene2pubmed call in the same
    session.
    """

    model_config = ConfigDict(extra="forbid")

    hgnc_symbol: str
    mode: LiteratureMode
    papers: list[Paper] = Field(default_factory=list)
    n_total: int = 0
    n_returned: int = 0
    topic_anchors_used: list[TopicAnchor] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# patent_lookup return shapes
# ---------------------------------------------------------------------------


class PatentFigureEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    figure_id: str
    modality: Literal[
        "ihc",
        "flow_cytometry",
        "mab_characterization",
        "binding_assay",
        "in_vivo_efficacy",
        "other",
    ]
    summary: str


class PatentSummary(BaseModel):
    """Return shape of ``patent_lookup``.

    Patent claims are *not* peer-reviewed primary evidence — ``evidence_provenance``
    is hard-coded to ``"patent"`` so downstream evidence-tier logic can down-weight
    these accordingly.
    """

    model_config = ConfigDict(extra="forbid")

    wo_number: str
    title: str
    applicant: str | None = None
    priority_date: datetime | None = None
    publication_date: datetime | None = None
    claims_summary: str
    cited_genes: list[str] = Field(default_factory=list)
    experimental_evidence_figures: list[PatentFigureEvidence] = Field(default_factory=list)
    evidence_provenance: Literal["patent"] = "patent"


# ---------------------------------------------------------------------------
# Per-gene Evidence chain (SourceRef → EvidenceSpan → Evidence → GeneAnnotation)
# Source: docs/plans/2026-04-16-surface-proteome-annotation.md, "Pydantic schemas (revised)".
# ---------------------------------------------------------------------------


SourceType = Literal[
    "pubmed",
    "pmc",
    "europe_pmc",
    "openalex",
    "uniprot",
    "biorxiv",
    "medrxiv",
    "hpa",
    "pdb",
    "patent",
    "web",
]

License = Literal["cc_by", "cc_by_nc", "cc_by_sa", "cc0", "closed", "unknown"]


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: SourceType
    source_id: str  # "PMID:12345678" / "DOI:10.xx/yy" / "UniProt:P12345" / "PDB:2ABC"
    pmc_id: str | None = None  # separate tracking for PubMed↔PMC linkage
    url: HttpUrl
    title: str
    retrieved_at: datetime
    content_sha256: str  # hash of fetched text at retrieval
    publication_type: PublicationType
    is_retracted: bool
    retraction_checked_at: datetime  # TTL-bounded; rechecked at publish-time
    license: License = "unknown"


PaperSection_ = Literal[
    "title",
    "abstract",
    "introduction",
    "results",
    "discussion",
    "methods",
    "figure_legend",
    "table",
    "structure_header",
    "other",
]


class EvidenceSpan(BaseModel):
    """A verbatim quote anchored to a specific source location.

    ``char_offset`` is REQUIRED — any record missing it is rejected by the
    deterministic validator (``docs/plans/2026-04-16-surface-proteome-annotation.md``,
    rule 3). This prevents paraphrased "evidence" from sneaking through.
    """

    model_config = ConfigDict(extra="forbid")

    source: SourceRef
    section: PaperSection_
    figure_or_table_id: str | None = None  # "Figure 3A", "Table S1", "Chain A"
    quote: str = Field(..., max_length=200)  # ≤200 chars, ALWAYS verbatim
    quote_sha256: str  # tamper-detection
    char_offset: int  # position in source; REQUIRED, no None
    normalized_source_sha256: str  # hash of normalized form used for substring check


Species = Literal["human", "mouse", "rat", "macaque", "dog", "other", "unspecified"]


class AssayContext(BaseModel):
    """Why this exists: surface-vs-intracellular reads hinge on permeabilization
    and species. Carrying the context lets the synthesis layer down-weight or
    discard a quote that's positive but obtained under permeabilizing conditions
    (where surface-vs-intracellular cannot be distinguished).
    """

    model_config = ConfigDict(extra="forbid")

    species: Species
    cell_type_or_line: str | None = None
    permeabilized: bool | None = None
    fixation: Literal["live", "fixed", "unspecified"] | None = None
    isoform: str | None = None  # UniProt isoform ID if specified


ClaimType = Literal[
    "surface_expression",
    "topology",
    "tissue_expression",
    "methodological",
    "contradictory",
]
Direction = Literal["supports", "refutes", "ambiguous"]
EvidenceType = Literal[
    "flow_cytometry",
    "surface_biotinylation",
    "mass_spec_surfaceome",
    "immunohistochemistry",
    "immunofluorescence",
    "crystal_structure",
    "cryo_em",
    "computational_prediction",
    "orthology",
    "review_assertion",
    "db_annotation",
]
EvidenceTier = Literal["primary", "secondary"]
EvidenceConfidence = Literal["strong", "moderate", "weak"]


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str
    claim_type: ClaimType
    direction: Direction
    evidence_type: EvidenceType
    evidence_tier: EvidenceTier  # primary = experimental; secondary = review/db
    confidence: EvidenceConfidence
    assay_context: AssayContext
    spans: list[EvidenceSpan] = Field(..., min_length=1)
    entailment_verified: bool = False  # set by claim_entailment.py audit


# ---------------------------------------------------------------------------
# SurfaceomeRecord — the per-protein reconciled annotation persisted to
# data/annotations/{gene}.json. Replaces the proof-of-concept GeneAnnotation
# schema with a structure that lets a biopharma scientist evaluating ADC /
# antibody / delivery candidates see surface biology AND therapeutic context
# in one place.
#
# Several enums are intentionally **hybrid** — closed list + ``"other"``
# escape hatch with a required ``*_other_label`` for the agent to describe a
# novel category. This is by design: ``other`` accumulating in the corpus is
# the input to a future ontology-review agent that proposes new categories
# or merges duplicates. ``schema_version`` lets us track which ontology a
# record was made under as we evolve.
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "v0.2.0"


# ---- shared enums (closed) ------------------------------------------------

SurfaceStatus = Literal[
    "strong_surface",
    "moderate_surface",
    "weak_surface",
    "rare_surface",
    "absent",
    "contradictory",
]
Topology = Literal[
    "transmembrane_single_pass",
    "transmembrane_multi_pass",
    "outer_leaflet_peripheral",
    "gpi_anchored",
    "inner_leaflet_peripheral",
    "cytosolic_pm_adjacent",
    "not_pm_associated",
]
AnchorType = Literal[
    "transmembrane_single",
    "transmembrane_multi",
    "gpi_anchored",
    "lipidated",
    "peripheral",
    "mhc_presented_peptide",
    "none",
    "unknown",
]
SynthesisConfidence = Literal["high", "medium", "low"]
ModelPath = Literal["sonnet_only", "opus_light", "opus_heavy"]


# Closed: the gold-standard list itself uses a fixed taxonomy. If the agent
# encounters a candidate that doesn't fit, the right answer is to expand the
# enum, not sneak it in via "other".
TargetabilityTier = Literal[
    "validated_target",  # approved drug exists targeting this surface protein
    "clinical_stage",  # in clinical trials
    "preclinical",  # patent disclosures or published preclinical mAbs/ADCs
    "novel_candidate",  # plausible surface target with no therapeutic precedent
    "edge_case",  # mechanism doesn't fit conventional surface targeting (KAAG1)
    "contraindicated",  # safety/biology rules it out (e.g. essential organ expression)
    "non_target",  # not surface-accessible
]


# ---- hybrid enums (closed list + "other") ---------------------------------

ModalityKind = Literal[
    "adc",
    "naked_mab",
    "bispecific",
    "car_t",
    "tcr_mimic",
    "radioligand",
    "lnp_cargo",
    "peptide_drug_conjugate",
    "bicycles",
    "oligo_conjugate",
    "not_recommended",
    "other",
]


class ModalityRecommendation(BaseModel):
    """One recommended therapeutic modality.

    Hybrid enum: ``kind`` is closed except for ``"other"`` which requires a
    ``kind_other_label``. The ``other`` entries are inputs to ontology review;
    treat their accumulation as a signal to add a new modality literal.
    """

    model_config = ConfigDict(extra="forbid")

    kind: ModalityKind
    kind_other_label: str | None = None
    rationale: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _check_other_label(self) -> ModalityRecommendation:
        if self.kind == "other" and not self.kind_other_label:
            raise ValueError("ModalityRecommendation.kind='other' requires kind_other_label")
        if self.kind != "other" and self.kind_other_label is not None:
            raise ValueError(
                f"ModalityRecommendation.kind_other_label must be None when kind={self.kind!r}"
            )
        return self


RiskFlagKind = Literal[
    "shedding_decoy",  # soluble pool of antigen acts as ADC decoy
    "paralog_cross_reactivity",  # related family members the antibody could bind
    "essential_normal_tissue",  # CNS, gut epithelium, cardiac, etc.
    "mechanism_caveat",  # KAAG1's MHC presentation, polytopic short ECDs, …
    "low_density",  # below ADC payload-delivery threshold
    "tumor_heterogeneity",  # only a subset of tumor cells express it
    "polymorphism_dependent",  # HLA restriction, isoform-specific expression
    "patent_density",  # crowded IP space
    "internalization_unknown",  # required for ADCs but not characterized
    "other",
]
RiskSeverity = Literal["blocking", "high", "medium", "low"]


class RiskFlag(BaseModel):
    """A specific risk that affects therapeutic targetability.

    Hybrid enum: same pattern as ``ModalityRecommendation``. ``other`` requires
    a ``kind_other_label`` so the future ontology-review agent can propose a
    new category once a label appears repeatedly.
    """

    model_config = ConfigDict(extra="forbid")

    kind: RiskFlagKind
    kind_other_label: str | None = None
    severity: RiskSeverity
    description: str = Field(..., max_length=500)

    @model_validator(mode="after")
    def _check_other_label(self) -> RiskFlag:
        if self.kind == "other" and not self.kind_other_label:
            raise ValueError("RiskFlag.kind='other' requires kind_other_label")
        if self.kind != "other" and self.kind_other_label is not None:
            raise ValueError(f"RiskFlag.kind_other_label must be None when kind={self.kind!r}")
        return self


# ---- bucket: targetability ------------------------------------------------


class TargetabilityVerdict(BaseModel):
    """Top-of-page summary: is this a target, and how would you go after it?"""

    model_config = ConfigDict(extra="forbid")

    tier: TargetabilityTier
    recommended_modalities: list[ModalityRecommendation] = Field(default_factory=list)
    tldr: str = Field(..., max_length=400)


# ---- bucket: surface biology ----------------------------------------------


ECDAccessibility = Literal["accessible", "membrane_proximal", "buried", "unknown"]


class ExtracellularDomainSummary(BaseModel):
    """Sketch of the extracellular face — what an antibody actually sees."""

    model_config = ConfigDict(extra="forbid")

    size_aa: int | None = None
    domains: list[str] = Field(default_factory=list)  # e.g. ["Ig-like C2", "Fibronectin III"]
    accessibility: ECDAccessibility = "unknown"
    notes: str | None = Field(default=None, max_length=400)


class DBComparison(BaseModel):
    """Compact per-source vote summary embedded in the surface_biology bucket.

    Distinct from ``DBVotePanel`` (which is a tool return with rich per-source
    evidence payloads). This is the side-by-side bool vote table the record
    ships, suitable for a blog table or join key.
    """

    model_config = ConfigDict(extra="forbid")

    surfy: bool | None = None
    cspa: bool | None = None
    uniprot_query: bool | None = None
    go: bool | None = None
    hpa: bool | None = None
    deeptmhmm: bool | None = None
    compartments: bool | None = None
    patent_handle: bool | None = None
    n_sources_voting_surface: int


class SurfaceBiology(BaseModel):
    """The reconciled surface call + supporting biology.

    ``surface_status`` and ``topology`` are intentionally orthogonal: KRAS is
    ``topology=inner_leaflet_peripheral`` and ``surface_status=absent`` (membrane-
    anchored but not extracellularly accessible). Conflating them reproduces the
    SURFY false-positive pattern this project exists to correct.
    """

    model_config = ConfigDict(extra="forbid")

    surface_status: SurfaceStatus
    topology: Topology
    anchor_type: AnchorType
    extracellular_domain: ExtracellularDomainSummary | None = None
    glycosylation: bool | None = None  # any reported N- or O-linked glycosylation
    shedding_documented: bool | None = None  # critical for ADC: soluble decoys
    db_comparison: DBComparison


# ---- bucket: expression ---------------------------------------------------


TumorSpecificity = Literal[
    "pan_tumor",  # widely overexpressed across tumor types
    "indication_restricted",  # one or a few cancer types
    "subset_within_indication",  # subpopulation of an indication's tumors
    "tumor_isoform_specific",  # only tumor-specific isoform/PTM
    "broad_low_specificity",  # widely expressed in tumor and normal
    "unknown",
]


class ExpressionProfile(BaseModel):
    """Where this protein is expressed and how specific that is."""

    model_config = ConfigDict(extra="forbid")

    tumor_indications: list[str] = Field(default_factory=list)
    tumor_specificity: TumorSpecificity = "unknown"
    normal_tissue_top: list[str] = Field(default_factory=list)
    normal_tissue_concerns: list[str] = Field(default_factory=list)  # CNS, gut, heart…
    summary: str | None = Field(default=None, max_length=600)


# ---- bucket: ADC properties -----------------------------------------------


Internalization = Literal["validated", "predicted", "non_internalizing", "unknown"]
ExpressionHomogeneity = Literal["homogeneous", "heterogeneous", "subpopulation", "unknown"]


class ADCProperties(BaseModel):
    """ADC-specific characteristics. Intentionally sparse — most fields will
    be ``None`` until ``gene_literature`` lands and we can mine internalization
    + copy-number reports. The fields exist now so the structure is stable as
    we light them up over time.
    """

    model_config = ConfigDict(extra="forbid")

    internalization: Internalization = "unknown"
    estimated_copies_per_cell: str | None = None  # free text — wide ranges in lit
    expression_homogeneity: ExpressionHomogeneity = "unknown"
    payload_compatibility_notes: str | None = Field(default=None, max_length=500)


# ---- bucket: therapeutic landscape ---------------------------------------


class ApprovedDrug(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str  # generic + brand if known
    modality: ModalityKind
    modality_other_label: str | None = None
    indication: str
    sponsor: str | None = None
    approval_year: int | None = None

    @model_validator(mode="after")
    def _check_other_label(self) -> ApprovedDrug:
        if self.modality == "other" and not self.modality_other_label:
            raise ValueError("ApprovedDrug.modality='other' requires modality_other_label")
        if self.modality != "other" and self.modality_other_label is not None:
            raise ValueError("ApprovedDrug.modality_other_label only valid when modality='other'")
        return self


ClinicalPhase = Literal["preclinical", "phase_1", "phase_1_2", "phase_2", "phase_2_3", "phase_3", "approved", "discontinued", "unknown"]


class ClinicalTrial(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nct_id: str | None = None
    title: str | None = None
    modality: ModalityKind
    modality_other_label: str | None = None
    phase: ClinicalPhase = "unknown"
    indication: str | None = None
    sponsor: str | None = None
    status: str | None = None  # free text — recruiting / completed / terminated

    @model_validator(mode="after")
    def _check_other_label(self) -> ClinicalTrial:
        if self.modality == "other" and not self.modality_other_label:
            raise ValueError("ClinicalTrial.modality='other' requires modality_other_label")
        if self.modality != "other" and self.modality_other_label is not None:
            raise ValueError("ClinicalTrial.modality_other_label only valid when modality='other'")
        return self


class PatentDisclosure(BaseModel):
    """A patent that claims this protein as a delivery / antibody target."""

    model_config = ConfigDict(extra="forbid")

    wo_number: str  # WO/EP/US patent number — the canonical identifier
    title: str | None = None
    applicant: str | None = None
    modality: ModalityKind
    modality_other_label: str | None = None
    priority_year: int | None = None
    summary: str = Field(..., max_length=400)

    @model_validator(mode="after")
    def _check_other_label(self) -> PatentDisclosure:
        if self.modality == "other" and not self.modality_other_label:
            raise ValueError("PatentDisclosure.modality='other' requires modality_other_label")
        if self.modality != "other" and self.modality_other_label is not None:
            raise ValueError(
                "PatentDisclosure.modality_other_label only valid when modality='other'"
            )
        return self


class PreclinicalEvidence(BaseModel):
    """A published preclinical mAb / ADC / CAR / TCR-mimic characterization."""

    model_config = ConfigDict(extra="forbid")

    citation: str  # PMID:..., DOI:..., or PMC:...
    modality: ModalityKind
    modality_other_label: str | None = None
    finding_summary: str = Field(..., max_length=400)

    @model_validator(mode="after")
    def _check_other_label(self) -> PreclinicalEvidence:
        if self.modality == "other" and not self.modality_other_label:
            raise ValueError("PreclinicalEvidence.modality='other' requires modality_other_label")
        if self.modality != "other" and self.modality_other_label is not None:
            raise ValueError(
                "PreclinicalEvidence.modality_other_label only valid when modality='other'"
            )
        return self


class TherapeuticLandscape(BaseModel):
    """What's been tried — by whom, in what modality, with what outcome.

    Sparse for novel candidates; rich for the validated 11 ADC targets we
    benchmark against.
    """

    model_config = ConfigDict(extra="forbid")

    approved_drugs: list[ApprovedDrug] = Field(default_factory=list)
    clinical_trials: list[ClinicalTrial] = Field(default_factory=list)
    patent_disclosures: list[PatentDisclosure] = Field(default_factory=list)
    preclinical_evidence: list[PreclinicalEvidence] = Field(default_factory=list)


# ---- top-level record -----------------------------------------------------


class SurfaceomeRecord(BaseModel):
    """The reconciled per-protein record persisted to data/annotations/{gene}.json.

    Primary purpose: answer "is this a candidate for therapeutic surface
    targeting, and what would you need to know to evaluate it?" The headline
    is the surface-biology classification (which is the project's core
    deliverable — the gold-standard surfaceome list); therapeutic context
    fills in the metadata a biopharma scientist needs alongside the call.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION

    # Identity
    gene: GeneIdentifier
    canonical_isoform: str
    isoform_flattened: bool

    # Headline + supporting buckets
    targetability: TargetabilityVerdict
    surface_biology: SurfaceBiology
    expression: ExpressionProfile
    adc_properties: ADCProperties
    therapeutic_landscape: TherapeuticLandscape
    risk_flags: list[RiskFlag] = Field(default_factory=list)

    # Provenance
    primary_evidence_count: int = 0
    secondary_evidence_count: int = 0
    evidence_count: int = 0
    cited_evidence_ids: list[str] = Field(default_factory=list)  # quote_sha256 refs

    # Synthesis metadata
    confidence: SynthesisConfidence
    confidence_reasoning: str
    contradiction_flag: bool
    rationale: str = Field(..., max_length=600)
    model_path: ModelPath


# ---------------------------------------------------------------------------
# Public re-export list
# ---------------------------------------------------------------------------


__all__ = [
    # Shared identifiers
    "GeneIdentifier",
    # gene_lookup
    "IdentifierBundle",
    "UniProtStatus",
    "AliasCollisionRisk",
    "SourceName",
    "SourceVote",
    "DBVotePanel",
    "SubcellularLocation",
    "SubcellularReliability",
    "TopologyFeature",
    "PTMRecord",
    "CrossReference",
    "IsoformRecord",
    "PublicationStub",
    "UniProtSummary",
    "SourceRuleResult",
    "MissDiagnosis",
    # gene_literature
    "Paper",
    "PaperSection",
    "LiteraturePack",
    "LiteratureMode",
    "TopicAnchor",
    "PublicationType",
    # patent_lookup
    "PatentSummary",
    "PatentFigureEvidence",
    # Evidence chain
    "SourceRef",
    "SourceType",
    "License",
    "EvidenceSpan",
    "AssayContext",
    "Species",
    "Evidence",
    "ClaimType",
    "Direction",
    "EvidenceType",
    "EvidenceTier",
    "EvidenceConfidence",
    # SurfaceomeRecord + buckets
    "SCHEMA_VERSION",
    "SurfaceomeRecord",
    "TargetabilityVerdict",
    "TargetabilityTier",
    "ModalityKind",
    "ModalityRecommendation",
    "SurfaceBiology",
    "AnchorType",
    "ExtracellularDomainSummary",
    "ECDAccessibility",
    "DBComparison",
    "ExpressionProfile",
    "TumorSpecificity",
    "ADCProperties",
    "Internalization",
    "ExpressionHomogeneity",
    "TherapeuticLandscape",
    "ApprovedDrug",
    "ClinicalTrial",
    "ClinicalPhase",
    "PatentDisclosure",
    "PreclinicalEvidence",
    "RiskFlag",
    "RiskFlagKind",
    "RiskSeverity",
    "SurfaceStatus",
    "Topology",
    "SynthesisConfidence",
    "ModelPath",
]
