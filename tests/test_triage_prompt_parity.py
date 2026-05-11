"""Enforce cross-variant parity for the surface_triage system prompts.

We run four prompt variants (system.md, system_naive.md, system_web.md,
system_web_naive.md) in a single comparative benchmark, so any drift in
**substantive** guidance silently confounds the (model × variant) accuracy
comparison. This test pins the shared substantive blocks: a fingerprint
string drawn from each block must appear byte-identically in every variant
where the block belongs.

Three categories of content:

1. **Shared everywhere** — verdict definitions, cardinal-rule logic, full
   reason-enum descriptions, probes 1–6 of the Pre-`no` checklist, the
   "don't defer" closing emphasis. These MUST be identical across all four
   variants. Fingerprints in ``SHARED_FINGERPRINTS`` enforce this.

2. **Resolver-only** — probes 7 (HGNC gene-group / CD designation) and 8
   (NCBI summary signal) plus the resolver-context preamble. Only the two
   resolver variants (system.md, system_web.md) carry these. Fingerprints
   in ``RESOLVER_ONLY_FINGERPRINTS`` enforce presence in those two AND
   absence in the other two.

3. **Tool-only / variant-specific** — Tools section mentioning
   ``web_search`` (only in the two web variants). Naming variations across
   variants are expected here; the test doesn't pin exact wording for
   these tool-availability mentions.

If you need to change a shared block, change every variant in the same
commit. The test catches you next run if you forgot.
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
)
RESOLVER_VARIANTS = ("system.md", "system_web.md")
NO_RESOLVER_VARIANTS = ("system_naive.md", "system_web_naive.md")
WEB_VARIANTS = ("system_web.md", "system_web_naive.md")
NON_WEB_VARIANTS = ("system.md", "system_naive.md")


# Each entry is a short fingerprint string that uniquely identifies a
# substantive block. Keys are human-readable IDs; the strings themselves
# must appear verbatim in every variant the block belongs to.
SHARED_FINGERPRINTS: dict[str, str] = {
    # --- Verdict definitions
    "verdict_yes": (
        "the protein body is stably present on the outer face of the PM "
        "under its baseline localization, via its own mechanism (TM domain, "
        "GPI anchor, other outer-leaflet lipidation, direct outer-leaflet "
        "lipid binding, pore assembly, or stable non-covalent partner of "
        "an anchored protein co-trafficked as a complex). See the `reason` "
        "enum below for the specific mechanism categories."
    ),
    "verdict_contextual": (
        "the protein body reaches the outer face only under specific, "
        "documented conditions (cell state, tissue / cell type, trafficking "
        "cycling, dual localization, stable post-translational TM-partner "
        "anchoring). *Transient* recruitment to other surface receptors "
        "does NOT count."
    ),
    "verdict_no": (
        "the protein body is not accessible from outside the cell: "
        "cytoplasmic, nuclear, mitochondrial-internal, endomembrane-resident, "
        "nuclear-envelope, inner-leaflet-anchored, secreted-only, or "
        "pMHC-only-intracellular."
    ),
    # --- Cardinal rule
    "cardinal_lead": (
        "The distinction that drives most borderline calls: **does this "
        "protein reach the outer leaflet by its own mechanism, or only "
        "because something else on the surface holds it there?**"
    ),
    "cardinal_recruiter": (
        "the **recruiter** is the surface target, not the recruited protein. "
        "The same exclusion applies to vesicle cargo and to covalent "
        "deposition into the extracellular matrix or stroma."
    ),
    "cardinal_wash_test": (
        "When in doubt, ask: *if you wash the cells, does the protein stay "
        "on the surface via a stable physical link to the membrane or a TM "
        "partner?* If yes, it's at least `contextual`. If it leaves with "
        "the wash, it's `no`."
    ),
    "cardinal_apply_recruitment_test": (
        "Apply the recruitment test before defaulting to `secreted_only`."
    ),
    "preamble_treat_no_as_highest_cost": (
        "Treat `no` as the highest-cost error: false negatives are not "
        "recoverable downstream while false positives are."
    ),
    "closing_do_not_emit_no_with_membrane_association": (
        "Do not emit `no` for any protein with documented membrane "
        "association at any stage of its lifecycle."
    ),
    "probe6_treat_naming_as_hint": (
        "Treat activation- or stress-state naming as a hint toward "
        "cell-state induction"
    ),
    "probe6_treat_latent_as_hint": (
        "as hints toward "
    ),  # both variants use "as hints toward TM-partner tethering" or "...covalent / wash-resistant TM-partner tethering"
    # --- Reason enum: contextual (the most-evolved bucket)
    "enum_cell_state_induced": (
        "translocates to the outer leaflet only under a defined non-baseline "
        "cellular state. Covers (a) **stress**"
    ),
    "enum_cell_state_oncogenic": (
        "**oncogenic transformation** — proteins canonically intracellular "
        "at baseline that are displayed on the outer leaflet of tumor cells"
    ),
    "enum_tissue_restricted_germline": (
        "**Germline / gamete-restricted display with its own anchor (TM, GPI, "
        "or outer-leaflet lipidation) still goes here**"
    ),
    "enum_dual_localization_equivalent": (
        "Treat vesicular cycling and steady-state dual home equivalently "
        "for accessibility"
    ),
    "enum_dual_localization_tm_proligands": (
        "Also covers single-pass TM proligands whose ectodomain is released "
        "by regulated proteolysis, where the **TM precursor stage is "
        "transient** and the **soluble shed form is the dominant "
        "biological actor**"
    ),
    "enum_stable_surface_attachment_covalent_chemistry": (
        "covalently (e.g. disulfide tethering to a TM scaffold, "
        "thioester-mediated covalent attachment to a cell-surface acceptor, "
        "transamidase / transglutaminase cross-linking, or similar "
        "wash-resistant covalent chemistry)"
    ),
    "enum_pmhc_only_intracellular": (
        "pMHC presentation is NOT credited for surface accessibility — every "
        "intracellular protein has potentially MHC-presentable peptides, so "
        "it is not a discriminating signal."
    ),
    # --- Pre-`no` checklist probes 1-6
    "probe1_anti_soluble_exception": (
        "anti-cytokine, anti-growth-factor, or anti-complement programs "
        "targeting the secreted form don't establish surface accessibility "
        "on cells"
    ),
    "probe1_pmhc_exception": (
        "TCR-T / TCR-mimic / bispecifics that engage an MHC-presented peptide "
        "do not establish surface accessibility for the protein body"
    ),
    "probe2_shedding_header": (
        "Is the protein an ectodomain-shedding target — a single-pass TM "
        "precursor whose soluble form is the released ectodomain?"
    ),
    "probe2_stable_tm": (
        "**Stable TM precursor → `yes` / `classical_surface_receptor`.**"
    ),
    "probe2_transient_tm": (
        "**Transient TM precursor of a shed-ligand-dominant gene → "
        "`contextual` / `dual_localization`.**"
    ),
    "probe2_alt_splicing": (
        "**TM-and-secreted alternative splicing.** When the gene encodes "
        "both a TM and a soluble-decoy isoform"
    ),
    "probe3_latent_hints": (
        'Naming hints like "latent" / "pro-protein" / "propeptide" / '
        '"pre-pro" point here.'
    ),
    "probe3_secretory_compartment": (
        "stably deposited onto a cell surface during transit through a "
        "specialized secretory compartment"
    ),
    "probe3_covalent_chemistry_list": (
        "covalent linkage (disulfide, thioester, transamidase / transglutaminase) "
        "or by wash-resistant non-covalent association"
    ),
    "probe4_minority_pm_pool": (
        "**Do not gate `contextual` on the surface pool being the dominant "
        "compartment.**"
    ),
    "probe5_header": (
        "Is there a documented non-baseline surface pool in any of these "
        "four contexts?"
    ),
    "probe5_cancer": "1. **Cancer / oncogenic-state ecto-presentation.**",
    "probe5_cell_death": "2. **Cell-death-induced surface display.**",
    "probe5_developmental": (
        "3. **Developmental / germline-restricted surface display.**"
    ),
    "probe5_activation": "4. **Activation-induced surface display.**",
    "probe5_dont_defer": (
        "**don't defer to the baseline compartment when a non-baseline "
        "ecto-pool is documented.**"
    ),
    # --- Output contract
    "output_contract_json_shape": (
        '"verdict": "yes" | "contextual" | "no"'
    ),
    "output_contract_reasoning": (
        '"verdict_reasoning": "<= 800 chars explaining the call"'
    ),
    "preamble_must_enumerate_contextual": (
        "When you emit `no`, your `verdict_reasoning` must explicitly name "
        "each of the 5 contextual reasons and state the specific evidence "
        "that rules each one out"
    ),
    "preamble_do_not_skip": (
        "Do not skip any of the 5 buckets; do not anchor on a single "
        "dominant compartment from the NCBI summary, gene-group lineage, "
        "or your trained knowledge."
    ),
}


# Probes / preamble that should appear ONLY in the resolver variants.
# Listed (fingerprint, expected_variants_set) — the test enforces both
# presence in the expected set and absence in the complement.
RESOLVER_ONLY_FINGERPRINTS: dict[str, str] = {
    "preamble_resolver_inputs": (
        "Treat the task-context inputs — HGNC gene-group memberships, CD "
        "designation, NCBI subcellular summary, aliases, previous symbols"
    ),
    "probe7_hgnc_gene_group": (
        "Do the HGNC gene-group memberships or a CD designation imply "
        "surface biology?"
    ),
    "probe7_body_registry_curated": (
        "The task context lists each protein's HGNC gene-group families "
        "(registry-curated lineages — chemokine receptors, solute carriers, "
        "claudins, tetraspanins, GPCRs, etc.) and its CD nomenclature "
        "designation when assigned."
    ),
    "probe7_treat_family_as_signal": (
        "Treat membership in a canonical surface-protein gene-family — or "
        "possession of a CD number at all — as a strong surface signal"
    ),
    "ncbi_caveat_not_authoritative": (
        "Do not treat the NCBI subcellular call as authoritative — those "
        "notes are often terse, occasionally outdated, and sometimes refer "
        "to a single experimental context."
    ),
    "probe7_weight_registry_heavier": (
        "When the HGNC gene-group family lineage and the NCBI summary "
        "disagree, weight the registry-curated family lineage more heavily"
    ),
    "probe8_ncbi_summary": (
        "Does the NCBI summary suggest non-classical surface biology?"
    ),
    "probe8_body_resolver_signals": (
        "If the resolver context mentions latent complex, activation-induced "
        "expression, ectodomain shedding, dual localization, or any "
        "surface-relevant biology beyond the dominant subcellular call — "
        "pause and consider the relevant contextual reason."
    ),
}


# Tool-availability fingerprints. These ARE expected to differ between
# web vs non-web variants — we just sanity-check that web_search is
# mentioned only in the web variants.
TOOL_FINGERPRINTS: dict[str, tuple[str, ...]] = {
    "web_search_tool": WEB_VARIANTS,
    "no tools": NON_WEB_VARIANTS,
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
        "If you intentionally changed this block, update it in all four "
        "variants in the same commit (and update this test's fingerprint)."
    )


# --- Resolver-only parity --------------------------------------------------


@pytest.mark.parametrize(
    "block_id,fingerprint", sorted(RESOLVER_ONLY_FINGERPRINTS.items())
)
def test_resolver_only_block_in_resolver_variants(
    variant_texts: dict[str, str], block_id: str, fingerprint: str
) -> None:
    """Resolver-dependent blocks must be present in the 2 resolver variants
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


def test_web_search_mention_only_in_web_variants(
    variant_texts: dict[str, str],
) -> None:
    """web_search should be mentioned in the 2 web variants only."""
    for v in WEB_VARIANTS:
        assert "web_search" in variant_texts[v], (
            f"{v} should mention web_search"
        )
    for v in NON_WEB_VARIANTS:
        assert "web_search" not in variant_texts[v], (
            f"{v} should NOT mention web_search"
        )


def test_no_tools_phrase_only_in_naive_variant(
    variant_texts: dict[str, str],
) -> None:
    """system_naive.md should explicitly state no tools are available."""
    assert "no tools" in variant_texts["system_naive.md"].lower(), (
        "system_naive.md should explicitly say it has no tools available"
    )


# --- Gene-name leakage -----------------------------------------------------

# Genes from the subbench + main bench that have been discussed in
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
