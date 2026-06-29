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
import re
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


def _has_inline_evi_cite(s: str) -> bool:
    """True when the string carries at least one inline ``(a1_evi_NN)`` /
    ``(a2_evi_NN)`` evidence-id token (A1.6 / A8.2). Substring check —
    deliberately loose, since this only backstops a warn-only validator."""
    return "a1_evi_" in s or "a2_evi_" in s


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
    # UniProt curator-assigned protein family from the SIMILARITY comment, with the
    # "Belongs to the " boilerplate stripped (e.g. "G-protein coupled receptor 1 family").
    # Deterministic, single-string family tag complementing hgnc_gene_groups; None when
    # UniProt has no SIMILARITY annotation (common for poorly-characterized proteins).
    uniprot_family: str | None = None
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
    # 'compartments' is no longer produced by any loader (JensenLab COMPARTMENTS
    # was removed in the v0 cleanup), but the value is kept here so historical
    # records that include SourceVote(name="compartments") still deserialize.
    "compartments",
    "patent_handle",
]


class SourceVote(BaseModel):
    """One source's vote on whether a gene is surface, with source-specific evidence.

    ``evidence`` is intentionally a free-form dict — each source's loader emits a
    different shape (GO returns ``[{go_id, evidence_code, term}]``; SURFY returns
    the ML class; etc.). Locking these down before the loaders settle would be
    premature.
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
    # Normal-tissue SURFACE expression across the six high-consequence tox
    # organs (on-target/off-tumor); retrieved as MED literature, never an
    # RNA atlas (the protein-level method categories carry surface proof).
    "normal_tissue_expression",
    # Surface-reachability barriers (BBB, tumor penetration,
    # luminal/abluminal vasculature, surface/antibody accessibility) —
    # distinct axis from surface-presence.
    "surface_reachability",
    # Partner / co-receptor dependency for surface trafficking — feeds the
    # co_receptor_requirements risk chip (obligate heterodimer, escort,
    # chaperone-assisted surface delivery, accessory subunit).
    "partner_dependency",
    # Plasma-membrane subdomain / polarity distribution — feeds
    # restricted_subdomain (lipid raft, apical/basolateral, ciliary, synaptic).
    "membrane_subdomain",
    # Epitope-masking evidence across the three mechanism axes the
    # epitope_masking risk records: HOMO self-association (homodimer /
    # oligomerization), HETERO partner/complex coverage, and OTHER
    # (glycan shield / conformational occlusion). Feeds epitope_masking.
    "epitope_masking",
    # Cell-state-conditional surface biology — activation, stress,
    # senescence, differentiation, disease-state shifts, tumor-
    # microenvironment effects. Feeds the merged accessibility_modulation
    # builder (both CONTRAST and SINGLE-CONTEXT shapes — the latter
    # absorbed the retired cell_states block in schema 2.5.0). Load-
    # bearing A2 axis for genes whose surface accessibility is
    # state-modulated; without it, state-context evidence relied on
    # gene2pubmed / recent_corpus baselines that under-recalled.
    "cell_state_modulation",
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


LiteratureMode = Literal[
    "gene2pubmed",
    "topic_search",
    "fetch_abstract",
    "fetch_fulltext",
    "recent_corpus",
]


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
    "if",
    "flow_cytometry",
    "surface_biotinylation",
    "mass_spec_surfaceome",
    # Ectodomain shedding / soluble-form-in-circulation evidence. Quote-grounded
    # because shed_form + secreted_form risks need a verbatim "soluble ectodomain
    # measured in serum" / "ADAM17-mediated shedding" sentence. Pulled out of the
    # catch-all ``other`` into its own focused category.
    "shedding",
    # Assay-less, context-tagged surface-expression mentions. The method
    # categories (ihc / if / flow / biotin / MS) all require a method term in
    # their query, so they systematically MISS bare location-tagged statements
    # like "X is expressed on the surface of activated T cells". This category
    # casts a precision-tuned net for surface/membrane tokens PAIRED with a
    # context cue (tissue / cell type / expression-level word) so A2's
    # ExpressionObservation rows are quote-grounded. A2-focus.
    "surface_expression",
    # Dedicated over-expression-precedent search: papers showing the protein
    # TRAFFICS TO THE CELL SURFACE when over-expressed / ectopically /
    # heterologously expressed (a surface-CAPABILITY signal — can it reach the
    # surface at all). Distinct from the OE *terms* sprinkled inside if / flow /
    # surface_biotinylation (those find OE-context WITHIN those assays); this
    # casts a wider net for OE-surface-trafficking regardless of detection
    # method. A1-focus.
    "overexpression",
    "western_blot_paired",
    "structure_with_ecd",
    "other",
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
    # Cross-planner duplicate marker. Populated by the orchestrator's
    # post-promotion dedup pass when two ``Evidence`` records share the
    # same ``(spans[0].source_id, spans[0].quote_sha256)`` — i.e. A1
    # and A2 both extracted the same span from the same paper.
    #
    # When non-null, references the ``evidence_id`` of the canonical
    # record this entry was folded onto (canonical = preferred A1 over
    # A2; tie-break on earliest evidence_id). The duplicate record IS
    # kept in the ledger so per-builder citations still resolve to the
    # exact id they were emitted with — but the viewer collapses
    # duplicates onto the canonical card so the reader sees ONE entry
    # per unique source span (with both planner interpretations
    # stacked underneath).
    duplicate_of: str | None = None

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

# Adds explicit ``"no"`` (PR follow-up after the design review): when
# the synthesizer's read is "this protein is confidently NOT on the
# surface", the catalog should be able to distinguish that from the
# weaker ``"uncertain"`` (no signal either way). Mirrors the triage
# ``verdict="no"`` end of the scale.
SurfaceAccessibility = Literal["high", "moderate", "low", "uncertain", "no"]
EvidenceGrade = Literal[
    "direct_multi_method",
    "direct_single_method",
    "supportive_but_indirect",
    "conflicting",
    "weak",
]
# A2 analog of ``EvidenceGrade``: how well-characterized and internally
# consistent the biological-context picture (expression / cell_states /
# subcellular_localization / anatomical_accessibility /
# accessibility_modulation) is. Rolled up by the A2 ``biological_context_grade``
# builder and surfaced flat on ``BiologicalContext`` (mirroring how
# ``SurfaceEvidence.evidence_grade`` sits flat). Values run high → low coverage.
BiologicalContextGrade = Literal[
    "rich",
    "moderate",
    "sparse",
    "absent",
]
Confidence = Literal["high", "moderate", "low"]
StateDependence = Literal["low", "moderate", "high", "unclear"]
# Subcategory = ARCHITECTURE only — how the protein sits in the
# membrane. Function lives on the separate ``ProteinFamily`` axis.
# Slimmed in the SURFACE-Bind alignment (Balbi et al. 2026 PNAS,
# doi:10.1073/pnas.2506269123): the SURFACE-Bind taxonomy splits
# function (Receptor / Enzyme / Transporter / Miscellaneous) from
# architectural detail (which SURFACE-Bind doesn't enumerate to
# this depth — we keep our own architecture axis).
#
# Removed values: ``ion_channel`` and ``transporter`` were functional,
# not architectural — they now flow to ``ProteinFamily=transporter``
# with ``Subcategory=multi_pass``. ``GPCR`` stays here as a common-
# name shortcut for the 7TM heptahelical architecture (the canonical
# functional use, but the name labels architecture in this taxonomy).
Subcategory = Literal[
    "single_pass_T1",
    "single_pass_T2",
    "multi_pass",
    "GPCR",
    "GPI_anchored",
    "tetraspanin",
    "other",
]

# ProteinFamily = FUNCTIONAL family. Mirrors SURFACE-Bind's four main
# classes verbatim (Balbi et al. 2026 PNAS), dropping the
# bookkeeping ``unclassified`` / ``unmatched`` since those reflect
# their mapping-pipeline state rather than biology.
ProteinFamily = Literal[
    "receptor",
    "enzyme",
    "transporter",
    "miscellaneous",
]
# Headline risks — slimmed from 11 → 5 after the redundancy audit.
# Each remaining value names a real load-bearing risk that the reader
# can't easily reconstruct from another structured field.
#
# Removed values + replacement signal:
#   * ``ecd_too_small`` → read ``filters.ecd_accessibility_class``
#     (small / minimal / none) — the headline flag was a binary
#     restatement of the same field.
#   * ``restricted_subdomain`` → read
#     ``accessibility_risks.restricted_subdomain.present`` — the
#     headline flag was a direct copy.
#   * ``antibody_validation_weak`` → read
#     ``surface_evidence.evidence_grade`` (weak / conflicting); per-
#     antibody detail lives in ``AntibodyRef.validation_strategy``.
#   * ``low_endogenous_expression`` → read the DERIVED
#     ``filters.low_endogenous_expression`` (computed deterministically
#     from ``filters.expression_level`` + ``expression_breadth`` — see
#     the field's docstring for the exact rule), so the headline list
#     can't drift from the filter the catalog filters on.
#   * ``ligand_unknown`` → not a "risk"; orphan-receptor status now
#     lives on ``filters.has_known_ligand: bool``.
#   * ``other`` → forbidden escape hatch. If the risk doesn't fit one
#     of the five remaining values, raise it in
#     ``executive_summary.one_paragraph`` instead and let the reader
#     see the prose.
HeadlineRisk = Literal[
    "shed_form",
    "secreted_form",
    "co_receptor",
    "epitope_masked",
    "isoform_decoy",
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
    # Functional engagement / pharmacology demonstrations of surface
    # access — antibody-mediated tumor killing in xenografts, ADC
    # efficacy, surface-targeted photo-tag labeling, FRET-on-surface,
    # radioligand binding. Use ``functional_surface_assay`` instead of
    # ``other`` for these; ``other`` stays for true catch-all cases
    # the bucket list doesn't cover.
    "functional_surface_assay",
    "other",
]
MethodSubclass = Literal[
    "live_cell_flow",
    "fixed_cell_flow",
    "nonpermeabilized_IF",
    "permeabilized_IF",
    "IHC_membranous",
    # Non-membranous IHC — tissue staining that reports expression
    # without a described membrane-pattern. Supportive-but-indirect:
    # the protein is present in the tissue but the assay does not
    # localize it to the cell surface. ``IHC_membranous`` is reserved
    # for explicit membrane-pattern staining.
    "IHC",
    "surface_biotinylation",
    "cell_surface_capture",
    "N_glycoproteomics",
    "plasma_membrane_fractionation",
    "whole_cell_proteomics",
    # Functional / pharmacological readouts that imply surface access
    # without direct staining or isolation of the protein: ADC
    # killing, anti-target-mediated tumor depletion, CAR-T cytotoxicity
    # against target+ cells, radioligand binding on live cells,
    # surface-restricted small-molecule probes. The functional
    # readout is impossible without surface access, so this counts as
    # DIRECT surface evidence (anti-pattern caps in the prompt apply).
    "functional_surface_assay",
    # True fallback for novel / hybrid methods the enum does not cover.
    # Prefer over ``unknown`` whenever the method is identified but
    # does not fit a named subclass.
    "other",
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
# Direction of the surface-pool change — orthogonal to the favorable/restricted
# accessibility verdict, so the viewer can show the up/down arrow independently
# of the risk grade.
ModulationDirection = Literal[
    "increases",
    "decreases",
    "bidirectional",
    "no_change",
    "unclear",
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
# Coarse induction-context bucket for the catalog `induction_trigger`
# filter — the dominant CellStateTrigger across a record's
# accessibility_modulation rows, grouped so the catalog can ask "show me
# stimulus-induced surface candidates" at one level instead of 18.
InductionTrigger = Literal[
    "none",
    "oncogenic",
    "immune",
    "stress_hypoxia",
    "cell_death",
    "infection",
    "other",
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

# Cancer-context vocabulary — gates the oncogenic_transformation trigger so a
# non-cancer disease state can't be mapped into it (A7.2). Substring match,
# case-insensitive.
_CANCER_VOCAB: tuple[str, ...] = (
    "tumor", "tumour", "cancer", "carcinoma", "malignan", "oncogen",
    "metasta", "neoplas", "sarcoma", "leukemia", "leukaemia", "lymphoma",
    "glioma", "glioblastoma", "melanoma", "adenocarcinoma",
)

# Clause markers that signal a value is a sentence, not a canonical name —
# rejected in compartment / subdomain fields (A5.1).
_CLAUSE_MARKERS: tuple[str, ...] = (
    " upon ", " under ", " when ", " during ", " after ", " following ",
    " if ", " in response to ", " stimulat",
)


def _assert_short_canonical(value: str, field: str) -> str:
    """Reject sentence-like compartment / subdomain values (A5.1).

    Canonical organelle / microdomain names are short and condition-free; a
    clause-packed value ("endosome upon ligand stimulation") belongs in a
    ``condition`` field, not the name.
    """
    # Generous length backstop — the parenthetical + clause-marker guards below
    # catch the real "packed a sentence into the field" failure mode; the cap
    # only stops a genuine run-on. 60 admits the longest real organelle names
    # (e.g. "endoplasmic reticulum-Golgi intermediate compartment", 52 chars).
    if len(value) > 60:
        raise ValueError(
            f"{field} must be a short canonical name (≤60 chars), not a "
            f"sentence; got {value!r}. Move conditions out of the name."
        )
    if "(" in value or ")" in value:
        raise ValueError(
            f"{field} must not contain parentheticals; got {value!r}."
        )
    padded = f" {value.lower()} "
    for marker in _CLAUSE_MARKERS:
        if marker in padded:
            raise ValueError(
                f"{field} must be a canonical name, not a conditional clause; "
                f"got {value!r} (contains '{marker.strip()}')."
            )
    return value


TerminalOrientation = Literal["extracellular", "cytoplasmic"]
OrthologyType = Literal["one2one", "one2many", "many2many"]
# AFDB bumps its model version periodically (v1→v6 between 2021 and
# 2026 for many entries; old versions are removed from the file
# server, so a stale ``v4`` URL is now a 404 for a sizable subset).
# The fetcher reads the real ``latestVersion`` from AFDB's metadata
# API at write time; we accept any vN through v9 in the schema and an
# ``"unknown"`` sentinel for the placeholder path. Widen further when
# v10+ ships.
AFDBVersion = Literal[
    "v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8", "v9", "unknown"
]

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
    # OTHER — glycocalyx / N-/O-glycan shielding of the epitope.
    "glycan",
    # HETERO — a *different* protein in a hetero-complex covers the epitope
    # (e.g. CD19 over the CD81 large extracellular loop). Self-association
    # does NOT go here — use ``oligomerization``.
    "partner",
    # HOMO — the target's *own* homodimer / homo-oligomer interface buries
    # epitope surface (tetraspanin / claudin cis-clustering, GPCR or
    # receptor homodimers). Distinct from ``partner`` (a second protein) and
    # from ``conformational`` (a monomer closed/open state).
    "oligomerization",
    # OTHER — closed/open conformer occlusion intrinsic to the monomer.
    "conformational",
    # OTHER — epitope removed by proteolytic cleavage.
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
    # A1.7 — the load-bearing §03 headline: ONE sentence on WHEN and WHERE the
    # protein is surface-accessible (not a generic blurb). Optional default ""
    # so v1 records emitted before this field still validate.
    accessibility_context_summary: str = ""
    surface_accessibility: SurfaceAccessibility
    evidence_grade_summary: EvidenceGrade
    confidence: Confidence
    state_dependence: StateDependence
    # Architecture (how the protein sits in the membrane). See the
    # ``Subcategory`` Literal for the closed enum + the SURFACE-Bind
    # alignment that splits architecture from function.
    subcategory: Subcategory
    # NEW: functional family per SURFACE-Bind (Balbi et al. 2026 PNAS).
    # ``receptor`` = signaling receptors (GPCRs, RTKs, cytokine
    # receptors, integrins, immunoreceptors). ``enzyme`` = surface-
    # exposed catalytic activity (CD13/ANPEP, CD26/DPP4, CD73/NT5E,
    # PSMA/FOLH1, ADAM family, MMPs, ectonucleotidases — and inner-
    # leaflet kinases like SRC by protein identity, even when the
    # ectopic-surface story is moderate). ``transporter`` = SLCs, ABC
    # transporters, ion channels, aquaporins, pumps. ``miscellaneous``
    # = adhesion / junction / tetraspanin / scaffold / structural /
    # chaperone proteins that don't fit the first three.
    #
    # Named ``llm_family`` to make explicit that this is the model's
    # high-level functional call — distinct from the deterministic,
    # curator-assigned ``hgnc_gene_groups`` / ``uniprot_family`` tags
    # that the orchestrator injects alongside it.
    llm_family: ProteinFamily = "miscellaneous"
    # Deterministic, curator-assigned family tags injected by the
    # orchestrator from the resolved ``IdentifierBundle`` (NOT emitted by
    # the synthesizer). They sit beside ``llm_family`` so the reader can
    # cross-check the model's high-level call against registry/curator
    # ground truth. ``hgnc_gene_groups`` = HGNC gene-group lineage
    # (e.g. ["G protein-coupled receptors, Class A orphans"]);
    # ``uniprot_family`` = UniProt SIMILARITY family with the "Belongs to
    # the " boilerplate stripped (e.g. "G-protein coupled receptor 1
    # family"). Both default empty/None for back-compat with records
    # generated before the injection landed.
    hgnc_gene_groups: list[str] = Field(default_factory=list)
    uniprot_family: str | None = None
    # The synthesizer's re-derived reason for its surface call. Reuses
    # the TriageReason enum so the catalog can filter by the same
    # vocabulary regardless of which agent emitted the reason. The
    # synth MUST re-derive from the A1+A2 evidence ledger — not just
    # copy ``triage_record.reason`` — so the rolled-up value is the
    # deep-dive's verdict, not the triage's echo. Often agrees with
    # the triage (e.g., canonical surface receptors); deliberately
    # disagrees when A1+A2 evidence overrides (e.g., a ``no /
    # inner_leaflet_anchored`` triage that the deep-dive promotes to
    # a contextual reason like ``lysosomal_exocytosis`` after finding
    # the cancer-state surface evidence).
    surface_call_reason: TriageReason
    # One-sentence, reader-facing rationale for WHEN / WHERE the protein
    # is surface-accessible — the headline behind the §03 "Localization &
    headline_risks: list[HeadlineRisk] = Field(default_factory=list, max_length=3)
    cited_evidence_ids: list[str] = Field(default_factory=list)

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {"one_paragraph": 600}

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> "ExecutiveSummary":
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self

    @model_validator(mode="after")
    def _check_surface_call_reason_aligns_with_accessibility(
        self,
    ) -> "ExecutiveSummary":
        """Enforce bucket alignment between ``surface_accessibility``,
        ``state_dependence``, and ``surface_call_reason``.

        The synth-side analogue of TriageRecord's
        ``_check_reason_matches_verdict``. Without this, the synth can
        emit nonsensical combos like ``surface_accessibility=high`` +
        ``state_dependence=low`` + ``surface_call_reason=cytoplasmic``
        (a high canonical-surface call with a NO-bucket reason) and
        nothing else in the schema catches it.

        Rules (mirror the bucket structure documented in the
        ``surface_call_reason`` section of
        ``surfaceome_synthesizer/prompts/system.md``):

        * ``high/moderate`` + ``low/unclear`` state_dep → YES-bucket only
          (canonical surface mechanisms)
        * ``high/moderate`` + ``moderate/high`` state_dep → YES OR
          CONTEXTUAL bucket (state-gated surface OK)
        * ``low`` → NO OR CONTEXTUAL bucket (marginal-yes state may
          justify a low headline)
        * ``no`` → NO-bucket only
        * ``uncertain`` → any reason (by definition the synth wasn't
          sure enough to constrain the explanation)

        ``other`` is in every bucket so it's always valid as an
        escape hatch.
        """
        sa = self.surface_accessibility
        sd = self.state_dependence
        r = self.surface_call_reason

        # uncertain → any reason allowed
        if sa == "uncertain":
            return self

        # `other` is in every bucket — always valid
        if r == "other":
            return self

        yes_bucket = _YES_REASONS - {"other"}
        contextual_bucket = _CONTEXTUAL_REASONS - {"other"}
        no_bucket = _NO_REASONS - {"other"}

        if sa == "no":
            if r not in no_bucket:
                raise ValueError(
                    f"surface_accessibility='no' requires surface_call_reason "
                    f"in the NO-bucket; got {r!r}. NO-bucket: "
                    f"{sorted(no_bucket)}"
                )
            return self

        if sa == "low":
            allowed = no_bucket | contextual_bucket
            if r not in allowed:
                raise ValueError(
                    f"surface_accessibility='low' requires surface_call_reason "
                    f"in the NO or CONTEXTUAL bucket; got {r!r}"
                )
            return self

        # sa ∈ {high, moderate}
        if sd in ("low", "unclear"):
            if r not in yes_bucket:
                raise ValueError(
                    f"surface_accessibility={sa!r} with state_dependence={sd!r} "
                    f"requires surface_call_reason in the YES-bucket "
                    f"(canonical surface mechanisms); got {r!r}. YES-bucket: "
                    f"{sorted(yes_bucket)}"
                )
            return self

        # sd ∈ {moderate, high}
        allowed = yes_bucket | contextual_bucket
        if r not in allowed:
            raise ValueError(
                f"surface_accessibility={sa!r} with state_dependence={sd!r} "
                f"requires surface_call_reason in the YES or CONTEXTUAL bucket "
                f"(canonical or state-gated surface); got {r!r}"
            )
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
    # Mirror of ``executive_summary.state_dependence``. Promoted to
    # Filters so catalog UI can D1-filter on state-conditional candidates
    # without joining through executive_summary.
    state_dependence: StateDependence
    # Mirror of ``executive_summary.surface_call_reason`` — the
    # synthesizer's re-derived reason for its surface call (reuses the
    # TriageReason enum). Distinct from the triage record's own reason:
    # the synth weighs A1+A2 evidence and re-emits, so the rolled-up
    # value is the deep-dive's verdict, not the triage's echo.
    surface_call_reason: TriageReason
    # Mirror of ``executive_summary.llm_family``. Rolled up by
    # the orchestrator so the catalog can filter by functional family
    # (SURFACE-Bind axis) at the top level alongside architecture.
    llm_family: ProteinFamily = "miscellaneous"
    evidence_grade: EvidenceGrade
    ecd_accessibility_class: ECDAccessibilityClass
    evidence_density: EvidenceDensity
    expression_level: ExpressionLevel
    expression_breadth: ExpressionBreadth
    surface_specificity: SurfaceSpecificity
    has_shed_form: bool
    has_secreted_form: bool
    requires_coreceptor_for_expression: bool
    # Full 4-value CoreceptorDependency enum
    # (required / modulatory / none / unknown). Mirror of
    # ``accessibility_risks.co_receptor_requirements.surface_expression_dependency``.
    # The existing ``requires_coreceptor_for_expression`` bool collapses
    # ``modulatory`` into ``False``, losing a real "not strictly required
    # but matters" signal; this enum field is the catalog-filterable version.
    co_receptor_dependency: CoreceptorDependency
    max_paralog_ecd_pct_identity: float | None = Field(default=None, ge=0.0, le=100.0)
    has_epitope_masking: bool
    has_restricted_subdomain: bool
    mouse_ortholog_ecd_pct_identity: float | None = Field(default=None, ge=0.0, le=100.0)
    cyno_ortholog_ecd_pct_identity: float | None = Field(default=None, ge=0.0, le=100.0)
    n_term_extracellular: bool
    c_term_extracellular: bool
    # Derived, NOT agent-emitted: the orchestrator computes this in
    # ``_derive_filters`` after the synthesizer call so the headline
    # signal can't drift from the catalog filter. ``True`` when EITHER
    # the baseline expression is low/absent OR it's moderate but
    # concentrated in one or two tissues:
    #   * ``expression_level ∈ {low, absent}``, OR
    #   * ``expression_level == 'moderate'`` AND
    #     ``expression_breadth == 'restricted'`` (catches the moderate-
    #     but-tissue-restricted case where endogenous burden in non-
    #     target tissues is effectively low — GPR75-class).
    # Replaces the now-dropped ``HeadlineRisk.low_endogenous_expression``
    # enum value — readers see one canonical signal, the catalog filters
    # on it.
    low_endogenous_expression: bool = False
    # Orphan-receptor status — ``True`` (the default) when a validated
    # endogenous ligand is documented. Set ``False`` for orphan
    # receptors (orphan GPCRs / nuclear receptors / kinases). Replaces
    # the now-dropped ``HeadlineRisk.ligand_unknown`` enum value; the
    # catalog can filter on this as a tractability signal.
    has_known_ligand: bool = True
    # Derived from ``surface_evidence.claim_stances`` by the
    # orchestrator. Lets the catalog distinguish "conflicting grade
    # from a single contradicting claim (artifact-suspect)" from
    # "conflicting grade from ≥3 contradicting claims (real
    # disagreement)" without re-parsing the grade_rationale prose.
    # Defaults to 0 — old records (no stance map emitted) and genes
    # whose builder didn't return stances both read as 0.
    n_supporting_claims_high_weight: int = Field(default=0, ge=0)
    n_contradicting_claims_high_weight: int = Field(default=0, ge=0)
    # Derived from ``surface_evidence.methods[]`` by the orchestrator.
    # True iff any MethodObservation has
    # ``expression_system ∈ {overexpression, mixed}`` AND
    # ``accessibility_relevance ∈ {direct_surface_accessibility,
    # supports_surface_localization}``. Signals "the gene has been
    # shown to surface-localize in an overexpression context" — useful
    # for assessing whether OE-based validation is on precedent for
    # this target. Distinct from ``has_known_ligand`` and
    # ``low_endogenous_expression``: this is specifically the OE +
    # surface combination, regardless of endogenous level or ligand
    # status. Defaults to False — records whose builder produced no
    # methods (weak grade, errored runs) read as False.
    overexpression_surface_localization_observed: bool = False

    # ---- deep-block rollups --------------------------------------------
    # Promoted to top-level catalog facets from blocks that previously
    # lived only nested (biological_context.tissues / .accessibility_
    # modulation, surface_evidence.methods). All deterministic — the
    # orchestrator derives them in ``_derive_filters``; default values keep
    # records emitted before these fields existed valid.
    #
    # Expressed in a tumor / tumor-adjacent tissue context (any
    # ``tissues[]`` row with disease_context ∈ {tumor, tumor_adjacent} at a
    # non-absent level). Oncology-target triage.
    tumor_associated: bool = False
    # Dominant induction trigger across ``accessibility_modulation`` rows —
    # *what stimulus* surfaces the protein, bucketed from CellStateTrigger.
    # ``surface_call_reason`` gives the *mechanism*; this gives the
    # *trigger*; ``"none"`` when no modulation row carries one.
    induction_trigger: InductionTrigger = "none"
    # ≥1 ``surface_evidence.methods`` row showing DIRECT surface
    # accessibility on live/intact cells in an endogenous context (flow
    # cytometry, surface biotinylation, or proximity labeling; expression
    # system endogenous/mixed). Filter by evidence MODALITY, not just grade.
    has_live_cell_surface_evidence: bool = False

    # ---- per-chip rationales -------------------------------------------
    # Every catalog chip carries a one-line "why". Four mirror B's
    # ``SynthesizerLLMFilters`` rationales (LLM-emitted rollups with no
    # deep block); two are composed deterministically by the orchestrator
    # for the derived booleans, referencing the source they were derived
    # from. The five remaining chips (co-receptor, restricted-subdomain,
    # shed, secreted, epitope-masking) carry their rationale in the deep
    # ``accessibility_risks`` blocks and are not duplicated here.
    #
    # Default ``""`` for backward compatibility: records emitted before
    # this field existed (or genes not yet re-annotated) read as empty,
    # and the viewer renders the chip without an expansion in that case.
    expression_level_rationale: str = ""
    expression_breadth_rationale: str = ""
    surface_specificity_rationale: str = ""
    has_known_ligand_rationale: str = ""
    # Orchestrator-composed (deterministic): the synth's
    # ``expression_level_rationale`` verbatim. No pipeline-internal
    # preamble (no enum names, no "Derived from" framing) — the synth
    # already writes natural-language reasoning anchored by cites; the
    # composition rule (see ``low_endogenous_expression`` above) is
    # documented in code, not surfaced to the reader. Empty when the
    # synth left its rationale blank.
    low_endogenous_expression_rationale: str = ""
    # Orchestrator-composed (deterministic): names the overexpression +
    # surface-localization method observation(s) that set the flag True.
    overexpression_surface_localization_observed_rationale: str = ""

    @model_validator(mode="after")
    def _require_has_known_ligand_rationale_when_true(self) -> "Filters":
        """Persisted-record gate: ``has_known_ligand=True`` requires a
        non-empty rationale.

        Same rule as the validator on ``SynthesizerLLMFilters`` (the
        draft slice), repeated here on ``Filters`` (the persisted shape
        the orchestrator assembles after merging the draft) so a record
        can't ship the bug even if a future code path bypasses the
        draft-side check. If the ligand can't be named, the bool should
        be ``False`` (orphan-receptor case).
        """
        if self.has_known_ligand and not self.has_known_ligand_rationale.strip():
            raise ValueError(
                "filters.has_known_ligand=True requires a non-empty "
                "has_known_ligand_rationale naming the ligand. If the "
                "ligand identity is genuinely unknown, set "
                "has_known_ligand=False (orphan-receptor case) and "
                "explain in the rationale."
            )
        return self


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
    """One expression-level observation anchored to a surface-evidence method.

    ``species`` defaults to ``"unspecified"`` (never ``"human"``) so the field
    is opt-in; downstream filters can distinguish "agent confirmed human" from
    "agent didn't say." ``species_inferred`` is set ``True`` by the deterministic
    post-pass when a cell-line token in ``context`` implied the species (e.g.
    "MC3T3-E1" → mouse) and the agent had left it unspecified.
    """

    model_config = ConfigDict(extra="forbid")

    context: str
    sample_type: SampleType
    level: ExpressionLevel
    species: Species = "unspecified"
    species_inferred: bool = False
    cited_evidence_ids: list[str] = Field(default_factory=list)


class OverexpressionContext(BaseModel):
    """Construct details for overexpression-based surface evidence.

    Populated by the methods builder when ``MethodObservation.expression_system``
    is ``"overexpression"`` or ``"mixed"``. The ``signal_peptide_source``
    field is the critical tier discriminator: a foreign / exogenous signal
    peptide forces secretory-pathway entry regardless of the protein's
    native trafficking, so foreign-SP overexpression cannot directly evidence
    native surface localization (csGRP78 / cell-surface-vimentin failure
    mode). The trim + select prompts require the SP source on every
    overexpression clip; this is where the builder lands it so downstream
    consumers (the viewer, the synthesizer, future automated audits) can
    tier the evidence without re-reading the methods sentence.

    Schema-optional: ``MethodObservation.overexpression`` defaults to
    ``None`` so endogenous-evidence records and pre-PR-#38 records remain
    valid.
    """

    model_config = ConfigDict(extra="forbid")

    signal_peptide_source: Literal["native", "exogenous", "unspecified"]
    signal_peptide_detail: str | None = None  # "IgG kappa leader", "preprotrypsin SP", "BiP leader"
    construct_tag: str | None = None  # "C-terminal FLAG", "N-terminal HA", "GFP fusion"
    cell_line: str | None = None  # "HEK293", "CHO", "293T", "HeLa"
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
    # Construct details for overexpression-based evidence. ``None`` for
    # ``expression_system="endogenous"``; required-in-practice (enforced by
    # the methods builder prompt, not the schema) when expression_system is
    # ``"overexpression"`` or ``"mixed"``.
    overexpression: OverexpressionContext | None = None
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


class Contradiction(BaseModel):
    """One piece of contradicting evidence + the LLM's read on whether it
    matters for surface accessibility."""

    model_config = ConfigDict(extra="forbid")

    claim: str
    contradiction_type: ContradictionType
    severity_for_surface_accessibility: ContradictionSeverity
    likely_explanation: str | None = None
    cited_evidence_ids: list[str] = Field(default_factory=list)


ClaimStance = Literal[
    "supports_surface",      # claim supports surface accessibility
    "contradicts_surface",   # claim refutes surface accessibility
    "tangential",            # informs picture but doesn't commit either way
    "expression_only",       # tissue/cell expression claim, not surface evidence
]

ClaimWeight = Literal[
    "high",      # direct surface methodology + KO control or multi-source
    "moderate",  # direct methodology, single source, weak validation
    "low",       # indirect / inferred / single mention
]


class ClaimStanceRow(BaseModel):
    """One per-claim stance backing the evidence_grade verdict.

    Structured per-claim accounting alongside the free-text
    ``grade_rationale`` prose. Lets the catalog query "conflicting grade
    with only 1 high-weight contradiction → likely artifact" vs "≥3
    high-weight contradictions → real disagreement" — distinctions the
    grade enum alone collapses.

    Weight criteria the LLM applies:
      * ``high`` — direct surface methodology (live flow, nonperm IF,
        surface biotin, IHC membranous) with knockout / siRNA control
        OR corroboration across multiple independent sources.
      * ``moderate`` — direct methodology, single source, weaker
        validation (e.g. one published flow study with vendor-only
        antibody validation).
      * ``low`` — indirect (fractionation / glycoproteomics) OR a
        single mention without methodology detail.
    """

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    stance: ClaimStance
    weight: ClaimWeight
    note: str | None = Field(
        default=None,
        description="Optional ≤120-char qualifier (e.g. 'antibody from non-KO-validated paper').",
    )


class ExcludedClaim(BaseModel):
    """One claim the methods builder REJECTED at the inclusion stage as
    receptor-engagement-as-ligand evidence rather than surface accessibility
    of the protein itself.

    The methods builder's inclusion criterion is: the protein must be the
    membrane-anchored entity in the assay. Claims where the protein is the
    SOLUBLE LIGAND whose engagement was captured by binding / crosslinking
    a receptor on ANOTHER cell describe biology (receptor pharmacology, DAMP
    signaling, partner engagement) but NOT surface accessibility of the
    protein in question. Those claims don't emit a ``MethodObservation``
    row; they're enumerated here with their original ``evidence_id`` + a
    short reason so the audit trail of "which papers were excluded and
    why" is visible to readers (and downstream re-grade scripts).

    Populated by the evidence-grade builder from its read of the same A1
    ledger the methods builder consumed — the grade builder marks each
    such claim with ``stance=tangential`` in ``claim_stances`` AND adds a
    row here. Parallel surface to ``non_surface_expression`` (claims that
    are real expression data but not surface evidence) so the reader can
    triage A1's input pile cleanly: surface-method observations, expression-
    only observations, ligand-engagement observations, and the residual.
    """

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(
        ...,
        description="The evidence_id from the input A1 ledger (e.g. 'a1_evi_13').",
    )
    reason: str = Field(
        ...,
        max_length=240,
        description=(
            "Short explanation of why this claim was excluded as ligand-"
            "engagement evidence rather than surface accessibility. Name "
            "the specific receptor / partner the protein was binding "
            "(e.g. 'HMGB1 binding TREM-1 on monocytes — soluble ligand "
            "engagement, not surface anchoring of HMGB1')."
        ),
    )


# Tokens that mark a "specific surface-method claim" in grade_rationale
# prose — used by the fail-validator below. When ANY of these appear in
# the rationale AND ``claim_stances`` has ≥2 rows AND zero inline
# ``(aN_evi_NN)`` cites are present, the validator refuses the record.
# Anchored on tokens that REQUIRE a citable source under the citation-
# discipline rule (named experimental method, structured enumeration of
# multiple claims, named structural technique). Kept narrow on purpose:
# loose prose without these tokens still passes warn-only so genuinely
# narrative rationales aren't blocked.
_GRADE_RATIONALE_STRUCTURED_CLAIM_TOKENS: frozenset[str] = frozenset(
    {
        # Numbered enumerations of separate claims: "(1)", "(2)", "(3)"
        "(1)",
        "(2)",
        "(3)",
        # Direct surface-method terms — when these appear, the reader
        # expects a citable source on the same line.
        "knockin",
        "knock-in",
        "knockout",
        "knock-out",
        "live-cell flow",
        "live cell flow",
        "non-permeabilized",
        "nonpermeabilized",
        "flow cytometry",
        "surface biotinylation",
        "cell surface capture",
        "crosslinking",
        "cross-linking",
        "cryo-em",
        "cryo em",
        "x-ray",
        "photoaffinity",
        "proteinase-k",
        "proteinase k",
    }
)


def _has_structured_claim_marker(s: str) -> bool:
    """True when ``s`` contains a token that marks a specific surface-method
    claim (per :data:`_GRADE_RATIONALE_STRUCTURED_CLAIM_TOKENS`). Case-
    insensitive substring match; kept loose because this gates a hard
    failure and the false-negative cost (no fail) is lower than the false-
    positive cost (fail on prose that doesn't actually need a cite).
    """
    lower = s.lower()
    return any(tok in lower for tok in _GRADE_RATIONALE_STRUCTURED_CLAIM_TOKENS)


class SurfaceEvidence(BaseModel):
    """Section 1 — the surface-accessibility evidence the agent assembled."""

    model_config = ConfigDict(extra="forbid")

    evidence_grade: EvidenceGrade
    grade_rationale: str = Field(
        ...,
        description="Why this evidence_grade. Soft target ≤800 chars (overshoots warned but accepted).",
    )
    # Per-claim structured accounting that backs the grade. Each row
    # names one EvidenceClaim from the input ledger + its stance
    # (supports/contradicts/tangential/expression_only) + weight
    # (high/moderate/low). Used by the orchestrator to derive the
    # ``n_supporting_claims_high_weight`` / ``n_contradicting_claims_high_weight``
    # filters so the catalog can distinguish artifact vs. real
    # conflicting-grade cases. Defaults to ``[]`` for backward compat
    # with records emitted before this field existed; the derived
    # filters read 0 in that case.
    claim_stances: list[ClaimStanceRow] = Field(default_factory=list)
    methods: list[MethodObservation] = Field(default_factory=list)
    non_surface_expression: list[NonSurfaceExpression] = Field(default_factory=list)
    contradicting_evidence: list[Contradiction] = Field(default_factory=list)
    # Audit trail of A1 ledger claims the methods builder rejected at the
    # inclusion stage as ligand-engagement-as-soluble-partner evidence
    # rather than surface accessibility of the protein itself. Parallel to
    # ``non_surface_expression``; default-empty for back-compat with v2
    # records emitted before this field landed.
    excluded_as_ligand_engagement: list[ExcludedClaim] = Field(default_factory=list)

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {"grade_rationale": 800}

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> "SurfaceEvidence":
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self

    @model_validator(mode="after")
    def _check_evidence_grade_methods_cardinality(self) -> "SurfaceEvidence":
        _validate_evidence_grade_methods_cardinality(
            self.evidence_grade,
            self.methods,
        )
        return self

    @model_validator(mode="after")
    def _warn_grade_rationale_missing_cite(self) -> "SurfaceEvidence":
        """Warn when ``grade_rationale`` has no inline ``(aN_evi_NN)`` cite.

        Same shape as ``_warn_rationale_missing_cite`` on
        ``SynthesizerLLMFilters`` — soft signal for citation discipline so
        the reader can click straight to the source for every claim.
        Loud-fails to a hard error are reserved for the stricter validator
        below; this one just logs.

        Skip placeholder content (an em-dash, "n/a", "—", or anything
        shorter than 20 chars when stripped) — those can't carry claim-
        shaped prose, so flagging a missing cite would be noise.
        """
        stripped = (self.grade_rationale or "").strip()
        if len(stripped) < 20:
            return self
        if not _has_inline_evi_cite(self.grade_rationale):
            logger.warning(
                "SurfaceEvidence.grade_rationale lacks an inline "
                "(a1_evi_NN)/(a2_evi_NN) cite: %r",
                self.grade_rationale[:200],
            )
        return self

    @model_validator(mode="after")
    def _fail_grade_rationale_structured_claims_uncited(
        self,
    ) -> "SurfaceEvidence":
        """Refuse the record when ``grade_rationale`` makes specific
        surface-method claims without backing them with inline cites.

        Trigger condition:
          * the rationale contains structured-claim markers (numbered
            enumerations like ``(1)`` / ``(2)`` / ``(3)``, OR named
            experimental methods — see
            :data:`_GRADE_RATIONALE_STRUCTURED_CLAIM_TOKENS`), AND
          * ``claim_stances`` has ≥2 rows (i.e. the grader already
            committed structured per-claim attributions, so the cites are
            available — the writer just didn't inline them), AND
          * the rationale contains zero ``(aN_evi_NN)`` cites.

        Together those three conditions mean "the writer made specific
        claims that the schema knows have citable sources, and chose not
        to cite them." That's an unambiguous citation-discipline failure
        and the reader can't audit it.

        Loose prose without specific method claims still passes (warn-
        only above), so genuinely narrative rationales for genes with
        only one or two stance rows aren't blocked.
        """
        rationale = self.grade_rationale or ""
        if not rationale:
            return self
        if _has_inline_evi_cite(rationale):
            return self
        if len(self.claim_stances) < 2:
            return self
        if not _has_structured_claim_marker(rationale):
            return self
        raise ValueError(
            "SurfaceEvidence.grade_rationale makes specific surface-method "
            "claims (numbered items or named experimental methods) and "
            "claim_stances has "
            f"{len(self.claim_stances)} attributions, but the rationale "
            "carries no inline (aN_evi_NN) cites — readers cannot verify "
            "which claim_stances row backs each prose claim. "
            "Inline a cite per substantive claim, drawn from claim_stances."
        )


# ---- biological context (section 2) ---------------------------------------


class ExpressionRow(BaseModel):
    """One ``(tissue × cell_type × disease_context)`` expression observation.

    Tissue and cell-type are the same pivot — where the protein was seen — so
    they live on one self-describing row rather than two cross-referenced
    arrays. Each row carries its OWN disease context (``disease_context`` enum
    + free-text ``disease_label``) and ``present`` level, so a reader never
    walks from a cell row to a paired tissue row to learn its disease state.

    The same tissue/cell_type can appear twice (a normal baseline row + a
    disease row) with different ``present`` levels — both are kept, because the
    off-tumor baseline is load-bearing for toxicity even when the level matches
    the disease read. ``cell_type`` is ``None`` for a tissue-level observation
    with no resolved cell type. Names are free text — no ontology IDs for
    v1.0.0. See ``ExpressionObservation`` for the ``species`` /
    ``species_inferred`` contract.
    """

    model_config = ConfigDict(extra="forbid")

    tissue: str
    cell_type: str | None = None
    present: TissuePresence
    disease_context: DiseaseContext
    disease_label: str | None = None
    cell_states: list[str] = Field(default_factory=list)
    species: Species = "unspecified"
    species_inferred: bool = False
    cited_evidence_ids: list[str] = Field(default_factory=list)


class TissueContext(BaseModel):
    """DEPRECATED (v1 only). Superseded by :class:`ExpressionRow`.

    Retained so the v1 ``biology_compiler`` Managed Agent — which emits
    ``tissues`` / ``cell_types`` and validates against the shared
    ``BiologicalContext`` — still reproduces. The v2 path leaves this empty and
    populates ``expression`` instead. Delete when v1 reproducibility is retired.
    """

    model_config = ConfigDict(extra="forbid")

    tissue: str | None = None
    cell_type: str | None = None
    present: TissuePresence
    disease_context: DiseaseContext
    # Specific disease name when ``disease_context`` can't name it on its own
    # (e.g. "Fabry disease", "diabetic nephropathy", "lung adenocarcinoma").
    # Free text; null for a plain normal read or a generic unnamed tumor. The
    # viewer shows this in place of the bare enum.
    disease_label: str | None = Field(default=None, max_length=120)
    cell_states: list[str] = Field(default_factory=list)
    species: Species = "unspecified"
    species_inferred: bool = False
    cited_evidence_ids: list[str] = Field(default_factory=list)


class CellTypeContextV1(BaseModel):
    """DEPRECATED (v1 only). Superseded by :class:`ExpressionRow`. See
    :class:`TissueContext` for why it's retained."""

    model_config = ConfigDict(extra="forbid")

    cell_type: str
    ontology_id: str | None = None
    present_in_tissues: list[str] = Field(default_factory=list)
    species: Species = "unspecified"
    species_inferred: bool = False
    cited_evidence_ids: list[str] = Field(default_factory=list)


class DualLocalization(BaseModel):
    """One non-primary compartment the protein also occupies."""

    model_config = ConfigDict(extra="forbid")

    compartment: str
    fraction_estimate: float | None = None
    condition: str | None = None
    rationale: str = Field(
        default="",
        description=(
            "Why this compartment - name the assay (IF / fractionation / IHC / "
            "biotinylation / Atlas annotation), cell type, and permeabilization "
            "status, with inline (a2_evi_NN) cites per claim. Soft target "
            "<=300 chars (overshoots warned but accepted). Defaults to "" "
            "for backward-compat with legacy records loaded from D1 / on-disk "
            "snapshots that pre-date this field; new annotator runs must fill it."
        ),
    )
    cited_evidence_ids: list[str] = Field(default_factory=list)

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {"rationale": 300}

    @field_validator("compartment")
    @classmethod
    def _short_compartment(cls, v: str) -> str:
        return _assert_short_canonical(v, "DualLocalization.compartment")

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> "DualLocalization":
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self


# Closed enum for membrane-subdomain assignments. Free text let models emit
# "cilia" / "primary cilium" / "Primary Cilium" for the same biology, which
# broke grouping queries; the enum collapses that to a canonical token. The
# ``mode="before"`` coercion below normalizes legacy free-text values so
# already-stored records (D1 rows, viewer snapshots) still load.
MembraneSubdomainName = Literal[
    "lipid_raft",
    "tight_junction",
    "primary_cilium",
    "apical_membrane",
    "basolateral_membrane",
    "immune_synapse",
    "focal_adhesion",
    "caveolae",
    "other",
]

# Synonym → canonical map applied AFTER whitespace/hyphen normalization
# (lowercase, strip, collapse runs of space/hyphen to a single underscore).
# Anything not present here — including inner-leaflet / cytoplasmic-face
# anchors, which are not surface-accessible — coerces to ``"other"`` rather
# than raising, so no legacy record is ever rejected on load.
_MEMBRANE_SUBDOMAIN_SYNONYMS: dict[str, str] = {
    # primary cilium
    "cilia": "primary_cilium",
    "cilium": "primary_cilium",
    "primary_cilium": "primary_cilium",
    "ciliary": "primary_cilium",
    "ciliary_membrane": "primary_cilium",
    # lipid raft
    "lipid_raft": "lipid_raft",
    "lipid_rafts": "lipid_raft",
    "raft": "lipid_raft",
    "rafts": "lipid_raft",
    "membrane_raft": "lipid_raft",
    # apical membrane
    "apical": "apical_membrane",
    "apical_membrane": "apical_membrane",
    "apical_surface": "apical_membrane",
    # basolateral membrane
    "basolateral": "basolateral_membrane",
    "basolateral_membrane": "basolateral_membrane",
    # tight junction
    "tight_junction": "tight_junction",
    "tight_junctions": "tight_junction",
    "zonula_occludens": "tight_junction",
    # immune synapse
    "immune_synapse": "immune_synapse",
    "immunological_synapse": "immune_synapse",
    "immunologic_synapse": "immune_synapse",
    # focal adhesion
    "focal_adhesion": "focal_adhesion",
    "focal_adhesions": "focal_adhesion",
    # caveolae
    "caveolae": "caveolae",
    "caveola": "caveolae",
    "caveolar": "caveolae",
}

# Canonical tokens that pass straight through (the Literal members).
_MEMBRANE_SUBDOMAIN_CANONICAL: frozenset[str] = frozenset(
    {
        "lipid_raft",
        "tight_junction",
        "primary_cilium",
        "apical_membrane",
        "basolateral_membrane",
        "immune_synapse",
        "focal_adhesion",
        "caveolae",
        "other",
    }
)


def _coerce_membrane_subdomain(value: str) -> str:
    """Normalize a free-text subdomain to a canonical ``MembraneSubdomainName``.

    Lowercase + strip, collapse any run of spaces / hyphens / underscores to a
    single underscore, then map through the synonym table. Already-canonical
    values pass through; anything unrecognized coerces to ``"other"`` — the
    field is a closed enum for NEW data but never rejects legacy data.
    """
    normalized = re.sub(r"[\s\-_]+", "_", value.strip().lower()).strip("_")
    if normalized in _MEMBRANE_SUBDOMAIN_CANONICAL:
        return normalized
    return _MEMBRANE_SUBDOMAIN_SYNONYMS.get(normalized, "other")


class MembraneSubdomain(BaseModel):
    """One membrane subdomain assignment (lipid raft, tight junction, cilium...)."""

    model_config = ConfigDict(extra="forbid")

    subdomain: MembraneSubdomainName
    rationale: str = Field(
        default="",
        description=(
            "Why this microdomain — name the assay that assigned it (raft "
            "purification, cilium IF, polarized-epithelium IHC, immune-synapse "
            "co-cluster), cell type, and permeabilization status, with inline "
            "``(a2_evi_NN)`` cites. Soft target ≤200 chars (overshoots warned "
            "but accepted). Defaults to ``\"\"`` for backward-compat with legacy "
            "records loaded from D1 / on-disk snapshots that pre-date this "
            "field; new annotator runs must fill it."
        ),
    )
    cited_evidence_ids: list[str] = Field(default_factory=list)

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {"rationale": 200}

    @field_validator("subdomain", mode="before")
    @classmethod
    def _coerce_subdomain(cls, v: object) -> object:
        # Backward-compat: stored records carry FREE-TEXT subdomain values
        # ("lipid rafts", "Primary Cilium", "apical surface", or even an
        # inner-leaflet / cytoplasmic-face anchor that is not surface-
        # accessible). Normalize every string to a canonical token so the
        # closed enum never rejects legacy data; unrecognized → "other".
        if isinstance(v, str):
            return _coerce_membrane_subdomain(v)
        return v

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> "MembraneSubdomain":
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self


class SubcellularLocalization(BaseModel):
    """Where the protein lives, and how its localization is split."""

    model_config = ConfigDict(extra="forbid")

    primary_compartment: PrimaryCompartment
    rationale: str = Field(
        default="",
        description=(
            "Why this primary compartment - name the methods that pinned it "
            "(IF / fractionation / IHC / Atlas annotation / nonperm flow), "
            "cell type, and permeabilization status, with inline "
            "(a2_evi_NN) cites per claim. Soft target <=400 chars "
            '(overshoots warned but accepted). Defaults to "" for '
            "backward-compat with legacy records loaded from D1 / on-disk "
            "snapshots that pre-date this field; new annotator runs must "
            "fill it."
        ),
    )
    dual_localization: list[DualLocalization] = Field(default_factory=list)
    membrane_subdomains: list[MembraneSubdomain] = Field(default_factory=list)

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {"rationale": 400}

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> "SubcellularLocalization":
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self


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
    # ``baseline_context`` and ``modulating_state`` are the two endpoints
    # of a state contrast. Both optional (default None) so the merged-in
    # cell_states case — a single-context state observation where the
    # paper describes the protein's behavior in one state without a
    # comparison condition — emits as a row with both fields null. When
    # both are set, the row is a contrast pair (the original modulation
    # row shape); when both are null, it is a single-context observation
    # (the former cell_states row shape). Mixed (one set, one null) is
    # forbidden by ``_check_contrast_and_trigger_vocab`` — pick one
    # shape per row.
    baseline_context: str | None = None
    modulating_state: str | None = None
    # Up/down direction of the surface-pool change — orthogonal to the
    # favorable/restricted verdict in ``accessibility_implication``. Optional
    # (defaults ``unclear``) so v1 records emitted before this field validate.
    direction: ModulationDirection = "unclear"
    change: str = Field(
        ...,
        description="What changes between baseline_context and modulating_state. Soft target ≤300 chars (overshoots warned but accepted).",
    )
    accessibility_implication: str = Field(
        ...,
        description="What the change means for accessibility. Soft target ≤300 chars (overshoots warned but accepted).",
    )
    # Structured up/down direction of the change described in ``change`` /
    # ``accessibility_implication``. Defaults to ``"unclear"`` so records
    # predating this field stay valid and the viewer shows no glyph for them.
    direction: ModulationDirection = "unclear"
    species: Species = "unspecified"
    species_inferred: bool = False
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

    @model_validator(mode="after")
    def _check_contrast_and_trigger_vocab(self) -> AccessibilityModulationObservation:
        # Post-2.5.0 — a row is either a CONTRAST (both baseline_context
        # and modulating_state set, naming two different states) or a
        # SINGLE-CONTEXT observation (both null — the merged-in
        # cell_states case where the paper describes the protein in one
        # state without a comparison condition). One set and the other
        # null is an under-specified contrast and is rejected — emit
        # both, or neither.
        has_baseline = bool(
            self.baseline_context is not None and self.baseline_context.strip()
        )
        has_modulating = bool(
            self.modulating_state is not None and self.modulating_state.strip()
        )
        if has_baseline != has_modulating:
            raise ValueError(
                "AccessibilityModulationObservation: baseline_context and "
                "modulating_state must both be set (contrast row) or both be "
                "null (single-context state observation). Got "
                f"baseline_context={self.baseline_context!r}, "
                f"modulating_state={self.modulating_state!r}."
            )
        # A7.1 — when the row IS a contrast, the two endpoints must name
        # two DIFFERENT states (a documented change), not the same one
        # ("cells express X" is not a modulation contrast).
        if has_baseline and has_modulating:
            assert self.baseline_context is not None  # narrowing for ty
            assert self.modulating_state is not None
            if (
                self.baseline_context.strip().lower()
                == self.modulating_state.strip().lower()
            ):
                raise ValueError(
                    "AccessibilityModulationObservation contrast: "
                    "baseline_context and modulating_state must name two "
                    "DIFFERENT states. Drop rows that merely restate "
                    "expression context, or emit as a single-context "
                    "observation (both null)."
                )
        # A7.2 — the oncogenic_transformation trigger is cancer-specific; a
        # non-cancer disease state must not be coerced into it. Only
        # enforceable when the row carries a contrast pair (single-context
        # observations pass through — the trigger still has to match the
        # category, which is checked separately).
        if self.cell_state_trigger == "oncogenic_transformation" and has_baseline:
            text = f"{self.baseline_context or ''} {self.modulating_state or ''}".lower()
            if not any(v in text for v in _CANCER_VOCAB):
                raise ValueError(
                    "cell_state_trigger='oncogenic_transformation' requires a "
                    "cancer / tumor context in baseline_context or "
                    "modulating_state; use a different trigger for non-cancer "
                    "disease states."
                )
        return self


class BiologicalContext(BaseModel):
    """Section 2 — where, in what cell types/states, and under what
    conditions the protein presents at the surface.

    Schema 2.5.0 retired the standalone ``cell_states: list[StateContext]``
    field — empirically ~70% of cell_states rows duplicated information
    already structured in ``accessibility_modulation``, and the unique
    remainder (single-context state observations without a clean baseline ↔
    modulating contrast) is now absorbed into
    ``AccessibilityModulationObservation`` rows with
    ``baseline_context=None`` + ``modulating_state=None``. Legacy records
    carrying a populated ``cell_states`` field are loadable — a
    ``model_validator(mode="before")`` drops the legacy data and emits a
    warning (re-annotate to recover the state content as modulation rows).
    """

    model_config = ConfigDict(extra="forbid")

    # v2: one self-describing (tissue × cell_type × disease_context) row each.
    expression: list[ExpressionRow] = Field(default_factory=list)
    # DEPRECATED (v1 only) — the v1 biology_compiler emits these; v2 leaves
    # them empty and populates ``expression``. Retained for v1 reproducibility.
    tissues: list[TissueContext] = Field(default_factory=list)
    cell_types: list[CellTypeContextV1] = Field(default_factory=list)
    subcellular_localization: SubcellularLocalization
    anatomical_accessibility: list[AnatomicalAccessibilityObservation] = Field(
        default_factory=list
    )
    accessibility_modulation: list[AccessibilityModulationObservation] = Field(
        default_factory=list
    )
    # A2 rollup (the A2 analog of ``SurfaceEvidence.evidence_grade``):
    # how well-characterized + internally consistent the biological-context
    # picture is, graded across the five A2 axes above. Emitted by the
    # ``biological_context_grade`` builder. Defaults so records predating the
    # rollup still validate.
    biological_context_grade: BiologicalContextGrade = "absent"
    grade_rationale: str = Field(
        default="",
        description="Why this biological_context_grade. Soft target ≤300 chars.",
    )
    grade_cited_evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _drop_legacy_cell_states(cls, data: Any) -> Any:
        """Schema 2.5.0 retired ``BiologicalContext.cell_states``. Old
        records (≤ 2.4.0) emit this field; absorb-on-load by dropping it
        so the record still parses. State content is permanently lost
        for those records — re-annotate to populate the corresponding
        single-context ``accessibility_modulation`` rows."""
        if isinstance(data, dict) and "cell_states" in data:
            dropped = data.pop("cell_states")
            if dropped:
                import warnings

                warnings.warn(
                    f"BiologicalContext: dropped {len(dropped)} legacy "
                    "cell_states row(s) on load (schema 2.5.0 merged "
                    "cell_states into accessibility_modulation). "
                    "Re-annotate to recover the state content as "
                    "single-context modulation rows.",
                    DeprecationWarning,
                    stacklevel=2,
                )
        return data


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
    # Amino-acid sequence this isoform's per_residue_topology indexes 1:1, so a
    # downstream consumer can do residue-level alignment without re-fetching
    # UniProt (A1.8). Nullable for records emitted before sequences were
    # populated.
    sequence: str | None = None
    tool_version: str
    retrieved_at: datetime
    # Sequence identity of an alternative isoform against this protein's own
    # canonical sequence (BLOSUM62 global alignment over the shared length;
    # see ``merge/isoform_identity.py``). Both fields are None on the
    # canonical row itself (it's the reference) and on isoforms predating the
    # identity sweep. ``ecd_pct_identity_to_canonical`` is additionally None
    # when either the canonical or the isoform has no extracellular residues.
    full_length_pct_identity_to_canonical: float | None = Field(default=None, ge=0.0, le=100.0)
    ecd_pct_identity_to_canonical: float | None = Field(default=None, ge=0.0, le=100.0)
    ecd_pct_similarity_to_canonical: float | None = Field(default=None, ge=0.0, le=100.0)
    # Full amino-acid sequence the ``per_residue_topology`` string above
    # aligns to (1:1, same length) — so a consumer can read which residue
    # each topology character refers to without a second UniProt fetch. The
    # record already ships the topology; the sequence it indexes was the
    # missing half. Sourced from ``topology_public.sequence`` (the exact
    # DeepTMHMM input). ``None`` on records built before this field existed,
    # or when the sweep didn't retain the input FASTA.
    sequence: str | None = Field(default=None)


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
    # Per-residue DeepTMHMM topology + categorical label for the
    # ortholog's canonical isoform. Sourced from ``topology_public``
    # filtered to ``cohort='mouse_ortholog'`` / ``cohort='cyno_ortholog'``.
    # Nullable because the candidate-set builder may include orthologs
    # whose DeepTMHMM run is still pending (or whose UniProt acc didn't
    # resolve in the sweep); the viewer's IsoformsCard renders a
    # placeholder when these are absent.
    per_residue_topology: str | None = Field(default=None)
    deeptmhmm_label: str | None = Field(default=None)  # 'TM' | 'SP+TM' | 'SP' | 'BETA' | 'GLOB'
    # Topology-projection provenance (merge.ortholog_topology_projection).
    # When set (``"projected_from_human_canonical"``), the per_residue_topology
    # / tm_helix_count / ecd_length_residues above are the HUMAN canonical
    # topology projected onto this ortholog via global alignment — not raw
    # DeepTMHMM-on-ortholog, which is unreliable on the truncated / padded
    # auto-annotated ortholog models (esp. cynomolgus TrEMBL). ``None`` on
    # rows that kept the raw DeepTMHMM values (projection not possible).
    topology_projection_source: str | None = Field(default=None)
    # True when a human TM helix aligned entirely to a gap in the ortholog
    # sequence (a truncated model) — the helix is conserved by homology but
    # physically absent from this model, so consumers should show "TM region
    # absent from model" rather than "topology diverged". ``n_tm_regions_absent``
    # is how many human helices fell in ortholog gaps.
    tm_absent_from_model: bool = False
    n_tm_regions_absent: int = 0
    # Amino-acid sequence the per_residue_topology indexes 1:1 (A1.8). Nullable
    # for records emitted before sequences were populated.
    sequence: str | None = None


class Orthologs(BaseModel):
    """Per-species ortholog isoform lists — canonical first, then alternatives."""

    model_config = ConfigDict(extra="forbid")

    mouse: list[OrthologEntry] = Field(default_factory=list)
    cynomolgus: list[OrthologEntry] = Field(default_factory=list)
    # Explicit "checked, none found" sentinel (mirrors
    # ``SurfaceBindFeatures.has_data``). ``False`` = this gene's orthologs were
    # never resolved (stub / D1 unreachable); ``True`` with empty mouse +
    # cynomolgus = checked against Ensembl Compara and no one2one ortholog
    # exists. Lets the viewer render "none found" instead of a placeholder.
    checked: bool = False


class ParalogEntry(BaseModel):
    """One within-species paralog — Ensembl Compara. Deterministic.

    ``ecd_pct_identity`` is ``None`` for ECD-less proteins (inner-leaflet
    kinases like SRC, soluble proteins, cytoplasmic enzymes) — there's
    no ECD to compute identity against. ``full_length_pct_identity`` is
    the whole-protein identity (Ensembl Compara / BioMart), which IS
    populated for those proteins, so the viewer can still color the
    antibody cross-reactivity risk tier for an ECD-less protein's paralogs
    by falling back to it (same ≥70 / 50–70 / <50 cutoffs, keyed on
    whole-protein homology rather than the extracellular surface). Family
    membership alone is still meaningful signal for the methods builder's
    antibody-validation discipline.
    """

    model_config = ConfigDict(extra="forbid")

    paralog_symbol: str
    paralog_uniprot_acc: str
    ecd_pct_identity: float | None = Field(default=None, ge=0.0, le=100.0)
    # Whole-protein percent identity vs the human canonical, straight from
    # Ensembl Compara's BioMart homology table (``compara_paralog.
    # biomart_percent_identity``) — same source as the ortholog full-length
    # identity (``compara_ortholog.percent_identity``), so the two are
    # directly comparable. Populated for ~all paralog pairs, INCLUDING
    # ECD-less proteins where ``ecd_pct_identity`` is None. ``None`` only on
    # records built before this field was surfaced by the deep-dive builder.
    full_length_pct_identity: float | None = Field(default=None, ge=0.0, le=100.0)
    family_id: str
    compara_version: str
    # (Per-residue DeepTMHMM topology was briefly added to this entry
    # in 6a220a90 and reverted shortly after: SRC's 32 paralogs are all
    # GLOB intracellular kinases, so the bars rendered as solid blue
    # with no signal. Isoform + ortholog topology are still surfaced
    # in §04 because those CAN show real TM patterns.)
    #
    # A1.9 re-adds topology + sequence, but GATED on close homology: only
    # paralogs at or above ``CLOSE_PARALOG_THRESHOLD`` ECD identity get these
    # populated — those are the ones a reader can actually reason about, and
    # the gate avoids the all-GLOB noise that motivated the earlier revert.
    # Nullable so far/ECD-less paralogs (and pre-population records) carry None.
    per_residue_topology: str | None = None
    tm_helix_count: int | None = None
    ecd_length_residues: int | None = None
    sequence: str | None = None


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
    # AlphaFold model download links from the AFDB prediction API. These are
    # the non-derivable bits: the working URL needs the current model
    # version, which only the API returns (``afdb_version`` above tracks it,
    # but the full cif/pdb/PAE URLs save the consumer reconstructing them).
    # ``None`` on the placeholder path (AFDB unreachable) and on records
    # built before the fields existed.
    model_cif_url: str | None = None
    model_pdb_url: str | None = None
    model_pae_url: str | None = None


class SurfaceBindSite(BaseModel):
    """One MaSIF-scored targetable patch on a SURFACE-Bind protein.

    Sourced from SURFACE-Bind's ``results_no_TM.csv`` per-site arrays
    (Balbi et al. 2026 PNAS). Each site is a surface patch the
    MaSIF scoring identified as designable for a de novo binder.

    Notes on the fields:

    * ``anchor_residue`` — the center residue of the MaSIF patch.
      SURFACE-Bind doesn't publish the full per-patch residue list
      in any programmatic endpoint; only this anchor. For 3D
      visualization, a viewer can highlight the anchor + nearby
      residues at render time.
    * ``area_a2`` — buried surface area in Å². The 1,103 ± 244 Å² band
      from antibody-antigen interfaces (Ramaraj 2012) gives one
      comparison point; SURFACE-Bind sites range much wider.
    * ``hydrophobicity`` — patch hydrophobicity score (Eisenberg-style
      scale). Positive = hydrophobic / lipid-facing-style; negative =
      polar / solvent-exposed-style. Sign + magnitude shape what
      binder chemistries pair well.
    """

    model_config = ConfigDict(extra="forbid")

    site_id: int = Field(..., ge=0)
    anchor_residue: int = Field(..., ge=1)
    area_a2: float = Field(..., ge=0.0)
    n_seeds_alpha: int = Field(..., ge=0)
    n_seeds_beta: int = Field(..., ge=0)
    hydrophobicity: float


# A1.9 — only paralogs at/above this ECD %identity get full topology +
# sequence populated; below it they carry identity only (a far paralog's
# topology is noise a reader can't act on).
CLOSE_PARALOG_THRESHOLD: float = 80.0


class RepresentativeStructure(BaseModel):
    """The single best experimental structure for a protein.

    Chosen from the PDBe SIFTS UniProt→PDB mapping by (coverage × resolution)
    so the reader gets "the experimental structure" with the metadata to judge
    it, instead of a flat list of PDB IDs with no ranking (A1.10).
    """

    model_config = ConfigDict(extra="forbid")

    pdb_id: str
    chain: str | None = None
    method: str | None = None  # e.g. "X-ray diffraction", "Electron Microscopy"
    resolution_angstrom: float | None = Field(default=None, ge=0.0)
    coverage_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    residue_start: int | None = None
    residue_end: int | None = None
    source: str = "PDBe SIFTS"


class SurfaceBindFeatures(BaseModel):
    """SURFACE-Bind per-UniProt summary (Balbi et al. 2026 PNAS).

    ``has_data=False`` is the explicit "not in SURFACE-Bind" signal —
    SURFACE-Bind's authoritative ``results_no_TM.csv`` table covers
    1,649 of the ~2,886 predicted surface proteins (loose ``seed_count``
    files contain ~2,529 entries but include unscored proteins). This
    block is always present so the catalog can distinguish "absent
    from SURFACE-Bind" from "present but un-scored" rather than
    collapsing both to null.

    Loaded by :func:`accessible_surfaceome.tools.surface_bind.lookup`
    from the checked-in summary JSON
    (``data/external/surface_bind/surface_bind_summary.json``) which
    is regenerated by ``scripts/build/build_surface_bind_summary.py``.
    """

    model_config = ConfigDict(extra="forbid")

    has_data: bool = False
    n_sites: int = Field(default=0, ge=0)
    n_seeds_alpha: int = Field(default=0, ge=0)
    n_seeds_beta: int = Field(default=0, ge=0)
    n_seeds_total: int = Field(default=0, ge=0)
    # PDB-chain identifier the SURFACE-Bind scoring was run against
    # (typically "A"; multi-chain UniProts kept the first chain).
    chain: str | None = None
    # Per-site detail. Empty list when ``has_data=False`` OR when the
    # protein is in SURFACE-Bind but with zero scored sites (rare;
    # GPR75 is one example — listed in seed_count files but with no
    # scored sites in the authoritative results_no_TM.csv).
    sites: list[SurfaceBindSite] = Field(default_factory=list)
    # SURFACE-Bind's own family / sub-family classification — useful
    # as a cross-check against our ``llm_family`` / ``subcategory``
    # but NOT what those fields are derived from.
    main_class: str | None = None
    sub_class: str | None = None
    # Human-readable protein-name (from UniProt via SURFACE-Bind's
    # join). May differ from our preferred display name; surface
    # for the deep-link readability.
    protein_name: str | None = None
    # PDB entries cross-referenced by SURFACE-Bind for this protein.
    # Often >100 entries for well-studied targets (EGFR has 250+);
    # truncated in the viewer to the first few. Kept as the raw list; the
    # ranked single pointer is ``representative_structure`` below (A1.10).
    pdbs: list[str] = Field(default_factory=list)
    # The one best experimental structure (highest coverage × resolution),
    # ranked from ``pdbs`` via PDBe SIFTS. Nullable: no PDB entries, or a
    # record emitted before the structure ranker was wired.
    representative_structure: RepresentativeStructure | None = None
    source: str = "SURFACE-Bind v1 (Balbi 2026 PNAS)"
    attribution: str = (
        "© Balbi et al., Correia lab — EPFL / Inria / Novo Nordisk"
    )
    citation: str = "10.1073/pnas.2506269123"


class HomoOligomerizationFeatures(BaseModel):
    """Schweke et al. 2024 AF2 homo-oligomer prediction (PMID 38325366).

    Schweke's atlas covers four proteomes; the human refset is ~3,946
    predicted homo-oligomers — a protein is a "candidate complex" when
    its AF2 homodimer interface clears a logistic-regression
    ``dimer_proba`` threshold. ~1,049 of the v2 candidate-universe
    surfaceome proteins are flagged as Schweke homomers (memory entry
    ``schweke-homomer-atlas``).

    The lookup is positives-only — Schweke's refset doesn't carry
    explicit negatives, so ``is_homo_oligomer=False`` means "not in the
    positive set" rather than "AF2 explicitly disagrees". This is a
    well-documented under-call: big multi-pass channels (KCNQ1, KCNMA1)
    and ligand/covalent dimers (EGFR, INSR) are missing despite being
    known dimers. Treat as a lower bound when piped into the synthesizer
    as a prior on ``epitope_masking.mechanism = "homo-oligomerization"``.

    The synthesizer should consult this block when deciding whether to
    emit a ``homo-oligomerization`` epitope-masking mechanism: a True
    here is a strong AF2-derived structural prior; a False is a soft
    "no positive prediction" — still allow the literature to override.

    Loaded by :func:`accessible_surfaceome.tools.schweke_homomer.lookup`.
    """

    model_config = ConfigDict(extra="forbid")

    # ``False`` is the explicit "not in Schweke's positive refset"
    # signal — analogous to :attr:`SurfaceBindFeatures.has_data`. The
    # block is always present so the catalog can distinguish "absent
    # from Schweke" from "in Schweke but no usable model" rather than
    # collapsing both to null.
    is_homo_oligomer: bool = False
    # Cyclic-symmetry order N of the predicted complex (2 for an
    # AF_dimer_models_core dimer; 3..13 for an AnAnaS-reconstructed
    # full complex from full_complexes_bigbang). ``None`` when
    # ``is_homo_oligomer=False`` OR when Schweke flagged the protein
    # as a dimer but didn't reconstruct higher-order. The synthesizer
    # weights epitope-masking severity by N (a 13-mer hides far more
    # surface than a 2-mer).
    stoichiometry: int | None = Field(default=None, ge=2, le=24)
    # AF2 model rank (1..5) Schweke retained as the canonical homomer
    # model. Carried so the viewer can construct the static-asset PDB
    # URL (``{ACC}_V1_{N}.pdb``) without consulting a separate manifest.
    # ``None`` when ``is_homo_oligomer=False``.
    af_model_num: int | None = Field(default=None, ge=1, le=5)
    # ``True`` iff Schweke's ``nodiso3`` contact-clustering filter
    # stripped the TM helix as a disconnected cluster — the predicted
    # homomer model is ECD-only. Important context for the synthesizer's
    # epitope-masking prior: an ECD-only dimer means the soluble ECD is
    # the dimerizing surface (which IS the epitope-accessible region),
    # while a full-membrane homomer might be a membrane-resident
    # oligomer with a different epitope-burial pattern.
    is_ecd_only: bool = False
    # ``True`` iff Schweke published a higher-order complex (c≥3) for
    # this protein in addition to the dimer model. Mirrors the
    # ``schweke_homomer_public.has_higher_order_complex`` column.
    has_higher_order_complex: bool = False
    # PDB filenames carried from D1 so the viewer can construct asset
    # URLs without a local manifest. ``dimer_pdb_filename`` is always
    # present for a Schweke homomer ({ACC}_V1_{N}.pdb);
    # ``complex_pdb_filename`` is the AnAnaS-reconstructed higher-order
    # complex ({ACC}_V1_{N}_c{stoichiometry}.pdb) — ``None`` for
    # dimer-only entries. The viewer fetches these from
    # ``/data/structures/schweke/`` and gracefully falls back when the
    # asset isn't yet ingested.
    dimer_pdb_filename: str | None = None
    complex_pdb_filename: str | None = None
    source: str = "Schweke 2024 (PMID 38325366)"
    citation: str = "10.1016/j.cell.2024.01.022"


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
    # "Checked, none found" sentinels for the bare lists above (same rationale
    # as ``Orthologs.checked``). ``True`` once the loader has queried D1 for
    # this gene even when the list came back empty (genuine singleton /
    # single-isoform gene); ``False`` on stub / never-checked records.
    paralogs_checked: bool = False
    isoform_topologies_checked: bool = False
    structure: StructureFeatures
    # SURFACE-Bind summary (Balbi et al. 2026 PNAS); always present, with
    # ``has_data=False`` as the explicit "not scored" signal for the
    # ~12% of surfaceome proteins SURFACE-Bind omitted.
    surface_bind: SurfaceBindFeatures = Field(default_factory=SurfaceBindFeatures)
    # Schweke 2024 AF2 homo-oligomer prediction (PMID 38325366); always
    # present, with ``is_homo_oligomer=False`` as the explicit "not in the
    # positive set" signal. Strong AF2-derived structural prior on the
    # synthesizer's ``epitope_masking.mechanism = "homo-oligomerization"``
    # call (memory: schweke-homomer-atlas).
    homo_oligomerization: HomoOligomerizationFeatures = Field(
        default_factory=HomoOligomerizationFeatures
    )


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
    rationale: str = Field(
        default="",
        description=(
            "Why this shed-form call - name the proteolysis evidence "
            "(sheddase identity, ectodomain release assay, serum/supernatant "
            "detection of the soluble target), cell type, and decoy-behavior "
            "evidence when graded above weak, with inline "
            "(a1_evi_NN)/(a2_evi_NN) cites per claim. Soft target "
            "<=300 chars (overshoots warned but accepted). Defaults to "
            '"" for backward-compat with legacy records loaded from '
            "D1 / on-disk snapshots that pre-date this field; new annotator "
            "runs must fill it."
        ),
    )
    cited_evidence_ids: list[str] = Field(default_factory=list)

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {"rationale": 300}

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> "ShedForm":
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self


class SecretedForm(BaseModel):
    """Secreted (non-membrane-anchored) form of the protein."""

    model_config = ConfigDict(extra="forbid")

    present: bool
    severity: RiskSeverity
    evidence_strength: EvidenceStrength
    ratio_to_membrane: float | None = None
    source: SecretedFormSource | None = None
    rationale: str = Field(
        default="",
        description=(
            "Why this secreted-form call - name the soluble-protein evidence "
            "(serum / plasma quantification, alternative splicing producing a "
            "TM-less isoform, documented antibody-decoy competition), cell "
            "type / sample, and the decoy-behavior evidence when graded above "
            "weak, with inline (a1_evi_NN)/(a2_evi_NN) cites per claim. "
            "Soft target <=300 chars (overshoots warned but accepted). Defaults "
            'to "" for backward-compat with legacy records loaded from D1 '
            "/ on-disk snapshots that pre-date this field; new annotator runs "
            "must fill it."
        ),
    )
    cited_evidence_ids: list[str] = Field(default_factory=list)

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {"rationale": 300}

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> "SecretedForm":
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self


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


def classify_ecd_accessibility_class(
    ecd_length_residues: int | None,
) -> ECDAccessibilityClass:
    """Canonical deterministic ECD-size classifier.

    These thresholds are the **single source of truth** for
    ``ecd_accessibility_class`` — the v2 orchestrator applies them to the
    deterministic
    ``deterministic_features.canonical_topology.ecd_length_residues`` after
    synthesis, overwriting whatever the synthesizer emitted. The synthesizer
    prompt documents the same numbers (for the model's awareness only); they
    are enforced here in code, not by LLM judgment, so there is no literature
    override.

    Threshold table (residue count → class):

    * ``None`` or ``0`` → ``"none"``   (no surface-exposed ECD)
    * ``< 30``          → ``"minimal"``
    * ``30 <= n < 60``  → ``"small"``
    * ``60 <= n < 200`` → ``"moderate"``
    * ``>= 200``        → ``"large"``

    ``None`` is treated identically to ``0`` (no ECD): a record without a
    deterministic ECD length has no surface to host a binder.
    """
    if ecd_length_residues is None or ecd_length_residues == 0:
        return "none"
    if ecd_length_residues < 30:
        return "minimal"
    if ecd_length_residues < 60:
        return "small"
    if ecd_length_residues < 200:
        return "moderate"
    return "large"


class ECDSizeAssessment(BaseModel):
    """How much extracellular surface a binder has to engage.

    Renamed from ``druggability_class``. The viewer reads
    ``deterministic_features.canonical_topology.ecd_length_residues``
    directly — no FK needed since that field is a known singleton.
    """
    # NOTE: ``ecd_accessibility_class`` is deterministic — the v2 orchestrator
    # overwrites this block post-synthesis via
    # ``classify_ecd_accessibility_class`` (single source of truth, no LLM
    # override). Kept as a code comment, not a class docstring, because the
    # docstring becomes the JSON-schema ``description`` and would churn the
    # SurfaceomeRecord schema fingerprint for a non-structural change.

    model_config = ConfigDict(extra="forbid")

    ecd_accessibility_class: ECDAccessibilityClass
    rationale: str = Field(
        ...,
        description="Why this ECD-size class. Soft target ≤300 chars (overshoots warned but accepted).",
    )
    cited_evidence_ids: list[str] = Field(default_factory=list)

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {"rationale": 300}

    classify = staticmethod(classify_ecd_accessibility_class)

    @model_validator(mode="after")
    def _warn_soft_target_overshoot(self) -> "ECDSizeAssessment":
        _warn_prose_overshoot(self, type(self)._PROSE_TARGETS)
        return self


class EpitopeMasking(BaseModel):
    """Whether the extracellular epitope is masked from binders.

    ``mechanism`` is a list so multi-mechanism cases don't collapse to a
    single value. It spans three masking axes: HOMO self-association
    (``oligomerization``), HETERO partner/complex coverage (``partner``),
    and other monomer-level causes (``glycan`` / ``conformational`` /
    ``cleaved``).
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


class HomoOligomerizationPredictionRisk(BaseModel):
    """Risk-side view of the Schweke 2024 AF2 homo-oligomer prediction.

    Mirrors ``deterministic_features.homo_oligomerization`` (Schweke 2024,
    PMID 38325366) as a structured *risk* chip so the viewer can render it
    alongside ``epitope_masking`` without conflating the two. The synthesizer
    already consults the deterministic block when choosing the
    ``homo-oligomerization`` mechanism for ``epitope_masking``; this field
    is the **deterministic, orchestrator-populated** counterpart — a separate
    AF2-derived signal a reader can scan independently from the LLM call.

    Severity is derived from cyclic-symmetry order N:

    * ``stoichiometry <= 2`` → ``low`` (a dimer hides relatively little
      surface),
    * ``3..7`` → ``moderate``,
    * ``8..24`` → ``high`` (large complexes bury substantial surface),
    * ``None`` (Schweke didn't reconstruct higher-order or
      ``present=False``) → ``unknown``.

    Populated by the v2 orchestrator post-pass (`_attach_homo_oligomerization_prediction`)
    from ``deterministic_features.homo_oligomerization``. The synthesizer
    never emits this — keeping it orchestrator-only mirrors the
    ``_attach_deterministic_families`` pattern and prevents the agent from
    smuggling a competing AF2 call into the draft.
    """

    model_config = ConfigDict(extra="forbid")

    # ``True`` iff Schweke flagged the protein in the positive refset.
    # Mirrors ``HomoOligomerizationFeatures.is_homo_oligomer``.
    present: bool = False
    # Cyclic-symmetry order N from Schweke's atlas. ``None`` when
    # ``present=False`` or Schweke flagged the protein as a dimer but
    # didn't reconstruct higher-order.
    stoichiometry: int | None = Field(default=None, ge=2, le=24)
    # Severity derived from N — the viewer reads it directly for the
    # chip color. See class docstring for the mapping.
    severity: RiskSeverity = "unknown"
    # Schweke ``nodiso3`` flag: the predicted homomer is ECD-only (the
    # TM helix was stripped as a disconnected cluster). Important
    # context — an ECD-only dimer means the soluble ECD is the
    # dimerizing surface, which IS the epitope-accessible region.
    is_ecd_only: bool = False
    source: str = "Schweke 2024 (PMID 38325366)"
    # Empty by default — this is a deterministic AF2 prediction, not a
    # literature-anchored claim. Kept for shape consistency with the
    # other accessibility-risk blocks so the viewer / markdown
    # renderers can iterate uniformly.
    cited_evidence_ids: list[str] = Field(default_factory=list)


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
    # Deterministic AF2 homo-oligomer prediction (Schweke 2024) rendered
    # as a sibling chip to ``epitope_masking``. ``None`` (the default) on
    # records emitted before this field existed — back-compat.
    # **Orchestrator-populated only.** The synthesizer never emits this;
    # the v2 orchestrator post-pass copies it from
    # ``deterministic_features.homo_oligomerization``.
    homo_oligomerization_prediction: HomoOligomerizationPredictionRisk | None = None


# ---- triage_signal ↔ surface_accessibility consistency --------------------

# Cross-agent coherence: when the triage verdict and the deep-dive
# ``surface_accessibility`` class point in OPPOSITE directions, that is a
# disagreement the LLM must justify in ``confidence_reasoning``. We don't
# hard-reject the disagreement (the deep-dive can legitimately overturn
# triage) — we require the record to carry an explanation. The synthesizer
# prompt promises ANY cross-agent disagreement is gated, so we enumerate
# every opposing (triage, accessibility) pair rather than only the strongest
# one (the historical ``unlikely``↔``high`` case).
#
# "Opposing" = the two agents lean to opposite ends of the accessibility
# scale:
#   * triage ``unlikely`` (surface-UNlikely) vs deep-dive a strongly
#     ACCESSIBLE class (``high`` / ``moderate``); and
#   * triage ``likely_accessible`` (likely-surface) vs deep-dive an
#     INACCESSIBLE / none class (``no`` / ``low``).
# Neutral / uncertain pairings do NOT fire: ``possibly_accessible`` and
# ``unknown`` are weak/no-signal on the triage side, ``uncertain`` is
# no-signal on the deep-dive side, and same-direction pairs (e.g.
# ``unlikely``↔``low``, ``likely_accessible``↔``high``) agree.
_TRIAGE_ACCESSIBILITY_CONFLICT: dict[str, frozenset[str]] = {
    "unlikely": frozenset({"high", "moderate"}),
    "likely_accessible": frozenset({"no", "low"}),
}


def _validate_triage_signal_consistency(
    triage_signal: str,
    surface_accessibility: str,
    confidence_reasoning: str,
) -> None:
    """Flag triage ↔ deep-dive disagreement that lacks a written justification.

    Raises ``ValueError`` when ``triage_signal`` points in the opposite
    direction from ``executive_summary.surface_accessibility`` and
    ``confidence_reasoning`` is empty — the LLM must explain the disagreement.
    """

    conflicting = _TRIAGE_ACCESSIBILITY_CONFLICT.get(triage_signal, frozenset())
    if surface_accessibility in conflicting and not confidence_reasoning.strip():
        raise ValueError(
            f"triage_signal={triage_signal!r} conflicts with "
            f"surface_accessibility={surface_accessibility!r}; the disagreement must "
            "be justified in a non-empty confidence_reasoning"
        )


# ---- cross-block coherence validators ------------------------------------
#
# These enforce that the v2 block-builders' outputs are internally
# coherent. The synthesizer is supposed to keep its claims aligned with
# the builders' structured output, but until v2.4.0 nothing in the schema
# stopped a record like ``evidence_grade='direct_multi_method'`` paired
# with an empty ``methods=[]`` from validating — the synthesizer could
# write a prose-level claim that no MethodObservation backed. Each helper
# below is exposed for both ``SurfaceomeRecord`` and ``SurfaceomeRecordDraft``
# so the agent's draft fails at synthesis time rather than at final
# assembly.


def _validate_evidence_grade_methods_cardinality(
    evidence_grade: str,
    methods: list["MethodObservation"],
) -> None:
    """``evidence_grade`` must have the methods support it claims.

    * ``direct_multi_method`` ⇒ ≥2 ``MethodObservation`` entries with
      ``accessibility_relevance='direct_surface_accessibility'`` and
      those entries cite ≥2 distinct ``evidence_id`` sources. ("Multi-
      method" requires at least two independent sources, not two
      observations from the same paper.)
    * ``direct_single_method`` ⇒ ≥1 such entry. The prompt allows "all
      direct observations from a single source," so source diversity is
      not required.
    * Other grades (``supportive_but_indirect``, ``conflicting``,
      ``weak``) impose no methods cardinality — they explicitly describe
      cases where the methods evidence is partial / indirect / absent.
    """
    if evidence_grade not in ("direct_multi_method", "direct_single_method"):
        return
    direct = [
        m for m in methods
        if m.accessibility_relevance == "direct_surface_accessibility"
    ]
    if evidence_grade == "direct_single_method":
        if not direct:
            raise ValueError(
                "evidence_grade='direct_single_method' requires at least one "
                "MethodObservation with "
                "accessibility_relevance='direct_surface_accessibility'; "
                "surface_evidence.methods has none. Either downgrade the "
                "grade or add the direct-method evidence."
            )
        return
    # direct_multi_method
    if len(direct) < 2:
        raise ValueError(
            "evidence_grade='direct_multi_method' requires at least 2 "
            "MethodObservations with "
            "accessibility_relevance='direct_surface_accessibility'; "
            f"surface_evidence.methods has {len(direct)}. Either "
            "downgrade the grade or add another direct-method observation."
        )
    distinct_sources: set[str] = set()
    for m in direct:
        distinct_sources.update(m.cited_evidence_ids or [])
    if len(distinct_sources) < 2:
        raise ValueError(
            "evidence_grade='direct_multi_method' requires direct-method "
            "observations from at least 2 distinct sources "
            f"(cited_evidence_ids). Found {len(direct)} direct methods "
            f"covering only {len(distinct_sources)} source(s) "
            f"({sorted(distinct_sources)}). Either downgrade to "
            "direct_single_method or cite an independent second source."
        )


# Compartments + dual-localization labels that count as secretory-pathway
# corroboration for ``secreted_form.present=True``. Loose string match on
# DualLocalization.compartment since the field is free-text (with a
# canonical-token validator) rather than a closed enum.
_SECRETORY_PRIMARY_COMPARTMENTS: frozenset[str] = frozenset({"secreted"})
_SECRETORY_DUAL_LABELS: frozenset[str] = frozenset(
    {
        "secreted",
        "extracellular",
        "supernatant",
        "serum",
        "plasma",
        "er",
        "endoplasmic_reticulum",
        "endoplasmic reticulum",
        "golgi",
        "secretory_vesicle",
    }
)


def _validate_secreted_form_corroboration(
    secreted_form: "SecretedForm",
    subcellular_localization: "SubcellularLocalization",
    methods: list["MethodObservation"],
) -> None:
    """``accessibility_risks.secreted_form.present=True`` must be backed
    by at least one of:

      a) ``cited_evidence_ids`` on the ``SecretedForm`` itself (the
         synthesizer pointed to specific ledger entries),
      b) a secretory-pathway compartment in
         ``biological_context.subcellular_localization`` (primary or
         dual),
      c) a fractionation / glycoproteomics method in
         ``surface_evidence.methods`` (``accessibility_relevance=
         supports_membrane_association``).

    A record claiming a secreted form with none of these is structurally
    unbacked — the synthesizer prose may sound right, but downstream
    consumers (the catalog, the viewer's risk chip) read this as a hard
    risk signal and the absence of any backing is the signature pattern
    of a hallucinated risk."""
    if not secreted_form.present:
        return
    # (a) explicit citation — accept
    if secreted_form.cited_evidence_ids:
        return
    # (b) subcellular_localization corroboration
    if (
        subcellular_localization.primary_compartment
        in _SECRETORY_PRIMARY_COMPARTMENTS
    ):
        return
    for dual in subcellular_localization.dual_localization:
        compartment = (dual.compartment or "").strip().lower()
        if compartment in _SECRETORY_DUAL_LABELS:
            return
    # (c) fractionation / glycoproteomics method evidence
    for m in methods:
        if m.accessibility_relevance == "supports_membrane_association":
            return
    raise ValueError(
        "accessibility_risks.secreted_form.present=True but no "
        "corroboration: SecretedForm.cited_evidence_ids is empty AND "
        "biological_context.subcellular_localization has no secretory "
        "compartment (primary or dual) AND surface_evidence.methods has "
        "no supports_membrane_association entry. Either cite a ledger "
        "evidence_id, add a secretory dual_localization, include a "
        "fractionation method, or set secreted_form.present=False."
    )


def _is_headline_risk_backed(headline: str, risks: "AccessibilityRisks") -> bool:
    """True iff ``headline`` corresponds to a non-trivially-present sub-block
    in ``risks``. ``isoform_decoy`` has no dedicated risk sub-block — the
    synthesizer's prose carries it — so it always passes here. Unknown
    headline values also pass (forward-compat)."""
    if headline == "shed_form":
        return risks.shed_form.present
    if headline == "secreted_form":
        return risks.secreted_form.present
    if headline == "co_receptor":
        return risks.co_receptor_requirements.surface_expression_dependency in (
            "required",
            "modulatory",
        )
    if headline == "epitope_masked":
        return risks.epitope_masking.severity in ("low", "moderate", "high")
    return True


def _validate_headline_risks_match_present_risks(
    headline_risks: list[str],
    risks: "AccessibilityRisks",
) -> None:
    """Each ``headline_risks`` entry must correspond to a present
    ``accessibility_risks`` sub-block. The orchestrator post-pass already
    SCRUBS unbacked entries (``scrub_headline_risks`` in orchestrator.py)
    so this is a belt-and-suspenders check that fires at the schema
    level — even if the orchestrator post-pass is skipped (e.g. a stub
    annotate path), a record can never persist with an unbacked
    headline."""
    unbacked = [h for h in headline_risks if not _is_headline_risk_backed(h, risks)]
    if unbacked:
        raise ValueError(
            f"executive_summary.headline_risks={headline_risks} contains "
            f"entries with no backing in accessibility_risks: {unbacked}. "
            "Either remove the unbacked entries from headline_risks or "
            "update the corresponding sub-block "
            "(shed_form.present / secreted_form.present / "
            "epitope_masking.severity / "
            "co_receptor_requirements.surface_expression_dependency)."
        )


# ---- assembled record + agent draft ---------------------------------------


class SurfaceomeRecord(BaseModel):
    """The reconciled per-protein surface-accessibility record (v1.0.0).

    Persisted to ``data/annotations/{gene}.json``. Two structurally separated
    regions — ``deterministic_features`` (orchestrator-populated tool output)
    and the LLM-synthesis blocks. Field order mirrors the viewer mockup.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "1.0.0", "1.1.0", "2.0.0", "2.1.0", "2.2.0", "2.3.0", "2.4.0", "2.4.1",
        "2.5.0", "2.6.0", "2.7.0", "2.8.0", "2.9.0", "2.10.0", "2.11.0", "2.12.0",
        "2.13.0",
    ] = "2.13.0"
    # The prompt corpus version active when this record was synthesized.
    # Default ``""`` for backward-compat with legacy records loaded from D1
    # / on-disk snapshots that pre-date this field; new annotator runs stamp
    # it from ``_version_guard.PROMPT_CORPUS_VERSION`` at synthesis time so
    # post-cohort forensic queries ("which prompt corpus produced this call?")
    # can join on the record itself, not just on the D1 mirror column.
    prompt_corpus_version: str = ""
    gene: GeneIdentifier

    # Cross-agent coherence — populated by the orchestrator from the most
    # recent surface_triage record.
    triage_signal: TriageSignal = "unknown"
    # The triage agent's prose justification for its verdict (the
    # ``verdict_reasoning`` field on the upstream ``TriageRecord``). Loaded
    # by the orchestrator alongside ``triage_signal`` — the triage record is
    # already fetched to derive the signal, so this carries no extra cost —
    # and surfaced verbatim in the viewer's Triage row so the reader can see
    # WHY the initial no-web-search pass called it the way it did, distinct
    # from the deep-dive ``confidence_reasoning``. ``None`` (the default)
    # when no triage record exists for the gene, so records generated before
    # this field existed validate unchanged.
    triage_reasoning: str | None = None

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

    @model_validator(mode="after")
    def _check_secreted_form_corroboration(self) -> SurfaceomeRecord:
        _validate_secreted_form_corroboration(
            self.accessibility_risks.secreted_form,
            self.biological_context.subcellular_localization,
            self.surface_evidence.methods,
        )
        return self

    @model_validator(mode="after")
    def _check_headline_risks_match_present_risks(self) -> SurfaceomeRecord:
        _validate_headline_risks_match_present_risks(
            list(self.executive_summary.headline_risks),
            self.accessibility_risks,
        )
        return self

    @model_validator(mode="after")
    def _check_state_dependence_consistent_with_modulation(
        self,
    ) -> SurfaceomeRecord:
        """Refuse ``state_dependence='low'`` when the biology shows
        state-conditional upregulation of the surface form.

        ``state_dependence`` captures how much the targetable surface
        fraction VARIES by state. ``low`` means "essentially the same
        across observed contexts." That is incompatible with the
        evidence patterns flagged below — picking ``low`` when the
        ledger carries oncogenic-induction or repeated "increases"
        modulation rows erases the very signal the catalog reader is
        filtering for (the TROP2-class miscalibration the synth made
        for this gene: state_dependence='low' alongside 10 increases-
        direction modulation rows + induction_trigger='oncogenic').

        Conditions that forbid ``state_dependence='low'``:
          * ``filters.induction_trigger != 'none'`` — the synth's own
            rollup says there IS a dominant induction trigger.
          * ``accessibility_modulation`` has ≥3 rows with
            ``direction='increases'`` — multiple independent
            observations of the surface form going up under some state.
          * any ``accessibility_modulation`` row carries
            ``cell_state_trigger='oncogenic_transformation'`` with
            ``direction='increases'`` AND the call isn't
            ``surface_accessibility='no'`` — the textbook tumor-induced
            overexpression case.

        ``tumor_associated=True`` is intentionally NOT in the gate —
        that flag means "found on tumors" (could be constitutive
        expression in tumor tissue without state-induction); the
        actual state-induction signal lives in
        ``induction_trigger`` and the modulation rows.
        """
        if self.executive_summary.state_dependence != "low":
            return self

        modulation = self.biological_context.accessibility_modulation
        n_increases = sum(1 for m in modulation if m.direction == "increases")
        has_oncogenic_increase = any(
            m.cell_state_trigger == "oncogenic_transformation"
            and m.direction == "increases"
            for m in modulation
        )
        sa = self.executive_summary.surface_accessibility
        induction = self.filters.induction_trigger

        violations: list[str] = []
        if induction != "none":
            violations.append(
                f"filters.induction_trigger={induction!r} (≠ 'none')"
            )
        if n_increases >= 3:
            violations.append(
                f"{n_increases} accessibility_modulation rows have "
                f"direction='increases'"
            )
        if has_oncogenic_increase and sa != "no":
            violations.append(
                "an accessibility_modulation row has "
                "cell_state_trigger='oncogenic_transformation' with "
                f"direction='increases' alongside surface_accessibility={sa!r}"
            )

        if violations:
            raise ValueError(
                "executive_summary.state_dependence='low' is incompatible "
                "with the A2 biology: "
                + "; ".join(violations)
                + ". The targetable surface fraction is state-conditional — "
                "pick at least state_dependence='moderate' so the catalog "
                "reader sees the gating."
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

    schema_version: Literal[
        "1.0.0", "1.1.0", "2.0.0", "2.1.0", "2.2.0", "2.3.0", "2.4.0", "2.4.1",
        "2.5.0", "2.6.0", "2.7.0", "2.8.0", "2.9.0", "2.10.0", "2.11.0", "2.12.0",
        "2.13.0",
    ] = "2.13.0"
    # The prompt corpus version active when this record was synthesized.
    # Default ``""`` for backward-compat with legacy records loaded from D1
    # / on-disk snapshots that pre-date this field; new annotator runs stamp
    # it from ``_version_guard.PROMPT_CORPUS_VERSION`` at synthesis time so
    # post-cohort forensic queries ("which prompt corpus produced this call?")
    # can join on the record itself, not just on the D1 mirror column.
    prompt_corpus_version: str = ""
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

    @model_validator(mode="after")
    def _check_secreted_form_corroboration(self) -> SurfaceomeRecordDraft:
        _validate_secreted_form_corroboration(
            self.accessibility_risks.secreted_form,
            self.biological_context.subcellular_localization,
            self.surface_evidence.methods,
        )
        return self

    @model_validator(mode="after")
    def _check_headline_risks_match_present_risks(self) -> SurfaceomeRecordDraft:
        _validate_headline_risks_match_present_risks(
            list(self.executive_summary.headline_risks),
            self.accessibility_risks,
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
        for contradiction in se.contradicting_evidence:
            cited.update(contradiction.cited_evidence_ids)
        # claim_stances rows each name one claim_id directly (not in
        # a cited_evidence_ids list) — fold their ids into the same
        # cross-check so an LLM that fabricates a claim_id in the
        # stance map fails fast at parse time.
        for stance_row in se.claim_stances:
            cited.add(stance_row.claim_id)
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
        for row in bc.expression:
            cited.update(row.cited_evidence_ids)
        for tissue in bc.tissues:  # deprecated v1 path
            cited.update(tissue.cited_evidence_ids)
        for cell_type in bc.cell_types:  # deprecated v1 path
            cited.update(cell_type.cited_evidence_ids)
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
    """The four ``filters`` rollups B is responsible for, each with its
    one-line rationale.

    The full :class:`Filters` block has 17 value fields; 14 of those are
    orchestrator-derived from A1/A2 deep blocks and ``deterministic_features``.
    B emits the rollups that don't have a deterministic source — surface vs.
    intracellular split, expression breadth across tissues, expression level
    for the protein's primary contexts, and orphan-ligand status — plus a
    short ``*_rationale`` for each so every catalog chip carries its "why".
    The orchestrator composes the full :class:`Filters` after the fact,
    mirroring these rationales onto the top-level block.
    """

    model_config = ConfigDict(extra="forbid")

    expression_level: ExpressionLevel
    expression_level_rationale: str = Field(
        ...,
        description="Why this expression_level. Cite the dominant tissue/context the call anchors to. Soft target ≤300 chars.",
    )
    expression_breadth: ExpressionBreadth
    expression_breadth_rationale: str = Field(
        ...,
        description="Why this expression_breadth — how many / which tissue families carry the protein. Soft target ≤300 chars.",
    )
    surface_specificity: SurfaceSpecificity
    surface_specificity_rationale: str = Field(
        ...,
        description="Why this surface-vs-intracellular split (e.g. dual-localization fractions, dominant compartment). Soft target ≤300 chars.",
    )
    # Orphan-receptor flag. Replaces the dropped
    # ``HeadlineRisk.ligand_unknown`` value — moved here so the
    # catalog can filter on ligand-known-or-not as a tractability
    # signal. Defaults to ``True`` (most surface proteins have a
    # validated endogenous ligand); the synthesizer flips it to
    # ``False`` for orphan GPCRs / nuclear receptors / kinases where
    # the deorphanization status is genuinely unknown.
    has_known_ligand: bool = True
    # A1.6 — one-line "why" per LLM-rollup chip, each with inline
    # ``(a1_evi_NN)`` / ``(a2_evi_NN)`` cites so the chip is self-auditable.
    # Optional default "" (v1-safe); a warn-only validator flags a non-empty
    # rationale that omits any inline cite (A8.2) — it warns rather than raises
    # because the synthesizer is a Managed Agent with no in-process repair loop.
    expression_level_rationale: str = ""
    expression_breadth_rationale: str = ""
    surface_specificity_rationale: str = ""
    has_known_ligand_rationale: str = ""

    @field_validator(
        "expression_level_rationale",
        "expression_breadth_rationale",
        "surface_specificity_rationale",
        "has_known_ligand_rationale",
    )
    @classmethod
    def _warn_rationale_missing_cite(cls, v: str) -> str:
        if v and not _has_inline_evi_cite(v):
            logger.warning(
                "SynthesizerLLMFilters rationale lacks an inline (a1_evi_NN)/"
                "(a2_evi_NN) cite: %r",
                v,
            )
        return v

    @model_validator(mode="after")
    def _require_has_known_ligand_rationale_when_true(
        self,
    ) -> SynthesizerLLMFilters:
        """``has_known_ligand=True`` requires a non-empty rationale.

        Catches the TROP2-class miscalibration: the synth flipped the
        bool to ``True`` (its default) but left
        ``has_known_ligand_rationale`` empty, so the catalog reader
        has no way to verify which ligand grounds the claim. If the
        ligand can't be named, the bool should be ``False`` (orphan-
        receptor case) — empty strings are not a valid third state.

        Warn-only on missing inline cite stays above; this validator
        is the harder backstop on the boolean half of the flag.
        """
        if self.has_known_ligand and not self.has_known_ligand_rationale.strip():
            raise ValueError(
                "has_known_ligand=True requires a non-empty "
                "has_known_ligand_rationale naming the ligand. If the "
                "ligand identity is genuinely unknown, set "
                "has_known_ligand=False (orphan-receptor case) and "
                "explain in the rationale."
            )
        return self


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
# NOTE: ``TriageModelPath`` was removed when the loader started threading
# the actual D1 row's model + prompt_variant via :class:`TriageProvenance`.
# The closed enum couldn't carry model version (4.5 vs 4.6 vs 4.7) or
# prompt variant, both of which the synthesizer needs to weight the prior.
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


class TriageProvenance(BaseModel):
    """Where a persisted TriageRecord actually came from.

    Populated when the record was hydrated from D1's ``triage_run_public``
    table; ``None`` when the record came from a local ``data/triage/{gene}.json``
    file or was emitted in-process by the triage agent. The synthesizer
    reads ``model`` + ``prompt_variant`` to weight the prior (a high-confidence
    Sonnet ``ncbi`` verdict is a stronger prior than a Haiku one, and a
    non-canonical variant choice is worth surfacing in confidence_reasoning).

    Replaces the prior ``TriageModelPath`` closed enum, which couldn't
    carry model version (4.5 vs 4.6 vs 4.7) or prompt_variant — both
    needed to calibrate the prior correctly.
    """

    model_config = ConfigDict(extra="forbid")

    model: str = Field(
        ...,
        description="Exact model identifier from D1 (e.g. 'claude-sonnet-4-6').",
    )
    prompt_variant: str = Field(
        ...,
        description="Triage prompt variant (e.g. 'ncbi', 'web_ncbi', 'naive').",
    )
    run_id: str = Field(
        ...,
        description="D1 run_id (e.g. 'mainbench_canonical_v1').",
    )
    replicate: int | None = Field(
        default=None,
        description="Replicate index from the sweep; None when not recorded.",
    )


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
        description="Why this triage verdict. Soft target ≤1250 chars (overshoots warned but accepted). Floor set from the empirical distribution on the 2026-05-12 mainbench Sonnet ncbi sweep (147 cells): median 956, p99 1199, max 1221. Catches genuine multi-thousand-char outliers without flagging the typical case.",
    )
    reason: TriageReason
    confidence: TriageConfidence
    key_uncertainty: str | None = Field(
        default=None,
        description="The most important uncertainty. Soft target ≤300 chars (overshoots warned but accepted). Floor set from the empirical distribution (Sonnet ncbi 2026-05-12 sweep): p90 250, max 267.",
    )

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {
        # Caps set from empirical distribution of 147 Sonnet ncbi cells
        # in the 2026-05-12 mainbench sweep: verdict_reasoning median
        # 956 / p99 1199 / max 1221; key_uncertainty p90 250 / max 267.
        # Old caps (800 / 200) fired on 80% / 37% of rows respectively.
        "verdict_reasoning": 1250,
        "key_uncertainty": 300,
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
        description="Why this triage verdict. Soft target ≤1250 chars (overshoots warned but accepted). Floor set from the empirical distribution on the 2026-05-12 mainbench Sonnet ncbi sweep (147 cells): median 956, p99 1199, max 1221. Catches genuine multi-thousand-char outliers without flagging the typical case.",
    )
    reason: TriageReason
    confidence: TriageConfidence
    key_uncertainty: str | None = Field(
        default=None,
        description="The most important uncertainty. Soft target ≤300 chars (overshoots warned but accepted). Floor set from the empirical distribution (Sonnet ncbi 2026-05-12 sweep): p90 250, max 267.",
    )
    search_log: list[SearchEntry] = Field(default_factory=list)
    provenance: TriageProvenance | None = Field(
        default=None,
        description=(
            "D1 row provenance (model + prompt_variant + run_id + replicate) "
            "when hydrated from triage_run_public; None for local-file records "
            "or in-process drafts."
        ),
    )

    _PROSE_TARGETS: ClassVar[dict[str, int]] = {
        # Caps set from empirical distribution of 147 Sonnet ncbi cells
        # in the 2026-05-12 mainbench sweep: verdict_reasoning median
        # 956 / p99 1199 / max 1221; key_uncertainty p90 250 / max 267.
        # Old caps (800 / 200) fired on 80% / 37% of rows respectively.
        "verdict_reasoning": 1250,
        "key_uncertainty": 300,
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
    "BiologicalContextGrade",
    "Confidence",
    "StateDependence",
    "Subcategory",
    "ProteinFamily",
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
    "ContradictionType",
    "ContradictionSeverity",
    "TissuePresence",
    "DiseaseContext",
    "PrimaryCompartment",
    "Orientation",
    "AccessibilityImplication",
    "ModulationCategory",
    "ModulationDirection",
    "CellStateTrigger",
    "RestrictedLineage",
    "DualLocPartnerCompartment",
    "TerminalOrientation",
    "OrthologyType",
    "AFDBVersion",
    "RiskSeverity",
    "EvidenceStrength",
    "RestrictedSubdomainName",
    "MembraneSubdomainName",
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
    "OverexpressionContext",
    "MethodObservation",
    "NonSurfaceExpression",
    "ExcludedClaim",
    "Contradiction",
    "SurfaceEvidence",
    # v1.0.0 — biological context (section 2)
    "ExpressionRow",
    "TissueContext",
    "CellTypeContextV1",
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
    "RepresentativeStructure",
    "SurfaceBindSite",
    "SurfaceBindFeatures",
    "DeterministicFeatures",
    # v1.0.0 — accessibility risks (section 6)
    "CoReceptorRequirements",
    "ShedForm",
    "SecretedForm",
    "RestrictedSubdomain",
    "ECDSizeAssessment",
    "classify_ecd_accessibility_class",
    "EpitopeMasking",
    "HomoOligomerizationPredictionRisk",
    "AccessibilityRisks",
    # TriageRecord
    "TRIAGE_SCHEMA_VERSION",
    "TriageProvenance",
    "ClaimStance",
    "ClaimWeight",
    "ClaimStanceRow",
    # NOTE: ``TriageModelPath`` removed — provenance.model carries the
    # full model identifier (e.g. ``claude-sonnet-4-6``) instead.
    "TriageRecord",
    "TriageRecordDraft",
    "TriageVerdict",
    "TriageReason",
    "TriageConfidence",
    "YesReason",
    "ContextualReason",
    "NoReason",
]
