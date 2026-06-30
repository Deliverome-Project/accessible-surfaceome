"""Build per-figure consolidated TSVs from canonical sources.

Each published gist (``data/analysis/figures/gist_map.json``) gets
ONE bundled TSV that carries everything its mirror script needs.
This is the invariant the gist single-TSV pattern enforces — see
``tests/test_gist_single_tsv.py``.

Sources read (idempotent, no LLM, no D1):
  • ``data/eval/triage_benchmark_v1.tsv`` — 147-gene SurfaceBench
  • ``data/processed/triage_bench/mainbench_canonical_v2.tsv`` — per-cell preds + truth + 5 per-DB flags
  • ``data/processed/triage_bench/mainbench_replicates_v2.tsv`` — per-rep is_match + truth
  • ``data/processed/triage_bench/db_optimized_cutoffs.tsv`` — uniprot_optimized / cspa_optimized per UniProt
  • ``data/processed/catalog/whole_proteome_catalog.tsv`` — genome-wide DB-vote table
  • ``data/processed/positive_controls/positive_control_long.tsv`` — positive-control combined long TSV
  • ``data/analysis/db_vs_sonnet_inclusion/per_protein_features.tsv`` — per-protein topology + family flags

Outputs (one per non-compliant figure today, written to
``data/processed/figures/<slug>.tsv``):
  • ``benchmark_cost_vs_accuracy.tsv``
  • ``db_correctness_by_class.tsv``
  • ``db_correctness_overall.tsv``
  • ``db_vs_sonnet_whole_proteome.tsv``
  • ``ensemble_vs_best_db_vs_sonnet.tsv``
  • ``deep_dive_final_categories.tsv`` — MOCK placeholder
  • ``positive_control_db_coverage_bars.tsv``
  • ``bench_topology_vs_universe.tsv``
  • ``triage_vs_deep_dive_reason.tsv`` — MOCK long-form counts
  • ``evidence_corpus_vs_selected.tsv`` — MOCK per-gene synthesis

The remaining 4 gists already use a single canonical TSV as-is
(``db_cutoff_tradeoff``, ``db_overlap_venn``, ``paywall_bot_block_compare``,
``topology_coverage_by_source``, ``zero_db_rescues_by_triage``) — those
keep their existing TSV; no per-figure copy is written for them.

Run::

    uv run python scripts/build_figure_tsvs.py [--out data/processed/figures]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data/processed/figures"

BENCH_TSV       = ROOT / "data/eval/triage_benchmark_v1.tsv"
PREDS_TSV       = ROOT / "data/processed/triage_bench/mainbench_canonical_v2.tsv"
REPS_TSV        = ROOT / "data/processed/triage_bench/mainbench_replicates_v2.tsv"
OPT_CUTOFFS_TSV = ROOT / "data/processed/triage_bench/db_optimized_cutoffs.tsv"
CATALOG_TSV     = ROOT / "data/processed/catalog/whole_proteome_catalog.tsv"
POS_LONG_TSV    = ROOT / "data/processed/positive_controls/positive_control_long.tsv"
FEATURES_TSV    = ROOT / "data/analysis/db_vs_sonnet_inclusion/per_protein_features.tsv"


def _load_sources() -> dict[str, pd.DataFrame]:
    return {
        "bench":   pd.read_csv(BENCH_TSV, sep="\t"),
        "preds":   pd.read_csv(PREDS_TSV, sep="\t"),
        "reps":    pd.read_csv(REPS_TSV, sep="\t"),
        "opt":     pd.read_csv(OPT_CUTOFFS_TSV, sep="\t"),
        "catalog": pd.read_csv(CATALOG_TSV, sep="\t"),
    }


def _join_truth_into_preds(preds: pd.DataFrame, bench: pd.DataFrame) -> pd.DataFrame:
    """Denormalize ground_truth_verdict onto preds. The canonical
    mainbench_canonical_v2 already has this per CLAUDE.md — we
    no-op when the column is already there."""
    out = preds.copy()
    if "ground_truth_verdict" not in out.columns:
        truth = bench.set_index("gene_symbol")["ground_truth_verdict"]
        out["ground_truth_verdict"] = out["gene_symbol"].map(truth)
    return out


def _join_truth_into_reps(reps: pd.DataFrame, bench: pd.DataFrame) -> pd.DataFrame:
    out = reps.copy()
    if "ground_truth_verdict" not in out.columns:
        truth = bench.set_index("gene_symbol")["ground_truth_verdict"]
        out["ground_truth_verdict"] = out["gene_symbol"].map(truth)
    return out


def _join_optimized_cutoffs(catalog: pd.DataFrame, opt: pd.DataFrame) -> pd.DataFrame:
    """Denormalize the two ``*_optimized`` flags from db_optimized_cutoffs
    onto each candidate row, keyed on uniprot_acc/accession. Genes
    outside the optimized-cutoff set get 0 for both flags."""
    out = catalog.copy()
    uniprot_opt = set(opt.loc[opt["uniprot_optimized"] == 1, "accession"].astype(str))
    cspa_opt    = set(opt.loc[opt["cspa_optimized"]    == 1, "accession"].astype(str))
    out["uniprot_optimized"] = out["uniprot_acc"].astype(str).isin(uniprot_opt).astype(int)
    out["cspa_optimized"]    = out["uniprot_acc"].astype(str).isin(cspa_opt).astype(int)
    # Drop internal-only columns that leaked through from the catalog —
    # `universe_version` is provenance bookkeeping, not figure-input data.
    out = out.drop(columns=["universe_version"], errors="ignore")
    return out


# ─────────────────────────── per-figure builders ──────────────────────


def build_cost_vs_accuracy(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per (gene, model, prompt_variant, replicate). Carries
    tokens (per-rep, may be aggregated across reps depending on upstream)
    + ground_truth_verdict + is_match. The figure plots cost vs accuracy
    per (model, variant) cell — accuracy = mean(is_match), cost =
    aggregate(tokens). All columns it needs live on mainbench_replicates_v2
    once truth is denormalized in."""
    return _join_truth_into_reps(src["reps"], src["bench"])


