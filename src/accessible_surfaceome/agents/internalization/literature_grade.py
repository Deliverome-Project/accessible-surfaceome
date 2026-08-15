"""Grade internalization by mode (basal / native-ligand / therapeutic) from the
span-verified evidence ledger (Sonnet). Emits a ``LiteratureLLMOut``; code then
scrubs any cited_source_ids the model invented that aren't in the ledger."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from accessible_surfaceome.agents.internalization.model_prior import (
    SONNET_MODEL,
    call_model_structured,
)
from accessible_surfaceome.agents.internalization.models import LiteratureLLMOut

_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "literature_grade_system.md"
_MAX_TOKENS_GRADE = 16_000


def load_grade_prompt() -> str:
    return _PROMPT_PATH.read_text()


def _render_evidence(evidence: list[Any]) -> str:
    lines: list[str] = []
    for e in evidence:
        span = e.spans[0] if getattr(e, "spans", None) else None
        source_id = span.source.source_id if span else "?"
        quote = span.quote if span else ""
        lines.append(f"[{e.evidence_id}] ({source_id}) {e.claim} | quote: {quote}")
    return "\n".join(lines)


def _scrub_unknown_cites(out: LiteratureLLMOut, *, known: set[str]) -> LiteratureLLMOut:
    def keep(ids: list[str]) -> list[str]:
        return [i for i in ids if i in known]

    gbm = out.grades_by_mode
    new_gbm = gbm.model_copy(
        update={
            "basal": gbm.basal.model_copy(
                update={"cited_source_ids": keep(gbm.basal.cited_source_ids)}
            ),
            "native_ligand": gbm.native_ligand.model_copy(
                update={"cited_source_ids": keep(gbm.native_ligand.cited_source_ids)}
            ),
            "therapeutic": gbm.therapeutic.model_copy(
                update={"cited_source_ids": keep(gbm.therapeutic.cited_source_ids)}
            ),
        }
    )
    new_obs = [
        o.model_copy(update={"cited_source_ids": keep(o.cited_source_ids)})
        for o in out.observations
    ]
    return out.model_copy(update={"grades_by_mode": new_gbm, "observations": new_obs})


def grade_from_evidence(
    client: Any,
    *,
    gene: str,
    evidence: list[Any],
    synonyms: list[str] | None = None,
    system_prompt: str | None = None,
) -> LiteratureLLMOut:
    if not evidence:
        return LiteratureLLMOut()  # nothing to grade → all modes 'unknown'
    system_prompt = system_prompt or load_grade_prompt()
    schema_str = json.dumps(LiteratureLLMOut.model_json_schema(), indent=2)
    aka = f"Also known as: {', '.join(synonyms)}\n" if synonyms else ""
    user = (
        f"Gene: {gene}\n{aka}\nSpan-verified evidence ledger (cite ONLY these "
        f"evidence_ids):\n\n{_render_evidence(evidence)}\n\n"
        f"Emit one ```json block matching this LiteratureLLMOut schema exactly:\n\n"
        f"```json\n{schema_str}\n```"
    )
    out = call_model_structured(
        client,
        model=SONNET_MODEL,
        system_prompt=system_prompt,
        user_prompt=user,
        schema=LiteratureLLMOut,
        max_tokens=_MAX_TOKENS_GRADE,
    )
    return _scrub_unknown_cites(out, known={e.evidence_id for e in evidence})
