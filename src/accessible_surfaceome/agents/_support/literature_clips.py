"""SHARED clip-pool construction (body fetch via ``apply_triage_outcomes``) + a
REAL ``SourceTextStore`` built from fetched body text. Used by BOTH the
internalization and tag-site literature agents (agent-agnostic — only shared
primitives). Extracted from agents/internalization/literature_pool.py.

This is the crux of genuine span verification: the deep-dive orchestrator
promotes claims against a *synthetic* store (char-offsets into a concatenated
quote-blob), so its offsets don't point at the real paper. Here we register the
actual fetched full text (or the abstract when no body was fetched) so
``promote_claim`` yields real char offsets into the real source.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from accessible_surfaceome.agents.plan_trim_select.abstract_triage import (
    TriageAction,
    apply_triage_outcomes,
)
from accessible_surfaceome.tools._shared.europepmc import fetch_fulltext
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import EvidenceClaimDraft, Paper
from accessible_surfaceome.agents._support.evidence_promotion import promote_claim
from accessible_surfaceome.agents._support.structured_call import (
    SONNET_MODEL,
    call_model_structured,
)
from accessible_surfaceome.agents.plan_trim_select.schemas import SelectionResponse
from accessible_surfaceome.tools._shared.models import Evidence, EvidenceClaim
from accessible_surfaceome.tools._shared.normalize import normalize_for_quote_matching
from accessible_surfaceome.tools._shared.source_text import SourceText, SourceTextStore


def _add_to_pool(
    draft: EvidenceClaimDraft,
    pool: dict[str, EvidenceClaimDraft],
    by_source: dict[str, list[EvidenceClaimDraft]],
) -> None:
    """Verbatim copy of ``plan_trim_select.runner._add_to_pool`` (module-private
    there; copied rather than imported). Inserts a draft under a globally-unique
    clip_id with content-dedup within a source."""
    normalized = normalize_for_quote_matching(draft.quote)
    for existing in by_source.get(draft.source_id, []):
        if normalize_for_quote_matching(existing.quote) == normalized:
            return
    clip_id = draft.suggested_evidence_id
    if clip_id in pool:
        k = 2
        while f"{clip_id}_{k}" in pool:
            k += 1
        clip_id = f"{clip_id}_{k}"
    redrafted = draft.model_copy(update={"suggested_evidence_id": clip_id})
    pool[clip_id] = redrafted
    by_source[redrafted.source_id].append(redrafted)


def build_pool(
    outcomes: list[Any],
    papers_by_id: dict[str, Paper],
    *,
    http: CachedHTTP,
    retraction_index: Any,
) -> tuple[dict[str, EvidenceClaimDraft], list[TriageAction]]:
    """Run body fetch for ``worth_fetching`` outcomes and build the clip pool.
    Returns ``(pool, actions)``."""
    pool: dict[str, EvidenceClaimDraft] = {}
    by_source: dict[str, list[EvidenceClaimDraft]] = defaultdict(list)
    actions = apply_triage_outcomes(
        outcomes,
        papers_by_id,
        pool=pool,
        by_source=by_source,
        http=http,
        retraction_index=retraction_index,
        add_to_pool_fn=_add_to_pool,
    )
    return pool, actions


def _body_text(
    paper: Paper,
    *,
    fetched: bool,
    http: CachedHTTP,
    retraction_index: Any,
    drafts: list[EvidenceClaimDraft],
) -> str:
    """Store body for span verification. ALWAYS include the abstract (a paper
    can contribute abstract-derived clips even after it was fetched — e.g. a
    worth_fetching body-fetch that fell back to the abstract), PLUS the
    full-text body when fetched, from two complementary sources:

    * **Real JATS body** (``fetch_fulltext``) when the paper has a PMC id AND PMC
      returns sections — so clips keep offsets into the real source text.
    * **Body-derived clip drafts** — folded in for EVERY fetched paper as the
      span-verify safety net. The drafts in the pool ARE verbatim excerpts of the
      body ``abstract_triage`` actually fetched (whatever the path), and are
      exactly what ``select`` picks from. This covers the cases the JATS re-fetch
      misses: (a) non-PMC papers — bioRxiv/medRxiv preprints, Unpaywall/DataCite
      OA-PDF-only papers (PMC has nothing) — the TMEM123/EndoNB gap; AND (b) a
      paper WITH a PMC id whose JATS came back empty, so ``abstract_triage``
      fetched the body via Unpaywall/DataCite instead (the PMC-PDF-only case) —
      the ``if``/``elif`` version silently dropped those body clips too. Without
      this, body-derived clips fail verification against an abstract-only store
      and get silently dropped. For a normal PMC paper the real JATS body is
      added first, so its clips keep real offsets and the redundant draft copies
      are harmless (first-occurrence match wins)."""
    parts: list[str] = []
    abstract = getattr(paper, "abstract", None)
    if abstract:
        parts.append(abstract)
    if fetched and paper.pmc_id:
        full = fetch_fulltext(http=http, pmcid=paper.pmc_id, retraction_index=retraction_index)
        secs = getattr(full, "sections", None) or []
        parts.extend(s.text for s in secs if getattr(s, "text", None))
    if fetched:
        # Safety net — ALWAYS fold in the body-derived drafts (verbatim excerpts
        # of the fetched body), not just when pmc_id is absent, so a PMC paper
        # with empty JATS (body via Unpaywall/DataCite) doesn't lose its clips.
        parts.extend(d.quote for d in drafts if getattr(d, "quote", None))
    return "\n\n".join(parts)


def build_source_store(
    pool: dict[str, EvidenceClaimDraft],
    *,
    papers_by_source_id: dict[str, tuple[Paper, bool]],
    http: CachedHTTP,
    retraction_index: Any,
) -> SourceTextStore:
    """Register a real ``SourceText`` for every source_id present in the pool
    (full body when the paper was fetched, else its abstract)."""
    store = SourceTextStore()
    drafts_by_source: dict[str, list[EvidenceClaimDraft]] = defaultdict(list)
    for draft in pool.values():
        drafts_by_source[draft.source_id].append(draft)
    for source_id in drafts_by_source:
        entry = papers_by_source_id.get(source_id)
        if entry is None:
            continue
        paper, fetched = entry
        raw = _body_text(
            paper,
            fetched=fetched,
            http=http,
            retraction_index=retraction_index,
            drafts=drafts_by_source[source_id],
        )
        if not raw:
            continue
        norm = normalize_for_quote_matching(raw)
        now = datetime.now(UTC)
        url = (
            f"https://pubmed.ncbi.nlm.nih.gov/{paper.pmid}/"
            if paper.pmid
            else f"https://www.ncbi.nlm.nih.gov/pmc/articles/{paper.pmc_id}/"
        )
        store.put(
            SourceText(
                source_id=source_id,
                source_type="pubmed",
                url=url,
                title=paper.title,
                raw_text=raw,
                normalized_text=norm,
                content_sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                normalized_source_sha256=hashlib.sha256(norm.encode("utf-8")).hexdigest(),
                retrieved_at=now,
                publication_type=paper.publication_type,
                is_retracted=bool(getattr(paper, "is_retracted", False)),
                retraction_checked_at=now,
                license="unknown",
                authors=tuple(getattr(paper, "authors", []) or []),
                year=getattr(paper, "year", None),
                journal=getattr(paper, "journal", None),
            )
        )
    return store


# --- clip selection + span-verified promotion (shared) ----------------------

logger = logging.getLogger(__name__)
_MAX_TOKENS_SELECT = 32_000
_MAX_CLIP_MENU = 100
_RETRY_CLIP_MENU = 40
_DEFAULT_MENU_INSTRUCTION = (
    "pick the relevant clips by clip_id; do NOT paraphrase — the quote is "
    "auto-filled from the clip"
)


def _normalize_clip_id(clip_id: str) -> str:
    s = re.sub(r"[^a-z0-9]", "", clip_id.lower())
    return re.sub(r"pmid|pmc", "", s)


def promote_selections(
    selection_response: SelectionResponse,
    *,
    pool: dict[str, EvidenceClaimDraft],
    evidence_id_prefix: str,
) -> tuple[list[EvidenceClaim], list[str]]:
    """Selected clip_ids -> EvidenceClaims, copying each clip's quote VERBATIM
    from the pool (the model never authors quotes). Fuzzy-matches a mangled
    clip_id when it normalizes to exactly one pool entry."""
    norm_index: dict[str, list[str]] = defaultdict(list)
    for cid in pool:
        norm_index[_normalize_clip_id(cid)].append(cid)
    claims: list[EvidenceClaim] = []
    warnings: list[str] = []
    seq = 1
    for sel in selection_response.selections:
        draft = pool.get(sel.clip_id)
        if draft is None:
            candidates = norm_index.get(_normalize_clip_id(sel.clip_id), [])
            if len(candidates) == 1:
                draft = pool[candidates[0]]
            else:
                detail = f"{len(candidates)} normalized matches" if candidates else "no match"
                warnings.append(
                    f"selector picked unknown clip_id={sel.clip_id!r} ({detail}); skipping"
                )
                continue
        claim = EvidenceClaim(
            evidence_id=f"{evidence_id_prefix}{seq:02d}",
            claim=sel.claim,
            claim_type=sel.claim_type,
            direction=sel.direction,
            evidence_type=sel.evidence_type,
            evidence_tier=sel.evidence_tier,
            confidence=sel.confidence,
            assay_context=sel.assay_context,
            source_id=draft.source_id,
            quote=draft.quote,  # verbatim, copied from the pool
            section=draft.section,
            figure_or_table_id=draft.figure_or_table_id,
        )
        claims.append(claim)
        seq += 1
    return claims, warnings


def render_clip_menu(pool: dict[str, EvidenceClaimDraft], *, limit: int | None = None) -> str:
    """Render the clip menu. When ``limit`` is set and the pool is larger, keep
    only the top-``limit`` clips by draft score (bounds the selector's output)."""
    items = list(pool.items())
    if limit is not None and len(items) > limit:
        items = sorted(
            items, key=lambda kv: getattr(kv[1], "score", 0.0) or 0.0, reverse=True
        )[:limit]
    return "\n".join(
        f"[{clip_id}] ({d.source_id}, {d.section}): {d.quote}" for clip_id, d in items
    )


def _build_select_prompt(
    pool: dict[str, EvidenceClaimDraft],
    *,
    gene: str,
    synonyms: list[str] | None,
    menu_limit: int | None,
    menu_instruction: str,
) -> str:
    schema_str = json.dumps(SelectionResponse.model_json_schema(), indent=2)
    aka = f"Also known as: {', '.join(synonyms)}\n" if synonyms else ""
    return (
        f"Gene: {gene}\n{aka}\nClip menu ({menu_instruction}):\n\n"
        f"{render_clip_menu(pool, limit=menu_limit)}\n\n"
        f"Emit one ```json block matching this SelectionResponse schema exactly "
        f"(note: `confidence` is strong|moderate|weak; `assay_context` is an "
        f"object with a required `species`):\n\n```json\n{schema_str}\n```"
    )


def select_clips(
    client: Any,
    *,
    pool: dict[str, EvidenceClaimDraft],
    gene: str,
    synonyms: list[str] | None = None,
    system_prompt: str,
    model: str = SONNET_MODEL,
    menu_instruction: str = _DEFAULT_MENU_INSTRUCTION,
    usage_sink: list[Any] | None = None,
) -> SelectionResponse:
    """Ask the selector to pick relevant clips by clip_id (never authoring quotes),
    resiliently: cap the menu at the top clips by score, salvage-retry with a
    smaller menu, and last-resort return an empty selection so one clip-dense gene
    can't crash the run."""
    if not pool:
        return SelectionResponse(selections=[], notes="empty pool")
    for menu_limit, label in ((_MAX_CLIP_MENU, "capped"), (_RETRY_CLIP_MENU, "salvage")):
        if len(pool) > menu_limit:
            logger.info("select %s: clip menu %d -> top %d by score (%s)",
                        gene, len(pool), menu_limit, label)
        try:
            return call_model_structured(
                client,
                model=model,
                system_prompt=system_prompt,
                user_prompt=_build_select_prompt(
                    pool, gene=gene, synonyms=synonyms, menu_limit=menu_limit,
                    menu_instruction=menu_instruction,
                ),
                schema=SelectionResponse,
                max_tokens=_MAX_TOKENS_SELECT,
                usage_sink=usage_sink,
            )
        except ValueError as err:
            logger.warning("select failed for %s (menu<=%d): %s", gene, menu_limit, str(err)[:140])
    logger.error("select giving up for %s after menu-cap retries — empty selection", gene)
    return SelectionResponse(selections=[], notes="select failed after menu-cap retries")


def promote(
    selection: SelectionResponse,
    *,
    pool: dict[str, EvidenceClaimDraft],
    store: SourceTextStore,
    evidence_id_prefix: str,
) -> list[Evidence]:
    """Selected clips -> span-verified Evidence (real char offsets into the
    fetched body via promote_claim)."""
    claims, _warnings = promote_selections(selection, pool=pool, evidence_id_prefix=evidence_id_prefix)
    return [promote_claim(c, store=store) for c in claims]
