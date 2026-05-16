"""A2 → ``list[AccessibilityModulationObservation]``.

The heaviest builder — category-conditional sub-field rules are validator-
enforced. Post-validation we also scrub un-cited ids and re-validate per
row to catch any mispairings the model emitted; mispaired rows get
dropped rather than crashing the entire builder.
"""

from __future__ import annotations

import logging
from typing import Any

from anthropic import Anthropic
from pydantic import ValidationError

from accessible_surfaceome.agents._support.pricing import UsageRecord
from accessible_surfaceome.agents.surfaceome_v2.builders._common import (
    MAX_TOKENS_HEAVY,
    call_builder,
    format_ledger_block,
    format_schema_block,
    load_prompt,
)
from accessible_surfaceome.tools._shared.models import (
    AccessibilityModulationObservation,
    EvidenceClaim,
)

logger = logging.getLogger(__name__)


def build_accessibility_modulation(
    claims: list[EvidenceClaim],
    *,
    client: Anthropic,
    usage_sink: list[UsageRecord],
    context: dict[str, Any] | None = None,
) -> list[AccessibilityModulationObservation]:
    context = context or {}
    if not claims:
        return []
    gene = context.get("gene", "<unknown>")
    system_prompt = load_prompt("accessibility_modulation_builder_system")
    user_prompt = (
        f"# Gene: {gene}\n\n"
        f"{format_ledger_block(claims, header='A2 ledger (full)')}\n"
        f"{format_schema_block(AccessibilityModulationObservation.model_json_schema(), name='AccessibilityModulationObservation')}\n"
        "Emit a JSON ARRAY in ONE fenced ```json block. Empty `[]` is "
        "acceptable. RE-READ the category-conditional pairing rules in "
        "the system prompt before EACH row.\n"
    )
    parsed = call_builder(
        client,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=AccessibilityModulationObservation,
        usage_sink=usage_sink,
        label="accessibility_modulation_builder",
        expect_array=True,
        array_item_model=AccessibilityModulationObservation,
        # Heavy builder: per-row prose ("change", "accessibility_implication")
        # is verbose, category-conditional sub-fields can stack. EGFR
        # produced 9 rows; rich proteins (CD81-class signaling) may
        # produce 15+.
        max_tokens=MAX_TOKENS_HEAVY,
    )
    if parsed is None:
        return []
    known = {c.evidence_id for c in claims}
    out: list[AccessibilityModulationObservation] = []
    for row in parsed:
        if not isinstance(row, AccessibilityModulationObservation):
            continue
        cleaned_ids = [i for i in row.cited_evidence_ids if i in known]
        try:
            scrubbed = row.model_copy(update={"cited_evidence_ids": cleaned_ids})
            # Re-validate to catch any mispairings the model emitted.
            AccessibilityModulationObservation.model_validate(scrubbed.model_dump())
        except ValidationError as exc:
            logger.warning(
                "accessibility_modulation row failed re-validation; dropping: %s",
                str(exc)[:200],
            )
            continue
        out.append(scrubbed)
    logger.info("accessibility_modulation_builder: %d rows", len(out))
    return out


__all__ = ["build_accessibility_modulation"]
