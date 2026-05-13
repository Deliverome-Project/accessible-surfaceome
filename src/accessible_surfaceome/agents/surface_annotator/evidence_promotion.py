"""Promote agent-emitted ``EvidenceClaim`` records into full ``Evidence``.

This is the orchestrator-side bookkeeping that anchors each claim's verbatim
quote to a cached source body. The agent never sees this code; it emits the
small ``EvidenceClaim`` shape (claim + quote + source_id), and we run:

1. Look up the source body by ``source_id`` in the run's :class:`SourceTextStore`.
2. Normalize source body and quote (NFKC + Greek + HTML entities + whitespace
   + lowercase) so byte-level inconsistencies between abstract text and the
   agent's quoted form don't sink the substring check.
3. Substring-search the normalized quote in the normalized source body.
4. On success: build the full :class:`Evidence` chain (``EvidenceSpan`` →
   ``SourceRef``) with hashes and char offset; ``entailment_verified=True``.
5. On failure: persist the claim with ``entailment_verified=False`` and a
   warning. We don't reject — the claim is still useful debug data and
   gets surfaced in the run summary.

The companion ``build_search_log`` walks ``events.jsonl`` after the run and
builds ``SearchEntry`` records for every tool consultation, populating
``contributed_evidence_ids`` from a ``source_id → [evidence_id]`` map.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import HttpUrl

from accessible_surfaceome.tools._shared.models import (
    Evidence,
    EvidenceClaim,
    EvidenceSpan,
    SearchEntry,
    SourceRef,
)
from accessible_surfaceome.tools._shared.normalize import (
    find_quote_in_normalized,
    normalize_for_quote_matching,
)
from accessible_surfaceome.tools._shared.source_text import SourceTextStore

logger = logging.getLogger(__name__)


def promote_claim(claim: EvidenceClaim, *, store: SourceTextStore) -> Evidence:
    """Promote one ``EvidenceClaim`` into a validated ``Evidence`` record.

    Failure modes are persisted as ``Evidence`` with ``entailment_verified=False``
    and a ``validation_warnings`` entry — never raises. The agent's claim, its
    classification metadata, and the cited source_id are preserved either way;
    only the anchored span is contingent on the substring check passing.
    """

    base_kwargs: dict[str, Any] = {
        "evidence_id": claim.evidence_id,
        "claim": claim.claim,
        "claim_type": claim.claim_type,
        "direction": claim.direction,
        "evidence_type": claim.evidence_type,
        "evidence_tier": claim.evidence_tier,
        "confidence": claim.confidence,
        "assay_context": claim.assay_context,
    }

    source = store.get(claim.source_id)
    if source is None:
        return Evidence(
            **base_kwargs,
            spans=[],
            entailment_verified=False,
            validation_warnings=[
                f"source_id={claim.source_id} not in session source store "
                f"(agent cited a source it didn't fetch)"
            ],
        )

    normalized_quote = normalize_for_quote_matching(claim.quote)
    char_offset = find_quote_in_normalized(normalized_quote, source.normalized_text)
    if char_offset is None:
        return Evidence(
            **base_kwargs,
            spans=[],
            entailment_verified=False,
            validation_warnings=[
                f"substring not found in normalized {claim.source_id} text "
                f"after normalization (NFKC + Greek + HTML + whitespace + lowercase)"
            ],
        )

    span = EvidenceSpan(
        source=SourceRef(
            source_type=source.source_type,
            source_id=source.source_id,
            pmc_id=_extract_pmc_id(source.source_id),
            url=HttpUrl(source.url),
            title=source.title or claim.source_id,
            retrieved_at=source.retrieved_at,
            content_sha256=source.content_sha256,
            publication_type=source.publication_type,
            is_retracted=source.is_retracted,
            retraction_checked_at=source.retraction_checked_at,
            license=source.license,
        ),
        section=claim.section,
        figure_or_table_id=claim.figure_or_table_id,
        quote=claim.quote,
        quote_sha256=hashlib.sha256(claim.quote.encode("utf-8")).hexdigest(),
        char_offset=char_offset,
        normalized_source_sha256=source.normalized_source_sha256,
    )
    return Evidence(
        **base_kwargs,
        spans=[span],
        entailment_verified=True,
        validation_warnings=[],
    )


def _extract_pmc_id(source_id: str) -> str | None:
    """Pull the PMC accession out of a ``"PMC:PMC..."`` source_id."""

    if source_id.startswith("PMC:"):
        return source_id.split(":", 1)[1]
    return None


# ---------------------------------------------------------------------------
# search_log construction from events.jsonl
# ---------------------------------------------------------------------------


def build_search_log(
    events_path: Path,
    *,
    contributed_by: dict[str, list[str]] | None = None,
) -> list[SearchEntry]:
    """Walk ``events.jsonl`` and produce one ``SearchEntry`` per tool call.

    The events file is the orchestrator's authoritative record of what the
    agent looked at. We pair each ``agent.custom_tool_use`` with its
    matching ``user.custom_tool_result`` (by ``custom_tool_use_id``) and
    build a structured entry with the tool name, mode, query parameters,
    and source_ids touched.

    ``contributed_by`` maps ``source_id → [evidence_id, ...]`` so we can
    populate ``SearchEntry.contributed_evidence_ids`` for the entries
    whose sources actually got cited. Pass ``None`` (or omit) when you
    don't have evidence yet — the entries will all carry an empty list.
    """

    contributed_by = contributed_by or {}
    if not events_path.exists():
        return []

    tool_uses: dict[str, dict[str, Any]] = {}
    tool_results: dict[str, dict[str, Any]] = {}
    use_order: list[str] = []

    with events_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            etype = event.get("type")
            if etype == "agent.custom_tool_use":
                use_id = event.get("id")
                if not use_id:
                    continue
                tool_uses[use_id] = event
                use_order.append(use_id)
            elif etype == "user.custom_tool_result":
                use_id = event.get("custom_tool_use_id")
                if use_id:
                    tool_results[use_id] = event

    entries: list[SearchEntry] = []
    for use_id in use_order:
        use = tool_uses[use_id]
        result = tool_results.get(use_id)
        entry = _build_search_entry(use, result, contributed_by)
        if entry is not None:
            entries.append(entry)
    return entries


def _build_search_entry(
    use: dict[str, Any],
    result: dict[str, Any] | None,
    contributed_by: dict[str, list[str]],
) -> SearchEntry | None:
    tool = use.get("name") or "unknown"
    raw_input = use.get("input") or {}
    mode = raw_input.get("mode")
    sources_seen: list[str] = []
    n_results = 0

    if result is not None:
        result_text = _result_text(result)
        if result_text is not None:
            try:
                payload = json.loads(result_text)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                sources_seen, n_results = _extract_sources(tool, mode, payload)

    contributed = sorted(
        {
            evi
            for source_id in sources_seen
            for evi in contributed_by.get(source_id, [])
        }
    )
    return SearchEntry(
        tool=tool,
        mode=mode,
        query={k: v for k, v in raw_input.items() if k != "mode"},
        n_results=n_results,
        sources_seen=sources_seen,
        retrieved_at=datetime.now(UTC),
        contributed_evidence_ids=contributed,
    )


def _result_text(result_event: dict[str, Any]) -> str | None:
    """Pull the JSON-stringified tool result out of a ``user.custom_tool_result``.

    The event's ``content`` field is ``[{type: "text", text: "..."}]`` per the
    SDK conventions. We grab the first text block; tool returns are always a
    single Pydantic-dumped JSON document.
    """

    content = result_event.get("content") or []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                return text
    return None


def _extract_sources(
    tool: str, mode: str | None, payload: dict[str, Any]
) -> tuple[list[str], int]:
    """Map a tool's structured return to ``(sources_seen, n_results)``.

    The sources_seen format mirrors :class:`SourceTextStore`'s source_id
    convention so the search log joins cleanly with promoted evidence.
    """

    if tool == "gene_lookup":
        acc = payload.get("uniprot_acc")
        if isinstance(acc, str) and acc:
            return [f"UniProt:{acc}"], 1
        return [], 0

    if tool == "gene_literature":
        if mode in {"gene2pubmed", "topic_search"}:
            papers = payload.get("papers") or []
            ids: list[str] = []
            for paper in papers:
                if isinstance(paper, dict) and paper.get("pmid") is not None:
                    ids.append(f"PMID:{paper['pmid']}")
            n_total = payload.get("n_total")
            return ids, int(n_total) if isinstance(n_total, int) else len(ids)
        if mode == "fetch_abstract":
            pmid = payload.get("pmid")
            return ([f"PMID:{pmid}"] if pmid is not None else [], 1)
        if mode == "fetch_fulltext":
            pmcid = payload.get("pmc_id")
            return ([f"PMC:{pmcid}"] if pmcid else [], 1)
        return [], 0

    if tool == "patent_lookup":
        wo = payload.get("wo_number")
        return ([f"WO:{wo}"] if wo else [], 1)

    if tool == "evidence_retrieval":
        ids: list[str] = []
        for paper in payload.get("papers") or []:
            if not isinstance(paper, dict):
                continue
            pmc_id = paper.get("pmc_id")
            if pmc_id:
                ids.append(f"PMC:{pmc_id}")
            pmid = paper.get("pmid")
            if pmid is not None:
                ids.append(f"PMID:{pmid}")
        for synthetic in payload.get("synthetic_sources") or []:
            if isinstance(synthetic, dict):
                src = synthetic.get("source_id")
                if src:
                    ids.append(src)
        n_results = int(payload.get("n_papers_with_snippets") or len(ids))
        return ids, n_results

    return [], 0


__all__ = ["promote_claim", "build_search_log"]
