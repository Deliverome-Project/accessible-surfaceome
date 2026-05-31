"""Pydantic schemas for the plan → trim → select loop.

Three I/O surfaces:

* :class:`SearchPlan` — Sonnet planner output (step 1).
* :class:`TrimResponse` — Haiku trimmer output per paper (step 3).
* :class:`SelectionResponse` — Sonnet selector output (step 4).

The selector schema deliberately has **no ``quote`` field** — the agent
selects clips by ID. The orchestrator constructs the verbatim
``EvidenceClaim.quote`` from the clip pool on promotion, so paraphrase
is structurally impossible (see
``docs/plans/2026-05-16-clip-and-judge-flow.html`` for the rationale).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from accessible_surfaceome.tools._shared.models import (
    AssayContext,
    ClaimType,
    Direction,
    EvidenceCategory,
    EvidenceConfidence,
    EvidenceTier,
    EvidenceType,
    LiteratureMode,
    TopicAnchor,
)


# ---------------------------------------------------------------------------
# Step 1 — Sonnet's SearchPlan output
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    """One search the planner / selector wants the orchestrator to run.

    Mirrors the input space of the existing custom tools without inventing a
    new tool surface. Validators enforce (tool, mode, category) consistency
    at parse time so malformed requests fail the schema check (and trigger
    the repair loop) rather than reaching the dispatcher and getting
    silently dropped with an error.

    Valid shapes:
      * tool=evidence_retrieval, category=<EvidenceCategory>
      * tool=gene_literature, mode=gene2pubmed
      * tool=gene_literature, mode=topic_search, anchors=[...]
      * tool=gene_literature, mode=fetch_abstract, pmid=<int>
      * tool=gene_literature, mode=fetch_fulltext, pmcid="PMC<digits>"
      * tool=gene_literature, mode=recent_corpus
    """

    model_config = ConfigDict(extra="forbid")

    tool: str  # "evidence_retrieval" | "gene_literature"
    # evidence_retrieval params
    category: EvidenceCategory | None = None
    # gene_literature params
    mode: LiteratureMode | None = None
    anchors: list[TopicAnchor] | None = None
    pmid: int | None = None
    pmcid: str | None = None
    intent: str = Field(
        default="",
        description="Short why-we're-running-this note; not used by the dispatcher but stored on the search log for audit.",
    )

    @model_validator(mode="after")
    def _check_tool_params(self) -> "SearchRequest":
        if self.tool == "evidence_retrieval":
            if self.category is None:
                raise ValueError(
                    "tool='evidence_retrieval' requires `category` (one of "
                    "ihc, if, flow_cytometry, surface_biotinylation, "
                    "mass_spec_surfaceome, western_blot_paired, "
                    "structure_with_ecd, other)"
                )
            if self.mode or self.anchors or self.pmid or self.pmcid:
                raise ValueError(
                    "tool='evidence_retrieval' must not set mode / anchors / "
                    "pmid / pmcid (those are gene_literature params). "
                    "If you want to fetch a specific paper, use "
                    "tool='gene_literature' with mode='fetch_abstract'/"
                    "'fetch_fulltext'."
                )
        elif self.tool == "gene_literature":
            if self.mode is None:
                raise ValueError(
                    "tool='gene_literature' requires `mode` (one of "
                    "gene2pubmed, topic_search, fetch_abstract, fetch_fulltext, "
                    "recent_corpus)"
                )
            if self.category is not None:
                raise ValueError(
                    "tool='gene_literature' must not set `category` (that's an "
                    "evidence_retrieval param)"
                )
            if self.mode == "topic_search" and not self.anchors:
                raise ValueError(
                    "mode='topic_search' requires `anchors` (list of TopicAnchor)"
                )
            if self.mode == "fetch_abstract" and self.pmid is None:
                raise ValueError("mode='fetch_abstract' requires `pmid` (int)")
            if self.mode == "fetch_fulltext" and not self.pmcid:
                raise ValueError(
                    "mode='fetch_fulltext' requires `pmcid` (string like 'PMC12345')"
                )
        else:
            raise ValueError(
                f"tool must be 'evidence_retrieval' or 'gene_literature'; got {self.tool!r}"
            )
        return self


class SearchPlan(BaseModel):
    """The planner's batch of search requests + rationale."""

    model_config = ConfigDict(extra="forbid")

    searches: list[SearchRequest] = Field(default_factory=list)
    rationale: str = Field(
        default="",
        description="One paragraph on why these searches; informs the audit log.",
    )


