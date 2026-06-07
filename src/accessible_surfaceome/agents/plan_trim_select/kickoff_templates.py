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
    # Shared with A2 — shed/soluble-form evidence feeds both the surface-side
    # shed_form risk and A2's secreted_form risk.
    "shedding",
    # A1-only — dedicated over-expression-precedent search (does the protein
    # traffic to the surface AT ALL when over-expressed). A surface-capability
    # signal, distinct from the OE terms inside if/flow/surface_biotinylation.
    "overexpression",
    "western_blot_paired",
    "structure_with_ecd",
    "other",
)
_A2_CATEGORIES: tuple[EvidenceCategory, ...] = (
    "ihc",
    "if",
    "flow_cytometry",
    "mass_spec_surfaceome",
    "shedding",
    # A2-only — assay-less, context-tagged surface-expression mentions so A2's
    # ExpressionObservation rows are quote-grounded. This makes A2 no longer a
    # strict subset of A1 (the prompt-review renders an "A2 only" block).
    "surface_expression",
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


def _standing_axes(
    n_tmh: int | None,  # noqa: ARG001  # kept for signature stability with callers
    ecd_aa: int | None,  # noqa: ARG001
) -> list[SearchRequest]:
    """Retrieval axes shared by every focus — all unconditional.

    The deep-dive is only invoked on genes triage already thought might be
    surface-accessible. Suppressing the barrier / co-receptor / subdomain /
    masking axes for "known TM=0" or "small canonical ECD" genes loses
    exactly the edge cases the deep-dive exists to catch — cancer-specific
    surface exposure, ectopic trafficking, polarized non-canonical surface,
    state-dependent topology inversion (e.g. SRC's ALE flip). The cost of
    four extra topic_search queries per gene is trivial compared with the
    cost of a silently missed surface-accessibility signal.

    Five always-on axes:

    * ``normal_tissue_expression`` — surface coverage across the six
      high-consequence tox organs (liver/lung/kidney/intestine/heart/brain).
      On-target / off-tumor toxicity is set by surface expression there.
    * ``surface_reachability`` — BBB / tumor penetration /
      luminal-vs-abluminal / binder accessibility.
    * ``partner_dependency`` — obligate co-receptor / escort for surface
      trafficking (feeds ``co_receptor_requirements``).
    * ``membrane_subdomain`` — lipid raft / apical / ciliary / synaptic
      microdomain distribution (feeds ``restricted_subdomain``).
    * ``epitope_masking`` — homo-oligomer / hetero-partner / glycan /
      conformational occlusion (feeds ``epitope_masking``).

    ``n_tmh`` and ``ecd_aa`` are still accepted to keep the call signature
    stable for other callers, but they no longer gate any axis here.
    Topology-based grading still lives downstream in the orchestrator's
    ``secreted_form`` post-pass — the right place for a precision call.
    """
    return [
        SearchRequest(
            tool="gene_literature",
            mode="topic_search",
            anchors=["normal_tissue_expression"],
            intent="standing: normal-tissue surface expression (six high-consequence tox organs)",
        ),
        SearchRequest(
            tool="gene_literature",
            mode="topic_search",
            anchors=["surface_reachability"],
            intent="standing: surface-reachability barriers (BBB / tumor penetration / luminal / accessibility)",
        ),
        SearchRequest(
            tool="gene_literature",
            mode="topic_search",
            anchors=["partner_dependency"],
            intent="standing: co-receptor / partner-dependency for surface trafficking",
        ),
        SearchRequest(
            tool="gene_literature",
            mode="topic_search",
            anchors=["membrane_subdomain"],
            intent="standing: plasma-membrane subdomain / polarity distribution",
        ),
        SearchRequest(
            tool="gene_literature",
            mode="topic_search",
            anchors=["epitope_masking"],
            intent="standing: epitope-masking evidence (homo / hetero / other)",
        ),
    ]


def _surface_method_search() -> SearchRequest:
    """The shared surface-expression + surface-method topic_search, emitted
    identically by A1 and A2 (single source of truth for that mirror)."""
    return SearchRequest(
        tool="gene_literature",
        mode="topic_search",
        anchors=list(_SURFACE_METHOD_ANCHORS),
        intent="A1/A2 shared: surface-expression + surface-method topic_search",
    )


def _shedding_ptm_search() -> SearchRequest:
    """The shared shedding + PTM topic_search, emitted identically by A1 and
    A2 (single source of truth for that mirror). PTM lives here, not in A1's
    topology/structure search, so it stays mirrored across the two foci."""
    return SearchRequest(
        tool="gene_literature",
        mode="topic_search",
        anchors=["shedding", "ptm"],
        intent="A1/A2 shared: shedding + PTM topic_search",
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
            anchors=["topology", "structure"],
            intent="A1 default: structure / topology topic_search",
        ),
        _shedding_ptm_search(),
    ])
    searches.extend(_standing_axes(n_tmh, ecd_aa))
    return SearchPlan(
        searches=searches,
        rationale=(
            "A1 deterministic kickoff: all evidence_retrieval categories; "
            "gene2pubmed + recent_corpus; three topic_search variants "
            "(surface+methods (shared) / structure / shedding+ptm (shared)); standing axes "
            "(normal-tissue surface-expression always; surface-reachability / "
            "partner + subdomain + epitope-masking — all always-on, no topology gate). "
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
        _shedding_ptm_search(),
    ])
    searches.extend(_standing_axes(n_tmh, ecd_aa))
    return SearchPlan(
        searches=searches,
        rationale=(
            "A2 deterministic kickoff: biology-leaning evidence_retrieval "
            "categories (ihc, if, flow_cytometry, mass_spec_surfaceome, shedding, "
            "surface_expression — the last A2-only, for quote-grounded "
            "ExpressionObservation rows); "
            "gene2pubmed + recent_corpus; two topic_search variants "
            "(surface+methods (shared) + shedding+ptm (shared)); standing axes "
            "(normal-tissue surface-expression always; surface-reachability / "
            "partner + subdomain + epitope-masking — all always-on, no topology gate). "
            "Selector iterates from observed paper inventory."
        ),
    )


def build_kickoff(
    focus: str,
    n_tmh: int | None = None,
    ecd_aa: int | None = None,
) -> SearchPlan:
    """Dispatch to the per-focus deterministic kickoff builder.

    ``focus`` is required and must be ``"a1"`` or ``"a2"`` — the
    unified-ledger (None) path was retired with the legacy
    ``trim_system.md`` / ``select_system.md`` prompts. ``n_tmh`` /
    ``ecd_aa`` are the canonical topology counts (TM-helix count and
    ectodomain length) used to gate the membrane-specific standing
    axes; ``None`` means "topology unknown" and fires those axes
    recall-biased.
    """

    if focus == "a1":
        return build_a1_kickoff(n_tmh, ecd_aa)
    if focus == "a2":
        return build_a2_kickoff(n_tmh, ecd_aa)
    raise ValueError(f"unknown focus {focus!r}; expected 'a1' or 'a2'")


__all__ = [
    "build_a1_kickoff",
    "build_a2_kickoff",
    "build_kickoff",
]
