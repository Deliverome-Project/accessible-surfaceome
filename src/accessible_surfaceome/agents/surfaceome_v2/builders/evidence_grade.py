"""A1 → ``EvidenceGradeBlock`` (grade + rationale + non_surface_expression).

Single object output that bundles the three things this builder produces
for the assembled ``SurfaceEvidence`` block.
"""

from __future__ import annotations

import logging
from typing import Any

from anthropic import Anthropic
from pydantic import BaseModel, ConfigDict, Field

from accessible_surfaceome.agents._support.pricing import UsageRecord
from accessible_surfaceome.agents.surfaceome_v2.builders._common import (
    MAX_TOKENS_HEAVY,
    call_builder,
    format_ledger_block,
    format_schema_block,
    load_prompt,
)
from accessible_surfaceome.tools._shared.models import (
    ClaimStanceRow,
    EvidenceClaim,
    EvidenceGrade,
    ExcludedClaim,
    NonSurfaceExpression,
)

logger = logging.getLogger(__name__)


class EvidenceGradeBlock(BaseModel):
    """Bundle: the A1 evidence grade verdict + supporting non-surface rows
    + per-claim stance map.

    Field declaration order is load-bearing: ``claim_stances`` is listed
    BEFORE ``grade_rationale`` so the JSON schema the LLM follows asks
    for per-claim judgments first, then the prose rationale that
    summarizes them. This forces the structured per-claim call to come
    before the prose (which the LLM would otherwise write first and
    then back-fill stances to match).
    """

    model_config = ConfigDict(extra="forbid")

    evidence_grade: EvidenceGrade
    claim_stances: list[ClaimStanceRow] = Field(default_factory=list)
    grade_rationale: str
    non_surface_expression: list[NonSurfaceExpression] = Field(default_factory=list)
    # Audit trail of ledger claims rejected by the methods builder's
    # inclusion criterion as ligand-engagement-as-soluble-partner evidence.
    # Empty by default for back-compat with rollouts that emit the older
    # 4-key shape; the grade builder prompt asks for this key explicitly.
    excluded_as_ligand_engagement: list[ExcludedClaim] = Field(
        default_factory=list
    )


_DEFAULT_BLOCK = EvidenceGradeBlock(
    evidence_grade="weak",
    claim_stances=[],
    grade_rationale="No evidence claims were available to grade.",
    non_surface_expression=[],
    excluded_as_ligand_engagement=[],
)


