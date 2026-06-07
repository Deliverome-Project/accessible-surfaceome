"""A2 → ``BiologicalContextGradeBlock`` (grade + rationale + cited_evidence_ids).

The A2 analog of :mod:`evidence_grade`. A1's ``evidence_grade`` rolls up the
surface-accessibility *methods* + contradictions into a five-value grade;
this builder rolls up the A2 *biological context* — expression,
subcellular_localization, anatomical_accessibility, accessibility_modulation
(cell-state context now lives in accessibility_modulation) — into a single
``biological_context_grade`` capturing how well-characterized
and internally consistent that picture is.

Light builder: it consumes the full A2 ledger and emits ONE small object
(grade + ≤300-char rationale + cited ids). No per-claim stance map and no
non-surface-expression rollup — those live on the A1 side.

NOTE — model home. ``BiologicalContextGrade`` (the closed enum) and the
carrier object are PROPOSED for ``tools/_shared/models.py`` (symmetric to
``EvidenceGrade`` / ``SurfaceEvidence.evidence_grade``); see the module's
report. Until the lead lands them in models.py, the enum + block are
defined locally here — exactly as ``EvidenceGradeBlock`` is defined in the
``evidence_grade`` builder rather than in models.py. Once
``BiologicalContextGrade`` lands in models.py, import it here instead of
the local ``Literal`` and keep the block (the block is a builder-internal
bundle, like ``EvidenceGradeBlock``).
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from anthropic import Anthropic
from pydantic import BaseModel, ConfigDict, Field

from accessible_surfaceome.agents._support.pricing import UsageRecord
from accessible_surfaceome.agents.surfaceome_v2.builders._common import (
    MAX_TOKENS_BLOCK,
    call_builder,
    format_ledger_block,
    format_schema_block,
    load_prompt,
)
from accessible_surfaceome.tools._shared.models import EvidenceClaim

logger = logging.getLogger(__name__)

# Proposed for models.py as ``BiologicalContextGrade`` (see module docstring).
# Mirrors ``EvidenceGrade``'s closed-enum shape; values run high → low
# coverage/consistency of the A2 biological-context picture.
BiologicalContextGrade = Literal[
    "rich",
    "moderate",
    "sparse",
    "absent",
]


class BiologicalContextGradeBlock(BaseModel):
    """Bundle: the A2 biological-context grade verdict + rationale + cites.

    Builder-internal carrier (like ``EvidenceGradeBlock``). When the lead
    lands the carrier object in models.py, this stays the builder's
    transport type and the orchestrator maps it onto the record field.
    """

    model_config = ConfigDict(extra="forbid")

    biological_context_grade: BiologicalContextGrade
    grade_rationale: str
    cited_evidence_ids: list[str] = Field(default_factory=list)


_DEFAULT_BLOCK = BiologicalContextGradeBlock(
    biological_context_grade="absent",
    grade_rationale="No A2 biological-context claims were available to grade.",
    cited_evidence_ids=[],
)


def build_biological_context_grade(
    claims: list[EvidenceClaim],
    *,
    client: Anthropic,
    usage_sink: list[UsageRecord],
    context: dict[str, Any] | None = None,
) -> BiologicalContextGradeBlock:
    """Grade the A2 ledger's biological-context coverage + consistency.

    Consumes the FULL A2 ledger (every claim the A2 plan_trim_select pass
    emitted — expression / localization / anatomical / modulation evidence,
    with cell-state context folded into modulation), not a claim-type-filtered
    slice, because the grade is a rollup across the four A2 axes. Mirrors
    :func:`build_evidence_grade`, which reads the full A1 ledger.

    Always returns a valid :class:`BiologicalContextGradeBlock`. Falls back
    to ``"absent"`` / empty when there are no claims or on repair failure.
    """
    context = context or {}
    if not claims:
        return _DEFAULT_BLOCK
    gene = context.get("gene", "<unknown>")
    system_prompt = load_prompt("biological_context_grade_builder_system")
    user_prompt = (
        f"# Gene: {gene}\n\n"
        f"{format_ledger_block(claims, header='A2 full ledger')}\n"
        f"{format_schema_block(BiologicalContextGradeBlock.model_json_schema(), name='BiologicalContextGradeBlock')}\n"
        "Emit ONE fenced ```json block containing a JSON OBJECT with keys "
        "`biological_context_grade`, `grade_rationale`, `cited_evidence_ids`. "
        "No prose around it.\n"
    )
    parsed = call_builder(
        client,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=BiologicalContextGradeBlock,
        usage_sink=usage_sink,
        label="biological_context_grade_builder",
        # Light builder: one small object (grade + ≤300-char rationale +
        # an id list). The default block cap is ample — no nested lists.
        max_tokens=MAX_TOKENS_BLOCK,
    )
    if parsed is None or not isinstance(parsed, BiologicalContextGradeBlock):
        logger.warning(
            "biological_context_grade_builder failed → falling back to absent/empty"
        )
        return _DEFAULT_BLOCK
    # Scrub any cited id the LLM fabricated (same discipline as the A1 side).
    known = {c.evidence_id for c in claims}
    cleaned = [i for i in parsed.cited_evidence_ids if i in known]
    n_dropped = len(parsed.cited_evidence_ids) - len(cleaned)
    if n_dropped > 0:
        logger.warning(
            "biological_context_grade_builder: dropped %d cited_evidence_ids "
            "with unresolved id (LLM cited ids absent from the input A2 ledger)",
            n_dropped,
        )
    return parsed.model_copy(update={"cited_evidence_ids": cleaned})


__all__ = ["BiologicalContextGradeBlock", "build_biological_context_grade"]
