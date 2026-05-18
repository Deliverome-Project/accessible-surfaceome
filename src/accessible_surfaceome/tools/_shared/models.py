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

import logging
from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

logger = logging.getLogger(__name__)


def _warn_prose_overshoot(instance: BaseModel, targets: dict[str, int]) -> None:
    """Log a warning per prose field that exceeds its soft target.

    Used by per-class ``model_validator(mode="after")`` hooks to keep the
    "aim for ≤N chars" signal alive *without* dropping the agent's
    submission. LLMs don't count characters reliably and a 20-30%
    overshoot on a content-rich gene is not worth discarding a $1.40
    annotation; we log it so the audit step can find it. Empty / ``None``
    values are skipped.
    """

    for field, target in targets.items():
        value = getattr(instance, field, None)
        if not value:
            continue
        n = len(value)
        if n > target:
            logger.warning(
                "soft-target overshoot on %s.%s: len=%d, target=%d (over by %d chars, %.0f%%)",
                type(instance).__name__,
                field,
                n,
                target,
                n - target,
                100.0 * (n - target) / target,
            )

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

    ``target_mention_excerpts`` is populated for the high-throughput
    ``evidence_retrieval`` categories (``mass_spec_surfaceome``,
    ``surface_biotinylation``, ``western_blot_paired``). Each entry is a
    ≤200-char verbatim sentence from the paper body where the target gene
    is named. The agent can quote one of these *in addition to* a
    methodology snippet to anchor a paper-level claim like "PMC X
    performed [method] and identified [target] in [context]". For
    antibody assays and other strict-filter categories the field stays
    empty — target-naming sentences are already covered by the
    hallmark+target snippets in those categories.
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
    # Which layer of the full-text fallback chain produced ``sections``.
    # ``"europepmc"`` — EuropePMC's fullTextXML endpoint (preferred path).
    # ``"ncbi"`` — NCBI E-utilities efetch (used when EuropePMC 404s or
    #   otherwise refuses the article; same JATS schema).
    # ``"abstract_only"`` — both fulltext sources failed; ``sections`` is
    #   empty and the caller should treat the abstract as the body.
    # ``None`` — the paper was produced by a path that didn't attempt a
    #   fulltext fetch (e.g. ``gene2pubmed`` / ``topic_search`` listings,
    #   ``fetch_abstract`` mode).
    fulltext_fetch_source: Literal["europepmc", "ncbi", "abstract_only"] | None = None
    target_mention_excerpts: list[str] = Field(default_factory=list)
    # Pre-extracted verbatim-anchored EvidenceClaimDraft skeletons from the
    # paper's abstract (and full-text sections when ``fetch_fulltext`` was
    # used). Mirrors what ``evidence_retrieval`` provides for the category-
    # bounded path — the (quote, source_id, section) triple is locked by
    # the tool so the agent can copy-paste anchors verbatim and the
    # substring check at promotion passes by construction. Empty for
    # ``gene2pubmed`` / ``topic_search`` listings, which don't fetch
    # bodies. Populated by ``gene_literature.fetch_abstract`` and
    # ``gene_literature.fetch_fulltext`` (and any caller that builds a
    # Paper with body text).
    evidence_claim_drafts: list["EvidenceClaimDraft"] = Field(default_factory=list)


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
# evidence_retrieval return shapes
# ---------------------------------------------------------------------------


# One first-class retrieval slot per assay category. The agent calls
# ``evidence_retrieval`` once per category it wants to ground a claim
# on; empty returns are still recorded in the search_log so reviewers
# can distinguish "absent" from "not retrieved".
EvidenceCategory = Literal[
    "ihc",
    "if_intact",
    "flow_cytometry",
    "surface_biotinylation",
    "mass_spec_surfaceome",
    "western_blot_paired",
    "structure_with_ecd",
    "hpa_ihc",
]


class CandidateSnippet(BaseModel):
    """One candidate verbatim fragment ready to drop into ``EvidenceClaim.quote``.

    The text is ≤200 chars and copied verbatim from the cached source body,
    so the orchestrator's substring check passes when the agent pastes it
    back into a claim. ``hallmark_phrase`` is the regex tag that fired and
    is included for audit, not for the agent to act on.

    ``context_excerpt`` is the broader surrounding context in the same
    section (≤1500 chars), verbatim. The agent reads this to *understand*
    what the snippet says — useful when a methodology description spans
    multiple sentences ("Cells were biotinylated… Eluted material was
    analyzed by LC-MS/MS… CD81 was identified in the enriched fraction").
    The agent must still copy ``text`` (not ``context_excerpt``) into the
    claim's ``quote`` field.
    """

    model_config = ConfigDict(extra="forbid")

    source_id: str  # "PMID:..." | "PMC:..." | "HPA:<symbol>"
    section: PaperSection_
    figure_or_table_id: str | None = None
    text: str = Field(..., max_length=600)
    score: float
    hallmark_phrase: str
    context_excerpt: str | None = Field(default=None, max_length=1500)


class EvidenceClaimDraft(BaseModel):
    """Pre-built ``EvidenceClaim`` skeleton emitted by ``evidence_retrieval``.

    The tool fills the load-bearing anchor fields (``quote``, ``source_id``,
    ``section``, ``figure_or_table_id``) directly from a CandidateSnippet so
    that the (quote, source_id) pair the orchestrator substring-checks at
    promotion time is locked together by construction — the agent cannot
    paraphrase the quote, and cannot mis-attribute it to a different
    source. The agent's remaining job is to fill the narrative fields
    (``claim`` text, ``claim_type``, ``evidence_type``, ``direction``,
    ``evidence_tier``, ``confidence``, ``assay_context``) and decide
    whether to keep this draft at all.

    ``suggested_evidence_id`` is a deterministic, paper-keyed handle the
    agent may adopt as ``EvidenceClaim.evidence_id`` (or replace with a
    sequential ``a1_evi_NN`` — either works downstream).

    ``context_excerpt`` carries the broader surrounding context from the
    same section for the agent's understanding (≤1500 chars). Do NOT copy
    ``context_excerpt`` into the claim's ``quote`` — ``quote`` is the
    substring-anchored field.

    Drafts are emitted for every snippet returned by ``evidence_retrieval``
    (hallmark snippets + target-mention snippets for high-throughput
    categories), so the agent can choose by score / hallmark_phrase
    without bouncing between two parallel lists.
    """

    model_config = ConfigDict(extra="forbid")

    suggested_evidence_id: str
    quote: str = Field(..., max_length=600)
    source_id: str
    section: PaperSection_
    figure_or_table_id: str | None = None
    context_excerpt: str | None = Field(default=None, max_length=1500)
    hallmark_phrase: str
    score: float


class SyntheticSource(BaseModel):
    """A source body the tool synthesized (e.g. from a local TSV) rather
    than fetched as a paper. Registered with the orchestrator's
    ``SourceTextStore`` so quote substring validation works the same way
    as for PMC papers. ``HPA:<symbol>`` is the current canonical example.
    """

    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_type: SourceType
    url: str
    title: str | None = None
    raw_text: str


class EvidenceRetrievalPack(BaseModel):
    """Return shape of ``evidence_retrieval``.

    One call → one ``(uniprot_acc, category)`` pair → up to N candidate
    snippets across up to M papers. ``empty_reason`` is set when no
    snippets came out; the agent should still pass through (the search
    log records the consultation) and try other categories.

    ``synthetic_sources`` carries source bodies the tool fabricated from
    local data (HPA snapshot, etc.) so the orchestrator can register
    them in its ``SourceTextStore`` alongside the papers. Agent-facing
    consumers can ignore this field; it's plumbing.
    """

    model_config = ConfigDict(extra="forbid")

    uniprot_acc: str
    category: EvidenceCategory
    n_papers_searched: int = 0
    n_papers_with_snippets: int = 0
    papers: list[Paper] = Field(default_factory=list)
    snippets: list[CandidateSnippet] = Field(default_factory=list)
    evidence_claim_drafts: list[EvidenceClaimDraft] = Field(default_factory=list)
    synthetic_sources: list[SyntheticSource] = Field(default_factory=list)
    empty_reason: str | None = None


