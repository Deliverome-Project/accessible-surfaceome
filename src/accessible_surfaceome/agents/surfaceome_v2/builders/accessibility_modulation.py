"""A2 → ``list[AccessibilityModulationObservation]``.

The heaviest builder — category-conditional sub-field rules are validator-
enforced. Post-validation we also scrub un-cited ids and re-validate per
row to catch any mispairings the model emitted; mispaired rows get
dropped rather than crashing the entire builder.
"""

from __future__ import annotations

import logging
import re
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


# Quote-level signal words used to classify an A2 ``tissue_expression``
# claim as describing a NORMAL vs TUMOR baseline. Matched
# case-insensitively against the claim's verbatim quote. The model still
# arbitrates whether the pair qualifies as a modulation row — these are
# only candidate-pair hints, not ground truth.
_NORMAL_QUOTE_TOKENS: tuple[str, ...] = (
    "normal",
    "healthy",
    "non-tumor",
    "non-malignant",
    "non-cancerous",
    "non-neoplastic",
    "control",
    "adjacent normal",
)
_TUMOR_QUOTE_TOKENS: tuple[str, ...] = (
    "tumor",
    "tumour",
    "cancer",
    "carcinoma",
    "malignant",
    "neoplastic",
    "adenocarcinoma",
    "metastatic",
    "metastasis",
    "tumor-adjacent",
    "tumour-adjacent",
)
# Tissue-keyword vocabulary used to bucket a claim's quote by anatomical
# site. A claim is assigned to a bucket if any keyword from that bucket
# is present in the quote (case-insensitive whole-word). The vocabulary
# is intentionally narrow and high-precision — generic words like
# "tissue" or "cells" aren't here because they over-match. Buckets a
# normal-vs-tumor pair share is the join key.
_TISSUE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "colon": ("colon", "colonic", "colorectal", "rectal", "rectum"),
    "breast": ("breast", "mammary"),
    "lung": ("lung", "pulmonary", "bronchial", "alveolar", "NSCLC", "SCLC"),
    "pancreas": ("pancreas", "pancreatic"),
    "prostate": ("prostate", "prostatic"),
    "ovary": ("ovary", "ovarian"),
    "stomach": ("stomach", "gastric"),
    "liver": ("liver", "hepatic", "hepatocellular", "hepatocyte", "HCC"),
    "kidney": ("kidney", "renal", "nephron"),
    "bladder": ("bladder", "urothelial", "urothelium"),
    "skin": ("skin", "melanoma", "epidermal", "keratinocyte"),
    "thyroid": ("thyroid",),
    "brain": ("brain", "glioma", "glioblastoma", "astrocyte"),
    "head_and_neck": ("head and neck", "HNSCC", "oral", "laryngeal", "esophageal", "esophagus"),
    "blood": ("blood", "leukemia", "lymphoma", "AML", "ALL", "CLL", "myeloma"),
    "bone": ("bone", "osteosarcoma"),
    "uterus": ("uterus", "uterine", "endometrial", "cervical", "cervix"),
}


def _classify_disease_context(quote: str) -> str | None:
    """Return ``"normal"`` / ``"tumor"`` / ``None`` for a claim's quote.

    Tumor language wins when both are present (the more clinically
    load-bearing read), so "tumor-adjacent normal colon" tags TUMOR
    rather than NORMAL — which is the right call for a TROP2-shape
    "expressed in tumor but not adjacent normal" sentence pair.
    """
    q = quote.lower()
    has_tumor = any(t in q for t in _TUMOR_QUOTE_TOKENS)
    has_normal = any(t in q for t in _NORMAL_QUOTE_TOKENS)
    if has_tumor:
        return "tumor"
    if has_normal:
        return "normal"
    return None


def _classify_tissue_bucket(quote: str) -> str | None:
    """Return a single tissue-bucket key for the claim's quote, or
    ``None`` if no keyword matched. First hit wins by ``_TISSUE_KEYWORDS``
    iteration order — predictable across runs."""
    q = quote.lower()
    for bucket, words in _TISSUE_KEYWORDS.items():
        for w in words:
            # Lowercase already; use a word-boundary regex so "colon"
            # doesn't match "colonel" and "AML" doesn't match "small".
            if re.search(rf"\b{re.escape(w.lower())}\b", q):
                return bucket
    return None


