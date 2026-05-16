"""A1 → ``EvidenceGradeBlock`` (grade + rationale + non_surface_expression).

Single object output that bundles the three things this builder produces
for the assembled ``SurfaceEvidence`` block.
"""

from __future__ import annotations

import logging
from typing import Any

from anthropic import Anthropic
from pydantic import BaseModel, ConfigDict, Field

from accessible_surfaceome.agents._support.pricing import UsageRecord
from accessible_surfaceome.agents.surfaceome_v2.builders._common import (
    MAX_TOKENS_HEAVY,
    call_builder,
    format_ledger_block,
    format_schema_block,
    load_prompt,
)
from accessible_surfaceome.tools._shared.models import (
    EvidenceClaim,
    EvidenceGrade,
    NonSurfaceExpression,
)

logger = logging.getLogger(__name__)


class EvidenceGradeBlock(BaseModel):
    """Bundle: the A1 evidence grade verdict + supporting non-surface rows."""

    model_config = ConfigDict(extra="forbid")

    evidence_grade: EvidenceGrade
    grade_rationale: str
    non_surface_expression: list[NonSurfaceExpression] = Field(default_factory=list)


_DEFAULT_BLOCK = EvidenceGradeBlock(
    evidence_grade="weak",
    grade_rationale="No evidence claims were available to grade.",
    non_surface_expression=[],
)


def build_evidence_grade(
    claims: list[EvidenceClaim],
    *,
    client: Anthropic,
    usage_sink: list[UsageRecord],
    context: dict[str, Any] | None = None,
) -> EvidenceGradeBlock:
    """Grade the A1 ledger + emit non-surface expression rows.

    Always returns a valid :class:`EvidenceGradeBlock` — the orchestrator
    can't assemble a SurfaceEvidence block without a grade. Falls back to
    ``"weak"`` / empty when no claims or repair failure.
    """
    context = context or {}
    if not claims:
        return _DEFAULT_BLOCK
    gene = context.get("gene", "<unknown>")
    system_prompt = load_prompt("evidence_grade_builder_system")
    user_prompt = (
        f"# Gene: {gene}\n\n"
        f"{format_ledger_block(claims, header='A1 full ledger')}\n"
        f"{format_schema_block(EvidenceGradeBlock.model_json_schema(), name='EvidenceGradeBlock')}\n"
        "Emit ONE fenced ```json block containing a JSON OBJECT with keys "
        "`evidence_grade`, `grade_rationale`, `non_surface_expression`. "
        "No prose around it.\n"
    )
    parsed = call_builder(
        client,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=EvidenceGradeBlock,
        usage_sink=usage_sink,
        label="evidence_grade_builder",
        # Heavy builder: consumes the FULL A1 ledger and emits both a
        # grade verdict + a non_surface_expression list. The latter can
        # be long on broadly-expressed proteins.
        max_tokens=MAX_TOKENS_HEAVY,
    )
    if parsed is None or not isinstance(parsed, EvidenceGradeBlock):
        logger.warning("evidence_grade_builder failed → falling back to weak/empty")
        return _DEFAULT_BLOCK
    known = {c.evidence_id for c in claims}
    cleaned_rows = [
        row.model_copy(
            update={
                "cited_evidence_ids": [i for i in row.cited_evidence_ids if i in known]
            }
        )
        for row in parsed.non_surface_expression
    ]
    return parsed.model_copy(update={"non_surface_expression": cleaned_rows})


__all__ = ["EvidenceGradeBlock", "build_evidence_grade"]