# ---------------------------------------------------------------------------
# PubTator3 search return shapes
# ---------------------------------------------------------------------------


class PubTatorHit(BaseModel):
    """One paper from a PubTator3 entity-anchored search.

    PubTator's value over keyword search is *subject grounding*: a hit
    means PubTator's NER tagged the queried gene as an entity in the
    paper, not merely that the gene's name appears somewhere in the
    indexed metadata. ``score`` is PubTator's own relevance score
    (higher = more on-topic); hits arrive pre-sorted by it.

    PubTator does not return abstracts or open-access status — those are
    filled in downstream by resolving the PMID against Europe PMC.
    """

    model_config = ConfigDict(extra="forbid")

    pmid: int
    pmcid: str | None = None
    doi: str | None = None
    title: str
    journal: str | None = None
    year: int | None = None
    score: float = 0.0
    authors: list[str] = Field(default_factory=list)


class PubTatorSearchResult(BaseModel):
    """Return shape of one PubTator3 entity-anchored search request."""

    model_config = ConfigDict(extra="forbid")

    query: str
    total_count: int = 0
    page: int = 1
    hits: list[PubTatorHit] = Field(default_factory=list)


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
    "hpa_ihc",
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
    quote: str = Field(..., max_length=600)  # ≤600 chars, ALWAYS verbatim (up to ~3 sentences)
    quote_sha256: str  # tamper-detection
    char_offset: int  # position in source; REQUIRED, no None
    normalized_source_sha256: str  # hash of normalized form used for substring check


Species = Literal["human", "mouse", "rat", "macaque", "dog", "other", "unspecified"]


# v0.5.0: structured cell-type / tissue annotation. Backwards-compatible
# companion to the free-text ``cell_type_or_line`` carried on
# :class:`AssayContext` and :class:`SurfaceLocalizationAssay`. Old records
# emit only the free-text field; new records SHOULD populate this when the
# cell-type identity is load-bearing (apical vs basolateral surface,
# primary cell vs cell line, activation state, etc.).
CellMaterialKind = Literal[
    "primary_cell",
    "cell_line",
    "ipsc_derived",
    "primary_tissue",
    "organoid",
    "xenograft",
    "unspecified",
    "other",
]


class CellTypeContext(BaseModel):
    """Structured cell-type / tissue identity for an assay observation.

    Hybrid enum: ``material_kind="other"`` requires a
    ``material_kind_other_label``. All other fields are nullable; the model
    captures whatever the source paper specified without forcing the agent
    to invent details. Loadable on :class:`AssayContext`,
    :class:`SurfaceLocalizationAssay`, and :class:`InducedPresentation`.
    """

    model_config = ConfigDict(extra="forbid")

    material_kind: CellMaterialKind
    material_kind_other_label: str | None = Field(default=None, max_length=80)
    cell_type: str | None = Field(default=None, max_length=200)
    cell_line_name: str | None = Field(default=None, max_length=120)
    cellosaurus_id: str | None = Field(default=None, max_length=40)
    tissue: str | None = Field(default=None, max_length=120)
    disease_state: str | None = Field(default=None, max_length=200)
    activation_state: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _check_other_label(self) -> CellTypeContext:
        if self.material_kind == "other" and not self.material_kind_other_label:
            raise ValueError(
                "CellTypeContext.material_kind='other' requires material_kind_other_label"
            )
        if self.material_kind != "other" and self.material_kind_other_label is not None:
            raise ValueError(
                "CellTypeContext.material_kind_other_label must be None when "
                f"material_kind={self.material_kind!r}"
            )
        return self


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
    # v0.5.0: structured supplement to ``cell_type_or_line``. Optional; old
    # records populate only the free-text field and remain valid.
    cell_context: CellTypeContext | None = None


