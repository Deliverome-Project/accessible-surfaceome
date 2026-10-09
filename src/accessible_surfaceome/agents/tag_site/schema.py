"""Structured output schema for the literature tag-site agent."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, computed_field

# Evidence-strength ladder (verbatim from the agentic tag-site benchmark prompt).
EVIDENCE_TYPES = (
    "published tag insertion at this exact site",
    "published tag insertion in the same loop or domain",
    "published tolerance of a different insertion (transposon, FP fusion)",
)
# "structural inference" and "topology inference only" were valid values here
# while the prompt forbade justifying any site by structural inference — the
# schema offered exactly what the prose banned. Deciding a site on topology is
# the deterministic pipeline's job, which does it with computed RSA/DSSP, so a
# literature site has no honest use for either value.

EvidenceType = Literal[
    "published tag insertion at this exact site",
    "published tag insertion in the same loop or domain",
    "published tolerance of a different insertion (transposon, FP fusion)",
]
SiteType = Literal["terminal_n", "terminal_c", "internal"]
#: "unknown" is deliberate and load-bearing: a compartment that could not be
#: derived must never read as extracellular. Mirrors `compartmentAt` in
#: viewer/lib/surface-bind.ts, which carries the same rule.
TopologyState = Literal["extracellular", "intracellular", "membrane", "signal", "unknown"]
PositionEvidence = Literal["validated", "inferred"]
Confidence = Literal["high", "medium", "low"]

# Validation strength of the cited tagging construct, best -> worst. The headline
# ranking signal: prioritize sites where the tag was shown to DISPLAY on the surface
# AND preserve function/expression vs untagged (the positive-control gold standard,
# e.g. EndoNB knock-ins, Huet ecto-tagged integrins). Mirrors the "Impact measured
# vs untagged" column of data/tag_sites/positive_controls.md.
VALIDATION_LEVELS = (
    "surface_and_function",  # non-permeabilized surface display AND function/expression RETAINED (cleanly isolated)
    "surface_only",          # surface display shown; function not compared
    "function_only",         # function/expression retained; surface display not directly shown
    "detected_only",         # construct expressed/detected, but no surface OR function comparison
    "function_perturbed",    # function WAS measured but REDUCED, or CONFOUNDED/not-isolated — NOT a clean validation
    "not_measured",          # tag reported without validation
)
VALIDATION_RANK = {v: i for i, v in enumerate(VALIDATION_LEVELS)}
ValidationLevel = Literal[
    "surface_and_function", "surface_only", "function_only",
    "detected_only", "function_perturbed", "not_measured",
]

# Source tier of the supporting reference, best -> worst (see literature_discovery).
SOURCE_TIERS = ("paper", "patent", "other", "vendor")
SourceTier = Literal["paper", "patent", "other", "vendor"]


class TagSiteProposal(BaseModel):
    #: Overwritten unconditionally by `rank_sites` after the gates run, so the
    #: model's ordering is discarded — do not ask for it.
    rank: int = 0
    site_type: SiteType = Field(description='"terminal_n" | "terminal_c" | "internal"')
    insert_after_residue: int = Field(
        description="Junction: tag sits between this residue and +1 (UniProt canonical numbering)."
    )
    residue_before: str = Field(description="1-letter residue AT insert_after_residue.")
    residue_after: str = Field(description="1-letter residue AT insert_after_residue+1.")
    topology_state: TopologyState = Field(
        default="unknown",
        description=(
            "Derived in code from the computed topology by `compartment_for_site` "
            "after the geometry pass — the model is not asked for it. Per-kind, so "
            "a terminal_n reads the MATURE N-terminus rather than the junction."
        ),
    )
    tag_type: str = Field(description="e.g. 'short epitope, ALFA 15 aa, GS linkers'")
    evidence_type: EvidenceType = Field(description="One of the EVIDENCE_TYPES ladder values.")
    position_evidence: PositionEvidence = Field(
        description=(
            '"validated" — a tag was published AT this exact residue/junction (or immediately '
            'adjacent, +/-1). "inferred" — the loop/domain has tagging precedent ELSEWHERE, but '
            "THIS specific position is your own structural choice. If the cited tag is not at "
            "insert_after_residue, this MUST be 'inferred'."
        )
    )
    cited_tag_residue: int | None = Field(
        default=None,
        description=(
            "The residue where the CITED tag was actually placed (UniProt numbering). Equals "
            "insert_after_residue when position_evidence='validated'; the real precedent position "
            "(e.g. 89) when you inferred a different site (e.g. 120). Null if not a point tag."
        ),
    )
    evidence_detail: str = Field(description="What was measured/observed, in what system.")
    functional_or_expression_impact_measured: str = Field(
        description="What was MEASURED (assay + result), or 'NOT MEASURED'. Never inferred."
    )
    validation_level: ValidationLevel = Field(
        default="not_measured",
        description=(
            "One of VALIDATION_LEVELS. The priority ranking signal: was the tag shown to "
            "DISPLAY on the cell surface (non-permeabilized) and/or preserve function/expression "
            "vs untagged? Use 'surface_and_function' ONLY when surface display is shown AND "
            "function is RETAINED (~unchanged vs untagged) in a clean, isolated measurement. If "
            "function was measured but came out REDUCED (e.g. Vmax cut to ~half) or CONFOUNDED "
            "(e.g. recorded with the endogenous protein co-expressed, so not isolated), that is "
            "'function_perturbed' — NOT surface_and_function. 'not_measured' if no validation is "
            "reported. Derive it from what was actually measured — never infer beyond the evidence."
        ),
    )
    source_tier: SourceTier = Field(
        default="paper",
        description=(
            "Reference tier: 'paper' (peer-reviewed/preprint) > 'patent' > 'other' > 'vendor' "
            "(catalog/reagent page). Papers are preferred; vendor pages are kept but rank lowest."
        ),
    )
    supporting_pmid: int | None = Field(
        default=None, description="PMID of the supporting paper when one exists (grounds the citation)."
    )
    supporting_quote: str | None = Field(
        default=None,
        description=(
            "A VERBATIM sentence copied from the cited paper (abstract/methods/results, provided "
            "to you above) that states the tag was inserted at this site and/or its validation. "
            "This exact string is checked against the source text — do NOT paraphrase or invent it."
        ),
    )
    entailment_verified: bool = Field(
        default=False,
        description="Set by the pipeline (not the model): True iff supporting_quote is found in the cited source text.",
    )
    quote_probative: bool = Field(
        default=False,
        description=(
            "Set by the pipeline (not the model): True iff supporting_quote actually DESCRIBES "
            "an insertion/tag rather than background biology. Distinct from entailment_verified, "
            "which only proves the quote came from the cited source — a site can be correct and "
            "its quote still say nothing about a tag."
        ),
    )
    position_repaired: bool = Field(
        default=False,
        description=(
            "Set by the pipeline (not the model): True iff the geometry pass MOVED this site's "
            "junction — because the model's integer disagreed with the computed sequence and a "
            "deterministic repair recovered the intended position. Keeps a rewrite auditable "
            "instead of silent."
        ),
    )
    rationale: str
    confidence: Confidence = Field(description='"high" | "medium" | "low"')

    @computed_field  # type: ignore[prop-decorator]
    @property
    def residue_label(self) -> str:
        """Canonical single-token residue for downstream analysis, e.g. ``G101``.

        Convention (matches ``data/tag_sites/positive_controls.md`` "after N" and
        the EndoNB majority): the residue immediately N-terminal to the junction —
        the tag is inserted AFTER this residue, between it and residue+1. Derived
        from ``residue_before`` + ``insert_after_residue`` so it is always
        consistent regardless of how the model phrased the site."""
        return f"{self.residue_before}{self.insert_after_residue}"


#: Bump with any change to the shape of a persisted tag-site record.
TAG_SITE_SCHEMA_VERSION = "1.0.0"


class RejectedSite(BaseModel):
    """A site the model proposed and the pipeline removed.

    Recorded, not merely logged. A log line helps whoever watches a run; it does
    nothing for a reviewer opening the record six months later, who otherwise
    cannot tell a site was never found from one that was found and deleted. The
    agent ranked KCNH2 T436 FIRST and the record shipped without a trace of it."""

    residue_label: str = ""
    insert_after_residue: int | None = None
    gate: str = Field(description='Which gate removed it: "entailment" | "validation" | "geometry"')
    reason: str = ""


class TagSiteResult(BaseModel):
    # Stamped by the runner from what the caller already holds — never asked of
    # the model, which would only be echoing back its own input and failing
    # validation when it forgot. `sequence_length` is provenance: it records
    # which sequence the junctions were pinned against, so it has to come from
    # the real sequence rather than a guess.
    gene_symbol: str = ""
    uniprot_accession: str = ""
    sequence_length: int = 0
    sites: list[TagSiteProposal] = Field(default_factory=list)
    notes: str = ""
    rejected: list[RejectedSite] = Field(default_factory=list)

    # Prompt provenance. Mandatory for any pipeline whose LLM output is
    # persisted (CLAUDE.md), and absent here until now: four prompt edits in one
    # day produced records that were indistinguishable afterwards, so a rerun
    # could not be told from a stale row and an A/B had to recover the old
    # prompt from git rather than read it off the record.
    schema_version: str = TAG_SITE_SCHEMA_VERSION
    prompt_sha: str = ""
    prompt_version: str = ""
    model: str = ""
    generated_at: str = ""
