"""A2 → ``list[TissueContext]``."""

from __future__ import annotations

import logging
from typing import Any

from anthropic import Anthropic

from accessible_surfaceome.agents._support.pricing import UsageRecord
from accessible_surfaceome.agents.surfaceome_v2.builders._common import (
    MAX_TOKENS_HEAVY,
    call_builder,
    filter_by_claim_type,
    format_ledger_block,
    format_schema_block,
    load_prompt,
)
from accessible_surfaceome.tools._shared.models import EvidenceClaim, TissueContext

logger = logging.getLogger(__name__)


def build_tissues(
    claims: list[EvidenceClaim],
    *,
    client: Anthropic,
    usage_sink: list[UsageRecord],
    context: dict[str, Any] | None = None,
) -> list[TissueContext]:
    context = context or {}
    selected = filter_by_claim_type(claims, {"tissue_expression"})
    if not selected:
        logger.info("tissues_builder: no qualifying claims → empty")
        return []
    gene = context.get("gene", "<unknown>")
    system_prompt = load_prompt("tissues_builder_system")
    user_prompt = (
        f"# Gene: {gene}\n\n"
        f"{format_ledger_block(selected, header='A2 tissue_expression claims')}\n"
        f"{format_schema_block(TissueContext.model_json_schema(), name='TissueContext')}\n"
        "Emit a JSON ARRAY of TissueContext rows in ONE fenced ```json block. "
        "Group by (tissue, disease_context). No prose around it.\n"
    )
    parsed = call_builder(
        client,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=TissueContext,
        usage_sink=usage_sink,
        label="tissues_builder",
        expect_array=True,
        array_item_model=TissueContext,
        # Heavy builder: per-tissue rows × disease-context split can
        # blow past 8k tokens on broadly-expressed proteins (GPR75
        # produced 29 rows). Use the high cap.
        max_tokens=MAX_TOKENS_HEAVY,
    )
    if parsed is None:
        return []
    known = {c.evidence_id for c in selected}
    out: list[TissueContext] = []
    for row in parsed:
        if not isinstance(row, TissueContext):
            continue
        scrubbed = row.model_copy(
            update={
                "cited_evidence_ids": [i for i in row.cited_evidence_ids if i in known]
            }
        )
        out.append(scrubbed)
    logger.info("tissues_builder: %d TissueContext rows", len(out))
    return out


__all__ = ["build_tissues"]
