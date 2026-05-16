"""A1 → ``list[Contradiction]``.

Picks claims with ``claim_type=contradictory`` OR ``direction=refutes``
and turns them into Contradiction rows.
"""

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
from accessible_surfaceome.tools._shared.models import Contradiction, EvidenceClaim

logger = logging.getLogger(__name__)


def _select_input_claims(claims: list[EvidenceClaim]) -> list[EvidenceClaim]:
    out: list[EvidenceClaim] = []
    seen: set[str] = set()
    for c in claims:
        if c.claim_type == "contradictory" or c.direction == "refutes":
            if c.evidence_id not in seen:
                out.append(c)
                seen.add(c.evidence_id)
    return out


def build_contradictions(
    claims: list[EvidenceClaim],
    *,
    client: Anthropic,
    usage_sink: list[UsageRecord],
    context: dict[str, Any] | None = None,
) -> list[Contradiction]:
    context = context or {}
    selected = _select_input_claims(claims)
    if not selected:
        logger.info("contradiction_builder: no qualifying claims → empty")
        return []
    gene = context.get("gene", "<unknown>")
    system_prompt = load_prompt("contradiction_builder_system")
    user_prompt = (
        f"# Gene: {gene}\n\n"
        f"{format_ledger_block(selected, header='A1 contradictory claims')}\n"
        f"{format_schema_block(Contradiction.model_json_schema(), name='Contradiction')}\n"
        "Emit a JSON ARRAY of Contradiction rows in ONE fenced ```json "
        "block. Empty array `[]` is acceptable.\n"
    )
    parsed = call_builder(
        client,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=Contradiction,
        usage_sink=usage_sink,
        label="contradiction_builder",
        expect_array=True,
        array_item_model=Contradiction,
    )
    if parsed is None:
        return []
    known = {c.evidence_id for c in selected}
    out: list[Contradiction] = []
    for row in parsed:
        if not isinstance(row, Contradiction):
            continue
        scrubbed = row.model_copy(
            update={
                "cited_evidence_ids": [i for i in row.cited_evidence_ids if i in known]
            }
        )
        out.append(scrubbed)
    logger.info("contradiction_builder: %d Contradiction rows", len(out))
    return out


__all__ = ["build_contradictions"]
