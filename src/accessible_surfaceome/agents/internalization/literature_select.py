"""Select internalization clips from the pool (Sonnet), then promote the
selected claims to span-verified ``Evidence`` against the REAL source store.

``_normalize_clip_id`` + ``_promote_selections`` are copied verbatim from
``plan_trim_select.runner`` (module-private there) with the internalization
``int_evi_`` id prefix.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from accessible_surfaceome.agents._support.evidence_promotion import promote_claim
from accessible_surfaceome.agents.internalization.model_prior import (
    SONNET_MODEL,
    call_model_structured,
)
from accessible_surfaceome.agents.plan_trim_select.schemas import SelectionResponse
from accessible_surfaceome.tools._shared.models import (
    Evidence,
    EvidenceClaim,
    EvidenceClaimDraft,
)
from accessible_surfaceome.tools._shared.source_text import SourceTextStore

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "literature_select_system.md"
# A clip-dense gene (a heavily-studied ADC target like a folate/PSMA receptor)
# emits a huge SelectionResponse. At 16k the JSON still truncated mid-object and
# the repair loop can't fix a cut-off output (it re-truncates and appends the
# broken text), crashing that gene. 32k gives ample headroom paired with the
# clip-menu cap below; you only pay for tokens actually generated.
_MAX_TOKENS_SELECT = 32_000
# Cap the menu SHOWN to the selector at the top-N clips by score — this bounds how
# many clips it can select, which bounds the output size (the truncation root
# cause). The full pool is still used for promotion; only the pick-from menu is
# capped. A salvage retry uses a much smaller menu if the capped one still fails.
_MAX_CLIP_MENU = 100
_RETRY_CLIP_MENU = 40


def load_select_prompt() -> str:
    return _PROMPT_PATH.read_text()


def _normalize_clip_id(clip_id: str) -> str:
    s = re.sub(r"[^a-z0-9]", "", clip_id.lower())
    return re.sub(r"pmid|pmc", "", s)


def _promote_selections(
    selection_response: SelectionResponse,
    *,
    pool: dict[str, EvidenceClaimDraft],
    evidence_id_prefix: str = "int_evi_",
) -> tuple[list[EvidenceClaim], list[str]]:
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


def render_clip_menu(
    pool: dict[str, EvidenceClaimDraft], *, limit: int | None = None
) -> str:
    """Render the clip menu. When ``limit`` is set and the pool is larger, keep
    only the top-``limit`` clips by draft score (most relevant) — bounding the
    selector's output. Equal scores keep insertion order (stable sort)."""
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
) -> str:
    schema_str = json.dumps(SelectionResponse.model_json_schema(), indent=2)
    aka = f"Also known as: {', '.join(synonyms)}\n" if synonyms else ""
    return (
        f"Gene: {gene}\n{aka}\nClip menu (pick the internalization-relevant clips "
        f"by clip_id; do NOT paraphrase — the quote is auto-filled from the "
        f"clip):\n\n"
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
    system_prompt: str | None = None,
) -> SelectionResponse:
    """Ask the selector to pick internalization-relevant clips, resiliently.

    A clip-dense gene can make the selector emit a ``SelectionResponse`` that
    overruns ``max_tokens`` and truncates mid-JSON — which the repair loop cannot
    fix (it crashed FOLH1 in the pilot). Defense-in-depth so ONE dense gene never
    crashes: (1) cap the menu at the top clips by score (bounds the selection
    count), (2) on failure retry once with a much smaller menu, (3) last resort
    return an empty selection — the gene then grades on whatever else it has
    (``unknown`` if nothing) instead of aborting the whole annotation."""
    system_prompt = system_prompt or load_select_prompt()
    if not pool:
        return SelectionResponse(selections=[], notes="empty pool")
    for menu_limit, label in ((_MAX_CLIP_MENU, "capped"), (_RETRY_CLIP_MENU, "salvage")):
        if len(pool) > menu_limit:
            logger.info(
                "select %s: clip menu %d -> top %d by score (%s)",
                gene, len(pool), menu_limit, label,
            )
        try:
            return call_model_structured(
                client,
                model=SONNET_MODEL,
                system_prompt=system_prompt,
                user_prompt=_build_select_prompt(
                    pool, gene=gene, synonyms=synonyms, menu_limit=menu_limit
                ),
                schema=SelectionResponse,
                max_tokens=_MAX_TOKENS_SELECT,
            )
        except ValueError as err:
            logger.warning(
                "select failed for %s (menu<=%d): %s", gene, menu_limit, str(err)[:140]
            )
    logger.error("select giving up for %s after menu-cap retries — empty selection", gene)
    return SelectionResponse(selections=[], notes="select failed after menu-cap retries")


def promote(
    selection: SelectionResponse,
    *,
    pool: dict[str, EvidenceClaimDraft],
    store: SourceTextStore,
) -> list[Evidence]:
    """Selected clips → span-verified Evidence (real char offsets into the
    fetched body via promote_claim)."""
    claims, _warnings = _promote_selections(selection, pool=pool, evidence_id_prefix="int_evi_")
    return [promote_claim(c, store=store) for c in claims]
