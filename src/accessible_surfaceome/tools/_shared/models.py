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
    # HGNC gene-group memberships (e.g. ["CD molecules", "Erb-b2 receptor tyrosine kinases"]).
    # Registry-curated family lineage; useful for the triage agent to recognize
    # surface-protein family conventions without prompt-embedded enumerations.
    hgnc_gene_groups: list[str] = Field(default_factory=list)
    # CD nomenclature designation when assigned (e.g. "CD340" for ERBB2). CD numbers
    # are awarded to differentiation-cluster antigens — almost always surface or
    # pseudo-surface markers. Strong surface signal when present.
    cd_designation: str | None = None
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
    authors: list[str] = Field(default_factory=list)  # ordered, full-name strings (e.g. "Van Den Eynde BJ")
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


class EvidenceClaim(BaseModel):
    """What the AGENT emits for a load-bearing claim.

    Small, human-shaped: an `evidence_id` (agent-assigned, used for
    cross-references via per-bucket `cited_evidence_ids`), a `claim`, the
    classification fields, the assay context, the source identifier, and a
    verbatim quote (≤200 chars) with the section it came from. **No hashes,
    char offsets, URLs, or retrieval timestamps** — those are deterministic
    bookkeeping the orchestrator computes from cached source data after the
    agent emits.

    The orchestrator promotes `EvidenceClaim` → :class:`Evidence` by
    normalizing the source + quote, running a substring check, and (on
    success) computing the hashes + char offset + filling in
    :class:`SourceRef` metadata from the cached HTTP response.
    """

    model_config = ConfigDict(extra="forbid")

    evidence_id: str  # agent-assigned, e.g. "evi_001"; stable cross-reference handle
    claim: str
    claim_type: ClaimType
    direction: Direction
    evidence_type: EvidenceType
    evidence_tier: EvidenceTier
    confidence: EvidenceConfidence
    assay_context: AssayContext
    source_id: str  # "PMID:10601354" | "WO2024036333A2" | "UniProt:Q9UBP8" | "PDB:2ABC"
    quote: str = Field(..., max_length=200)  # verbatim, ≤200 chars
    section: PaperSection_
    figure_or_table_id: str | None = None  # "Figure 3A", "Table S1"


class Evidence(BaseModel):
    """Orchestrator-constructed full Evidence record persisted in the corpus.

    Carries the same classification fields as :class:`EvidenceClaim` plus the
    full provenance chain (:class:`EvidenceSpan` with :class:`SourceRef`
    inside) and validation outcome. ``entailment_verified`` is set ``True``
    only when the substring check passes cleanly; ``validation_warnings``
    surfaces normalization quirks ("matched after Greek-letter
    transliteration") or substring failures so the run summary documents
    what happened without dropping the agent's attempt.
    """

    model_config = ConfigDict(extra="forbid")

    evidence_id: str  # carried from EvidenceClaim; per-bucket cited_evidence_ids resolve here
    claim: str
    claim_type: ClaimType
    direction: Direction
    evidence_type: EvidenceType
    evidence_tier: EvidenceTier  # primary = experimental; secondary = review/db
    confidence: EvidenceConfidence
    assay_context: AssayContext
    # ``spans`` may be empty when ``entailment_verified=False`` — the agent
    # cited a source we couldn't anchor the quote in (or a source we never
    # fetched). Persisting unanchored evidence with the warning preserves the
    # claim for review without lying about the provenance chain. Verified
    # evidence (``entailment_verified=True``) is required to carry ≥1 span,
    # enforced by the model validator below.
    spans: list[EvidenceSpan] = Field(default_factory=list)
    entailment_verified: bool = False  # True iff substring check passed cleanly
    # Result of the opt-in Sonnet claim-entailment audit (set when annotate
    # runs with --audit). ``None`` = not audited; ``True`` = audit passed
    # ((quote, claim, direction) entailed); ``False`` = audit said the quote
    # doesn't support the claim direction. We persist failed audits with the
    # flag and a warning rather than dropping — same persist-with-flags policy
    # as the substring check.
    entailment_audit_passed: bool | None = None
    validation_warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_verified_has_spans(self) -> Evidence:
        if self.entailment_verified and not self.spans:
            raise ValueError(
                "Evidence with entailment_verified=True must carry at least one EvidenceSpan"
            )
        return self


