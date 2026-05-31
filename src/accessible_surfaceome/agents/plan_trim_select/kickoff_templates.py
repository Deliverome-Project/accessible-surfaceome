"""Deterministic kickoff templates — drop-in replacement for the LLM planner.

The Sonnet planner spent ~$0.04/gene reasoning about which searches to run
from a closed search-tool surface (enum categories, enum modes, enum
anchors). Empirically the resulting plans were ~90% template-shaped with
no gene-specific reasoning that a fixed dispatcher couldn't reproduce.
The remaining 10% (specific PMID/PMCID fetches) is unsafe because the
planner can't reliably recall identifiers — that work is better done by
the selector in iteration 1+, which sees the actual paper inventory.

These builders emit the same ``SearchPlan`` shape the orchestrator
already consumes, so the rest of the plan→execute→trim→select pipeline
is unchanged.
"""

from __future__ import annotations

from accessible_surfaceome.agents.plan_trim_select.schemas import (
    SearchPlan,
    SearchRequest,
)
from accessible_surfaceome.tools._shared.models import EvidenceCategory

# evidence_retrieval categories per focus. western_blot_paired +
# structure_with_ecd are A1's domain and skipped by A2 (per a2_plan_system.md
# guidance). hpa_ihc was retired upstream — HPA surface vote + main_location
# ride on the db_panel input now, and broader IHC literature is covered by
# category="ihc". "other" is a catch-all for category-shaped but unlisted
# evidence; A1 runs it for surface-evidence breadth.
_A1_CATEGORIES: tuple[EvidenceCategory, ...] = (
    "ihc",
    "if",
    "flow_cytometry",
    "surface_biotinylation",
    "mass_spec_surfaceome",
    "western_blot_paired",
    "structure_with_ecd",
    "other",
)
_A2_CATEGORIES: tuple[EvidenceCategory, ...] = (
    "ihc",
    "if",
    "flow_cytometry",
    "mass_spec_surfaceome",
)


def build_a1_kickoff() -> SearchPlan:
    """Deterministic A1 (surface-evidence) kickoff plan."""

    searches: list[SearchRequest] = [
        SearchRequest(
            tool="evidence_retrieval",
            category=category,
            intent=f"A1 default sweep: {category}",
        )
        for category in _A1_CATEGORIES
    ]
    searches.extend([
        SearchRequest(
            tool="gene_literature",
            mode="gene2pubmed",
            intent="A1 default: NCBI gene2pubmed baseline",
        ),
        SearchRequest(
            tool="gene_literature",
            mode="recent_corpus",
            intent="A1 default: recent_corpus sweep",
        ),
        SearchRequest(
            tool="gene_literature",
            mode="topic_search",
            anchors=[
                "flow_cytometry",
                "surface_biotinylation",
                "mass_spec_surfaceome",
                "ihc",
            ],
            intent="A1 default: method-anchored topic_search",
        ),
        SearchRequest(
            tool="gene_literature",
            mode="topic_search",
            anchors=["topology", "structure", "ptm"],
            intent="A1 default: structure / topology / PTM topic_search",
        ),
        SearchRequest(
            tool="gene_literature",
            mode="topic_search",
            anchors=["surface_expression", "shedding"],
            intent="A1 default: surface-presence + shedding topic_search",
        ),
    ])
    return SearchPlan(
        searches=searches,
        rationale=(
            "A1 deterministic kickoff: all evidence_retrieval categories; "
            "gene2pubmed + recent_corpus; three topic_search variants "
            "(methods / structure / surface-presence). Selector iterates from "
            "observed paper inventory."
        ),
    )


def build_a2_kickoff() -> SearchPlan:
    """Deterministic A2 (biological-context) kickoff plan."""

    searches: list[SearchRequest] = [
        SearchRequest(
            tool="evidence_retrieval",
            category=category,
            intent=f"A2 default sweep: {category}",
        )
        for category in _A2_CATEGORIES
    ]
    searches.extend([
        SearchRequest(
            tool="gene_literature",
            mode="gene2pubmed",
            intent="A2 default: NCBI gene2pubmed baseline",
        ),
        SearchRequest(
            tool="gene_literature",
            mode="recent_corpus",
            intent="A2 default: recent_corpus sweep",
        ),
        SearchRequest(
            tool="gene_literature",
            mode="topic_search",
            anchors=["surface_expression", "ihc"],
            intent="A2 default: tissue / distribution topic_search",
        ),
        SearchRequest(
            tool="gene_literature",
            mode="topic_search",
            anchors=["shedding", "ptm"],
            intent="A2 default: state / modulation topic_search",
        ),
    ])
    return SearchPlan(
        searches=searches,
        rationale=(
            "A2 deterministic kickoff: four biology-leaning evidence_retrieval "
            "categories (ihc, if, flow_cytometry, mass_spec_surfaceome); "
            "gene2pubmed + recent_corpus; two topic_search variants "
            "(tissue/distribution + state/modulation). Selector iterates from "
            "observed paper inventory."
        ),
    )


def build_kickoff(focus: str) -> SearchPlan:
    """Dispatch to the per-focus deterministic kickoff builder."""

    if focus == "a1":
        return build_a1_kickoff()
    if focus == "a2":
        return build_a2_kickoff()
    raise ValueError(f"unknown focus {focus!r}; expected 'a1' or 'a2'")


__all__ = [
    "build_a1_kickoff",
    "build_a2_kickoff",
    "build_kickoff",
]
