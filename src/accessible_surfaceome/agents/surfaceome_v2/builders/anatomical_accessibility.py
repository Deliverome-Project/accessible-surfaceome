"""A2 → ``list[AnatomicalAccessibilityObservation]``."""

from __future__ import annotations

import logging
from typing import Any

from anthropic import Anthropic

from accessible_surfaceome.agents._support.pricing import UsageRecord
from accessible_surfaceome.agents.surfaceome_v2.builders._common import (
    call_builder,
    format_ledger_block,
    format_schema_block,
    load_prompt,
)
from accessible_surfaceome.tools._shared.models import (
    AnatomicalAccessibilityObservation,
    EvidenceClaim,
)

logger = logging.getLogger(__name__)


def build_anatomical_accessibility(
    claims: list[EvidenceClaim],
    *,
    client: Anthropic,
    usage_sink: list[UsageRecord],
    context: dict[str, Any] | None = None,
) -> list[AnatomicalAccessibilityObservation]:
    context = context or {}
    if not claims:
        return []
    gene = context.get("gene", "<unknown>")
    system_prompt = load_prompt("anatomical_accessibility_builder_system")
    user_prompt = (
        f"# Gene: {gene}\n\n"
        f"{format_ledger_block(claims, header='A2 ledger (full)')}\n"
        f"{format_schema_block(AnatomicalAccessibilityObservation.model_json_schema(), name='AnatomicalAccessibilityObservation')}\n"
        "Emit a JSON ARRAY in ONE fenced ```json block. Empty `[]` is "
        "acceptable when no polarized-tissue evidence exists.\n"
    )
    parsed = call_builder(
        client,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=AnatomicalAccessibilityObservation,
        usage_sink=usage_sink,
        label="anatomical_accessibility_builder",
        expect_array=True,
        array_item_model=AnatomicalAccessibilityObservation,
    )
    if parsed is None:
        return []
    known = {c.evidence_id for c in claims}
    out: list[AnatomicalAccessibilityObservation] = []
    for row in parsed:
        if not isinstance(row, AnatomicalAccessibilityObservation):
            continue
        scrubbed = row.model_copy(
            update={
                "cited_evidence_ids": [
                    i for i in row.cited_evidence_ids if i in known
                ]
            }
        )
        out.append(scrubbed)
    logger.info("anatomical_accessibility_builder: %d rows", len(out))
    return out


__all__ = ["build_anatomical_accessibility"]