class SearchEntry(BaseModel):
    """One source consultation. The orchestrator builds the search log from
    ``events.jsonl`` after the run; the agent never sees this during the
    session.

    Two purposes:

    1. **Comprehensiveness audit.** Was the shedding literature checked for
       this gene? Grep `search_log` for `topic_search` with the `shedding`
       anchor. If absent, this record is audit-incomplete.
    2. **Re-run efficiency.** When re-annotating under a newer schema, the
       orchestrator can summarize prior searches in the kickoff message so
       the agent doesn't redundantly re-fetch.
    """

    model_config = ConfigDict(extra="forbid")

    tool: str  # "gene_lookup" | "gene_literature" | "patent_lookup"
    mode: str | None = None  # tool-specific mode, e.g. "gene2pubmed"
    query: dict[str, Any] = Field(default_factory=dict)
    n_results: int = 0
    sources_seen: list[str] = Field(default_factory=list)  # source_ids that were touched
    retrieved_at: datetime
    contributed_evidence_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# SurfaceomeRecord — the per-protein reconciled annotation persisted to
# data/annotations/{gene}.json. The agent's job is the *accessibility call*:
# physical surface localization, extracellular-face exposure, and any
# conditional/induced surface presentation. Therapeutic context (approved
# drugs, trials, patents, preclinical characterizations) accompanies the
# call. Modality-agnostic by design — a target reachable by any extracellular
# binder is in scope, regardless of whether the eventual therapeutic is an
# ADC, naked mAb, bispecific, CAR-T, TCR-T, TCR-mimic, radioligand,
# peptide-drug conjugate, oligo-conjugate, etc.
#
# Several enums are intentionally **hybrid** — closed list + ``"other"``
# escape hatch with a required ``*_other_label`` for the agent to describe a
# novel category. This is by design: ``other`` accumulating in the corpus is
# the input to a future ontology-review agent that proposes new categories
# or merges duplicates. ``schema_version`` lets us track which ontology a
# record was made under as we evolve.
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "v0.4.0"


# ---- shared enums (closed) ------------------------------------------------

SurfaceStatus = Literal[
    "strong_surface",
    "moderate_surface",
    "weak_surface",
    "rare_surface",
    "conditional_surface",  # induced/state-dependent surface presentation
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
    "small_molecule",  # any small-molecule agent engaging the protein at an extracellularly-accessed pocket
    "adc",
    "naked_mab",
    "bispecific",
    "car_t",  # CAR-T: antibody-derived ECD-binding receptor; targets full-length surface protein.
    "tcr_t",  # TCR-T: TCR-engineered T cells recognizing pMHC; for MHC-presented peptide antigens.
    "tcr_mimic",  # mAb that recognizes a peptide-MHC complex like a TCR.
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
    "soluble_shedding",  # cleavage/shedding releases a soluble pool of antigen
    "secreted_form",  # alternative isoform/variant generates a secreted form (no shedding required)
    "other",
]
RiskSeverity = Literal["blocking", "high", "medium", "low"]


class RiskFlag(BaseModel):
    """A surface-biology risk flag that affects accessibility / targetability.

    Scope is narrow on purpose: the agent's job is the accessibility call,
    not systematic safety profiling. The two closed kinds capture the
    accessibility-relevant risks that arise directly from surface biology
    (a soluble pool of antigen produced by either shedding or an alternative
    secreted form competes for binders). Anything else uses ``"other"`` with
    a ``kind_other_label`` so the corpus can surface emerging categories.

    Hybrid enum: same pattern as ``ModalityRecommendation``. ``other`` requires
    a ``kind_other_label``.
    """

    model_config = ConfigDict(extra="forbid")

    kind: RiskFlagKind
    kind_other_label: str | None = None
    severity: RiskSeverity
    description: str = Field(..., max_length=500)
    cited_evidence_ids: list[str] = Field(default_factory=list)

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
    cited_evidence_ids: list[str] = Field(default_factory=list)


# ---- bucket: surface biology ----------------------------------------------


ECDAccessibility = Literal["accessible", "membrane_proximal", "buried", "unknown"]


