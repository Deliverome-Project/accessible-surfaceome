"""A2 → ``SubcellularLocalization`` (always one row)."""

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
    EvidenceClaim,
    SubcellularLocalization,
)

logger = logging.getLogger(__name__)


_DEFAULT_BLOCK = SubcellularLocalization(
    primary_compartment="other",
    dual_localization=[],
    membrane_subdomains=[],
)


def build_subcellular_localization(
    claims: list[EvidenceClaim],
    *,
    client: Anthropic,
    usage_sink: list[UsageRecord],
    context: dict[str, Any] | None = None,
    meta_sink: dict[str, Any] | None = None,
) -> SubcellularLocalization:
    """Always returns a valid block — the parent BiologicalContext
    REQUIRES this field, so a builder failure falls back to ``other`` /
    empty rather than crashing the orchestrator."""
    context = context or {}
    if not claims:
        return SubcellularLocalization(
            primary_compartment="plasma_membrane",
            dual_localization=[],
            membrane_subdomains=[],
        )
    gene = context.get("gene", "<unknown>")
    system_prompt = load_prompt("subcellular_localization_builder_system")
    user_prompt = (
        f"# Gene: {gene}\n\n"
        f"{format_ledger_block(claims, header='A2 ledger (full)')}\n"
        f"{format_schema_block(SubcellularLocalization.model_json_schema(), name='SubcellularLocalization')}\n"
        "Emit ONE fenced ```json block containing a JSON OBJECT (not an array). "
        "No prose around it.\n"
    )
    parsed = call_builder(
        client,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=SubcellularLocalization,
        usage_sink=usage_sink,
        label="subcellular_localization_builder",
        meta_sink=meta_sink,
    )
    if parsed is None or not isinstance(parsed, SubcellularLocalization):
        logger.warning("subcellular_localization_builder failed → fallback")
        return _DEFAULT_BLOCK
    known = {c.evidence_id for c in claims}
    dl = [
        d.model_copy(
            update={
                "cited_evidence_ids": [
                    i for i in d.cited_evidence_ids if i in known
                ]
            }
        )
        for d in parsed.dual_localization
    ]
    ms = [
        s.model_copy(
            update={
                "cited_evidence_ids": [
                    i for i in s.cited_evidence_ids if i in known
                ]
            }
        )
        for s in parsed.membrane_subdomains
    ]
    return parsed.model_copy(update={"dual_localization": dl, "membrane_subdomains": ms})


__all__ = ["build_subcellular_localization"]
