"""Helpers for shaping the messages-API request payload — caching + compaction.

Two responsibilities, both gated on the same place (the per-iteration call
to ``client.messages.create``):

1. **Compaction.** ``evidence_retrieval`` returns an
   ``EvidenceRetrievalPack`` with both pre-extracted ``snippets``
   (≤200-char verbatim fragments, what the agent actually quotes from)
   AND the full ``papers[*].sections[*].text`` they came from. The
   sections can be ~50k tokens per call and accumulate across the loop.
   The snippets carry everything the agent needs to file a claim; the
   full body lives in the orchestrator's :class:`SourceTextStore`
   (registered by ``register_from_tool_return`` *before* the result is
   serialized for the model), so stripping sections from the
   transported payload doesn't affect substring anchoring at promotion.

2. **Prompt caching.** Anthropic's 5-minute ephemeral cache reads at
   0.1× the base input rate. The runners loop through many iterations
   where 90%+ of the input is the same accumulated prior context. Two
   cache breakpoints per request keep the cost flat across iterations:
   one on the system prompt (always), one on the latest tool_result
   block (rotates each iteration). Older tool_result cache markers are
   stripped on each call so we stay inside Anthropic's 4-breakpoint
   limit even on long runs.
"""

from __future__ import annotations

from typing import Any

from accessible_surfaceome.tools._shared.models import (
    EvidenceRetrievalPack,
    LiteraturePack,
    Paper,
)


# ---------------------------------------------------------------------------
# Compaction — strip heavy paper.sections from tool returns for transport
# ---------------------------------------------------------------------------


def compact_for_agent_transport(result: Any) -> Any:
    """Return a model-transport-friendly copy of a tool result.

    Strips ``paper.sections[*]`` from ``EvidenceRetrievalPack`` and
    ``LiteraturePack`` payloads. Other shapes pass through unchanged.
    A single direct ``Paper`` (from ``gene_literature(mode='fetch_fulltext')``)
    is intentionally NOT stripped — the agent calls that mode specifically to
    read full text and it's already char-capped to ~10k tokens at fetch time.

    Compaction is sound because:

    - ``SourceTextStore`` already holds the unstripped body (registered by
      ``register_from_tool_return`` before this function runs).
    - The agent's system prompt directs it to quote ``evidence_retrieval``
      snippets verbatim; raw sections aren't used in claim construction.
    - The substring check at promotion runs against the full body in the
      store, not against the model-visible payload.
    """
    if isinstance(result, EvidenceRetrievalPack):
        return result.model_copy(
            update={"papers": [_compact_paper(p) for p in result.papers]}
        )
    if isinstance(result, LiteraturePack):
        return result.model_copy(
            update={"papers": [_compact_paper(p) for p in result.papers]}
        )
    return result


def _compact_paper(paper: Paper) -> Paper:
    """Strip ``sections`` body text; keep all metadata fields the agent cites.

    ``truncated_sections`` is reused to advertise which section names *did*
    exist on the unstripped paper, so the agent can still reason "this paper
    has methods + results we can cite a snippet from" without paying for the
    raw bytes.
    """
    if not paper.sections:
        return paper
    section_names = [s.name for s in paper.sections]
    return paper.model_copy(
        update={
            "sections": [],
            "truncated_sections": sorted(set(section_names)),
        }
    )


# ---------------------------------------------------------------------------
# Prompt caching — system + rolling tool_result breakpoints
# ---------------------------------------------------------------------------


def cached_system(system_text: str) -> list[dict[str, Any]]:
    """Wrap a plain system prompt string into a single cache-controlled block.

    Anthropic's Messages API accepts ``system`` as either a string or a list
    of content blocks; the list form is the only one that supports
    ``cache_control``. We always cache the system prompt because (a) it's
    static across iterations and (b) it's the largest fixed prefix in every
    request — the 1.25× write premium pays back on the first cache read.
    """
    return [{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}]


def cached_user_text(text: str) -> dict[str, Any]:
    """Build a user message whose single text block carries a cache breakpoint.

    Used for the synthesizer's initial task message, which embeds both the
    full ``SurfaceomeEvidenceDraft`` + ``BiologicalContextDraft`` ledgers and
    the schema definition — large, static across repair iterations.
    """
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}
        ],
    }


def mark_latest_tool_result_for_cache(messages: list[dict[str, Any]]) -> None:
    """Rotate the rolling cache breakpoint onto the most recent tool_result.

    Walks ``messages`` from the end. The last ``tool_result`` block in the
    most-recent user message gets ``cache_control: ephemeral`` attached.
    Every earlier ``tool_result`` block (including in older user messages)
    has its ``cache_control`` stripped, so each request only ever carries
    two breakpoints (system + latest tool_result) — well under Anthropic's
    4-breakpoint per-request limit, even on a 30-iteration run.
    """
    found_latest = False
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        tr_blocks = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"]
        if not tr_blocks:
            continue
        if not found_latest:
            tr_blocks[-1]["cache_control"] = {"type": "ephemeral"}
            for block in tr_blocks[:-1]:
                block.pop("cache_control", None)
            found_latest = True
        else:
            for block in tr_blocks:
                block.pop("cache_control", None)


__all__ = [
    "compact_for_agent_transport",
    "cached_system",
    "cached_user_text",
    "mark_latest_tool_result_for_cache",
]