# Single signal answering "is there a binder-targetable extracellular
# protrusion?" — distinct from ``surface_status`` (which says whether the
# protein reaches the outer leaflet at all). A 7TM GPCR with tiny extracellular
# loops is ``minimal_ectoloops`` even though ``surface_status="strong_surface"``.
ExposureClass = Literal[
    "exposed_ecd",  # one or more meaningful extracellular protrusions
    "minimal_ectoloops",  # only short loops between TM helices reach outside
    "embedded_no_ecd",  # essentially no extracellular face protruding from the bilayer
    "none",  # not at the plasma membrane at all
    "unknown",
]


# Why a protein that is intracellular at baseline reaches the outer leaflet.
# Backs ``SurfaceStatus="conditional_surface"`` calls.
InducedContextKind = Literal[
    "cell_state_stress",  # heat shock, ER stress, oxidative stress, etc.
    "immunogenic_cell_death",  # ICD-induced exposure (e.g. calreticulin)
    "infection_induced",  # viral or bacterial infection drives surfacing
    "oncogenic_state",  # transformation-driven mislocalization
    "tissue_subset",  # baseline-intracellular but surface-positive in a specific tissue/cell type
    "trafficking_cycling",  # cycles between intracellular vesicles and PM (low steady-state surface)
    "other",
]


class InducedPresentation(BaseModel):
    """One context under which an otherwise-intracellular protein reaches the surface.

    Used to back ``SurfaceStatus="conditional_surface"`` calls (e.g.
    calreticulin during ICD; HSP70 stress exposure; GLUT4-style trafficking
    cycling). Hybrid enum: ``context_kind="other"`` requires a
    ``context_kind_other_label`` so the corpus can surface new categories.
    """

    model_config = ConfigDict(extra="forbid")

    context_kind: InducedContextKind
    context_kind_other_label: str | None = None
    description: str = Field(..., max_length=400)
    cited_evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_other_label(self) -> InducedPresentation:
        if self.context_kind == "other" and not self.context_kind_other_label:
            raise ValueError(
                "InducedPresentation.context_kind='other' requires context_kind_other_label"
            )
        if self.context_kind != "other" and self.context_kind_other_label is not None:
            raise ValueError(
                "InducedPresentation.context_kind_other_label must be None when "
                f"context_kind={self.context_kind!r}"
            )
        return self


class ExtracellularDomainSummary(BaseModel):
    """Sketch of the extracellular face — what a binder actually sees."""

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
    """The reconciled accessibility call + supporting biology.

    Three orthogonal axes:

    * ``surface_status`` — does the protein reach the outer leaflet at all,
      and if so under what regime? ``conditional_surface`` is reserved for
      proteins intracellular at baseline that reach the surface only under
      defined conditions (see ``induced_presentation``).
    * ``topology`` — physical localization in/around the bilayer. KRAS is
      ``topology=inner_leaflet_peripheral`` and ``surface_status=absent``.
      Conflating these reproduces the SURFY false-positive pattern.
    * ``exposure_class`` — is there a binder-targetable extracellular
      protrusion? A 7TM GPCR with tiny ECLs is ``minimal_ectoloops`` even
      though it's ``surface_status=strong_surface``.

    ``induced_presentation`` carries the context list backing a
    ``conditional_surface`` call (or capturing tissue-subset / trafficking
    nuance even when the headline is ``rare_surface`` or stronger).
    """

    model_config = ConfigDict(extra="forbid")

    surface_status: SurfaceStatus
    topology: Topology
    anchor_type: AnchorType
    exposure_class: ExposureClass = "unknown"
    extracellular_domain: ExtracellularDomainSummary
    induced_presentation: list[InducedPresentation] = Field(default_factory=list)
    # ``bool`` is the canonical "yes/no glycosylated" flag, but for densely-
    # glycosylated targets (HER2's seven N-linked sites, MUC1's tandem-repeat
    # O-glycans) the agent has informative prose to share — N-site positions,
    # ECD-vs-cytoplasmic distribution, antibody-accessibility implications.
    # Accepting ``str`` keeps that signal instead of forcing it into a binary.
    # Downstream readers should treat any non-null value as "glycosylated";
    # the prose form just adds detail.
    glycosylation: bool | str | None = None
    shedding_documented: bool | None = None  # soluble pool present (relevant to any extracellular-binder modality)
    db_comparison: DBComparison
    cited_evidence_ids: list[str] = Field(default_factory=list)


# ---- bucket: therapeutic landscape ---------------------------------------


