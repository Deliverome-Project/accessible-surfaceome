"""A2 → ``list[StateContext]`` (orthogonal cell-state pivot).

Cell-states populate the ``BiologicalContext.cell_states`` ledger
alongside ``cell_types``. Where ``cell_types`` answers "which cells
express this protein", ``cell_states`` answers "under which cell-state
condition (activation / stress / EMT / hypoxia / senescence /
differentiation stage / disease state) does expression or surface
fractionation change". Critical for csGRP78-class proteins where the
literature gates surface presentation on ER stress, and for VIM-class
proteins where the literature gates surface presentation on EMT.
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
from accessible_surfaceome.tools._shared.models import (
    EvidenceClaim,
    StateContext,
)

logger = logging.getLogger(__name__)


def build_cell_states(
    claims: list[EvidenceClaim],
    *,
    client: Anthropic,
    usage_sink: list[UsageRecord],
    context: dict[str, Any] | None = None,
) -> list[StateContext]:
    context = context or {}
    if not claims:
        return []
    gene = context.get("gene", "<unknown>")
    system_prompt = load_prompt("cell_states_builder_system")
    user_prompt = (
        f"# Gene: {gene}\n\n"
        f"{format_ledger_block(claims, header='A2 ledger (full)')}\n"
        f"{format_schema_block(StateContext.model_json_schema(), name='StateContext')}\n"
        "Emit a JSON ARRAY of StateContext rows in ONE fenced ```json "
        "block. Empty `[]` is fine when the literature only reports "
        "steady-state expression. No prose around it.\n"
    )
    parsed = call_builder(
        client,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=StateContext,
        usage_sink=usage_sink,
        label="cell_states_builder",
        expect_array=True,
        array_item_model=StateContext,
    )
    if parsed is None:
        return []
    known = {c.evidence_id for c in claims}
    out: list[StateContext] = []
    for row in parsed:
        if not isinstance(row, StateContext):
            continue
        scrubbed = row.model_copy(
            update={
                "cited_evidence_ids": [
                    i for i in row.cited_evidence_ids if i in known
                ],
            }
        )
        out.append(scrubbed)
    logger.info("cell_states_builder: %d StateContext rows", len(out))
    return out


__all__ = ["build_cell_states"]