ClaimType = Literal[
    "surface_expression",
    "topology",
    "tissue_expression",
    "methodological",
    "contradictory",
]
Direction = Literal["supports", "refutes", "ambiguous"]
EvidenceType = Literal[
    # ---- Surface-protein assays ----
    "flow_cytometry",
    "surface_biotinylation",
    "mass_spec_surfaceome",
    "immunohistochemistry",
    "immunofluorescence",
    # ``western_blot`` is only valid surface evidence when paired with a
    # fractionation / biotinylation step from the same source — a WB on
    # whole-cell lysate doesn't distinguish surface from intracellular pool.
    # The pairing is enforced by ``SurfaceomeRecordDraft._check_wb_pairing``.
    "western_blot",
    # ---- Structural ----
    "crystal_structure",
    "cryo_em",
    "computational_prediction",
    "orthology",
    # ---- RNA / transcript-level techniques (added 2026-05-16 for A2 accuracy).
    # These do NOT establish surface accessibility on their own; downstream
    # block builders should route them to ``non_surface_expression`` rows
    # with ``measurement_type=RNA`` or ``single_cell_RNA`` as appropriate.
    "rt_qpcr",
    "rna_seq",
    "single_cell_rna_seq",
    "in_situ_hybridization",
    "northern_blot",
    "microarray",
    # ---- Functional / signaling readouts ----
    # Calcium imaging, insulin / hormone secretion ELISA, electrophysiology,
    # receptor-activation reporter assays. Do not establish surface
    # localization on their own but corroborate functional engagement when
    # paired with a direct surface assay from the same source.
    "functional_assay",
    # ---- Human / mouse genetics ----
    # Akbari-class large-cohort exome / GWAS associations and KO / CRISPR
    # phenotype readouts. ``genetic_association`` is for population-genetics
    # associations; ``loss_of_function_phenotype`` is for mouse / cellular
    # KO phenotype data. Both go to ``tissue_expression`` or
    # ``contradictory`` claim_type rollups at the EvidenceClaim layer.
    "genetic_association",
    "loss_of_function_phenotype",
    # ---- Aggregation ----
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
    quote: str = Field(..., max_length=600)  # verbatim, ≤600 chars (up to ~3 sentences)
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

SCHEMA_VERSION = "1.0.0"


# ===========================================================================
# SurfaceomeRecord v1.0.0 — surface-accessibility deep-dive record.
#
# Two structurally separated regions:
#   * ``deterministic_features`` — verbatim tool output, populated by the
#     orchestrator. The agent never writes here; a validator on
#     :class:`SurfaceomeRecordDraft` rejects any attempt to populate it.
#   * the LLM-synthesis blocks (``executive_summary``, ``surface_evidence``,
#     ``biological_context``, ``accessibility_risks``, ``filters``) — the
#     agent's work.
# Evidence + search log live at the top level and are referenced from both.
# Field order mirrors the viewer mockup so JSON-reading humans see the same
# scientific flow.
#
# Several enums are intentionally **hybrid** — a closed list plus an
# ``"other"`` escape hatch with a required ``*_other_label`` and a validator
# enforcing ``category == "other" ↔ label is not None``.
# ===========================================================================


# ---- closed enums ---------------------------------------------------------

TriageSignal = Literal[
    "likely_accessible",
    "possibly_accessible",
    "unlikely",
    "unknown",
]

SurfaceAccessibility = Literal["high", "moderate", "low", "uncertain"]
EvidenceGrade = Literal[
    "direct_multi_method",
    "direct_single_method",
    "supportive_but_indirect",
    "conflicting",
    "weak",
]
Confidence = Literal["high", "moderate", "low"]
StateDependence = Literal["low", "moderate", "high", "unclear"]
Subcategory = Literal[
    "single_pass_T1",
    "single_pass_T2",
    "multi_pass",
    "GPCR",
    "GPI_anchored",
    "tetraspanin",
    "ion_channel",
    "transporter",
    "other",
]
HeadlineRisk = Literal[
    "shed_form",
    "secreted_form",
    "co_receptor",
    "ecd_too_small",
    "epitope_masked",
    "isoform_decoy",
    "restricted_subdomain",
    "low_endogenous_expression",
    "antibody_validation_weak",
    "ligand_unknown",
    "other",
]

ExpressionLevel = Literal["high", "moderate", "low", "absent"]
ExpressionBreadth = Literal["pan_tissue", "broad", "restricted", "rare"]
SurfaceSpecificity = Literal["surface_dominant", "mixed", "mostly_intracellular"]
EvidenceDensity = Literal["low", "moderate", "high"]
ECDAccessibilityClass = Literal["large", "moderate", "small", "minimal", "none"]

MethodFamily = Literal[
    "flow_cytometry",
    "immunofluorescence",
    "immunohistochemistry",
    "mass_spec",
    "biotinylation",
    "glycoproteomics",
    "proximity_labeling",
    "fractionation",
    "other",
]
MethodSubclass = Literal[
    "live_cell_flow",
    "fixed_cell_flow",
    "nonpermeabilized_IF",
    "permeabilized_IF",
    "IHC_membranous",
    "surface_biotinylation",
    "cell_surface_capture",
    "N_glycoproteomics",
    "plasma_membrane_fractionation",
    "whole_cell_proteomics",
    "unknown",
]
Permeabilization = Literal[
    "live_cell",
    "nonpermeabilized",
    "permeabilized",
    "fixed_unknown",
    "unknown",
]
ExpressionSystem = Literal[
    "endogenous",
    "overexpression",
    "knock_in_tag",
    "mixed",
    "unknown",
]
AccessibilityRelevance = Literal[
    "direct_surface_accessibility",
    "supports_surface_localization",
    "supports_membrane_association",
    "expression_only",
    "weak_or_ambiguous",
]
SurfaceClaimType = Literal[
    "surface_accessible",
    "plasma_membrane_localized",
    "membrane_fraction_enriched",
    "cell_junction_localized",
    "apical_or_luminal",
    "secreted_or_shed",
    "intracellular_pool",
    "unclear",
]
AntibodyClonality = Literal["monoclonal", "polyclonal", "recombinant", "unknown"]
AntibodyEpitopeRegion = Literal[
    "extracellular",
    "intracellular",
    "conformational",
    "isoform_specific",
    "unknown",
]
ValidationStrategy = Literal[
    "genetic_KO",
    "siRNA_knockdown",
    "CRISPR_KO",
    "orthogonal_method",
    "ip_ms_pulldown",
    "isoform_specific_KO",
    "overexpression_reference",
    "vendor_claim_only",
    "none",
    "unknown",
]
ValidationStrength = Literal["strong", "moderate", "weak", "none", "unknown"]
SampleType = Literal[
    "primary_human_tissue",
    "primary_human_cell",
    "patient_sample",
    "patient_derived_organoid",
    "iPSC_derived",
    "established_cell_line",
    "xenograft",
    "ex_vivo",
    "unknown",
]
MeasurementType = Literal[
    "RNA",
    "bulk_protein",
    "IHC_protein",
    "single_cell_RNA",
    "unknown",
]
TherapeuticStage = Literal[
    "approved_drug",
    "in_clinical_trials",
    "preclinical_in_vivo",
    "none_documented",
    "unknown",
]
ContradictionType = Literal[
    "intracellular_pool",
    "alternative_localization",
    "secreted_only",
    "cell_line_specific_absence",
    "antibody_conflict",
    "proteomics_conflict",
    "isoform_conflict",
    "other",
]
ContradictionSeverity = Literal["high", "moderate", "low", "unclear"]

TissuePresence = Literal["high", "moderate", "low", "absent", "mixed", "unknown"]
DiseaseContext = Literal[
    "normal",
    "tumor",
    "tumor_adjacent",
    "other_disease",
    "mixed",
    "unknown",
]
PrimaryCompartment = Literal[
    "plasma_membrane",
    "endosome",
    "lysosome",
    "ER",
    "Golgi",
    "mitochondrion",
    "nucleus",
    "cytosol",
    "secreted",
    "other",
]
Orientation = Literal[
    "blood_interstitial_facing",
    "luminal_facing",
    "apical",
    "basolateral",
    "lateral",
    "junction_restricted",
    "ciliary",
    "synaptic",
    "matrix_facing",
    "unknown",
]
AccessibilityImplication = Literal[
    "favorable",
    "restricted",
    "context_dependent",
    "unclear",
]
ModulationCategory = Literal[
    # First five are VERBATIM from surface_triage's contextual `reason`
    # taxonomy so cross-agent vocabulary stays in sync.
    "cell_state_induced",
    "tissue_restricted_surface",
    "lysosomal_exocytosis",
    "dual_localization",
    "stable_surface_attachment",
    # Deep-dive expansions — roll up to the broader triage category at
    # cross-validation time.
    "activation_induced",
    "stress_induced",
    "disease_state_induced",
    "polarization_dependent",
    "post_translational_dependent",
    "developmental_stage",
    "none",
    "other",
    "unknown",
]
CellStateTrigger = Literal[
    "ER_stress",
    "heat_shock",
    "oxidative_stress",
    "DNA_damage_response",
    "apoptosis",
    "necroptosis",
    "oncogenic_transformation",
    "infection_viral",
    "infection_bacterial",
    "immune_activation",
    "antigen_stimulation",
    "cytokine_stimulation",
    "hypoxia",
    "nutrient_deprivation",
    "hyperthermia",
    "mechanical_stress",
    "other",
    "unknown",
]
RestrictedLineage = Literal[
    "germline_reproductive",
    "embryonic_developmental",
    "hematopoietic",
    "neural",
    "epithelial",
    "endothelial",
    "muscle",
    "endocrine",
    "specialized_somatic_other",
    "other",
    "unknown",
]
DualLocPartnerCompartment = Literal[
    "ER",
    "Golgi",
    "endosome",
    "lysosome",
    "mitochondrion",
    "nucleus",
    "cytosol",
    "secretory_vesicle",
    "other",
    "unknown",
]

# accessibility_modulation category-conditional pairings (validator support).
_STATE_INDUCED_CATEGORIES: frozenset[str] = frozenset(
    {
        "cell_state_induced",
        "stress_induced",
        "activation_induced",
        "disease_state_induced",
        "lysosomal_exocytosis",
    }
)

TerminalOrientation = Literal["extracellular", "cytoplasmic"]
OrthologyType = Literal["one2one", "one2many", "many2many"]
AFDBVersion = Literal["v4"]

RiskSeverity = Literal["high", "moderate", "low", "unknown"]
EvidenceStrength = Literal["strong", "moderate", "weak", "inferred"]
RestrictedSubdomainName = Literal[
    "apical",
    "junctional",
    "ciliary",
    "synaptic",
    "raft",
    "basolateral",
    "other",
    "unknown",
]
CoreceptorDependency = Literal["required", "modulatory", "none", "unknown"]
CoreceptorEvidenceBasis = Literal[
    "co_expression_only",
    "trafficking",
    "knockout",
    "mixed",
]
SecretedFormSource = Literal["alternative_splicing", "proteolytic", "both", "unknown"]
EpitopeMaskingMechanism = Literal[
    "glycan",
    "partner",
    "conformational",
    "cleaved",
    "none",
]
EpitopeMaskingSeverity = Literal["high", "moderate", "low", "none"]


# ---- executive summary ----------------------------------------------------


class ExecutiveSummary(BaseModel):
    """LLM-emitted top-line synthesis — the consultant-readable headline."""

    model_config = ConfigDict(extra="forbid")

    one_paragraph: str = Field(
        ...,
        description="Consultant-readable headline. Soft target ≤600 chars (overshoots are warned but accepted).",
    )
    surface_accessibility: SurfaceAccessibility
    evidence_grade_summary: EvidenceGrade
    confidence: Confidence
    state_dependence: StateDependence
    subcategory: Subcategory
    headline_risks: list[HeadlineRisk] = Field(default_factory=list, max_length=3)
    cited_evidence_ids: list[str] = Field(default_factory=list)

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {"one_paragraph": 600}

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> "ExecutiveSummary":
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self


# ---- filters --------------------------------------------------------------


class Filters(BaseModel):
    """Flat, closed-enum/bool/list rollups of the deep buckets.

    Top-level so every field is a D1-indexed column on ``deep_dive_run``;
    the catalog page renders one chip per field. Most fields are
    orchestrator-derived from deeper blocks; three (``expression_level``,
    ``expression_breadth``, ``surface_specificity``) are LLM-emitted rollups
    that live ONLY here (no duplication in the deep blocks).
    """

    model_config = ConfigDict(extra="forbid")

    surface_accessibility: SurfaceAccessibility
    confidence: Confidence
    subcategory: Subcategory
    evidence_grade: EvidenceGrade
    ecd_accessibility_class: ECDAccessibilityClass
    evidence_density: EvidenceDensity
    expression_level: ExpressionLevel
    expression_breadth: ExpressionBreadth
    surface_specificity: SurfaceSpecificity
    has_shed_form: bool
    has_secreted_form: bool
    requires_coreceptor_for_expression: bool
    max_paralog_ecd_pct_identity: float | None = Field(default=None, ge=0.0, le=100.0)
    has_epitope_masking: bool
    has_restricted_subdomain: bool
    mouse_ortholog_ecd_pct_identity: float | None = Field(default=None, ge=0.0, le=100.0)
    cyno_ortholog_ecd_pct_identity: float | None = Field(default=None, ge=0.0, le=100.0)
    n_term_extracellular: bool
    c_term_extracellular: bool


# ---- surface evidence (section 1) -----------------------------------------


class AntibodyRef(BaseModel):
    """One antibody reagent used in a :class:`MethodObservation`.

    Antibody specificity is load-bearing for surface evidence — a "positive"
    flow signal from an antibody that cross-reacts with a paralog is a false
    positive that's nearly invisible without these fields. ``validation_strategy``
    is the gold-standard evidence; ``validation_strength`` is the LLM's
    rolled-up judgment after weighing the strategy + cross-reactivity caveats.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    clone: str | None = None
    vendor: str | None = None
    catalog: str | None = None
    rrid: str | None = None
    monoclonal_or_polyclonal: AntibodyClonality
    antibody_epitope_region: AntibodyEpitopeRegion
    validation_strategy: ValidationStrategy
    validation_strength: ValidationStrength
    cross_reactivity_notes: str | None = Field(
        default=None,
        description="Cross-reactivity notes. Soft target ≤200 chars (overshoots warned but accepted).",
    )

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {"cross_reactivity_notes": 200}

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> "AntibodyRef":
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self


class ExpressionObservation(BaseModel):
    """One expression-level observation anchored to a surface-evidence method."""

    model_config = ConfigDict(extra="forbid")

    context: str
    sample_type: SampleType
    level: ExpressionLevel
    cited_evidence_ids: list[str] = Field(default_factory=list)


class MethodObservation(BaseModel):
    """One surface-evidence method panel: how the surface claim was measured."""

    model_config = ConfigDict(extra="forbid")

    method_family: MethodFamily
    method_subclass: MethodSubclass
    permeabilization: Permeabilization
    expression_system: ExpressionSystem
    antibodies: list[AntibodyRef] = Field(default_factory=list)
    accessibility_relevance: AccessibilityRelevance
    surface_claim_type: SurfaceClaimType
    expression_observations: list[ExpressionObservation] = Field(default_factory=list)
    cited_evidence_ids: list[str] = Field(default_factory=list)


class NonSurfaceExpression(BaseModel):
    """RNA / IHC / bulk-protein levels NOT tied to a surface-evidence panel.

    Held separately so the report can't drift into treating RNA expression as
    surface accessibility.
    """

    model_config = ConfigDict(extra="forbid")

    context: str
    sample_type: SampleType
    measurement_type: MeasurementType
    level: ExpressionLevel
    cited_evidence_ids: list[str] = Field(default_factory=list)


class TherapeuticEngagementContext(BaseModel):
    """Lightweight signal that a therapeutic has reached this protein at the
    cell surface — NOT a comprehensive therapeutic-landscape assessment.

    ``surface_form_rationale`` is required and load-bearing for proteins with
    both surface and secreted forms (GRP78, EGFR, etc.) — it clarifies which
    form the drug actually engages.
    """

    model_config = ConfigDict(extra="forbid")

    highest_stage: TherapeuticStage
    description: str = Field(
        ...,
        description="Therapeutic engagement description. Soft target ≤600 chars (overshoots warned but accepted).",
    )
    surface_form_rationale: str = Field(
        ...,
        description="Which form the drug engages (surface vs. secreted). Soft target ≤400 chars (overshoots warned but accepted).",
    )
    cited_evidence_ids: list[str] = Field(default_factory=list)

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {
        "description": 600,
        "surface_form_rationale": 400,
    }

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> "TherapeuticEngagementContext":
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self


class Contradiction(BaseModel):
    """One piece of contradicting evidence + the LLM's read on whether it
    matters for surface accessibility."""

    model_config = ConfigDict(extra="forbid")

    claim: str
    contradiction_type: ContradictionType
    severity_for_surface_accessibility: ContradictionSeverity
    likely_explanation: str | None = None
    cited_evidence_ids: list[str] = Field(default_factory=list)


class SurfaceEvidence(BaseModel):
    """Section 1 — the surface-accessibility evidence the agent assembled."""

    model_config = ConfigDict(extra="forbid")

    evidence_grade: EvidenceGrade
    grade_rationale: str = Field(
        ...,
        description="Why this evidence_grade. Soft target ≤800 chars (overshoots warned but accepted).",
    )
    methods: list[MethodObservation] = Field(default_factory=list)
    non_surface_expression: list[NonSurfaceExpression] = Field(default_factory=list)
    therapeutic_engagement: TherapeuticEngagementContext | None = None
    contradicting_evidence: list[Contradiction] = Field(default_factory=list)

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {"grade_rationale": 800}

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> "SurfaceEvidence":
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self


# ---- biological context (section 2) ---------------------------------------


class TissueContext(BaseModel):
    """One tissue × disease_context expression row.

    The same tissue can appear twice (normal + tumor rows) with different
    ``present`` levels. Tissue / cell_type / cell_state names are free text —
    no ontology IDs for v1.0.0.
    """

    model_config = ConfigDict(extra="forbid")

    tissue: str
    present: TissuePresence
    disease_context: DiseaseContext
    cell_types: list[str] = Field(default_factory=list)
    cell_states: list[str] = Field(default_factory=list)
    cited_evidence_ids: list[str] = Field(default_factory=list)


class CellTypeContextV1(BaseModel):
    """Orthogonal cell-type pivot for biological context (v1.0.0)."""

    model_config = ConfigDict(extra="forbid")

    cell_type: str
    ontology_id: str | None = None
    present_in_tissues: list[str] = Field(default_factory=list)
    cited_evidence_ids: list[str] = Field(default_factory=list)


class StateContext(BaseModel):
    """Orthogonal cell-state pivot — activated/resting, stressed, EMT, etc."""

    model_config = ConfigDict(extra="forbid")

    state: str
    descriptor: str
    cited_evidence_ids: list[str] = Field(default_factory=list)


class DualLocalization(BaseModel):
    """One non-primary compartment the protein also occupies."""

    model_config = ConfigDict(extra="forbid")

    compartment: str
    fraction_estimate: float | None = None
    condition: str | None = None
    cited_evidence_ids: list[str] = Field(default_factory=list)


class MembraneSubdomain(BaseModel):
    """One membrane subdomain assignment (lipid raft, tight junction, cilium...)."""

    model_config = ConfigDict(extra="forbid")

    subdomain: str
    cited_evidence_ids: list[str] = Field(default_factory=list)


class SubcellularLocalization(BaseModel):
    """Where the protein lives, and how its localization is split."""

    model_config = ConfigDict(extra="forbid")

    primary_compartment: PrimaryCompartment
    dual_localization: list[DualLocalization] = Field(default_factory=list)
    membrane_subdomains: list[MembraneSubdomain] = Field(default_factory=list)


class AnatomicalAccessibilityObservation(BaseModel):
    """How the protein's anatomical orientation affects whether a systemic
    binder can physically reach it."""

    model_config = ConfigDict(extra="forbid")

    context: str
    orientation: Orientation
    accessibility_implication: AccessibilityImplication
    rationale: str = Field(
        ...,
        description="Why this orientation affects accessibility. Soft target ≤300 chars (overshoots warned but accepted).",
    )
    cited_evidence_ids: list[str] = Field(default_factory=list)

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {"rationale": 300}

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> "AnatomicalAccessibilityObservation":
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self


class AccessibilityModulationObservation(BaseModel):
    """How surface presence/exposure shifts with cell state, tissue, or disease.

    The first five ``category`` values are verbatim from ``surface_triage``'s
    contextual ``reason`` taxonomy. The three optional sub-fields
    (``cell_state_trigger``, ``restricted_lineage``,
    ``dual_loc_partner_compartment``) port the rich descriptive substructure
    from the triage prompt into closed enums for catalog filtering.

    Validators enforce category-conditional pairing.
    """

    model_config = ConfigDict(extra="forbid")

    category: ModulationCategory
    category_other_label: str | None = None
    cell_state_trigger: CellStateTrigger | None = None
    restricted_lineage: RestrictedLineage | None = None
    dual_loc_partner_compartment: DualLocPartnerCompartment | None = None
    baseline_context: str
    modulating_state: str
    change: str = Field(
        ...,
        description="What changes between baseline_context and modulating_state. Soft target ≤300 chars (overshoots warned but accepted).",
    )
    accessibility_implication: str = Field(
        ...,
        description="What the change means for accessibility. Soft target ≤300 chars (overshoots warned but accepted).",
    )
    cited_evidence_ids: list[str] = Field(default_factory=list)

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {
        "change": 300,
        "accessibility_implication": 300,
    }

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> AccessibilityModulationObservation:
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self

    @model_validator(mode="after")
    def _check_category_conditionals(self) -> AccessibilityModulationObservation:
        if self.category == "other" and not self.category_other_label:
            raise ValueError(
                "AccessibilityModulationObservation.category='other' requires "
                "category_other_label"
            )
        if self.category != "other" and self.category_other_label is not None:
            raise ValueError(
                "AccessibilityModulationObservation.category_other_label must be None "
                f"when category={self.category!r}"
            )
        if self.cell_state_trigger is not None and (
            self.category not in _STATE_INDUCED_CATEGORIES
        ):
            raise ValueError(
                "AccessibilityModulationObservation.cell_state_trigger may be set only "
                f"when category is one of {sorted(_STATE_INDUCED_CATEGORIES)}; "
                f"got category={self.category!r}"
            )
        if (
            self.restricted_lineage is not None
            and self.category != "tissue_restricted_surface"
        ):
            raise ValueError(
                "AccessibilityModulationObservation.restricted_lineage may be set only "
                f"when category=='tissue_restricted_surface'; got category={self.category!r}"
            )
        if (
            self.dual_loc_partner_compartment is not None
            and self.category != "dual_localization"
        ):
            raise ValueError(
                "AccessibilityModulationObservation.dual_loc_partner_compartment may be "
                f"set only when category=='dual_localization'; got category={self.category!r}"
            )
        return self


class BiologicalContext(BaseModel):
    """Section 2 — where, in what cell types/states, and under what
    conditions the protein presents at the surface."""

    model_config = ConfigDict(extra="forbid")

    tissues: list[TissueContext] = Field(default_factory=list)
    cell_types: list[CellTypeContextV1] = Field(default_factory=list)
    cell_states: list[StateContext] = Field(default_factory=list)
    subcellular_localization: SubcellularLocalization
    anatomical_accessibility: list[AnatomicalAccessibilityObservation] = Field(
        default_factory=list
    )
    accessibility_modulation: list[AccessibilityModulationObservation] = Field(
        default_factory=list
    )


# ---- deterministic features (sections 3, 4, 5, appendix) ------------------


class IsoformTopology(BaseModel):
    """DeepTMHMM-derived topology for one isoform. Orchestrator-emitted."""

    model_config = ConfigDict(extra="forbid")

    isoform_id: str
    uniprot_acc: str
    tm_helix_count: int
    n_terminal_orientation: TerminalOrientation
    c_terminal_orientation: TerminalOrientation
    signal_peptide_length: int
    ecd_length_residues: int
    icd_length_residues: int
    per_residue_topology: str
    tool_version: str
    retrieved_at: datetime


class OrthologEntry(BaseModel):
    """One ortholog isoform record — Ensembl Compara + DeepTMHMM. Deterministic."""

    model_config = ConfigDict(extra="forbid")

    is_canonical: bool
    isoform_id: str
    ensembl_id: str
    ortholog_uniprot_acc: str
    ortholog_symbol: str
    type: OrthologyType
    # ECD identity is NULL when the protein has no ECD (inner-leaflet, soluble,
    # GPI-anchored without surface loops). Full-length identity is always
    # available from Ensembl Compara BioMart.
    ecd_pct_identity_to_human_canonical: float | None = Field(default=None, ge=0.0, le=100.0)
    ecd_pct_similarity_to_human_canonical: float | None = Field(default=None, ge=0.0, le=100.0)
    full_length_pct_identity_to_human_canonical: float | None = Field(default=None, ge=0.0, le=100.0)
    ecd_length_residues: int
    tm_helix_count: int
    compara_version: str
    retrieved_at: datetime


class Orthologs(BaseModel):
    """Per-species ortholog isoform lists — canonical first, then alternatives."""

    model_config = ConfigDict(extra="forbid")

    mouse: list[OrthologEntry] = Field(default_factory=list)
    cynomolgus: list[OrthologEntry] = Field(default_factory=list)


class ParalogEntry(BaseModel):
    """One within-species paralog — Ensembl Compara. Deterministic."""

    model_config = ConfigDict(extra="forbid")

    paralog_symbol: str
    paralog_uniprot_acc: str
    ecd_pct_identity: float = Field(..., ge=0.0, le=100.0)
    family_id: str
    compara_version: str


class StructureFeatures(BaseModel):
    """AlphaFold DB structure-quality metrics for the canonical ECD.

    Both numeric metrics derive from per-residue pLDDT (no SASA/DSSP
    dependency). Attribution fields flow through to the viewer Structure card
    and the per-record Data Sources footer.
    """

    model_config = ConfigDict(extra="forbid")

    afdb_id: str
    afdb_version: AFDBVersion = "v4"
    ecd_mean_plddt: float = Field(..., ge=0.0, le=100.0)
    ecd_disordered_fraction: float = Field(..., ge=0.0, le=1.0)
    source: str
    license: str
    attribution: str
    citations: list[str] = Field(default_factory=list)


class DeterministicFeatures(BaseModel):
    """Verbatim tool output — populated by the orchestrator, never by the agent.

    A validator on :class:`SurfaceomeRecordDraft` rejects any attempt by the
    agent to populate this region in its draft.
    """

    model_config = ConfigDict(extra="forbid")

    canonical_topology: IsoformTopology
    isoform_topologies: list[IsoformTopology] = Field(default_factory=list)
    orthologs: Orthologs = Field(default_factory=Orthologs)
    paralogs: list[ParalogEntry] = Field(default_factory=list)
    structure: StructureFeatures


# ---- accessibility risks (section 6) --------------------------------------


class CoReceptorRequirements(BaseModel):
    """Does a partner have to be present for the target to reach the surface?

    Surface-expression axis ONLY — function-side dependency (does the partner
    have to be present for signaling?) is out of scope for v1.0.0.
    """

    model_config = ConfigDict(extra="forbid")

    surface_expression_dependency: CoreceptorDependency
    partners: list[str] = Field(default_factory=list)
    evidence_basis: CoreceptorEvidenceBasis
    rationale: str = Field(
        ...,
        description="Why this surface-expression dependency. Soft target ≤400 chars (overshoots warned but accepted).",
    )
    cited_evidence_ids: list[str] = Field(default_factory=list)

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {"rationale": 400}

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> "CoReceptorRequirements":
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self


class ShedForm(BaseModel):
    """Proteolytically shed soluble form of the protein."""

    model_config = ConfigDict(extra="forbid")

    present: bool
    severity: RiskSeverity
    evidence_strength: EvidenceStrength
    mechanism: str | None = None
    sheddase_if_known: str | None = None
    cited_evidence_ids: list[str] = Field(default_factory=list)


class SecretedForm(BaseModel):
    """Secreted (non-membrane-anchored) form of the protein."""

    model_config = ConfigDict(extra="forbid")

    present: bool
    severity: RiskSeverity
    evidence_strength: EvidenceStrength
    ratio_to_membrane: float | None = None
    source: SecretedFormSource | None = None
    cited_evidence_ids: list[str] = Field(default_factory=list)


class RestrictedSubdomain(BaseModel):
    """Surface presence restricted to a membrane subdomain (apical, junctional,
    ciliary, etc.) that a systemic binder may not reach."""

    model_config = ConfigDict(extra="forbid")

    present: bool
    domain: RestrictedSubdomainName
    severity: RiskSeverity
    evidence_strength: EvidenceStrength
    rationale: str = Field(
        ...,
        description="Why surface presence is restricted to this subdomain. Soft target ≤300 chars (overshoots warned but accepted).",
    )
    cited_evidence_ids: list[str] = Field(default_factory=list)

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {"rationale": 300}

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> "RestrictedSubdomain":
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self


class ECDSizeAssessment(BaseModel):
    """How much extracellular surface a binder has to engage.

    Renamed from ``druggability_class``. The viewer reads
    ``deterministic_features.canonical_topology.ecd_length_residues``
    directly — no FK needed since that field is a known singleton.
    """

    model_config = ConfigDict(extra="forbid")

    ecd_accessibility_class: ECDAccessibilityClass
    rationale: str = Field(
        ...,
        description="Why this ECD-size class. Soft target ≤300 chars (overshoots warned but accepted).",
    )
    cited_evidence_ids: list[str] = Field(default_factory=list)

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {"rationale": 300}

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> "ECDSizeAssessment":
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self


class EpitopeMasking(BaseModel):
    """Whether the extracellular epitope is masked from binders.

    ``mechanism`` is a list so multi-mechanism cases don't collapse to a
    single value.
    """

    model_config = ConfigDict(extra="forbid")

    mechanism: list[EpitopeMaskingMechanism] = Field(default_factory=list)
    severity: EpitopeMaskingSeverity
    evidence_strength: EvidenceStrength
    rationale: str = Field(
        ...,
        description="Why the epitope is (or isn't) masked. Soft target ≤400 chars (overshoots warned but accepted).",
    )
    cited_evidence_ids: list[str] = Field(default_factory=list)

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {"rationale": 400}

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> "EpitopeMasking":
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self


class AccessibilityRisks(BaseModel):
    """Section 6 — risks to a binder physically engaging the surface form.

    Every risk carries ``severity`` + ``evidence_strength`` so
    speculative-but-severe is distinguishable from real-but-mild.
    """

    model_config = ConfigDict(extra="forbid")

    co_receptor_requirements: CoReceptorRequirements
    shed_form: ShedForm
    secreted_form: SecretedForm
    restricted_subdomain: RestrictedSubdomain
    ecd_size_assessment: ECDSizeAssessment
    epitope_masking: EpitopeMasking


# ---- triage_signal ↔ surface_accessibility consistency --------------------

# Cross-agent coherence: a triage verdict of ``unlikely`` paired with a
# deep-dive ``surface_accessibility`` of ``high`` is a disagreement the LLM
# must justify in ``confidence_reasoning``. We don't hard-reject the
# disagreement (the deep-dive can legitimately overturn triage) — we require
# the record to carry an explanation. Only the strongest contradiction
# (triage=unlikely + accessibility=high) is gated.
_TRIAGE_HIGH_CONFLICT: dict[str, frozenset[str]] = {
    "unlikely": frozenset({"high"}),
}


def _validate_triage_signal_consistency(
    triage_signal: str,
    surface_accessibility: str,
    confidence_reasoning: str,
) -> None:
    """Flag triage ↔ deep-dive disagreement that lacks a written justification.

    Raises ``ValueError`` when ``triage_signal`` strongly contradicts
    ``executive_summary.surface_accessibility`` and ``confidence_reasoning``
    is empty — the LLM must explain the disagreement.
    """

    conflicting = _TRIAGE_HIGH_CONFLICT.get(triage_signal, frozenset())
    if surface_accessibility in conflicting and not confidence_reasoning.strip():
        raise ValueError(
            f"triage_signal={triage_signal!r} conflicts with "
            f"surface_accessibility={surface_accessibility!r}; the disagreement must "
            "be justified in a non-empty confidence_reasoning"
        )


# ---- assembled record + agent draft ---------------------------------------


class SurfaceomeRecord(BaseModel):
    """The reconciled per-protein surface-accessibility record (v1.0.0).

    Persisted to ``data/annotations/{gene}.json``. Two structurally separated
    regions — ``deterministic_features`` (orchestrator-populated tool output)
    and the LLM-synthesis blocks. Field order mirrors the viewer mockup.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    gene: GeneIdentifier

    # Cross-agent coherence — populated by the orchestrator from the most
    # recent surface_triage record.
    triage_signal: TriageSignal = "unknown"

    # LLM synthesis
    executive_summary: ExecutiveSummary

    # Catalog-facing flat rollups (D1-indexed)
    filters: Filters

    # Section 1
    surface_evidence: SurfaceEvidence

    # Section 2
    biological_context: BiologicalContext

    # Sections 3, 4, 5, appendix — orchestrator-only
    deterministic_features: DeterministicFeatures

    # Section 6
    accessibility_risks: AccessibilityRisks

    # Provenance — centralized Evidence array referenced by per-bucket
    # ``cited_evidence_ids``. Built by the orchestrator from agent-emitted
    # ``EvidenceClaim`` records after substring validation.
    evidence: list[Evidence] = Field(default_factory=list)
    search_log: list[SearchEntry] = Field(default_factory=list)
    evidence_count: int = 0
    primary_evidence_count: int = 0
    secondary_evidence_count: int = 0

    # Synthesis metadata
    confidence: Confidence
    confidence_reasoning: str = Field(
        ...,
        description="Why this confidence level. Soft target ≤600 chars (overshoots warned but accepted).",
    )
    model_path: str
    record_generated_at: datetime

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {"confidence_reasoning": 600}

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> SurfaceomeRecord:
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self

    @model_validator(mode="after")
    def _check_confidence_reasoning(self) -> SurfaceomeRecord:
        if self.confidence in ("moderate", "low") and not self.confidence_reasoning.strip():
            raise ValueError(
                f"confidence={self.confidence!r} requires a non-empty confidence_reasoning"
            )
        return self

    @model_validator(mode="after")
    def _check_triage_signal_consistency(self) -> SurfaceomeRecord:
        _validate_triage_signal_consistency(
            self.triage_signal,
            self.executive_summary.surface_accessibility,
            self.confidence_reasoning,
        )
        return self


class SurfaceomeRecordDraft(BaseModel):
    """What the AGENT emits for a surface-accessibility deep-dive.

    Same LLM-synthesis blocks as :class:`SurfaceomeRecord`, but:

    * ``deterministic_features`` is absent — the orchestrator populates that
      region after the agent emits. A validator rejects any attempt by the
      agent to smuggle a deterministic block into the draft.
    * Evidence is the small, human-shaped ``evidence_claims: list[EvidenceClaim]``
      rather than the promoted ``evidence: list[Evidence]`` chain. The
      orchestrator promotes ``EvidenceClaim`` → ``Evidence`` by normalizing
      the source + quote, running a substring check, and filling in hashes /
      char offsets / ``SourceRef`` metadata.
    * ``search_log`` and the derived evidence counts are orchestrator-built and
      not part of the draft.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    gene: GeneIdentifier

    # Orchestrator-injected before the agent call; the agent reads it but does
    # not change it.
    triage_signal: TriageSignal = "unknown"

    # LLM synthesis
    executive_summary: ExecutiveSummary
    filters: Filters
    surface_evidence: SurfaceEvidence
    biological_context: BiologicalContext
    accessibility_risks: AccessibilityRisks

    # Agent-emitted evidence — promoted to ``Evidence`` by the orchestrator.
    evidence_claims: list[EvidenceClaim] = Field(default_factory=list)

    # Synthesis metadata
    confidence: Confidence
    confidence_reasoning: str = Field(
        ...,
        description="Why this confidence level. Soft target ≤600 chars (overshoots warned but accepted).",
    )
    model_path: str

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {"confidence_reasoning": 600}

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> SurfaceomeRecordDraft:
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self

    @model_validator(mode="after")
    def _check_confidence_reasoning(self) -> SurfaceomeRecordDraft:
        if self.confidence in ("moderate", "low") and not self.confidence_reasoning.strip():
            raise ValueError(
                f"confidence={self.confidence!r} requires a non-empty confidence_reasoning"
            )
        return self

    @model_validator(mode="after")
    def _check_triage_signal_consistency(self) -> SurfaceomeRecordDraft:
        _validate_triage_signal_consistency(
            self.triage_signal,
            self.executive_summary.surface_accessibility,
            self.confidence_reasoning,
        )
        return self

    @model_validator(mode="before")
    @classmethod
    def _reject_deterministic_features(cls, data: Any) -> Any:
        # ``deterministic_features`` is orchestrator-only — the agent reads it
        # in its task prompt but must never emit it. ``extra="forbid"`` would
        # already reject the key with a generic error; this before-validator
        # raises a precise, self-documenting message so a stale-prompt run is
        # diagnosed immediately rather than as an opaque extra-field error.
        if isinstance(data, dict) and "deterministic_features" in data:
            raise ValueError(
                "SurfaceomeRecordDraft must not carry deterministic_features — "
                "that region is orchestrator-only and is populated after the agent emits"
            )
        return data


# ---- per-agent partial drafts (multi-agent topology) ----------------------


class SurfaceEvidenceDraft(BaseModel):
    """What agent A1 (Surface Evidence Compiler) emits.

    The ``surface_evidence`` block plus the evidence-ledger slice backing it.
    Claim ids are prefixed ``a1_evi_`` so the orchestrator can merge A1's and
    A2's ledgers without collision. Every ``cited_evidence_ids`` entry inside
    ``surface_evidence`` must resolve to an ``evidence_claims`` entry — A1
    cannot cite a claim it didn't emit.
    """

    model_config = ConfigDict(extra="forbid")

    surface_evidence: SurfaceEvidence
    evidence_claims: list[EvidenceClaim] = Field(default_factory=list)

    @field_validator("evidence_claims")
    @classmethod
    def _check_claim_id_prefix(cls, claims: list[EvidenceClaim]) -> list[EvidenceClaim]:
        bad = [c.evidence_id for c in claims if not c.evidence_id.startswith("a1_evi_")]
        if bad:
            raise ValueError(
                f"A1 evidence_claims must use the 'a1_evi_' id prefix; got: {bad}"
            )
        return claims

    @model_validator(mode="after")
    def _check_citations_resolve(self) -> SurfaceEvidenceDraft:
        known = {c.evidence_id for c in self.evidence_claims}
        cited: set[str] = set()
        se = self.surface_evidence
        for method in se.methods:
            cited.update(method.cited_evidence_ids)
            for obs in method.expression_observations:
                cited.update(obs.cited_evidence_ids)
        for nse in se.non_surface_expression:
            cited.update(nse.cited_evidence_ids)
        if se.therapeutic_engagement is not None:
            cited.update(se.therapeutic_engagement.cited_evidence_ids)
        for contradiction in se.contradicting_evidence:
            cited.update(contradiction.cited_evidence_ids)
        unresolved = sorted(cited - known)
        if unresolved:
            raise ValueError(
                "surface_evidence cites evidence_ids absent from evidence_claims: "
                f"{unresolved}"
            )
        return self


class BiologicalContextDraft(BaseModel):
    """What agent A2 (Biology Compiler) emits.

    The ``biological_context`` block plus the evidence-ledger slice backing
    it. Claim ids are prefixed ``a2_evi_`` so the orchestrator can merge A2's
    ledger with A1's (``a1_evi_``) without collision. Every
    ``cited_evidence_ids`` value referenced anywhere inside
    ``biological_context`` must resolve to a claim A2 emits.
    """

    model_config = ConfigDict(extra="forbid")

    biological_context: BiologicalContext
    evidence_claims: list[EvidenceClaim] = Field(default_factory=list)

    @field_validator("evidence_claims")
    @classmethod
    def _check_claim_id_prefix(cls, claims: list[EvidenceClaim]) -> list[EvidenceClaim]:
        bad = [c.evidence_id for c in claims if not c.evidence_id.startswith("a2_evi_")]
        if bad:
            raise ValueError(
                f"A2 evidence_claims must use the 'a2_evi_' id prefix; got: {bad}"
            )
        return claims

    @model_validator(mode="after")
    def _check_citations_resolve(self) -> BiologicalContextDraft:
        known = {c.evidence_id for c in self.evidence_claims}
        cited: set[str] = set()
        bc = self.biological_context
        for tissue in bc.tissues:
            cited.update(tissue.cited_evidence_ids)
        for cell_type in bc.cell_types:
            cited.update(cell_type.cited_evidence_ids)
        for state in bc.cell_states:
            cited.update(state.cited_evidence_ids)
        for dual in bc.subcellular_localization.dual_localization:
            cited.update(dual.cited_evidence_ids)
        for sub in bc.subcellular_localization.membrane_subdomains:
            cited.update(sub.cited_evidence_ids)
        for anat in bc.anatomical_accessibility:
            cited.update(anat.cited_evidence_ids)
        for mod in bc.accessibility_modulation:
            cited.update(mod.cited_evidence_ids)
        unresolved = sorted(cited - known)
        if unresolved:
            raise ValueError(
                "biological_context cites evidence_ids absent from evidence_claims: "
                f"{unresolved}"
            )
        return self


class SynthesizerLLMFilters(BaseModel):
    """The three ``filters`` rollups B is responsible for.

    The full :class:`Filters` block has 17 fields; 14 of those are
    orchestrator-derived from A1/A2 deep blocks and ``deterministic_features``.
    B emits only the three rollups that don't have a deterministic source —
    surface vs. intracellular split, expression breadth across tissues, and
    expression level for the protein's primary contexts. The orchestrator
    composes the full :class:`Filters` after the fact.
    """

    model_config = ConfigDict(extra="forbid")

    expression_level: ExpressionLevel
    expression_breadth: ExpressionBreadth
    surface_specificity: SurfaceSpecificity


class SynthesizerDraft(BaseModel):
    """What agent B (Surfaceome Synthesizer) emits.

    Cite-only integration over the merged A1 + A2 evidence ledger. B has no
    tools — the orchestrator validates ``cited_evidence_ids`` against the
    merged ledger after the fact, so this draft does NOT carry an
    ``evidence_claims`` slice.

    The ``confidence_reasoning`` non-empty-on-non-high rule mirrors the rule
    on the assembled :class:`SurfaceomeRecord` — surfacing the constraint at
    parse time keeps B honest before the orchestrator stitches the record.
    """

    model_config = ConfigDict(extra="forbid")

    executive_summary: ExecutiveSummary
    accessibility_risks: AccessibilityRisks
    filters_llm: SynthesizerLLMFilters
    confidence: Confidence
    confidence_reasoning: str = Field(
        ...,
        description="Why this confidence level. Soft target ≤600 chars (overshoots warned but accepted).",
    )

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {"confidence_reasoning": 600}

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> SynthesizerDraft:
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self

    @model_validator(mode="after")
    def _check_confidence_reasoning(self) -> SynthesizerDraft:
        if self.confidence in ("moderate", "low") and not self.confidence_reasoning.strip():
            raise ValueError(
                f"confidence={self.confidence!r} requires a non-empty confidence_reasoning"
            )
        return self


# ---------------------------------------------------------------------------
# Triage record — lightweight per-protein decision: is this protein surface
# accessible? Pure-model inference (no tools, no web search, no evidence
# emission); the orchestrator records the verdict + a single structured
# reason describing why.
# ---------------------------------------------------------------------------


TRIAGE_SCHEMA_VERSION = "v0.9.0"


TriageVerdict = Literal["yes", "contextual", "no"]
TriageModelPath = Literal["haiku_only", "sonnet_only", "opus_only"]
TriageConfidence = Literal["low", "medium", "high"]


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
    verdict_reasoning: str = Field(
        ...,
        description="Why this triage verdict. Soft target ≤800 chars (overshoots warned but accepted).",
    )
    reason: TriageReason
    confidence: TriageConfidence
    key_uncertainty: str | None = Field(
        default=None,
        description="The most important uncertainty. Soft target ≤200 chars (overshoots warned but accepted).",
    )
    model_path: TriageModelPath = "haiku_only"

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {
        "verdict_reasoning": 800,
        "key_uncertainty": 200,
    }

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> TriageRecordDraft:
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self

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
    verdict_reasoning: str = Field(
        ...,
        description="Why this triage verdict. Soft target ≤800 chars (overshoots warned but accepted).",
    )
    reason: TriageReason
    confidence: TriageConfidence
    key_uncertainty: str | None = Field(
        default=None,
        description="The most important uncertainty. Soft target ≤200 chars (overshoots warned but accepted).",
    )
    search_log: list[SearchEntry] = Field(default_factory=list)
    model_path: TriageModelPath = "haiku_only"

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {
        "verdict_reasoning": 800,
        "key_uncertainty": 200,
    }

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> TriageRecord:
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self

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
    # SurfaceomeRecord v1.0.0 — assembled record + agent draft
    "SCHEMA_VERSION",
    "SurfaceomeRecord",
    "SurfaceomeRecordDraft",
    "SurfaceEvidenceDraft",
    "BiologicalContextDraft",
    "SynthesizerLLMFilters",
    "SynthesizerDraft",
    # v1.0.0 — closed enums
    "TriageSignal",
    "SurfaceAccessibility",
    "EvidenceGrade",
    "Confidence",
    "StateDependence",
    "Subcategory",
    "HeadlineRisk",
    "ExpressionLevel",
    "ExpressionBreadth",
    "SurfaceSpecificity",
    "EvidenceDensity",
    "ECDAccessibilityClass",
    "MethodFamily",
    "MethodSubclass",
    "Permeabilization",
    "ExpressionSystem",
    "AccessibilityRelevance",
    "SurfaceClaimType",
    "AntibodyClonality",
    "AntibodyEpitopeRegion",
    "ValidationStrategy",
    "ValidationStrength",
    "SampleType",
    "MeasurementType",
    "TherapeuticStage",
    "ContradictionType",
    "ContradictionSeverity",
    "TissuePresence",
    "DiseaseContext",
    "PrimaryCompartment",
    "Orientation",
    "AccessibilityImplication",
    "ModulationCategory",
    "CellStateTrigger",
    "RestrictedLineage",
    "DualLocPartnerCompartment",
    "TerminalOrientation",
    "OrthologyType",
    "AFDBVersion",
    "RiskSeverity",
    "EvidenceStrength",
    "RestrictedSubdomainName",
    "CoreceptorDependency",
    "CoreceptorEvidenceBasis",
    "SecretedFormSource",
    "EpitopeMaskingMechanism",
    "EpitopeMaskingSeverity",
    # v1.0.0 — executive summary + filters
    "ExecutiveSummary",
    "Filters",
    # v1.0.0 — surface evidence (section 1)
    "AntibodyRef",
    "ExpressionObservation",
    "MethodObservation",
    "NonSurfaceExpression",
    "TherapeuticEngagementContext",
    "Contradiction",
    "SurfaceEvidence",
    # v1.0.0 — biological context (section 2)
    "TissueContext",
    "CellTypeContextV1",
    "StateContext",
    "DualLocalization",
    "MembraneSubdomain",
    "SubcellularLocalization",
    "AnatomicalAccessibilityObservation",
    "AccessibilityModulationObservation",
    "BiologicalContext",
    # v1.0.0 — deterministic features (sections 3, 4, 5, appendix)
    "IsoformTopology",
    "OrthologEntry",
    "Orthologs",
    "ParalogEntry",
    "StructureFeatures",
    "DeterministicFeatures",
    # v1.0.0 — accessibility risks (section 6)
    "CoReceptorRequirements",
    "ShedForm",
    "SecretedForm",
    "RestrictedSubdomain",
    "ECDSizeAssessment",
    "EpitopeMasking",
    "AccessibilityRisks",
    # TriageRecord
    "TRIAGE_SCHEMA_VERSION",
    "TriageRecord",
    "TriageRecordDraft",
    "TriageVerdict",
    "TriageModelPath",
    "TriageReason",
    "TriageConfidence",
    "YesReason",
    "ContextualReason",
    "NoReason",
]
