"""A1 → ``list[MethodObservation]``.

Picks claims with surface-evidence ``evidence_type`` OR
``claim_type in {surface_expression, methodological}`` and asks Sonnet
to extract MethodObservation rows.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import Anthropic

from accessible_surfaceome.agents._support.pricing import UsageRecord
from accessible_surfaceome.agents.surfaceome_v2.builders._common import (
    MAX_TOKENS_HEAVY,
    call_builder,
    filter_by_claim_type,
    filter_by_evidence_type,
    format_ledger_block,
    format_schema_block,
    load_prompt,
)
from accessible_surfaceome.tools._shared.models import EvidenceClaim, MethodObservation

logger = logging.getLogger(__name__)

_SURFACE_METHOD_EVIDENCE_TYPES: set[str] = {
    "flow_cytometry",
    "surface_biotinylation",
    "mass_spec_surfaceome",
    "immunohistochemistry",
    "immunofluorescence",
    "western_blot",
}
_METHOD_CLAIM_TYPES: set[str] = {"surface_expression", "methodological"}

# Anthropic server-side web search — enabled ONLY for the methods builder
# so it can resolve antibody REAGENT METADATA the source paper leaves
# unstated (clonality / epitope region / validation) from the vendor
# datasheet or Antibody Registry record. The prompt scopes its use tightly
# (identifier-anchored, metadata-only; surface claims stay cite-only).
# ``max_uses`` caps the search spend per gene. Web search must be enabled
# on the Anthropic account for this to run.
_WEB_SEARCH_TOOL: list[dict[str, Any]] = [
    {"type": "web_search_20250305", "name": "web_search", "max_uses": 8}
]


def _select_input_claims(claims: list[EvidenceClaim]) -> list[EvidenceClaim]:
    by_evi = filter_by_evidence_type(claims, _SURFACE_METHOD_EVIDENCE_TYPES)
    by_ct = filter_by_claim_type(claims, _METHOD_CLAIM_TYPES)
    seen: set[str] = set()
    out: list[EvidenceClaim] = []
    for c in (*by_evi, *by_ct):
        if c.evidence_id in seen:
            continue
        seen.add(c.evidence_id)
        out.append(c)
    return out


def build_methods(
    claims: list[EvidenceClaim],
    *,
    client: Anthropic,
    usage_sink: list[UsageRecord],
    context: dict[str, Any] | None = None,
) -> list[MethodObservation]:
    """Extract MethodObservation rows from the A1 claim ledger.

    Returns an empty list when no qualifying claims are present, or when
    the model fails to emit a valid block after the repair loop.
    """
    context = context or {}
    selected = _select_input_claims(claims)
    if not selected:
        logger.info("methods_builder: no qualifying claims → empty")
        return []
    gene = context.get("gene", "<unknown>")
    system_prompt = load_prompt("methods_builder_system")
    user_prompt = (
        f"# Gene: {gene}\n\n"
        f"{format_ledger_block(selected, header='A1 surface-method claims')}\n"
        f"{format_schema_block(MethodObservation.model_json_schema(), name='MethodObservation')}\n"
        "Emit a JSON ARRAY of MethodObservation rows in ONE fenced ```json "
        "block. No prose around it. Empty array `[]` is acceptable when no "
        "panel can be assembled.\n"
    )
    parsed = call_builder(
        client,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=MethodObservation,
        usage_sink=usage_sink,
        label="methods_builder",
        expect_array=True,
        array_item_model=MethodObservation,
        # Heavy builder: each MethodObservation carries nested antibodies +
        # expression_observations; a 50-claim ledger can produce 20+ rows
        # totalling ~12k output tokens. Use the higher cap so a single
        # round-trip suffices instead of paying for a repair retry.
        max_tokens=MAX_TOKENS_HEAVY,
        # Web search for antibody-metadata enrichment (see prompt §Tools).
        tools=_WEB_SEARCH_TOOL,
    )
    if parsed is None:
        logger.warning("methods_builder: validation failed; returning empty list")
        return []
    out: list[MethodObservation] = [m for m in parsed if isinstance(m, MethodObservation)]
    out = _filter_unknown_citations(out, selected)
    logger.info("methods_builder: %d MethodObservation rows", len(out))
    return out


def _filter_unknown_citations(
    methods: list[MethodObservation], selected: list[EvidenceClaim]
) -> list[MethodObservation]:
    """Drop ``cited_evidence_ids`` that aren't in the input ledger.

    The model occasionally invents a plausible-looking id; rather than
    fail the whole builder, scrub and continue.
    """
    known = {c.evidence_id for c in selected}
    cleaned: list[MethodObservation] = []
    for m in methods:
        scrubbed = m.model_copy(
            update={
                "cited_evidence_ids": [i for i in m.cited_evidence_ids if i in known],
                "expression_observations": [
                    obs.model_copy(
                        update={
                            "cited_evidence_ids": [
                                i for i in obs.cited_evidence_ids if i in known
                            ]
                        }
                    )
                    for obs in m.expression_observations
                ],
            }
        )
        cleaned.append(scrubbed)
    return cleaned


def _main() -> int:  # manual smoke-test helper
    import sys
    from pathlib import Path

    from accessible_surfaceome.agents._support.client import get_client
    from accessible_surfaceome.env import load_env

    load_env()
    logging.basicConfig(level=logging.INFO)
    args = sys.argv[1:]
    if not args:
        print(
            "usage: python -m accessible_surfaceome.agents.surfaceome_v2.builders.methods "
            "<dual_json_path>"
        )
        return 2
    path = Path(args[0])
    dual = json.loads(path.read_text())
    a1_claims = [EvidenceClaim.model_validate(c) for c in dual["a1"]["claims"]]
    client = get_client()
    usage_sink: list[UsageRecord] = []
    rows = build_methods(
        a1_claims,
        client=client,
        usage_sink=usage_sink,
        context={"gene": dual.get("gene")},
    )
    print(f"got {len(rows)} MethodObservation rows")
    for r in rows:
        print(json.dumps(r.model_dump(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
