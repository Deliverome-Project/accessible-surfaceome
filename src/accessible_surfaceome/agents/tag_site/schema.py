"""Structured output schema for the literature tag-site agent."""
from __future__ import annotations

from pydantic import BaseModel, Field, computed_field

# Evidence-strength ladder (verbatim from the agentic tag-site benchmark prompt).
EVIDENCE_TYPES = (
    "published tag insertion at this exact site",
    "published tag insertion in the same loop or domain",
    "published tolerance of a different insertion (transposon, FP fusion)",
    "structural inference",
    "topology inference only",
)

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

# Source tier of the supporting reference, best -> worst (see literature_discovery).
SOURCE_TIERS = ("paper", "patent", "other", "vendor")


class TagSiteProposal(BaseModel):
    rank: int
    site_type: str = Field(description='"terminal_n" | "terminal_c" | "internal"')
    insert_after_residue: int = Field(
        description="Junction: tag sits between this residue and +1 (UniProt canonical numbering)."
    )
    residue_before: str = Field(description="1-letter residue AT insert_after_residue.")
    residue_after: str = Field(description="1-letter residue AT insert_after_residue+1.")
    topology_state: str = Field(description='"extracellular" | "intracellular" | "membrane" | "signal"')
    tag_type: str = Field(description="e.g. 'short epitope, ALFA 15 aa, GS linkers'")
    evidence_type: str = Field(description="One of the EVIDENCE_TYPES ladder values.")
    position_evidence: str = Field(
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
    validation_level: str = Field(
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
    source_tier: str = Field(
        default="paper",
        description=(
            "Reference tier: 'paper' (peer-reviewed/preprint) > 'patent' > 'other' > 'vendor' "
            "(catalog/reagent page). Papers are preferred; vendor pages are kept but rank lowest."
        ),
    )
    supporting_pmid: int | None = Field(
        default=None, description="PMID of the supporting paper when one exists (grounds the citation)."
    )
    rationale: str
    confidence: str = Field(description='"high" | "medium" | "low"')

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


class TagSiteResult(BaseModel):
    gene_symbol: str
    uniprot_accession: str
    sequence_length: int
    sites: list[TagSiteProposal] = Field(default_factory=list)
    notes: str = ""