class ApprovedDrug(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str  # generic + brand if known
    modality: ModalityKind
    modality_other_label: str | None = None
    indication: str
    sponsor: str | None = None
    approval_year: int | None = None
    cited_evidence_ids: list[str] = Field(default_factory=list)

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
    cited_evidence_ids: list[str] = Field(default_factory=list)

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
    summary: str = Field(..., max_length=1000)
    cited_evidence_ids: list[str] = Field(default_factory=list)

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
    """A published preclinical characterization of a binder/agent against this protein.

    Modality-agnostic: small-molecule, naked mAb, ADC, bispecific, CAR-T,
    TCR-T, TCR-mimic, radioligand, peptide-drug conjugate, oligo-conjugate,
    or anything else captured by ``ModalityKind``.
    """

    model_config = ConfigDict(extra="forbid")

    citation: str  # PMID:..., DOI:..., or PMC:...
    modality: ModalityKind
    modality_other_label: str | None = None
    finding_summary: str = Field(..., max_length=1000)
    cited_evidence_ids: list[str] = Field(default_factory=list)

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

    Sparse for novel candidates; rich for proteins with validated targeting
    precedent (approved drugs, active clinical programs, or dense patent
    activity) across any modality.
    """

    model_config = ConfigDict(extra="forbid")

    approved_drugs: list[ApprovedDrug] = Field(default_factory=list)
    clinical_trials: list[ClinicalTrial] = Field(default_factory=list)
    patent_disclosures: list[PatentDisclosure] = Field(default_factory=list)
    preclinical_evidence: list[PreclinicalEvidence] = Field(default_factory=list)


# ---- deep-dive: isoforms, co-receptors, orthology -------------------------


DeepTMHMMLabel = Literal["TM", "SP", "SP+TM", "BETA", "GLOB"]
OrthologSpecies = Literal["mouse", "cynomolgus"]
OrthologyType = Literal[
    "one_to_one",
    "one_to_many",
    "many_to_many",
    "no_ortholog",
    "unknown",
]
CoreceptorRequirementKind = Literal[
    "obligate_heterodimer",  # cannot fold/exit ER without partner (TCRα needs CD3 chains)
    "trafficking_chaperone",  # transient partner required for surface delivery (HLA-I + TAP/tapasin)
    "stabilizing_partner",  # surface half-life depends on partner co-expression
    "complex_assembly",  # the protein only exists on the surface as part of a defined complex
    "other",
]


class IsoformAccessibility(BaseModel):
    """Per-isoform accessibility call.

    Why a list of these alongside the gene-level ``surface_biology``: a single
    gene can have isoforms with divergent localization (one membrane-bound,
    one secreted, one cytoplasmic). The gene-level record reports the
    canonical isoform; this list reports the others when their call differs.
    Emit a single entry for the canonical isoform when isoforms are not
    differential.
    """

    model_config = ConfigDict(extra="forbid")

    isoform_id: str  # UniProt isoform ID, e.g. "P04626-1"
    name: str | None = None
    is_canonical: bool = False
    length_aa: int | None = None

    surface_status: SurfaceStatus | None = None
    exposure_class: ExposureClass = "unknown"

    # Precomputed DeepTMHMM topology (from data/processed/deeptmhmm/deeptmhmm_human_isoforms.tsv).
    # Null when the isoform isn't in the cohort (e.g. wasn't an AFDB-resolved isoform).
    deeptmhmm_label: DeepTMHMMLabel | None = None
    tm_helix_count: int | None = None
    has_signal_peptide: bool | None = None

    # UniProt SUBCELLULAR LOCATION comments tagged "[Isoform N]" matching this isoform.
    # Pulled from UniProtSummary.subcellular_locations where is_isoform_specific=True.
    uniprot_isoform_specific_locations: list[str] = Field(default_factory=list)

    differential_from_canonical: bool = False
    rationale: str = Field(default="", max_length=500)
    cited_evidence_ids: list[str] = Field(default_factory=list)


class CoreceptorRequirement(BaseModel):
    """A partner required for this protein to reach or remain on the cell surface.

    Use only when the partner is *required* for surface delivery / retention,
    not for any constitutive interaction. Common patterns: CD3 chains require
    CD247 (ζ-chain); TCR α/β require the CD3 complex; HLA-I requires TAP +
    tapasin + β2-microglobulin; some heterodimeric receptors require both
    chains (IL-2Rα/β/γ). Source: UniProt SUBUNIT comments + literature.
    """

    model_config = ConfigDict(extra="forbid")

    partner_symbol: str
    partner_uniprot_acc: str | None = None
    requirement_kind: CoreceptorRequirementKind
    requirement_kind_other_label: str | None = None
    description: str = Field(..., max_length=500)
    cited_evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_other_label(self) -> CoreceptorRequirement:
        if self.requirement_kind == "other" and not self.requirement_kind_other_label:
            raise ValueError(
                "CoreceptorRequirement.requirement_kind='other' requires requirement_kind_other_label"
            )
        if self.requirement_kind != "other" and self.requirement_kind_other_label is not None:
            raise ValueError(
                "CoreceptorRequirement.requirement_kind_other_label must be None when "
                f"requirement_kind={self.requirement_kind!r}"
            )
        return self


class OrthologRecord(BaseModel):
    """Mouse or cynomolgus ortholog with surface-localization evidence.

    Cross-species concordance is a sanity check on the human surface call and
    a preclinical-model selector. The precomputed pack provides Ensembl
    Compara identity + DeepTMHMM topology; the agent contributes the
    surface-status interpretation (and any literature evidence) plus the
    concordance call.
    """

    model_config = ConfigDict(extra="forbid")

    species: OrthologSpecies
    ortholog_uniprot_acc: str | None = None
    ortholog_gene_symbol: str | None = None
    ensembl_gene_id: str | None = None
    orthology_type: OrthologyType = "unknown"
    percent_identity: float | None = None

    # Precomputed topology (from data/processed/deeptmhmm/deeptmhmm_{mouse,cyno}_ortholog.tsv).
    deeptmhmm_label: DeepTMHMMLabel | None = None
    tm_helix_count: int | None = None
    has_signal_peptide: bool | None = None

    surface_status: SurfaceStatus | None = None
    # Tri-state: True iff the ortholog's topology + status agrees with the human call,
    # False iff it diverges, None when either side is unknown.
    surface_concordant_with_human: bool | None = None
    notes: str = Field(default="", max_length=500)
    cited_evidence_ids: list[str] = Field(default_factory=list)


# ---- top-level record -----------------------------------------------------


class SurfaceomeRecord(BaseModel):
    """The reconciled per-protein record persisted to data/annotations/{gene}.json.

    Primary purpose: answer "is this protein accessible to extracellular
    therapeutic targeting, and what would you need to know to evaluate it?"
    The headline is the surface-biology / accessibility classification (which
    is the project's core deliverable); therapeutic context fills in the
    metadata a scientist needs alongside the call. Modality-agnostic — any
    extracellular-binder modality is in scope.
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
    therapeutic_landscape: TherapeuticLandscape
    risk_flags: list[RiskFlag] = Field(default_factory=list)

    # Deep-dive: per-isoform accessibility (when isoforms differ),
    # required surface co-receptors, and mouse/cyno ortholog records.
    isoform_accessibility: list[IsoformAccessibility] = Field(default_factory=list)
    coreceptor_requirements: list[CoreceptorRequirement] = Field(default_factory=list)
    orthology: list[OrthologRecord] = Field(default_factory=list)

    # Provenance — centralized Evidence array referenced by per-bucket
    # ``cited_evidence_ids``. Built by the orchestrator from agent-emitted
    # ``EvidenceClaim`` records in :class:`SurfaceomeRecordDraft` after
    # substring validation against cached source bodies.
    evidence: list[Evidence] = Field(default_factory=list)
    primary_evidence_count: int = 0
    secondary_evidence_count: int = 0
    evidence_count: int = 0

    # Search log — orchestrator-built from ``events.jsonl`` post-hoc. Records
    # every source consultation whether it yielded a citation or not, so we
    # can audit comprehensiveness ("did we check shedding lit?") and skip
    # redundant queries on re-annotation.
    search_log: list[SearchEntry] = Field(default_factory=list)

    # Synthesis metadata
    confidence: SynthesisConfidence
    confidence_reasoning: str
    contradiction_flag: bool
    rationale: str = Field(..., max_length=1500)
    model_path: ModelPath


class SurfaceomeRecordDraft(BaseModel):
    """What the AGENT emits as its final JSON.

    Mirrors :class:`SurfaceomeRecord` exactly except it carries
    ``evidence_claims: list[EvidenceClaim]`` (small, agent-shaped) instead of
    ``evidence: list[Evidence]`` (full provenance chain), and omits
    ``search_log`` (orchestrator-built from ``events.jsonl``).

    The orchestrator parses the agent's JSON as ``SurfaceomeRecordDraft``,
    promotes each ``EvidenceClaim`` to ``Evidence`` via the substring +
    normalization pipeline, attaches the ``search_log``, and emits a
    canonical ``SurfaceomeRecord`` for persistence.

    Per-bucket ``cited_evidence_ids`` use the agent-assigned
    ``EvidenceClaim.evidence_id`` strings; those handles carry over to
    the persisted ``Evidence`` records so cross-references remain stable.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION

    # Identity
    gene: GeneIdentifier
    canonical_isoform: str
    isoform_flattened: bool

    # Headline + supporting buckets — same shapes as SurfaceomeRecord
    targetability: TargetabilityVerdict
    surface_biology: SurfaceBiology
    therapeutic_landscape: TherapeuticLandscape
    risk_flags: list[RiskFlag] = Field(default_factory=list)

    # Deep-dive: per-isoform accessibility (when isoforms differ),
    # required surface co-receptors, and mouse/cyno ortholog records.
    isoform_accessibility: list[IsoformAccessibility] = Field(default_factory=list)
    coreceptor_requirements: list[CoreceptorRequirement] = Field(default_factory=list)
    orthology: list[OrthologRecord] = Field(default_factory=list)

    # Agent-emitted EvidenceClaim records — orchestrator promotes to Evidence
    evidence_claims: list[EvidenceClaim] = Field(default_factory=list)
    primary_evidence_count: int = 0
    secondary_evidence_count: int = 0
    evidence_count: int = 0

    # Synthesis metadata
    confidence: SynthesisConfidence
    confidence_reasoning: str
    contradiction_flag: bool
    rationale: str = Field(..., max_length=1500)
    model_path: ModelPath


# ---------------------------------------------------------------------------
# Triage record — lightweight per-protein decision: is this protein surface
# accessible? Pure-model inference (no tools, no web search, no evidence
# emission); the orchestrator records the verdict + a single structured
# reason describing why.
# ---------------------------------------------------------------------------


TRIAGE_SCHEMA_VERSION = "v0.9.0"


TriageVerdict = Literal["yes", "contextual", "no"]
TriageModelPath = Literal["haiku_only", "sonnet_only", "opus_only"]


# Per-verdict reason taxonomies. Each is a closed enum + escape-hatch
# "other" with a required free-text label. The union below is what the
# agent emits in the single ``reason`` field; a model_validator on the
# record enforces that the reason value is in the set allowed for the
# emitted verdict.

YesReason = Literal[
    # Single-pass TM with a substantial extracellular domain
    "classical_surface_receptor",
    # GPI anchor on the outer leaflet. (Almost all bona-fide
    # "outer-leaflet lipidation" cases are GPI; truly non-GPI outer-
    # leaflet lipidations are rare and usually transient.)
    "gpi_anchored",
    # Multi-pass TM (GPCR / transporter / channel) with extracellular
    # loops large enough for a binder to engage
    "multipass_with_exposed_loops",
    # Any other architecture with an explicit extracellular face
    "extracellular_face_protein",
    # Stable non-covalent partner of an anchored surface protein,
    # assembled intracellularly and co-trafficked to the PM as a
    # complex. Examples: β2-microglobulin co-trafficked with MHC-I /
    # CD1 family. The partner protein itself has no TM / GPI /
    # lipidation, but it is stably present on the surface under
    # baseline conditions as part of the complex.
    "stable_complex_partner",
    "other",
]


ContextualReason = Literal[
    # Cell-state translocates an otherwise intracellular protein to the
    # outer leaflet. Includes stress, immunogenic cell death, infection,
    # oncogenic transformation, apoptosis, AND disease-state ecto-forms
    # (e.g. cancer-cell-restricted ecto-Src / ecto-LYN). The unifying
    # feature is "the protein reaches the surface because the cell is
    # in a non-baseline state."
    "cell_state_induced",
    # Surface form exists only in specific tissues / cell types /
    # developmental contexts
    "tissue_restricted_surface",
    # Lysosomal / late-endosomal TM protein reaches PM during lysosomal
    # exocytosis
    "lysosomal_exocytosis",
    # The protein has a documented PM pool alongside a dominant non-PM
    # compartment. Covers both (a) active vesicular trafficking cycling
    # between an intracellular compartment and the PM — secretory
    # recycling (TGN ↔ PM), cargo-receptor cycling (ER ↔ Golgi ↔ PM),
    # regulated non-lysosomal exocytosis, ER-PM junctional clustering;
    # and (b) constitutive partial-PM residence (steady-state across
    # multiple compartments, e.g. plasma-membrane VDAC alongside its
    # dominant mitochondrial-OM pool). The mechanism distinction
    # (vesicular cycling vs steady-state dual home) doesn't change
    # accessibility — both have a minority but stable PM pool.
    "dual_localization",
    # A secreted (or otherwise non-membrane-anchored) protein becomes
    # STABLY anchored to a cell-surface partner post-translationally —
    # either COVALENTLY (disulfide tethering of a latent ligand to a TM
    # partner co-trafficked from the ER as a covalent complex; thioester
    # deposition on cells; transamidase cross-linking) or via
    # WASH-RESISTANT, NON-REVERSIBLE non-covalent association (very
    # strong, stable binding that does NOT stay in equilibrium with the
    # soluble pool). The defining criterion is that the protein remains
    # attached to the cell surface after washing — clinical antibody
    # programs against such surface complexes exist (e.g. livmoniplimab
    # against GARP:latent-TGF-β1).
    #
    # **Excluded — use `secreted_only` instead:** Ca²⁺-dependent
    # reversible binding to membrane lipids (prothrombin/F2 Gla-PS
    # interaction); integrin-mediated ECM tethering (fibronectin/FN1);
    # transient cytokine-receptor binding equilibria; any non-covalent
    # interaction that washes off.
    #
    # **ECM / matrix is also NOT cell surface.** Covalent attachment to
    # extracellular matrix (transamidase-cross-linked secreted proteins
    # deposited into tumor stroma, latent TGF-β bound to LTBP-ECM,
    # complement fragments deposited on connective tissue) does not
    # count — those are matrix-anchored, not cell-surface anchored.
    # Use `no` / `secreted_only` for matrix-deposited covalent products.
    "stable_surface_attachment",
    "other",
]


NoReason = Literal[
    # Soluble cytoplasmic, no membrane association
    "cytoplasmic",
    # Nuclear-resident (chromatin-bound, nucleolar, nucleoplasmic)
    "nuclear",
    # Mitochondrial matrix or inner-membrane facing matrix
    "mitochondrial_internal",
    # ER, Golgi, lysosomal, peroxisomal, or autophagosomal membrane only;
    # no documented PM access
    "endomembrane_resident",
    # Inner / outer nuclear membrane only
    "nuclear_envelope",
    # Lipidated or peripheral on the cytoplasmic face of the PM
    # (wrong-side; membrane-associated but not extracellular)
    "inner_leaflet_anchored",
    # Secreted with no stable surface anchoring. INCLUDES transient
    # non-covalent recruitment to surface receptors or ECM
    # (recruiting partner is the surface target, not the recruited
    # protein). Direct outer-leaflet *lipid* binding and covalent
    # post-translational attachment are NOT recruitment — use yes /
    # contextual reasons instead.
    "secreted_only",
    # The protein body is strictly intracellular; the only "surface"
    # story is that proteolytic peptides derived from it are MHC-
    # presented. pMHC presentation is NOT credited for surface
    # accessibility in this triage — every intracellular protein has
    # potentially MHC-presentable peptides, so pMHC is not a
    # discriminating signal. Downstream TCR / TCR-mimic / bispecific
    # programs are handled as a separate axis from surface accessibility.
    "pmhc_only_intracellular",
    "other",
]


# Union for the on-the-wire ``reason`` field. Pydantic will accept any
# value here; the model_validator below cross-checks against verdict.
TriageReason = Literal[
    "classical_surface_receptor",
    "gpi_anchored",
    "multipass_with_exposed_loops",
    "extracellular_face_protein",
    "stable_complex_partner",
    "cell_state_induced",
    "tissue_restricted_surface",
    "lysosomal_exocytosis",
    "dual_localization",
    "stable_surface_attachment",
    "cytoplasmic",
    "nuclear",
    "mitochondrial_internal",
    "endomembrane_resident",
    "nuclear_envelope",
    "inner_leaflet_anchored",
    "secreted_only",
    "pmhc_only_intracellular",
    "other",
]


_YES_REASONS: frozenset[str] = frozenset(
    {
        "classical_surface_receptor",
        "gpi_anchored",
        "multipass_with_exposed_loops",
        "extracellular_face_protein",
        "stable_complex_partner",
        "other",
    }
)
_CONTEXTUAL_REASONS: frozenset[str] = frozenset(
    {
        "cell_state_induced",
        "tissue_restricted_surface",
        "lysosomal_exocytosis",
        "dual_localization",
        "stable_surface_attachment",
        "other",
    }
)
_NO_REASONS: frozenset[str] = frozenset(
    {
        "cytoplasmic",
        "nuclear",
        "mitochondrial_internal",
        "endomembrane_resident",
        "nuclear_envelope",
        "inner_leaflet_anchored",
        "secreted_only",
        "pmhc_only_intracellular",
        "other",
    }
)
_REASONS_BY_VERDICT: dict[str, frozenset[str]] = {
    "yes": _YES_REASONS,
    "contextual": _CONTEXTUAL_REASONS,
    "no": _NO_REASONS,
}


class TriageRecordDraft(BaseModel):
    """What the AGENT emits for triage — small, self-contained.

    Pure-model inference. The agent has no tools, no web search, and emits
    no evidence quotes. Just a verdict (``yes`` / ``contextual`` / ``no``),
    a short prose reasoning, and a single structured ``reason`` enum
    explaining the verdict.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = TRIAGE_SCHEMA_VERSION
    gene: GeneIdentifier
    verdict: TriageVerdict
    verdict_reasoning: str = Field(..., max_length=600)
    reason: TriageReason
    model_path: TriageModelPath = "haiku_only"

    @model_validator(mode="after")
    def _check_reason_matches_verdict(self) -> TriageRecordDraft:
        allowed = _REASONS_BY_VERDICT[self.verdict]
        if self.reason not in allowed:
            raise ValueError(
                f"reason={self.reason!r} is not valid for verdict={self.verdict!r}; "
                f"allowed reasons are {sorted(allowed)}"
            )
        return self


class TriageRecord(BaseModel):
    """The reconciled per-protein triage decision persisted to data/triage/{gene}.json.

    Same shape as :class:`TriageRecordDraft` plus the orchestrator-built
    search_log (typically empty since the triage agent has no tools).
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = TRIAGE_SCHEMA_VERSION
    gene: GeneIdentifier
    verdict: TriageVerdict
    verdict_reasoning: str = Field(..., max_length=600)
    reason: TriageReason
    search_log: list[SearchEntry] = Field(default_factory=list)
    model_path: TriageModelPath = "haiku_only"

    @model_validator(mode="after")
    def _check_reason_matches_verdict(self) -> TriageRecord:
        allowed = _REASONS_BY_VERDICT[self.verdict]
        if self.reason not in allowed:
            raise ValueError(
                f"reason={self.reason!r} is not valid for verdict={self.verdict!r}; "
                f"allowed reasons are {sorted(allowed)}"
            )
        return self


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
    "SearchEntry",
    "EvidenceClaim",
    # SurfaceomeRecord + buckets
    "SCHEMA_VERSION",
    "SurfaceomeRecord",
    "SurfaceomeRecordDraft",
    "TargetabilityVerdict",
    "TargetabilityTier",
    "ModalityKind",
    "ModalityRecommendation",
    "SurfaceBiology",
    "AnchorType",
    "ExposureClass",
    "InducedContextKind",
    "InducedPresentation",
    "ExtracellularDomainSummary",
    "ECDAccessibility",
    "DBComparison",
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
    # Deep-dive
    "IsoformAccessibility",
    "CoreceptorRequirement",
    "CoreceptorRequirementKind",
    "OrthologRecord",
    "OrthologSpecies",
    "OrthologyType",
    "DeepTMHMMLabel",
    # TriageRecord
    "TRIAGE_SCHEMA_VERSION",
    "TriageRecord",
    "TriageRecordDraft",
    "TriageVerdict",
    "TriageModelPath",
    "TriageReason",
    "YesReason",
    "ContextualReason",
    "NoReason",
]
