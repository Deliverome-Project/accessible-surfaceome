"""Enforce cross-variant parity for the surface_triage system prompts.

The 5 variants (system.md, system_naive.md, system_web.md,
system_web_naive.md, system_pubmed.md) are evaluated head-to-head, so
any drift in **substantive** guidance silently confounds the
(model × variant) accuracy comparison. The fingerprints below pin
shared substantive blocks: each string must appear byte-identically in
every variant where the block belongs.

After the 2026-05-11 slim canonicalization, every variant carries the
same ~1,700-token slim body — verdict + reason-enum + before-emitting-
no + output-contract — and differs only in the per-variant
tools/context paragraph at the top.

Categories:

1. **Shared everywhere** — verdict definitions, every reason enum
   entry, the "Before emitting `no`" framing, and the output-contract
   shape. Identical across all 5. Pinned by ``SHARED_FINGERPRINTS``.

2. **Resolver-only** — the resolver-context phrase
   ("HGNC + UniProt + NCBI + gene-group + CD designation context").
   Present in resolver variants, absent in no-resolver variants. Pinned
   by ``RESOLVER_ONLY_FINGERPRINTS``.

3. **Tool / variant-specific** — ``web_search`` only in web variants,
   ``PubMed`` only in the pubmed variant. Pinned by ``TOOL_FINGERPRINTS``.

If you change a shared block, change every variant in the same commit.
The test catches you next run if you forgot.
"""

from __future__ import annotations

import pytest

from accessible_surfaceome.paths import REPO_ROOT

PROMPTS_DIR = (
    REPO_ROOT
    / "src"
    / "accessible_surfaceome"
    / "agents"
    / "surface_triage"
    / "prompts"
)

ALL_VARIANTS = (
    "system.md",
    "system_naive.md",
    "system_web.md",
    "system_web_naive.md",
    "system_pubmed.md",
)
RESOLVER_VARIANTS = ("system.md", "system_web.md", "system_pubmed.md")
NO_RESOLVER_VARIANTS = ("system_naive.md", "system_web_naive.md")
WEB_VARIANTS = ("system_web.md", "system_web_naive.md")
NON_WEB_VARIANTS = ("system.md", "system_naive.md", "system_pubmed.md")
PUBMED_VARIANTS = ("system_pubmed.md",)
NON_PUBMED_VARIANTS = tuple(v for v in ALL_VARIANTS if v not in PUBMED_VARIANTS)


