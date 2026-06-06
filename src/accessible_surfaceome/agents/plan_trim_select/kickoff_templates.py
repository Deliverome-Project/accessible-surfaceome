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

from accessible_surfaceome.agents._support.topology_gate import (
    is_likely_membrane_with_ecd,
)
from accessible_surfaceome.agents.plan_trim_select.schemas import (
    SearchPlan,
    SearchRequest,
)
from accessible_surfaceome.tools._shared.models import EvidenceCategory, TopicAnchor

# evidence_retrieval categories per focus. western_blot_paired +
# structure_with_ecd are A1's domain and skipped by A2. hpa_ihc was retired
# upstream — HPA surface vote + main_location ride on the db_panel input now,
# and broader IHC literature is covered by category="ihc". "other" is a
# catch-all for category-shaped but unlisted evidence; A1 runs it for
# surface-evidence breadth.
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

# Surface-method topic anchors shared by A1's method search and A2's
# surface-expression search, so both agents pull the same surface-method
# literature (flow cytometry / surface biotinylation / surfaceome MS / IHC).
# A2's tissue/distribution search adds "surface_expression" on top. Defined
# once so the A1↔A2 mirror is a single source of truth (asserted by
# test_a2_surface_search_mirrors_a1_method_anchors).
_METHOD_ANCHORS: tuple[TopicAnchor, ...] = (
    "flow_cytometry",
    "surface_biotinylation",
    "mass_spec_surfaceome",
    "ihc",
)

# The full surface-presence + surface-method topic_search = "surface_expression"
# + the four method anchors. Emitted IDENTICALLY by A1 and A2 (both call
# _surface_method_search()), so the two agents run the same surface/method
# retrieval. Byte-for-byte mirror asserted by
# test_surface_method_search_identical_across_a1_a2.
_SURFACE_METHOD_ANCHORS: tuple[TopicAnchor, ...] = ("surface_expression", *_METHOD_ANCHORS)


def _fires_membrane_ecd_gate(n_tmh: int | None, ecd_aa: int | None) -> bool:
    """Recall-biased membrane+ECD gate for the topology-conditional axes.

    Unknown topology (both ``None``) fires the gate so a D1 coverage miss
    never silently suppresses a retrieval axis; a *known* non-membrane or
    small-ECD protein is the only case that suppresses the membrane-specific
    axes. The runner maps the D1 placeholder topology to ``None`` so a
    coverage miss biases to recall rather than to a false TM=0 negative.
    """
    if n_tmh is None and ecd_aa is None:
        return True
    return is_likely_membrane_with_ecd(n_tmh, ecd_aa)


def _standing_axes(n_tmh: int | None, ecd_aa: int | None) -> list[SearchRequest]:
    """Retrieval axes shared by every focus.

    The normal-tissue surface-expression panel is **always** emitted —
    surface coverage across the six high-consequence organs
    (liver/lung/kidney/intestine/heart/brain) is mandatory for every gene
    because on-target/off-tumor toxicity is set by surface expression there.
    Four barrier/distribution axes are **gated** on the membrane+ECD predicate
    (they only matter for a surface-accessible target): surface-reachability
    (BBB / tumor penetration / luminal-vs-abluminal / binder accessibility),
    partner-dependency (obligate co-receptor / escort — feeds
    co_receptor_requirements), membrane-subdomain (lipid raft / apical /
    ciliary — feeds restricted_subdomain), and epitope-masking (homo / hetero
    / other occlusion — feeds epitope_masking).

    The soluble/shed-in-circulation axis (A2.4) is not a separate request
    here: it rides the always-on ``shedding`` topic_search, whose terms now
    include serum/plasma/circulating. The topology gate for *grading* a
    soluble form lives in the orchestrator's secreted_form post-pass, which
    is the correct stage for that precision call.
    """
    axes = [
        SearchRequest(
            tool="gene_literature",
            mode="topic_search",
            anchors=["normal_tissue_expression"],
            intent="standing: normal-tissue surface expression (six high-consequence tox organs)",
        )
    ]
    if _fires_membrane_ecd_gate(n_tmh, ecd_aa):
        axes += [
            SearchRequest(
                tool="gene_literature",
                mode="topic_search",
                anchors=["surface_reachability"],
                intent="standing (gated): surface-reachability barriers (BBB / tumor penetration / luminal / accessibility)",
            ),
            SearchRequest(
                tool="gene_literature",
                mode="topic_search",
                anchors=["partner_dependency"],
                intent="standing (gated): co-receptor / partner-dependency for surface trafficking",
            ),
            SearchRequest(
                tool="gene_literature",
                mode="topic_search",
                anchors=["membrane_subdomain"],
                intent="standing (gated): plasma-membrane subdomain / polarity distribution",
            ),
            SearchRequest(
                tool="gene_literature",
                mode="topic_search",
                anchors=["epitope_masking"],
                intent="standing (gated): epitope-masking evidence (homo / hetero / other)",
            ),
        ]
    return axes