def build_db_correctness_by_class(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per (gene, model, prompt_variant, replicate) on the bench.
    Carries truth + 5 per-DB flags + uniprot/cspa optimized-cutoff flags +
    is_match. The figure: per-bucket accuracy of Sonnet/ncbi vs the 5 DBs.

    We start from mainbench_replicates_v2 (per-rep), join in optimized
    cutoffs by uniprot_acc."""
    df = _join_truth_into_reps(src["reps"], src["bench"])
    uniprot_opt = set(src["opt"].loc[src["opt"]["uniprot_optimized"] == 1, "accession"].astype(str))
    cspa_opt    = set(src["opt"].loc[src["opt"]["cspa_optimized"]    == 1, "accession"].astype(str))
    df["uniprot_optimized"] = df["uniprot_acc"].astype(str).isin(uniprot_opt).astype(int)
    df["cspa_optimized"]    = df["uniprot_acc"].astype(str).isin(cspa_opt).astype(int)
    return df


def build_db_correctness_overall(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Same shape as by_class but the figure only needs the overall
    accuracy, no per-bucket breakdown. Same TSV works."""
    return _join_truth_into_reps(src["reps"], src["bench"])


def build_db_vs_sonnet_whole_proteome(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Genome-wide DB-vote + Sonnet-vote table. The catalog already has
    the per-DB flags + sonnet_verdict denormalized; we just join in the
    two optimized-cutoff columns."""
    return _join_optimized_cutoffs(src["catalog"], src["opt"])


def build_ensemble(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Bench + 5-DB flags + Sonnet ncbi vote + per-rep is_match. Same
    shape as db_correctness_by_class — one consolidated TSV serves both
    figures conceptually but each gist gets its own copy for the
    single-TSV-per-gist invariant."""
    return build_db_correctness_by_class(src)


def build_deep_dive_final_categories(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """MOCK PLACEHOLDER — distribution of surface_call_reason across
    the deep-dive cohort. Real source will be the deep_dive_run table
    in public D1 once the full ~5000-gene sweep completes. For now,
    a hand-authored mock TSV with plausible counts so the gist's
    mirror script has SOMETHING to read.

    Category keys match the mirror script's `_CATEGORY_LABELS` keys
    (``canonical``, ``likely``, ``cell_state``, ``cell_type_restricted``,
    ``no``) so the script can derive its bar-totals + cell-state-stack
    splits directly from the (category, subcategory, n_genes) rows.
    The actual figure is also a mock; see scripts/deep_dive_final_categories.py
    docstring."""
    return pd.DataFrame(
        [
            {"category": "canonical",            "subcategory": "all",             "n_genes": 2900},
            {"category": "likely",               "subcategory": "all",             "n_genes":  700},
            {"category": "cell_state",           "subcategory": "oncogenic",       "n_genes":  230},
            {"category": "cell_state",           "subcategory": "immune",          "n_genes":  140},
            {"category": "cell_state",           "subcategory": "stress_hypoxia",  "n_genes":   80},
            {"category": "cell_state",           "subcategory": "cell_death",      "n_genes":   60},
            {"category": "cell_state",           "subcategory": "infection",       "n_genes":   30},
            {"category": "cell_state",           "subcategory": "other",           "n_genes":   10},
            {"category": "cell_type_restricted", "subcategory": "all",             "n_genes":  450},
            {"category": "no",                   "subcategory": "all",             "n_genes":  400},
        ]
    )


def build_curator_vs_agent_reason(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Per-gene curator-vs-agent reason comparison. The figure is a
    3-panel composite (panel a: bucket-strict accuracy across 10 model
    variants; panel b: per-reason accuracy across 4 frontier configs;
    panel c: Sonnet/ncbi confusion matrix). Needs all (model, variant)
    predictions, so we start from the per-rep TSV (10 model variants ×
    147 genes × 3 reps + per-cell preds collapsed across reps for
    panel c).

    Per-rep TSV already has ground_truth_reason + ground_truth_verdict
    denormalized; predicted_reason comes from the per-cell collapse
    when we keep one row per (gene, model, variant, replicate).
    Slim the columns we don't need (tokens, cost, latency) to keep
    the TSV under the 5 MB practical cap."""
    keep = [
        "gene_symbol", "uniprot_acc", "hgnc_id",
        "model", "prompt_variant", "replicate",
        "predicted_verdict", "predicted_reason", "is_match",
        "ground_truth_verdict", "ground_truth_reason",
    ]
    reps = src["reps"]
    # ground_truth_reason isn't on mainbench_replicates_v2 — join from bench
    if "ground_truth_reason" not in reps.columns:
        reason_lookup = src["bench"].set_index("gene_symbol")["ground_truth_reason"]
        reps = reps.assign(
            ground_truth_reason=reps["gene_symbol"].map(reason_lookup)
        )
    return reps[keep]


def build_positive_control_db_coverage_bars(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Long-form positive-control coverage. Pass-through copy of the
    canonical ``positive_control_long.tsv`` — one row per (category × gene)
    with the per-DB flags + sonnet_full_flag + adc_source already
    denormalized. The figure groups by (category, source) and sums the
    flags from this single TSV without any joins."""
    return pd.read_csv(POS_LONG_TSV, sep="\t")


def _is_sonnet_2tier_yc(row: dict) -> bool:
    """Sonnet 2-tier yes/contextual filter, matching
    ``scripts/bench_topology_vs_universe.py``: NCBI sweep verdict ∈
    {yes, contextual} OR (NCBI=no AND PubMed-rescue verdict ∈ {yes,
    contextual}). This is what the catalog actually ships as the
    "accessible surfaceome" universe."""
    ncbi = (str(row.get("sonnet_verdict") or "")).strip().lower()
    if ncbi in ("yes", "contextual"):
        return True
    pubmed = (str(row.get("pubmed_verdict") or "")).strip().lower()
    return pubmed in ("yes", "contextual")


def build_bench_topology_vs_universe(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Sonnet 2-tier yes/contextual universe + bench-membership flag.
    One row per protein in the Sonnet 2-tier universe (~4,426 of the
    6,589-row per_protein_features TSV), carrying all 9 topology flags
    + an ``is_bench`` boolean marking the 146 of 147 bench members that
    join in by ``uniprot_accession``.

    The figure derives both bars (universe + bench) from this single
    TSV: bench = rows where is_bench=1, universe = all rows."""
    features = pd.read_csv(FEATURES_TSV, sep="\t", low_memory=False)
    bench = src["bench"]
    bench_accs = set(bench["uniprot_acc"].dropna().astype(str).tolist())
    # Filter to Sonnet 2-tier yes/contextual universe
    mask = features.apply(_is_sonnet_2tier_yc, axis=1)
    universe = features[mask].copy()
    universe["is_bench"] = universe["uniprot_accession"].astype(str).isin(bench_accs).astype(int)
    return universe


# ── MOCK long-form for triage_vs_deep_dive_reason ───────────────────────────
# Hand-tuned 10×10 confusion-matrix counts. Mirrors the dict in
# scripts/triage_vs_deep_dive_reason.py — kept here as the canonical
# source the figure bundles. Replace with a public-D1 SELECT once the
# v2 deep-dive sweep lands and joins onto triage_run.
_MOCK_TRIAGE_DD_COUNTS: dict[str, dict[str, int]] = {
    "classical_surface_receptor": {
        "classical_surface_receptor": 1380, "multipass_with_exposed_loops": 60,
        "gpi_anchored":               18,   "stable_complex_partner":       42,
        "stable_surface_attachment":  35,   "cell_state_induced":           28,
        "tissue_restricted_surface":  55,   "dual_localization":            22,
        "cytoplasmic":                14,   "endomembrane_resident":         8,
    },
    "multipass_with_exposed_loops": {
        "classical_surface_receptor": 45,   "multipass_with_exposed_loops": 685,
        "gpi_anchored":               5,    "stable_complex_partner":       18,
        "stable_surface_attachment":  12,   "cell_state_induced":           15,
        "tissue_restricted_surface":  22,   "dual_localization":             8,
        "cytoplasmic":                 6,   "endomembrane_resident":         4,
    },
    "gpi_anchored": {
        "classical_surface_receptor": 8,    "multipass_with_exposed_loops":  2,
        "gpi_anchored":               265,  "stable_complex_partner":        4,
        "stable_surface_attachment":  18,   "cell_state_induced":            3,
        "tissue_restricted_surface":  10,   "dual_localization":             5,
        "cytoplasmic":                 1,   "endomembrane_resident":         2,
    },
    "stable_complex_partner": {
        "classical_surface_receptor": 28,   "multipass_with_exposed_loops":  6,
        "gpi_anchored":               2,    "stable_complex_partner":       155,
        "stable_surface_attachment":  20,   "cell_state_induced":            5,
        "tissue_restricted_surface":  8,    "dual_localization":            10,
        "cytoplasmic":                 4,   "endomembrane_resident":         3,
    },
    "stable_surface_attachment": {
        "classical_surface_receptor": 12,   "multipass_with_exposed_loops":  4,
        "gpi_anchored":               6,    "stable_complex_partner":       18,
        "stable_surface_attachment":  295,  "cell_state_induced":           14,
        "tissue_restricted_surface":  22,   "dual_localization":            25,
        "cytoplasmic":                 5,   "endomembrane_resident":         8,
    },
    "cell_state_induced": {
        "classical_surface_receptor": 8,    "multipass_with_exposed_loops":  3,
        "gpi_anchored":               2,    "stable_complex_partner":        4,
        "stable_surface_attachment":  18,   "cell_state_induced":           475,
        "tissue_restricted_surface":  25,   "dual_localization":            32,
        "cytoplasmic":                10,   "endomembrane_resident":         6,
    },
    "tissue_restricted_surface": {
        "classical_surface_receptor": 25,   "multipass_with_exposed_loops":  8,
        "gpi_anchored":               6,    "stable_complex_partner":        7,
        "stable_surface_attachment":  20,   "cell_state_induced":           30,
        "tissue_restricted_surface":  385,  "dual_localization":            15,
        "cytoplasmic":                 5,   "endomembrane_resident":         4,
    },
    "dual_localization": {
        "classical_surface_receptor": 10,   "multipass_with_exposed_loops":  3,
        "gpi_anchored":               2,    "stable_complex_partner":        5,
        "stable_surface_attachment":  18,   "cell_state_induced":           22,
        "tissue_restricted_surface":  12,   "dual_localization":           175,
        "cytoplasmic":                 8,   "endomembrane_resident":        10,
    },
    "cytoplasmic": {
        "classical_surface_receptor":  5,   "multipass_with_exposed_loops":  2,
        "gpi_anchored":                1,   "stable_complex_partner":        2,
        "stable_surface_attachment":   8,   "cell_state_induced":           10,
        "tissue_restricted_surface":   4,   "dual_localization":             6,
        "cytoplasmic":               195,   "endomembrane_resident":        22,
    },
    "endomembrane_resident": {
        "classical_surface_receptor":  3,   "multipass_with_exposed_loops":  1,
        "gpi_anchored":                1,   "stable_complex_partner":        1,
        "stable_surface_attachment":  15,   "cell_state_induced":            8,
        "tissue_restricted_surface":   3,   "dual_localization":             5,
        "cytoplasmic":                18,   "endomembrane_resident":       145,
    },
}


def build_triage_vs_deep_dive_reason(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """MOCK PLACEHOLDER — long-form confusion-matrix counts for the
    triage-reason × deep-dive-reason figure. One row per non-zero
    cell with columns ``triage_reason``, ``deep_dive_reason``, ``count``.

    The figure pivots this into a 10×10 matrix at render time. Bundled
    as a TSV rather than re-declared as a dict in the mirror so the
    gist stays single-source. Mirrors the matching constant in
    ``scripts/triage_vs_deep_dive_reason.py``."""
    records = []
    for tr, row in _MOCK_TRIAGE_DD_COUNTS.items():
        for dd, count in row.items():
            records.append(
                {"triage_reason": tr, "deep_dive_reason": dd, "count": int(count)}
            )
    return pd.DataFrame(records)


# Synthesis parameters for evidence_corpus_vs_selected — duplicated
# verbatim from scripts/evidence_corpus_vs_selected.py so a fresh build
# regenerates the identical mock distribution.
_N_MOCK_EVIDENCE_GENES = 220
_EVIDENCE_RANDOM_SEED = 42


def build_evidence_corpus_vs_selected(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """MOCK PLACEHOLDER — synthesized per-gene (papers_found,
    papers_selected, verdict) tuples for the evidence-corpus figure.

    Joint shape mirrors the canonical generator at
    ``scripts/evidence_corpus_vs_selected.py``:

      • papers_found ~ Lognormal(μ=ln 234, σ=0.6), clipped to [25, 550]
      • selection rate decreases with log(found)
      • verdict assigned probabilistically from a latent quality
        score; bucketed into 4-grade evidence_grade enum
    """
    rng = np.random.default_rng(_EVIDENCE_RANDOM_SEED)
    n = _N_MOCK_EVIDENCE_GENES

    papers_found = np.clip(
        rng.lognormal(mean=np.log(234), sigma=0.6, size=n),
        25, 550,
    )

    base_rate = 0.12 * np.log(75) / np.log(papers_found)
    noise = rng.normal(0.0, 0.025, size=n)
    selection_rate = np.clip(base_rate + noise, 0.01, 0.30)
    papers_selected = np.clip(np.round(papers_found * selection_rate), 2, 50).astype(int)
    papers_found = np.round(papers_found).astype(int)

    quality = np.log1p(papers_selected) + 1.5 * selection_rate
    verdicts = np.empty(n, dtype=object)
    q_noise = rng.normal(0.0, 0.22, size=n)
    q = quality + q_noise
    verdicts[q >= 3.45] = "direct_multi_method"
    verdicts[(q >= 3.10) & (q < 3.45)] = "direct_single_method"
    verdicts[(q >= 2.75) & (q < 3.10)] = "supportive_but_indirect"
    verdicts[q < 2.75] = "weak"

    return pd.DataFrame({
        "papers_found": papers_found,
        "papers_selected": papers_selected,
        "verdict": verdicts,
    })


def build_surfaceome_deterministic_features_placeholder(
    src: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """MOCK-grouped per-gene deterministic features for Supp Fig 13.

    Pre-joins per_protein_features (Sonnet-positive subset) with DeepTMHMM
    canonical topology, an alt-isoform-topology-change flag, Schweke
    homo-oligomer state, and Ensembl-Compara mouse/cyno ortholog flags;
    assigns each gene to one of the three placeholder buckets the figure
    facets on. Mirrors ``scripts/surfaceome_deterministic_features_placeholder.py``
    ``load_data()`` exactly so the figure renders identically off the
    bundled single TSV.

    The three buckets are MOCKED from Sonnet verdicts for now (deep-dive
    hues are placeholders until the deep-dive runs over the surfaceome):
      • triage_yes               = Sonnet 'yes' (non-high confidence)
      • deep_dive_high_conf      = Sonnet 'yes' + high confidence
      • deep_dive_likely_surface = Sonnet 'contextual'
    """
    feats = pd.read_csv(
        ROOT / "data/analysis/db_vs_sonnet_inclusion/per_protein_features.tsv",
        sep="\t",
    )
    feats = feats[feats["sonnet_verdict"].isin(["yes", "contextual"])].copy()

    dt = pd.read_csv(
        ROOT / "data/processed/deeptmhmm/deeptmhmm_human_canonical.tsv", sep="\t",
    )
    dt_keep = ["uniprot_accession", "protein_length", "tm_helix_count",
               "has_signal_peptide", "signal_peptide_length",
               "n_term_extracellular", "c_term_extracellular"]
    feats = feats.merge(dt[dt_keep], on="uniprot_accession", how="left")

    iso = pd.read_csv(
        ROOT / "data/processed/deeptmhmm/deeptmhmm_human_isoforms.tsv", sep="\t",
    )
    iso["canonical_acc"] = iso["uniprot_accession"].str.split("-").str[0]
    iso_by_canon = iso.groupby("canonical_acc").agg(
        iso_n=("uniprot_accession", "count"),
        iso_tm_counts=("tm_helix_count", lambda x: set(x.dropna().astype(int))),
    ).reset_index().rename(columns={"canonical_acc": "uniprot_accession"})
    feats = feats.merge(iso_by_canon, on="uniprot_accession", how="left")

    def _alt_iso_diff_topology(row):
        if pd.isna(row.get("iso_n")) or row.get("iso_n", 0) == 0:
            return None
        canon_tm = row.get("tm_helix_count")
        if pd.isna(canon_tm):
            return None
        iso_tms = row.get("iso_tm_counts")
        if iso_tms is None or not isinstance(iso_tms, set):
            return 0
        return int(any(t != int(canon_tm) for t in iso_tms if not pd.isna(t)))

    feats["alt_iso_diff_topo"] = feats.apply(_alt_iso_diff_topology, axis=1)

    cmp = pd.read_csv(
        ROOT / "data/external/ensembl_compara_surfaceome_expressed"
             / "compara_mouse_cyno_one2one_highconf_by_gene.csv"
    )
    cmp_keep = cmp[["resolver_resolved_gene_symbol",
                    "mouse_has_one2one_high_confidence",
                    "cyno_has_one2one_high_confidence"]].rename(
        columns={"resolver_resolved_gene_symbol": "gene_symbol"})
    feats = feats.merge(cmp_keep, on="gene_symbol", how="left")

    def _group_of(row):
        if row["sonnet_verdict"] == "yes":
            if str(row.get("sonnet_confidence", "")).lower() == "high":
                return "deep_dive_high_conf"
            return "triage_yes"
        if row["sonnet_verdict"] == "contextual":
            return "deep_dive_likely_surface"
        return None

    feats["group"] = feats.apply(_group_of, axis=1)
    feats = feats.dropna(subset=["group"])

    # Emit only the columns the figure consumes — one tidy row per gene.
    cols = ["gene_symbol", "group", "tm_helix_count", "protein_length",
            "has_signal_peptide", "n_term_extracellular", "c_term_extracellular",
            "mouse_has_one2one_high_confidence", "cyno_has_one2one_high_confidence",
            "schweke_homomer", "alt_iso_diff_topo"]
    return feats[[c for c in cols if c in feats.columns]].reset_index(drop=True)


BUILDERS: dict[str, callable] = {
    "benchmark_cost_vs_accuracy":         build_cost_vs_accuracy,
    "db_correctness_by_class":            build_db_correctness_by_class,
    "db_correctness_overall":             build_db_correctness_overall,
    "db_vs_sonnet_whole_proteome":        build_db_vs_sonnet_whole_proteome,
    "ensemble_vs_best_db_vs_sonnet":      build_ensemble,
    "deep_dive_final_categories":         build_deep_dive_final_categories,
    "curator_vs_agent_reason":            build_curator_vs_agent_reason,
    "positive_control_db_coverage_bars":  build_positive_control_db_coverage_bars,
    "bench_topology_vs_universe":         build_bench_topology_vs_universe,
    "triage_vs_deep_dive_reason":         build_triage_vs_deep_dive_reason,
    "evidence_corpus_vs_selected":        build_evidence_corpus_vs_selected,
    "surfaceome_deterministic_features_placeholder":
        build_surfaceome_deterministic_features_placeholder,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help=f"output dir (default: {DEFAULT_OUT.relative_to(ROOT)})")
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    print("  loading canonical sources …")
    src = _load_sources()
    for slug, builder in BUILDERS.items():
        df = builder(src)
        out_path = args.out / f"{slug}.tsv"
        df.to_csv(out_path, sep="\t", index=False)
        size_kb = out_path.stat().st_size / 1024
        print(f"  wrote {out_path.relative_to(ROOT)}  ({len(df):>5} rows, {size_kb:>6.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