def _find_tumor_normal_pairs(
    claims: list[EvidenceClaim],
) -> list[tuple[str, EvidenceClaim, EvidenceClaim]]:
    """Group A2 ``tissue_expression`` claims into ``(tissue_bucket,
    normal_claim, tumor_claim)`` triples whose quotes describe the
    same anatomical site under different disease contexts.

    Returns one triple per unique tissue × pair of claims. When the
    ledger has multiple normal claims for one tissue we emit one
    triple per ``(normal, tumor)`` combination (small N — bounded by
    expression-claim count); the LLM dedupes downstream.

    The detector is intentionally cheap and over-eager: false positives
    are far less harmful than false negatives because the LLM gates each
    candidate against the system prompt's "qualifying shifts" rule before
    emitting a row. The cost is empty rows the LLM rejects — not bad
    rows that leak through.
    """
    normals_by_tissue: dict[str, list[EvidenceClaim]] = {}
    tumors_by_tissue: dict[str, list[EvidenceClaim]] = {}
    for c in claims:
        if c.claim_type != "tissue_expression":
            continue
        tissue = _classify_tissue_bucket(c.quote)
        if tissue is None:
            continue
        bucket = _classify_disease_context(c.quote)
        if bucket == "normal":
            normals_by_tissue.setdefault(tissue, []).append(c)
        elif bucket == "tumor":
            tumors_by_tissue.setdefault(tissue, []).append(c)
    pairs: list[tuple[str, EvidenceClaim, EvidenceClaim]] = []
    for tissue, normals in normals_by_tissue.items():
        for tumor in tumors_by_tissue.get(tissue, []):
            for normal in normals:
                pairs.append((tissue, normal, tumor))
    return pairs


def _format_tumor_pair_candidates_block(
    pairs: list[tuple[str, EvidenceClaim, EvidenceClaim]],
) -> str:
    """Render the candidate normal-vs-tumor pairs as a prompt section.

    Each pair becomes one bullet naming the tissue bucket, both
    evidence_ids, and a verbatim slice of each quote. The block ends
    with an explicit instruction: emit ONE row per qualifying pair with
    ``category='cell_state_induced'``,
    ``cell_state_trigger='oncogenic_transformation'``, ``direction=
    'increases'`` (or ``decreases`` if normal>tumor), and BOTH evidence
    ids cited.

    See ``docs/audit/amod_anat_regression_2026_06_08.md`` — this section
    is the deterministic lift for the TROP2-shape regression where the
    v2.8.0 builder produced 6× ``disease_state_induced ×
    oncogenic_transformation`` rows the v2.35.0 builder is no longer
    reliably reconstructing from prose.
    """
    if not pairs:
        return ""
    lines = [
        "## Candidate modulation rows derived from expression-level deltas",
        "",
        "The detector below scanned the A2 ledger and identified same-tissue ",
        "expression pairs that document a normal vs tumor / tumor-adjacent ",
        "contrast. Each pair is a CANDIDATE for ONE ",
        "`accessibility_modulation` row in the output. Apply the qualifying-",
        "shift gate: if both rows actually describe a SURFACE pool shift ",
        "(level differs by ≥1 enum step — `low/moderate` → `high`, ",
        "`absent` → any present, etc.) and not just an mRNA / total-protein ",
        "shift, emit ONE row with:",
        "",
        "  * `category='cell_state_induced'`",
        "  * `cell_state_trigger='oncogenic_transformation'`",
        "  * `direction='increases'` when the tumor read > normal read; ",
        "    `decreases` when normal > tumor; `bidirectional` if mixed.",
        "  * `baseline_context` = the normal observation's tissue / cell context.",
        "  * `modulating_state` = the tumor observation's tissue / cell context.",
        "  * `cited_evidence_ids` = BOTH the normal and tumor evidence_ids.",
        "",
        "Pairs:",
        "",
    ]
    for tissue, normal, tumor in pairs:
        lines.append(
            f"- Tissue bucket: `{tissue}` — normal `{normal.evidence_id}` "
            f"vs tumor `{tumor.evidence_id}`"
        )
        lines.append(f"  - Normal ({normal.source_id}): \"{normal.quote[:240]}\"")
        lines.append(f"  - Tumor ({tumor.source_id}): \"{tumor.quote[:240]}\"")
    lines.append("")
    lines.append(
        "If a pair does NOT describe a surface shift (e.g. RNA-only, "
        "intracellular pool only) — SKIP it. False-positive pairs in this "
        "list are expected; the gate is yours, not the detector's."
    )
    lines.append("")
    return "\n".join(lines)


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
    tumor_pair_block = _format_tumor_pair_candidates_block(
        _find_tumor_normal_pairs(claims)
    )
    user_prompt = (
        f"# Gene: {gene}\n\n"
        f"{format_ledger_block(claims, header='A2 ledger (full)')}\n"
        f"{tumor_pair_block}"
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
