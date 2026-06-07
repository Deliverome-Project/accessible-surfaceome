"""Consolidated A2 builder: SubcellularLocalization + AnatomicalAccessibility
in ONE Sonnet call.

Both blocks consume the same A2 evidence ledger and both reason about
tissue / cell-type / membrane-subdomain context (just from different
angles — compartment-assignment vs binder-reachability orientation).
The cost-reduction package consolidates them into a single Sonnet call
that emits a wrapper object carrying both:

  {
    "subcellular_localization": <SubcellularLocalization JSON>,
    "anatomical_accessibility": [<AnatomicalAccessibilityObservation>, ...]
  }

The caller (the v2 orchestrator) unpacks the wrapper into the two slots
the existing downstream code expects (``outputs["subcellular_localization"]``
and ``outputs["anatomical_accessibility"]``) — the per-block emitted
structures and the BiologicalContext schema are **unchanged**. Only the
LLM-call count drops from 2 → 1 per gene; estimated savings ~$0.04-0.08
per gene × 6,521 cohort ≈ $260-520 total.

The single-call form preserves both per-block scrub passes (filtering
``cited_evidence_ids`` to those present in the ledger, mirroring the
two separate builders' behaviour).
"""

from __future__ import annotations

import logging
from typing import Any

from anthropic import Anthropic
from pydantic import BaseModel, Field

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
    SubcellularLocalization,
)

logger = logging.getLogger(__name__)


_DEFAULT_SUBLOC = SubcellularLocalization(
    primary_compartment="other",
    dual_localization=[],
    membrane_subdomains=[],
)


class _CombinedOutput(BaseModel):
    """The Sonnet wrapper object — internal to this module.

    The model emits this; we unpack into the two existing block types
    before returning so callers see no shape change.
    """

    subcellular_localization: SubcellularLocalization
    anatomical_accessibility: list[AnatomicalAccessibilityObservation] = Field(
        default_factory=list
    )


def build_subloc_anatomical_combined(
    claims: list[EvidenceClaim],
    *,
    client: Anthropic,
    usage_sink: list[UsageRecord],
    context: dict[str, Any] | None = None,
) -> tuple[SubcellularLocalization, list[AnatomicalAccessibilityObservation]]:
    """One Sonnet call → both blocks unpacked + scrubbed.

    Always returns a valid pair. On an empty claim ledger we return the
    same defaults the standalone builders did (plasma_membrane single-
    row subloc, empty anatomical list). On a Sonnet failure we fall back
    to (_DEFAULT_SUBLOC, []), matching the standalone builders' behaviour.
    """
    context = context or {}
    if not claims:
        return (
            SubcellularLocalization(
                primary_compartment="plasma_membrane",
                dual_localization=[],
                membrane_subdomains=[],
            ),
            [],
        )

    gene = context.get("gene", "<unknown>")
    # Load both standalone system prompts and stitch them together. Each
    # carries the per-block rules already; we just frame the combined
    # output and add the output discipline. This keeps prompt-content
    # changes minimal — both prompts continue to drive the same per-block
    # behaviour they did standalone (so the prompt-corpus guardrails +
    # the gene-leak tests continue to pass without touching the per-block
    # prompts).
    subloc_rules = load_prompt("subcellular_localization_builder_system")
    anatomical_rules = load_prompt("anatomical_accessibility_builder_system")
    system_prompt = (
        f"# Consolidated A2 block — Subcellular Localization + Anatomical Accessibility\n\n"
        f"You produce TWO blocks from the same A2 ledger in a SINGLE pass:\n"
        f"the SubcellularLocalization object AND the list of "
        f"AnatomicalAccessibilityObservation rows.\n\n"
        f"Section A — SubcellularLocalization rules:\n\n"
        f"{subloc_rules}\n\n"
        f"---\n\n"
        f"Section B — AnatomicalAccessibility rules:\n\n"
        f"{anatomical_rules}\n\n"
        f"---\n\n"
        f"Apply BOTH sets of rules independently to the same ledger. The two "
        f"blocks are emitted side-by-side in the wrapper object.\n"
    )

    user_prompt = (
        f"# Gene: {gene}\n\n"
        f"{format_ledger_block(claims, header='A2 ledger (full)')}\n"
        f"{format_schema_block(_CombinedOutput.model_json_schema(), name='CombinedSublocAnatomical')}\n"
        "Emit ONE fenced ```json block containing a JSON OBJECT with two keys:\n"
        "  - `subcellular_localization`: one SubcellularLocalization object\n"
        "  - `anatomical_accessibility`: a JSON ARRAY of "
        "AnatomicalAccessibilityObservation rows (use `[]` when no polarized-"
        "tissue evidence exists)\n"
        "No prose around the JSON block.\n"
    )

    parsed = call_builder(
        client,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=_CombinedOutput,
        usage_sink=usage_sink,
        label="subloc_anatomical_combined",
    )
    if parsed is None or not isinstance(parsed, _CombinedOutput):
        logger.warning(
            "subloc_anatomical_combined: builder failed → fallback "
            "(empty subloc + empty anatomical list)"
        )
        return (_DEFAULT_SUBLOC, [])

    known = {c.evidence_id for c in claims}

    # Scrub subloc cite ids — mirrors the standalone subcellular_localization
    # builder's behaviour exactly.
    subloc = parsed.subcellular_localization
    dl = [
        d.model_copy(
            update={
                "cited_evidence_ids": [
                    i for i in d.cited_evidence_ids if i in known
                ]
            }
        )
        for d in subloc.dual_localization
    ]
    ms = [
        s.model_copy(
            update={
                "cited_evidence_ids": [
                    i for i in s.cited_evidence_ids if i in known
                ]
            }
        )
        for s in subloc.membrane_subdomains
    ]
    scrubbed_subloc = subloc.model_copy(
        update={"dual_localization": dl, "membrane_subdomains": ms}
    )

    # Scrub anatomical cite ids — mirrors the standalone anatomical
    # builder's behaviour exactly.
    anatomical_rows: list[AnatomicalAccessibilityObservation] = []
    for row in parsed.anatomical_accessibility:
        if not isinstance(row, AnatomicalAccessibilityObservation):
            continue
        anatomical_rows.append(
            row.model_copy(
                update={
                    "cited_evidence_ids": [
                        i for i in row.cited_evidence_ids if i in known
                    ]
                }
            )
        )

    logger.info(
        "subloc_anatomical_combined: subloc=1 (compartment=%s, "
        "dual=%d, subdomains=%d) anatomical=%d rows",
        scrubbed_subloc.primary_compartment,
        len(dl),
        len(ms),
        len(anatomical_rows),
    )
    return (scrubbed_subloc, anatomical_rows)


__all__ = ["build_subloc_anatomical_combined"]
