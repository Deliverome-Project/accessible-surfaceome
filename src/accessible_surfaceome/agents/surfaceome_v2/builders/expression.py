"""A2 → ``list[ExpressionRow]`` (unified tissue × cell-of-origin pivot).

Merges what used to be two builders (``tissues`` + ``cell_types``) into one:
the A2 ledger drives a single ``ExpressionRow`` list where each row names a
tissue, a cell type of origin, or both — see ``ExpressionRow`` in
``models.py``.
"""

from __future__ import annotations

import logging
from typing import Any

from anthropic import Anthropic

from accessible_surfaceome.agents._support.pricing import UsageRecord
from accessible_surfaceome.agents.surfaceome_v2.builders._common import (
    MAX_TOKENS_HEAVY,
    call_builder,
    format_ledger_block,
    format_schema_block,
    load_prompt,
)
from accessible_surfaceome.tools._shared.models import EvidenceClaim, ExpressionRow

logger = logging.getLogger(__name__)


def build_expression(
    claims: list[EvidenceClaim],
    *,
    client: Anthropic,
    usage_sink: list[UsageRecord],
    context: dict[str, Any] | None = None,
) -> list[ExpressionRow]:
    context = context or {}
    if not claims:
        logger.info("expression_builder: no A2 claims → empty")
        return []
    gene = context.get("gene", "<unknown>")
    system_prompt = load_prompt("expression_builder_system")
    user_prompt = (
        f"# Gene: {gene}\n\n"
        f"{format_ledger_block(claims, header='A2 ledger (full)')}\n"
        f"{format_schema_block(ExpressionRow.model_json_schema(), name='ExpressionRow')}\n"
        "Emit a JSON ARRAY of ExpressionRow rows in ONE fenced ```json block. "
        "No prose around it.\n"
    )
    parsed = call_builder(
        client,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=ExpressionRow,
        usage_sink=usage_sink,
        label="expression_builder",
        expect_array=True,
        array_item_model=ExpressionRow,
        # Heavy builder: a broadly-expressed protein can produce many rows
        # (per-tissue × disease-context × cell-of-origin). Use the high cap.
        max_tokens=MAX_TOKENS_HEAVY,
    )
    if parsed is None:
        return []
    known = {c.evidence_id for c in claims}
    out: list[ExpressionRow] = []
    for row in parsed:
        if not isinstance(row, ExpressionRow):
            continue
        scrubbed = row.model_copy(
            update={
                "cited_evidence_ids": [
                    i for i in row.cited_evidence_ids if i in known
                ]
            }
        )
        out.append(scrubbed)
    logger.info("expression_builder: %d ExpressionRow rows", len(out))
    return out


__all__ = ["build_expression"]