# Each entry is a short fingerprint string from a substantive block that
# all 5 slim-style prompts MUST carry byte-identically. The body of the
# prompts is generated from a single template, so drift in any of these
# means someone hand-edited one file without propagating.
SHARED_FINGERPRINTS: dict[str, str] = {
    # --- Opening (PM defined, scope sentence)
    "opening_pm_definition": (
        "reach the protein body from the **extracellular face** of the "
        "plasma membrane (PM)."
    ),
    # --- Verdict — pick one
    "verdict_pick_one_header": "## Verdict — pick one",
    "verdict_yes": (
        "protein body is stably on the outer leaflet under baseline "
        "localization via its own mechanism."
    ),
    "verdict_contextual": (
        "protein body reaches the outer leaflet only under documented "
        "conditions. *Transient* reversible recruitment to a surface "
        "receptor does NOT count."
    ),
    "verdict_no": "not accessible from outside the cell.",
    # --- Reason enum: verdict = yes
    "yes_classical_surface_receptor": (
        "`classical_surface_receptor` — single-pass TM with substantial "
        "extracellular domain."
    ),
    "yes_gpi_anchored": "`gpi_anchored` — GPI anchor on the outer leaflet.",
    "yes_multipass": (
        "`multipass_with_exposed_loops` — multi-pass TM (GPCR, "
        "transporter, channel) with extracellular loops."
    ),
    "yes_stable_complex_partner": (
        "`stable_complex_partner` — no membrane anchor of its own, but a "
        "stable non-covalent partner of an anchored surface protein, "
        "assembled intracellularly and co-trafficked."
    ),
    # --- Reason enum: verdict = contextual
    "contextual_cell_state_induced": (
        "`cell_state_induced` — surfaces only under stress, oncogenic "
        "transformation, immunogenic / programmed cell death, infection, "
        "or activation-induced display."
    ),
    "contextual_tissue_restricted": (
        "`tissue_restricted_surface` — surface display restricted to a "
        "narrow lineage (germline / reproductive, developmental, or a "
        "single specialized somatic cell type) — use this over `yes` "
        "even when the anchor type is unambiguous."
    ),
    "contextual_lysosomal_exocytosis": (
        "`lysosomal_exocytosis` — lysosomal / late-endosomal TM protein "
        "reaches the PM via lysosomal exocytosis."
    ),
    "contextual_dual_localization": (
        "`dual_localization` — documented PM pool alongside a dominant "
        "non-PM compartment, via active cycling or steady-state partial "
        "residence. Also covers TM proligands whose shed ectodomain is "
        "the dominant biological actor."
    ),
    "contextual_stable_surface_attachment": (
        "`stable_surface_attachment` — secreted protein **wash-"
        "resistantly anchored** to a TM partner post-translationally"
    ),
    # --- Reason enum: verdict = no
    "no_secreted_only": (
        "`secreted_only` — secreted with no wash-resistant surface "
        "anchoring."
    ),
    "no_pmhc_only_intracellular": (
        "`pmhc_only_intracellular` — strictly intracellular; only "
        '"surface" story is MHC-presented peptides.'
    ),
    "no_cytoplasmic": (
        "`cytoplasmic` — soluble cytoplasmic, no membrane association."
    ),
    "no_inner_leaflet": (
        "`inner_leaflet_anchored` — lipidated or peripheral on the "
        "cytoplasmic face of the PM."
    ),
    # --- Before emitting `no` framing
    "before_no_header": "## Before emitting `no`",
    "before_no_highest_cost_error": (
        "`no` is the highest-cost error: false negatives are not "
        "recoverable downstream while false positives are."
    ),
    "before_no_name_5_buckets": (
        "**Your `verdict_reasoning` must name each of the 5 contextual "
        "reasons and the specific evidence ruling each out**"
    ),
    "before_no_surface_directed_therapeutic": (
        "**Cell-surface-directed therapeutic.**"
    ),
    "before_no_ectodomain_shedding": (
        "**Ectodomain shedding / TM precursor.**"
    ),
    "before_no_stable_tm_arrow": (
        "**Stable TM precursor → `yes` / `classical_surface_receptor`**"
    ),
    "before_no_transient_tm_arrow": (
        "**transient TM precursor of a shed-ligand-dominant gene → "
        "`contextual` / `dual_localization`**"
    ),
    # NB: the "Do not emit `no` for any protein with documented membrane
    # association at any stage of its lifecycle" block was intentionally
    # removed from all 5 variants in SurfaceBench v2 (commit 45fbaffdb) —
    # it was over-broad and forbade `no` for endomembrane / inner-leaflet
    # proteins. No fingerprint pins it any more.
    # --- Output contract
    "output_contract_json_shape": '"verdict": "yes" | "contextual" | "no"',
    "output_contract_reasoning": (
        '"verdict_reasoning": "<= 800 chars explaining the call"'
    ),
    "output_contract_confidence": '"confidence": "low" | "medium" | "high"',
    "output_contract_key_uncertainty": (
        '"key_uncertainty": "<= 200 chars naming the unresolved ambiguity, or null"'
    ),
    "confidence_high_criterion": (
        "`high` only when the verdict rests on explicit, unambiguous evidence"
    ),
    "single_best_reason": "Pick the **single best** reason.",
}