def _surface_method_search() -> SearchRequest:
    """The shared surface-expression + surface-method topic_search, emitted
    identically by A1 and A2 (single source of truth for that mirror)."""
    return SearchRequest(
        tool="gene_literature",
        mode="topic_search",
        anchors=list(_SURFACE_METHOD_ANCHORS),
        intent="A1/A2 shared: surface-expression + surface-method topic_search",
    )


def build_a1_kickoff(
    n_tmh: int | None = None, ecd_aa: int | None = None
) -> SearchPlan:
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
        _surface_method_search(),
        SearchRequest(
            tool="gene_literature",
            mode="topic_search",
            anchors=["topology", "structure", "ptm"],
            intent="A1 default: structure / topology / PTM topic_search",
        ),
        SearchRequest(
            tool="gene_literature",
            mode="topic_search",
            anchors=["shedding"],
            intent="A1 default: shedding topic_search",
        ),
    ])
    searches.extend(_standing_axes(n_tmh, ecd_aa))
    return SearchPlan(
        searches=searches,
        rationale=(
            "A1 deterministic kickoff: all evidence_retrieval categories; "
            "gene2pubmed + recent_corpus; three topic_search variants "
            "(surface+methods (shared with A2) / structure / shedding); standing axes "
            "(normal-tissue surface-expression always; surface-reachability / "
            "partner / subdomain / epitope-masking when membrane+ECD). "
            "Selector iterates from observed paper inventory."
        ),
    )


def build_a2_kickoff(
    n_tmh: int | None = None, ecd_aa: int | None = None
) -> SearchPlan:
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
        _surface_method_search(),
        SearchRequest(
            tool="gene_literature",
            mode="topic_search",
            anchors=["shedding", "ptm"],
            intent="A2 default: state / modulation topic_search",
        ),
    ])
    searches.extend(_standing_axes(n_tmh, ecd_aa))
    return SearchPlan(
        searches=searches,
        rationale=(
            "A2 deterministic kickoff: four biology-leaning evidence_retrieval "
            "categories (ihc, if, flow_cytometry, mass_spec_surfaceome); "
            "gene2pubmed + recent_corpus; two topic_search variants "
            "(surface+methods (shared with A1) + state/modulation); standing axes "
            "(normal-tissue surface-expression always; surface-reachability / "
            "partner / subdomain / epitope-masking when membrane+ECD). "
            "Selector iterates from observed paper inventory."
        ),
    )


def build_unified_kickoff(
    n_tmh: int | None = None, ecd_aa: int | None = None
) -> SearchPlan:
    """Deterministic kickoff for the unified-ledger (focus=None) path.

    Unions the A1 and A2 search sets, deduplicated on (tool, category,
    mode, anchors). Used when no agent_focus is set — the single-agent
    MVP path that harvests one combined ledger rather than a split A1/A2.
    """

    seen: set[tuple] = set()
    merged: list[SearchRequest] = []
    for req in (
        *build_a1_kickoff(n_tmh, ecd_aa).searches,
        *build_a2_kickoff(n_tmh, ecd_aa).searches,
    ):
        key = (
            req.tool,
            req.category,
            req.mode,
            tuple(req.anchors) if req.anchors else None,
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(req)
    return SearchPlan(
        searches=merged,
        rationale=(
            "Unified deterministic kickoff: A1 ∪ A2 search sets, deduplicated. "
            "Selector iterates from observed paper inventory."
        ),
    )


def build_kickoff(
    focus: str | None,
    n_tmh: int | None = None,
    ecd_aa: int | None = None,
) -> SearchPlan:
    """Dispatch to the per-focus deterministic kickoff builder.

    ``focus=None`` returns the unified A1 ∪ A2 kickoff for the
    single-agent ledger path. ``n_tmh`` / ``ecd_aa`` are the canonical
    topology counts (TM-helix count and ectodomain length) used to gate the
    membrane-specific standing axes; ``None`` means "topology unknown" and
    fires those axes recall-biased.
    """

    if focus is None:
        return build_unified_kickoff(n_tmh, ecd_aa)
    if focus == "a1":
        return build_a1_kickoff(n_tmh, ecd_aa)
    if focus == "a2":
        return build_a2_kickoff(n_tmh, ecd_aa)
    raise ValueError(f"unknown focus {focus!r}; expected 'a1', 'a2', or None")


__all__ = [
    "build_a1_kickoff",
    "build_a2_kickoff",
    "build_unified_kickoff",
    "build_kickoff",
]
