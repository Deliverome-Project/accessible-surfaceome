"""Select internalization clips from the pool (Sonnet), then promote the
selected claims to span-verified ``Evidence`` against the REAL source store.

``_normalize_clip_id`` + ``_promote_selections`` are copied verbatim from
``plan_trim_select.runner`` (module-private there) with the internalization
``int_evi_`` id prefix.
"""

from __future__ import annotations

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

_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "literature_select_system.md"
_MAX_TOKENS_SELECT = 8_000


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


def render_clip_menu(pool: dict[str, EvidenceClaimDraft]) -> str:
    lines: list[str] = []
    for clip_id, d in pool.items():
        lines.append(f"[{clip_id}] ({d.source_id}, {d.section}): {d.quote}")
    return "\n".join(lines)


def select_clips(
    client: Any,
    *,
    pool: dict[str, EvidenceClaimDraft],
    gene: str,
    system_prompt: str | None = None,
) -> SelectionResponse:
    system_prompt = system_prompt or load_select_prompt()
    if not pool:
        return SelectionResponse(selections=[], notes="empty pool")
    user = (
        f"Gene: {gene}\n\nClip menu (pick the internalization-relevant clips by "
        f"clip_id; do NOT paraphrase — the quote is auto-filled from the clip):\n\n"
        f"{render_clip_menu(pool)}\n\nReturn one ```json SelectionResponse object."
    )
    return call_model_structured(
        client,
        model=SONNET_MODEL,
        system_prompt=system_prompt,
        user_prompt=user,
        schema=SelectionResponse,
        max_tokens=_MAX_TOKENS_SELECT,
    )


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