# Resolver-context phrase. Present in resolver variants, absent in
# no-resolver variants.
RESOLVER_ONLY_FINGERPRINTS: dict[str, str] = {
    "resolver_context_phrase": (
        "HGNC + UniProt + NCBI + gene-group + CD designation context"
    ),
}


# Tool / variant-specific fingerprints. Each maps to the set of variants
# where the fingerprint must appear; the complement must NOT contain it.
TOOL_FINGERPRINTS: dict[str, tuple[str, ...]] = {
    "web_search":  WEB_VARIANTS,
    "PubMed":      PUBMED_VARIANTS,
}


# --- Loaders ---------------------------------------------------------------


def _load(variant: str) -> str:
    return (PROMPTS_DIR / variant).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def variant_texts() -> dict[str, str]:
    return {v: _load(v) for v in ALL_VARIANTS}


# --- Shared-block parity ---------------------------------------------------


@pytest.mark.parametrize("block_id,fingerprint", sorted(SHARED_FINGERPRINTS.items()))
def test_shared_block_present_in_all_variants(
    variant_texts: dict[str, str], block_id: str, fingerprint: str
) -> None:
    """Every shared substantive block must appear in every variant."""
    missing = [v for v in ALL_VARIANTS if fingerprint not in variant_texts[v]]
    assert not missing, (
        f"Shared block {block_id!r} missing from: {missing}.\n"
        f"Expected fingerprint:\n  {fingerprint!r}\n"
        "If you intentionally changed this block, update it in all "
        "variants in the same commit (the body is regenerated from a "
        "shared template — see git history of system_slim.md "
        "canonicalization)."
    )


# --- Resolver-only parity --------------------------------------------------


@pytest.mark.parametrize(
    "block_id,fingerprint", sorted(RESOLVER_ONLY_FINGERPRINTS.items())
)
def test_resolver_only_block_in_resolver_variants(
    variant_texts: dict[str, str], block_id: str, fingerprint: str
) -> None:
    """Resolver-dependent blocks must be present in the 3 resolver variants
    and absent from the 2 no-resolver variants."""
    missing_in_resolver = [
        v for v in RESOLVER_VARIANTS if fingerprint not in variant_texts[v]
    ]
    leaked_to_no_resolver = [
        v for v in NO_RESOLVER_VARIANTS if fingerprint in variant_texts[v]
    ]
    assert not missing_in_resolver, (
        f"Resolver-only block {block_id!r} missing from resolver variants: "
        f"{missing_in_resolver}"
    )
    assert not leaked_to_no_resolver, (
        f"Resolver-only block {block_id!r} unexpectedly present in "
        f"no-resolver variants: {leaked_to_no_resolver}"
    )


# --- Tool mention sanity ---------------------------------------------------


@pytest.mark.parametrize(
    "fingerprint,expected_variants",
    sorted(TOOL_FINGERPRINTS.items()),
)
def test_tool_mention_only_in_expected_variants(
    variant_texts: dict[str, str],
    fingerprint: str,
    expected_variants: tuple[str, ...],
) -> None:
    """Tool-mention strings must be in the expected variants only."""
    for v in expected_variants:
        assert fingerprint in variant_texts[v], (
            f"{v} should mention {fingerprint!r}"
        )
    for v in ALL_VARIANTS:
        if v in expected_variants:
            continue
        assert fingerprint not in variant_texts[v], (
            f"{v} should NOT mention {fingerprint!r}"
        )


def test_no_tools_phrase_in_no_tool_variants(
    variant_texts: dict[str, str],
) -> None:
    """All non-web variants explicitly state they have no tools."""
    for v in NON_WEB_VARIANTS:
        assert "No tools available" in variant_texts[v], (
            f"{v} should state 'No tools available'"
        )


# --- Gene-name leakage -----------------------------------------------------