def build_evidence_grade(
    claims: list[EvidenceClaim],
    *,
    client: Anthropic,
    usage_sink: list[UsageRecord],
    context: dict[str, Any] | None = None,
    meta_sink: dict[str, Any] | None = None,
) -> EvidenceGradeBlock:
    """Grade the A1 ledger + emit non-surface expression rows.

    Always returns a valid :class:`EvidenceGradeBlock` — the orchestrator
    can't assemble a SurfaceEvidence block without a grade. Falls back to
    ``"weak"`` / empty when no claims or repair failure.
    """
    context = context or {}
    if not claims:
        return _DEFAULT_BLOCK
    gene = context.get("gene", "<unknown>")
    # Calibration context — triage prior + curator-assigned family tags.
    # Other builders are intentionally narrow (gene-symbol-only) because
    # extraction does best on focused input; evidence_grade is the
    # exception because its grade verdict is the deep-dive's confidence
    # anchor and benefits from these priors (see the orchestrator's
    # ``evidence_grade_ctx`` comment).
    triage_summary_json = context.get("triage_summary_json")
    hgnc_gene_groups = context.get("hgnc_gene_groups") or []
    uniprot_family = context.get("uniprot_family")

    triage_block = ""
    if triage_summary_json:
        triage_block = (
            "# Triage prior\n\n"
            "The upstream `surface_triage` Haiku verdict on this gene "
            "(before any deep literature). Use as calibration only: a "
            "`verdict='likely'` with high triage `confidence` makes a "
            "graded `weak` plausible IFF the ledger genuinely lacks "
            "direct method evidence (don't downgrade past what the "
            "claims support); a `verdict='no'` with high triage "
            "confidence should make you re-check whether the A1 "
            "claims really show surface accessibility or just "
            "non-specific signal. Do NOT cite the triage in "
            "`grade_rationale` — cite only the A1 ledger.\n\n"
            f"```json\n{triage_summary_json}\n```\n\n"
        )
    family_block = ""
    if hgnc_gene_groups or uniprot_family:
        family_block = (
            "# Curator-assigned family tags (ground truth)\n\n"
            "HGNC gene-group memberships + the parsed UniProt SIMILARITY "
            "family — NOT model output, curator-assigned. Use to anchor "
            "the antibody-cross-reactivity-with-paralog discussion in "
            "`grade_rationale` (and to weight any `paralog_decoy` "
            "claim in `claim_stances`).\n\n"
            "```json\n"
            f'{{"hgnc_gene_groups": {hgnc_gene_groups!r}, '
            f'"uniprot_family": {uniprot_family!r}}}\n'
            "```\n\n"
        )
    methods_summary = context.get("methods_summary", "")
    methods_block = ""
    if methods_summary:
        methods_block = (
            "# Methods builder output (already committed)\n\n"
            "Each row: `family/subclass | accessibility_relevance | "
            "species | cites`. Species is resolved deterministically from "
            "the cited claims' `assay_context.species` (human-anchored "
            "when any cite is human; otherwise the union of non-human "
            "species). Use it when applying the species rule:\n"
            "- `direct_*` requires ≥1 / ≥2 methods with "
            "`accessibility_relevance=direct_surface_accessibility`.\n"
            "- If no method carries `direct_surface_accessibility`, the "
            "grade cannot be `direct_*`.\n"
            "- If the ONLY direct rows are non-human-anchored "
            "(`species != human`), the grade caps at "
            "`supportive_but_indirect` — cross-species evidence supports "
            "membrane association but cannot anchor a `direct_*` call "
            "for the human protein on its own.\n\n"
            f"```\n{methods_summary}\n```\n\n"
        )
    # Retry-with-feedback path: when the orchestrator catches a
    # cardinality mismatch (direct_* grade with 0 direct_surface_
    # accessibility methods) and re-calls this builder, it injects an
    # explicit constraint into the context. Surface it at the top of the
    # user prompt so the second-attempt response sees the rejection
    # before the rest of the ledger.
    cardinality_feedback = context.get("cardinality_feedback", "")
    cardinality_block = ""
    if cardinality_feedback:
        cardinality_block = (
            "# CARDINALITY FEEDBACK (read first)\n\n"
            f"{cardinality_feedback}\n\n"
        )
    system_prompt = load_prompt("evidence_grade_builder_system")
    user_prompt = (
        f"# Gene: {gene}\n\n"
        f"{cardinality_block}"
        f"{triage_block}"
        f"{family_block}"
        f"{methods_block}"
        f"{format_ledger_block(claims, header='A1 full ledger')}\n"
        f"{format_schema_block(EvidenceGradeBlock.model_json_schema(), name='EvidenceGradeBlock')}\n"
        "Emit ONE fenced ```json block containing a JSON OBJECT with keys "
        "`evidence_grade`, `claim_stances`, `grade_rationale`, "
        "`non_surface_expression`, `excluded_as_ligand_engagement`. "
        "Emit `claim_stances` BEFORE `grade_rationale` so per-claim "
        "judgments commit first; the rationale then summarizes the "
        "stances rather than the reverse. No prose around it.\n"
    )
    parsed = call_builder(
        client,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=EvidenceGradeBlock,
        usage_sink=usage_sink,
        label="evidence_grade_builder",
        # Heavy builder: consumes the FULL A1 ledger and emits both a
        # grade verdict + a non_surface_expression list. The latter can
        # be long on broadly-expressed proteins.
        max_tokens=MAX_TOKENS_HEAVY,
        meta_sink=meta_sink,
    )
    if parsed is None or not isinstance(parsed, EvidenceGradeBlock):
        logger.warning("evidence_grade_builder failed → falling back to weak/empty")
        return _DEFAULT_BLOCK
    known = {c.evidence_id for c in claims}
    cleaned_rows = [
        row.model_copy(
            update={
                "cited_evidence_ids": [i for i in row.cited_evidence_ids if i in known]
            }
        )
        for row in parsed.non_surface_expression
    ]
    # Same scrubbing pattern for claim_stances — drop any stance row
    # whose claim_id the LLM fabricated. Logged so a high drop rate
    # surfaces as a builder-quality signal.
    cleaned_stances = [s for s in parsed.claim_stances if s.claim_id in known]
    n_dropped = len(parsed.claim_stances) - len(cleaned_stances)
    if n_dropped > 0:
        logger.warning(
            "evidence_grade_builder: dropped %d claim_stances rows with "
            "unresolved claim_id (LLM cited evidence_ids absent from the input ledger)",
            n_dropped,
        )
    cleaned_excluded = [
        ex for ex in parsed.excluded_as_ligand_engagement if ex.evidence_id in known
    ]
    n_excluded_dropped = (
        len(parsed.excluded_as_ligand_engagement) - len(cleaned_excluded)
    )
    if n_excluded_dropped > 0:
        logger.warning(
            "evidence_grade_builder: dropped %d excluded_as_ligand_engagement "
            "rows with unresolved evidence_id (LLM cited ids absent from input)",
            n_excluded_dropped,
        )
    return parsed.model_copy(
        update={
            "non_surface_expression": cleaned_rows,
            "claim_stances": cleaned_stances,
            "excluded_as_ligand_engagement": cleaned_excluded,
        }
    )


__all__ = ["EvidenceGradeBlock", "build_evidence_grade"]
