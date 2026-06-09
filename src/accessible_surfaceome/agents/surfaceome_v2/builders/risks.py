"""merged A1+A2 ledger (+ deterministic features) → ``AccessibilityRisks``.

The risks builder is a cross-focus Phase-2 builder: unlike the A1-only /
A2-only builders, it consumes the **merged** A1 + A2 ``EvidenceClaim``
ledger so every risk call can be grounded in (and cite) surface
methodology AND biological-context evidence at once. It emits ONE
``AccessibilityRisks`` object — the six risk sub-blocks the catalog
filters on — replacing the synthesizer's former risk-generation
responsibility. The synthesizer now CONSUMES the frozen risks block.

Two deterministic fields the builder must NOT really judge:

* ``ecd_size_assessment.ecd_accessibility_class`` is overwritten
  post-build by the orchestrator (``classify_ecd_accessibility_class``);
  the prompt has the model emit per the deterministic residue band so
  the pre-overwrite value is at least internally consistent.
* homo-oligomerization ships as its own deterministic chip
  (``homo_oligomerization_prediction``, attached by the orchestrator
  from Schweke 2024); the prompt treats the deterministic
  ``is_homo_oligomer`` / ``stoichiometry`` signal as CORROBORATION only.

HEAVY builder (``MAX_TOKENS_HEAVY``): six nested sub-blocks each with
rationale + cites over a merged ledger that can run 50+ claims.
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
    format_ledger_block,
    format_schema_block,
    load_prompt,
)
from accessible_surfaceome.tools._shared.models import (
    AccessibilityRisks,
    DeterministicFeatures,
    EvidenceClaim,
)

logger = logging.getLogger(__name__)


def _summarize_deterministic_for_risks(
    features: DeterministicFeatures,
) -> str:
    """Compact JSON summary of the deterministic block the risks builder reads.

    Narrow on purpose — the risks builder only needs:

    * ``canonical_topology.ecd_length_residues`` to emit
      ``ecd_size_assessment.ecd_accessibility_class`` per the
      deterministic bands (it gets overwritten post-build, but the
      pre-overwrite value should be internally consistent).
    * ``homo_oligomerization.{is_homo_oligomer,stoichiometry}`` as a
      CORROBORATION-only prior for the ``epitope_masking.oligomerization``
      mechanism (the authoritative AF2 signal ships as its own chip).
    """
    canon = features.canonical_topology
    schweke = features.homo_oligomerization
    payload: dict[str, Any] = {
        "canonical_topology": {
            "tm_helix_count": canon.tm_helix_count,
            "ecd_length_residues": canon.ecd_length_residues,
        },
        "homo_oligomerization": {
            "is_homo_oligomer": schweke.is_homo_oligomer,
            "stoichiometry": schweke.stoichiometry,
        },
    }
    return json.dumps(payload, indent=2)


def _scrub_unknown_citations(
    risks: AccessibilityRisks, known: set[str]
) -> AccessibilityRisks:
    """Drop any ``cited_evidence_ids`` the merged ledger doesn't carry.

    The model occasionally invents a plausible-looking id; rather than
    fail the whole builder, scrub each sub-block's cite list and continue.
    Mirrors the per-builder scrubbing in ``methods`` / ``contradictions``.
    Returns a *new* ``AccessibilityRisks`` via nested ``model_copy``.
    """

    def _clean(ids: list[str]) -> list[str]:
        return [i for i in ids if i in known]

    return risks.model_copy(
        update={
            "co_receptor_requirements": risks.co_receptor_requirements.model_copy(
                update={
                    "cited_evidence_ids": _clean(
                        risks.co_receptor_requirements.cited_evidence_ids
                    )
                }
            ),
            "shed_form": risks.shed_form.model_copy(
                update={"cited_evidence_ids": _clean(risks.shed_form.cited_evidence_ids)}
            ),
            "secreted_form": risks.secreted_form.model_copy(
                update={
                    "cited_evidence_ids": _clean(risks.secreted_form.cited_evidence_ids)
                }
            ),
            "restricted_subdomain": risks.restricted_subdomain.model_copy(
                update={
                    "cited_evidence_ids": _clean(
                        risks.restricted_subdomain.cited_evidence_ids
                    )
                }
            ),
            "ecd_size_assessment": risks.ecd_size_assessment.model_copy(
                update={
                    "cited_evidence_ids": _clean(
                        risks.ecd_size_assessment.cited_evidence_ids
                    )
                }
            ),
            "epitope_masking": risks.epitope_masking.model_copy(
                update={
                    "cited_evidence_ids": _clean(
                        risks.epitope_masking.cited_evidence_ids
                    )
                }
            ),
        }
    )


def build_risks(
    claims: list[EvidenceClaim],
    *,
    client: Anthropic,
    usage_sink: list[UsageRecord],
    context: dict[str, Any] | None = None,
    meta_sink: dict[str, Any] | None = None,
) -> AccessibilityRisks | None:
    """Emit an ``AccessibilityRisks`` from the MERGED A1+A2 ledger.

    Signature mirrors the other v2 builders so the orchestrator can
    dispatch it through ``_run_builders_concurrently``: positional
    ``claims`` (here the **merged** ledger, ``a1_claims + a2_claims``) and
    keyword ``client`` / ``usage_sink`` / ``context``.

    ``context`` keys:
      * ``gene`` — HGNC symbol (defaults to ``"<unknown>"``).
      * ``deterministic_features`` — the orchestrator's fetched
        :class:`DeterministicFeatures`. When present, a compact summary
        (ECD residue count + Schweke homo-oligomer prior) is rendered into
        the user prompt. Omit it (CLI / stub paths) and the builder runs
        ledger-only — the orchestrator's deterministic post-passes
        overwrite ``ecd_size_assessment`` / attach
        ``homo_oligomerization_prediction`` regardless.

    Returns the parsed ``AccessibilityRisks`` (with unknown cites
    scrubbed), or ``None`` when the repair loop fails. Returning ``None``
    (rather than a synthesized default) lets the orchestrator decide the
    fallback — a record can't ship without a risks block, so the caller
    must handle the miss explicitly rather than have a silent stub slip
    through. Unlike the A1-only / A2-only builders, the risks builder
    does NOT short-circuit on an empty ledger: the deterministic ECD /
    homo-oligomer signals still warrant a populated block even with zero
    claims, and the prompt instructs ``present=false`` defaults for the
    literature-driven risks.
    """
    context = context or {}
    gene = context.get("gene", "<unknown>")
    det_features: DeterministicFeatures | None = context.get("deterministic_features")

    deterministic_block = ""
    if det_features is not None:
        deterministic_block = (
            "## Deterministic features (read-only)\n\n"
            "Prefetched tool output — NOT a ledger entry; do NOT cite it as "
            "an `a*_evi_*` id. Use it for two things only:\n\n"
            "* `canonical_topology.ecd_length_residues` → emit "
            "`ecd_size_assessment.ecd_accessibility_class` per the "
            "deterministic bands (it gets overwritten in code; emit it right "
            "anyway).\n"
            "* `homo_oligomerization` → CORROBORATION-only prior for the "
            "`epitope_masking.oligomerization` mechanism (the authoritative "
            "AF2 chip ships separately; only emit `oligomerization` when the "
            "merged ledger documents it).\n\n"
            f"```json\n{_summarize_deterministic_for_risks(det_features)}\n```\n\n"
        )

    system_prompt = load_prompt("risks_builder_system")
    user_prompt = (
        f"# Gene: {gene}\n\n"
        f"{deterministic_block}"
        f"{format_ledger_block(claims, header='Merged A1+A2 ledger')}\n"
        f"{format_schema_block(AccessibilityRisks.model_json_schema(), name='AccessibilityRisks')}\n"
        "Emit ONE fenced ```json block containing a JSON OBJECT with the six "
        "risk sub-blocks (`co_receptor_requirements`, `shed_form`, "
        "`secreted_form`, `restricted_subdomain`, `ecd_size_assessment`, "
        "`epitope_masking`). Do NOT emit `homo_oligomerization_prediction` "
        "(orchestrator-only). No prose around the block.\n"
    )
    parsed = call_builder(
        client,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=AccessibilityRisks,
        usage_sink=usage_sink,
        label="risks_builder",
        # Heavy builder: six nested sub-blocks, each with rationale + cites,
        # over a merged ledger that can exceed 50 claims.
        max_tokens=MAX_TOKENS_HEAVY,
        meta_sink=meta_sink,
    )
    if parsed is None or not isinstance(parsed, AccessibilityRisks):
        logger.warning("risks_builder: validation failed; returning None")
        return None
    known = {c.evidence_id for c in claims}
    return _scrub_unknown_citations(parsed, known)


__all__ = ["build_risks"]
