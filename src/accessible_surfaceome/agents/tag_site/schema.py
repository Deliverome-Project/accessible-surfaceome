"""Structured output schema for the literature tag-site agent."""
from __future__ import annotations

from pydantic import BaseModel, Field

# Evidence-strength ladder (verbatim from the agentic tag-site benchmark prompt).
EVIDENCE_TYPES = (
    "published tag insertion at this exact site",
    "published tag insertion in the same loop or domain",
    "published tolerance of a different insertion (transposon, FP fusion)",
    "structural inference",
    "topology inference only",
)


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
    rationale: str
    confidence: str = Field(description='"high" | "medium" | "low"')


class TagSiteResult(BaseModel):
    gene_symbol: str
    uniprot_accession: str
    sequence_length: int
    sites: list[TagSiteProposal] = Field(default_factory=list)
    notes: str = ""