# Genes from the triage bench that have been discussed in
# conversations; if any of these symbols leak into the prompts, the
# benchmark is no longer "fair against gene-symbol knowledge". This is
# pattern-matching, not perfect — but it catches the obvious cases.
_FORBIDDEN_GENE_SYMBOLS = (
    "HSPA1A", "HSPA5", "HSPD1", "IZUMO1", "IZUMO4", "CRISP1", "KLK2",
    "SRC", "LYN", "BAX", "EREG", "TGOLN2", "B4GALT1", "STIM1", "ATP5F1B",
    "TMED10", "CALR", "PRAME", "KAAG1", "MUC1", "MUC5AC", "MUC16",
    "ERBB2", "FOLR1", "FOLH1", "CD19", "CD74", "CD276", "CD63", "CD68",
    "SLC34A2", "STEAP1", "STEAP2", "CLDN6", "CLDN18", "GPRC5D",
    "GUCY2C", "PSCA", "SEZ6", "FZD7", "FZD10", "EFNA4", "CSPG4", "MCSP",
    "ALPPL2", "ALPG", "LY6K", "LYPD1", "LYPD3", "TM4SF1", "AMHR2", "TACSTD2",
    "NECTIN4", "PTK7", "SSTR2", "TYRP1", "EPCAM", "CEACAM5", "CEACAM6",
    "GPC2", "GPC3", "DLK1", "GPNMB", "LRRC33", "NRROS",
)


@pytest.mark.parametrize("variant", ALL_VARIANTS)
def test_no_specific_gene_names_in_prompt(
    variant_texts: dict[str, str], variant: str
) -> None:
    """Specific gene symbols must not appear in any triage prompt — the
    triage is supposed to be evaluated on gene-symbol input alone, so
    naming benchmark genes in the prompt poisons the comparison."""
    text = variant_texts[variant]
    # Cheap whole-token search via boundary regex
    import re
    leaked = []
    for symbol in _FORBIDDEN_GENE_SYMBOLS:
        if re.search(rf"\b{re.escape(symbol)}\b", text):
            leaked.append(symbol)
    assert not leaked, (
        f"{variant} contains specific gene symbols: {leaked}. "
        "Triage prompts must be gene-symbol-agnostic."
    )


# --- Family-name leakage ---------------------------------------------------

# Specific protein-family / gene-family names that would prejudge benchmark
# genes belonging to those families. Naming "EGF-family" effectively tells
# the model "EREG, HBEGF, AREG, TGFA, BTC are all <X>" — which leaks the
# answer for any benchmark gene in that family. Same logic for specific
# sheddase / protease gene names (ADAM10, ADAM17, BACE, γ-secretase, etc.)
# which are themselves specific human genes.
#
# Functional / architectural categories ("single-pass TM", "sheddases",
# "growth-factor", "proligand") are OK — they describe shape / function,
# not a specific gene-family lineage.
_FORBIDDEN_FAMILY_NAMES = (
    # Ligand-family names that prejudge specific benchmark genes
    "EGF-family", "EGF family",
    "TNF-family", "TNF family",
    # Sheddase / protease gene names (specific human genes that ARE in the
    # human proteome; the prompt should say "sheddase" generically instead)
    "ADAM10", "ADAM17",
    "BACE1", "BACE2",
    "γ-secretase", "gamma-secretase",
    "PCSK-family",
    "MMP-family",
)


@pytest.mark.parametrize("variant", ALL_VARIANTS)
def test_no_specific_family_names_in_prompt(
    variant_texts: dict[str, str], variant: str
) -> None:
    """Specific protein-family / gene-family names must not appear in any
    triage prompt — naming a family (e.g. ``EGF-family``) effectively names
    every benchmark gene in that family. Use architectural / functional
    descriptions instead (``single-pass TM proligand``, ``sheddase``)."""
    text = variant_texts[variant]
    leaked = [name for name in _FORBIDDEN_FAMILY_NAMES if name in text]
    assert not leaked, (
        f"{variant} contains specific protein-family / gene names: {leaked}. "
        "Generalize to architectural or functional language instead."
    )