# ---------------------------------------------------------------------------
# Step 3 — Haiku's per-paper TrimResponse
# ---------------------------------------------------------------------------


class TrimKept(BaseModel):
    """One kept clip from Haiku's trim pass."""

    model_config = ConfigDict(extra="forbid")

    clip_id: str
    reason: str = Field(
        default="",
        description="One-line why-kept rationale, ≤140 chars; flows into the audit log.",
    )


class TrimResponse(BaseModel):
    """Haiku's per-paper trim output. Dropped clip ids are NOT enumerated —
    everything not in ``kept`` is discarded."""

    model_config = ConfigDict(extra="forbid")

    paper_id: str
    kept: list[TrimKept] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Step 4 — Sonnet's SelectionResponse
# ---------------------------------------------------------------------------


class Selection(BaseModel):
    """One selected clip + the agent's classifications + narrative claim.

    The ``claim`` field IS the agent's interpretive prose — what the
    evidence shows in the agent's words. The ``quote`` is NOT here; the
    orchestrator fills ``EvidenceClaim.quote`` from the clip's verbatim
    text using ``clip_id`` as the lookup key.
    """

    model_config = ConfigDict(extra="forbid")

    clip_id: str
    claim: str = Field(
        description="Agent's narrative interpretation of what the evidence shows. NOT the verbatim quote (orchestrator fills that from the clip).",
    )
    claim_type: ClaimType
    evidence_type: EvidenceType
    evidence_tier: EvidenceTier
    direction: Direction
    confidence: EvidenceConfidence
    assay_context: AssayContext


class SelectionResponse(BaseModel):
    """Sonnet's selector output — the final committed evidence selections.

    Single-pass: the selector picks its rows from the menu in front of it.
    Body-fetching is handled upstream by abstract-triage, so the selector
    no longer requests follow-up searches (the ``needs_more_searches`` /
    ``additional_searches`` iterate path was retired)."""

    model_config = ConfigDict(extra="forbid")

    selections: list[Selection] = Field(default_factory=list)
    notes: str = Field(
        default="",
        description="Optional one-paragraph rationale for the audit log.",
    )


# ---------------------------------------------------------------------------
# Abstract triage — Haiku's 3-way paper-level routing decision
# ---------------------------------------------------------------------------


class AbstractTriageResponse(BaseModel):
    """Haiku's per-paper triage decision based on the abstract alone.

    Three-way scientific routing call. Whether the orchestrator can
    actually retrieve the body (PMC OA, Unpaywall, paywalled) is a
    separate engineering question handled downstream — the agent's
    decision is forward-compatible with whatever fetch mechanisms the
    orchestrator wires up.

    * ``discard`` — gene mentioned incidentally (selection marker, peptide
      source, member of a long list); no primary surface-evidence content.
    * ``keep_abstract`` — abstract has a load-bearing surface-evidence
      claim that stands on its own (single-finding report, citable review
      claim, abstract states the methodology + result completely).
    * ``worth_fetching`` — primary surface-evidence work where the
      abstract teases substantive methods + results the body would
      expose. Orchestrator handles whether/how to obtain the body.
    """

    model_config = ConfigDict(extra="forbid")

    paper_id: str
    decision: Literal["discard", "keep_abstract", "worth_fetching"]
    reason: str = Field(
        default="",
        description="One-line rationale, ≤140 chars; flows into the audit log.",
    )


__all__ = [
    "SearchRequest",
    "SearchPlan",
    "TrimKept",
    "TrimResponse",
    "Selection",
    "SelectionResponse",
    "AbstractTriageResponse",
]
