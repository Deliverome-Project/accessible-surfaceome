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

# Hard cap on the number of claims sent to the methods LLM in a single
# call. Above this size the per-call cost dominates the deep-dive budget:
# TACSTD2's methods builder was observed at $0.36/call with 87k input
# tokens (87 claims through the prompt-cache miss path), and tail genes
# can push into low single dollars before the orchestrator's $7 ceiling
# kicks in. Capping at 25 keeps the heaviest gene's methods call <$0.15
# while preserving the top-confidence-first slice — the lower-rank
# rt_qpcr / tissue_expression filler that gets dropped here would have
# largely resolved to ``expression_only`` rows anyway.
#
# Important: ONLY the methods builder is capped. The synthesizer +
# evidence_grade builder still see the full claim ledger so the headline
# call and the grade count aren't affected by the trim.
MAX_CLAIMS_TO_LLM = 25

# Evidence-type weights for the pre-LLM rank.  Higher = more
# direct-surface-accessibility evidence. Tied weights tie-break on the
# rest of the rank key (permeabilization, species, evidence_tier,
# confidence, evidence_id).  These intentionally favour live-cell flow,
# surface biotinylation, and non-permeabilized IF — the three evidence
# shapes the synthesis layer treats as ``direct`` — over tissue-IHC,
# RNA, and review-assertion shapes that are at best
# ``supports_surface_localization`` or ``expression_only``.
_EVIDENCE_TYPE_RANK: dict[str, int] = {
    "flow_cytometry": 10,
    "surface_biotinylation": 10,
    "mass_spec_surfaceome": 9,
    "immunofluorescence": 8,
    "immunohistochemistry": 6,
    "western_blot": 5,
    "functional_assay": 4,
    "crystal_structure": 3,
    "cryo_em": 3,
    "computational_prediction": 2,
    "orthology": 2,
    "rt_qpcr": 1,
    "rna_seq": 1,
    "single_cell_rna_seq": 1,
    "in_situ_hybridization": 1,
    "northern_blot": 1,
    "microarray": 1,
    "genetic_association": 1,
    "loss_of_function_phenotype": 1,
    "review_assertion": 1,
    "db_annotation": 1,
}

# Anthropic server-side web search — enabled ONLY for the methods builder
# so it can resolve antibody REAGENT METADATA the source paper leaves
# unstated (clonality / epitope region / validation) from the vendor
# datasheet or Antibody Registry record. The prompt scopes its use tightly
# (identifier-anchored, metadata-only; surface claims stay cite-only).
# ``max_uses`` caps the search spend per gene. Web search must be enabled
# on the Anthropic account for this to run.
_WEB_SEARCH_TOOL: list[dict[str, Any]] = [
    {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 8,
        # ``cache_control`` on the last tool entry is the canonical
        # recipe (per Anthropic docs) for caching the tools+system
        # prefix together. The 2026-06-08 cache-engagement probe
        # confirmed that today's call shape (cache_control on system
        # only) ALREADY caches via the server's automatic-caching
        # behaviour — but that's an implicit / undocumented contract.
        # Marking the tool explicitly makes the recipe match the
        # documented one and immunizes us against future server-side
        # changes.
        "cache_control": {"type": "ephemeral"},
    }
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


def _rank_key(claim: EvidenceClaim) -> tuple[int, int, int, int, int, str]:
    """Sort key for top-N truncation. Lower tuple sorts FIRST (most
    valuable for the methods builder).

    Ranking axes, in order of precedence:

    1. Evidence-type weight — live flow / biotinylation / non-perm IF
       outrank tissue-IHC, RNA, computational, review.
    2. Permeabilization — ``False`` (i.e. live / non-perm) outranks the
       ``True`` (permeabilized) or ``None`` (unknown) cases. The methods
       builder is most valuable on non-perm signal.
    3. Species — ``human`` outranks every other.
    4. Evidence tier — ``primary`` outranks ``secondary``.
    5. Confidence — ``strong`` outranks ``moderate`` outranks ``weak``.
    6. Evidence id — stable tiebreaker so the truncation is deterministic
       across re-runs.
    """
    evi_weight = _EVIDENCE_TYPE_RANK.get(claim.evidence_type, 0)
    # Negate so higher weight sorts first.
    evi_rank = -evi_weight
    # permeabilized is Optional[bool]; False outranks True/None.
    perm_value = claim.assay_context.permeabilized
    if perm_value is False:
        perm_rank = 0
    elif perm_value is None:
        perm_rank = 1
    else:
        perm_rank = 2
    species_rank = 0 if claim.assay_context.species == "human" else 1
    tier_rank = 0 if claim.evidence_tier == "primary" else 1
    confidence_rank = {"strong": 0, "moderate": 1, "weak": 2}.get(
        claim.confidence, 3
    )
    return (
        evi_rank,
        perm_rank,
        species_rank,
        tier_rank,
        confidence_rank,
        claim.evidence_id,
    )


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
    if len(selected) > MAX_CLAIMS_TO_LLM:
        original_n = len(selected)
        selected = sorted(selected, key=_rank_key)[:MAX_CLAIMS_TO_LLM]
        logger.info(
            "methods_builder: truncated %d → %d (top-confidence-first)",
            original_n,
            MAX_CLAIMS_TO_LLM,
        )
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
