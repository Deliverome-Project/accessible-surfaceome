"""Internalization clip-select stage — now a thin wrapper over the SHARED select
stage in ``agents/_support/literature_clips``. Supplies the internalization
defaults (its select prompt, its menu instruction, the ``int_evi_`` evidence-id
prefix); the select + span-verified promotion logic is shared with tag-site.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from accessible_surfaceome.agents._support.literature_clips import (
    _normalize_clip_id,  # noqa: F401 - re-exported for tests
    promote as _promote,
    promote_selections,
    render_clip_menu,  # noqa: F401 - re-exported for callers/tests
    select_clips as _select_clips,
)
from accessible_surfaceome.agents.plan_trim_select.schemas import SelectionResponse
from accessible_surfaceome.tools._shared.models import Evidence, EvidenceClaim, EvidenceClaimDraft
from accessible_surfaceome.tools._shared.source_text import SourceTextStore

_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "literature_select_system.md"
_MENU_INSTRUCTION = (
    "pick the internalization-relevant clips by clip_id; do NOT paraphrase — the "
    "quote is auto-filled from the clip"
)
_EVIDENCE_ID_PREFIX = "int_evi_"


def load_select_prompt() -> str:
    return _PROMPT_PATH.read_text()


def _promote_selections(
    selection_response: SelectionResponse,
    *,
    pool: dict[str, EvidenceClaimDraft],
    evidence_id_prefix: str = _EVIDENCE_ID_PREFIX,
) -> tuple[list[EvidenceClaim], list[str]]:
    return promote_selections(selection_response, pool=pool, evidence_id_prefix=evidence_id_prefix)


def select_clips(
    client: Any,
    *,
    pool: dict[str, EvidenceClaimDraft],
    gene: str,
    synonyms: list[str] | None = None,
    system_prompt: str | None = None,
) -> SelectionResponse:
    return _select_clips(
        client,
        pool=pool,
        gene=gene,
        synonyms=synonyms,
        system_prompt=system_prompt or load_select_prompt(),
        menu_instruction=_MENU_INSTRUCTION,
    )


def promote(
    selection: SelectionResponse,
    *,
    pool: dict[str, EvidenceClaimDraft],
    store: SourceTextStore,
) -> list[Evidence]:
    return _promote(selection, pool=pool, store=store, evidence_id_prefix=_EVIDENCE_ID_PREFIX)
