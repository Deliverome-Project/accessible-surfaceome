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

Outputs (one per non-compliant figure today, written to
``data/processed/figures/<slug>.tsv``):
  • ``benchmark_cost_vs_accuracy.tsv``
  • ``db_correctness_by_class.tsv``
  • ``db_correctness_overall.tsv``
  • ``db_vs_sonnet_whole_proteome.tsv``
  • ``ensemble_vs_best_db_vs_sonnet.tsv``
  • ``deep_dive_final_categories.tsv`` — MOCK placeholder

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

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data/processed/figures"

BENCH_TSV       = ROOT / "data/eval/triage_benchmark_v1.tsv"
PREDS_TSV       = ROOT / "data/processed/triage_bench/mainbench_canonical_v2.tsv"
REPS_TSV        = ROOT / "data/processed/triage_bench/mainbench_replicates_v2.tsv"
OPT_CUTOFFS_TSV = ROOT / "data/processed/triage_bench/db_optimized_cutoffs.tsv"
CATALOG_TSV     = ROOT / "data/processed/catalog/whole_proteome_catalog.tsv"
FEATURES_TSV    = ROOT / "data/analysis/db_vs_sonnet_inclusion/per_protein_features.tsv"


def _load_sources() -> dict[str, pd.DataFrame]:
    return {
        "bench":    pd.read_csv(BENCH_TSV, sep="\t"),
        "preds":    pd.read_csv(PREDS_TSV, sep="\t"),
        "reps":     pd.read_csv(REPS_TSV, sep="\t"),
        "opt":      pd.read_csv(OPT_CUTOFFS_TSV, sep="\t"),
        "catalog":  pd.read_csv(CATALOG_TSV, sep="\t"),
        "features": pd.read_csv(FEATURES_TSV, sep="\t"),
    }


def _optimized_membership(df: pd.DataFrame, opt: pd.DataFrame, acc_col: str) -> pd.DataFrame:
    """Return a copy of ``df`` with optimized-cutoff DB membership +
    ``n_sources_optimized`` (the 5-DB vote under the SurfaceBench-tuned
    cutoffs: UniProt and CSPA use their recalibrated rule; GO CC, HPA,
    and SURFY use their unchanged ``*_surface_flag``). This is the
    downstream-canonical DB membership the accuracy figures already use;
    F3 (zero-DB rescues) and S9 (per-source coverage) join it so they
    stop using the pre-recalibration initial flags."""
    out = df.copy()
    uniprot_opt = set(opt.loc[opt["uniprot_optimized"] == 1, "accession"].astype(str))
    cspa_opt    = set(opt.loc[opt["cspa_optimized"]    == 1, "accession"].astype(str))
    acc = out[acc_col].astype(str)
    out["uniprot_optimized"] = acc.isin(uniprot_opt).astype(int)
    out["cspa_optimized"]    = acc.isin(cspa_opt).astype(int)
    return out


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


def build_zero_db_rescues(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Figure 3 — zero-DB rescues, defined under the OPTIMIZED cutoffs
    (consistent with the accuracy figures). Per genome-wide gene: the
    Sonnet verdict + reason, the 5 per-DB flags with UniProt/CSPA on
    their recalibrated rule, and ``n_sources_optimized`` so the figure
    selects the zero-DB slice as ``n_sources_optimized == 0`` rather
    than the pre-recalibration ``n_sources_surface == 0``."""
    df = _optimized_membership(src["catalog"], src["opt"], "uniprot_acc")
    # n_sources_optimized = the 5-DB vote under optimized cutoffs:
    # UniProt + CSPA recalibrated, GO/HPA/SURFY unchanged surface_flag.
    df["n_sources_optimized"] = (
        df["uniprot_optimized"].fillna(0).astype(int)
        + df["cspa_optimized"].fillna(0).astype(int)
        + df["go_surface_flag"].fillna(0).astype(int)
        + df["hpa_surface_flag"].fillna(0).astype(int)
        + df["surfy_surface_flag"].fillna(0).astype(int)
    )
    return df.drop(columns=["universe_version"], errors="ignore")


def build_topology_coverage_by_source(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Supp S9 — per-source topology coverage under the OPTIMIZED cutoffs.
    Starts from the per-protein-features table (topology classes + the
    initial ``src_*`` source flags) and joins UniProt/CSPA optimized
    membership so the figure renders UniProt and CSPA at their
    recalibrated cutoffs (GO/HPA/SURFY/Sonnet unchanged). Also carries
    ``n_sources_optimized`` so the Sonnet-only (zero-DB) subset is
    defined against the optimized DB vote, matching Figure 3."""
    feat = _optimized_membership(src["features"], src["opt"], "uniprot_accession")
    # GO/HPA/SURFY keep their initial src flags (not recalibrated).
    feat["n_sources_optimized"] = (
        feat["uniprot_optimized"].fillna(0).astype(int)
        + feat["cspa_optimized"].fillna(0).astype(int)
        + feat["src_go"].fillna(0).astype(int)
        + feat["src_hpa"].fillna(0).astype(int)
        + feat["src_surfy"].fillna(0).astype(int)
    )
    return feat


def build_bench_topology_vs_universe(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """bench_topology_vs_universe — topology composition of the SurfaceBench
    benchmark vs the Sonnet 2-tier yes/contextual universe. The TSV is the UNION
    of the two cohorts with ``in_universe`` + ``is_bench`` flags so the figure
    plots each cohort's per-class topology:
      • universe (in_universe=True) — sonnet/pubmed yes/contextual (~4,426).
      • bench    (is_bench=True)    — the benchmark's GROUND-TRUTH yes/contextual
        genes (99), keyed by ``ground_truth_verdict`` — NOT conditioned on
        Sonnet's call. The 3 ground-truth-yc genes Sonnet miscalled (C3, SRC,
        TGOLN2) sit outside the universe but stay in the bench cohort, so they
        ride the union. (The old "bench acc in universe" tag both dropped these
        3 and let Sonnet false-positives on ground-truth-no genes leak in.)
    NOT cutoff-dependent — scores no DB membership."""
    yc = {"yes", "contextual"}
    feat = src["features"]
    in_universe = feat["sonnet_verdict"].isin(yc) | feat["pubmed_verdict"].isin(yc)
    bench = src["bench"]
    gt_col = "ground_truth_verdict" if "ground_truth_verdict" in bench.columns else "verdict"
    bench_yc = set(
        bench.loc[
            bench[gt_col].astype(str).str.strip().str.lower().isin(yc), "uniprot_acc"
        ].dropna().astype(str)
    )
    is_bench = feat["uniprot_accession"].astype(str).isin(bench_yc)
    mask = in_universe | is_bench
    keep = feat[mask]
    feature_cols = [
        "topo_gpi_anchored", "topo_gpcr_7tm", "topo_multi_pass_tm",
        "topo_single_pass_tm", "topo_signal_only_secreted",
        "topo_inner_leaflet_lipidated", "topo_no_tm_no_signal",
        "up_has_glyc", "deeptm_TM_NO_SP",
    ]

    def _int01(col: pd.Series) -> pd.Series:
        return col.map(lambda v: 1 if str(v).strip() in ("1", "1.0") else 0)

    out = pd.DataFrame({
        "gene_symbol": keep["gene_symbol"].to_numpy(),
        "uniprot_acc": keep["uniprot_accession"].to_numpy(),
        "in_universe": in_universe[mask].to_numpy(),
        "is_bench": is_bench[mask].to_numpy(),
    })
    for col in feature_cols:
        out[col] = _int01(keep[col]).to_numpy()
    return out.sort_values("gene_symbol", kind="stable", ignore_index=True)


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


_DB_FLAG_COLS = [
    "uniprot_surface_flag", "go_surface_flag", "hpa_surface_flag",
    "surfy_surface_flag", "cspa_surface_flag",
]


def build_db_overlap_venn(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Figure 1 — the five databases' surface-membership overlap under
    each source's INITIAL (pre-recalibration) cutoff.

    This is a databases-overlap figure, NOT a whole-proteome view, so it
    gets its own minimal per-figure TSV rather than reusing the big
    whole_proteome_catalog.tsv. Columns: stable identifiers + the five
    initial ``*_surface_flag`` columns. Restricted to the union (rows
    where at least one source flags surface), since proteins no source
    calls aren't part of any Venn region. Deliberately DROPS:
      • ``universe_version`` — internal provenance, too technical for a
        figure-input TSV (per the figure-input-TSV conventions).
      • the optimized-cutoff columns + ``n_sources_surface`` — Figure 1
        is about the native/initial source definitions only.
      • ``sonnet_verdict`` / ``sonnet_reason`` / ``verdict_source`` —
        the triage agent isn't part of this DB-overlap figure.
    """
    cat = src["catalog"]
    keep_ids = ["hgnc_id", "hgnc_symbol", "uniprot_acc", "ensembl_gene", "ncbi_gene_id"]
    cols = [c for c in keep_ids if c in cat.columns] + _DB_FLAG_COLS
    out = cat[cols].copy()
    # Union members only: at least one source flags surface.
    flag_any = out[_DB_FLAG_COLS].apply(
        lambda s: s.astype(str).isin(["1", "1.0"]).astype(int)
    ).sum(axis=1)
    out = out[flag_any > 0].reset_index(drop=True)
    return out


BUILDERS: dict[str, callable] = {
    "db_overlap_venn":               build_db_overlap_venn,
    "benchmark_cost_vs_accuracy":    build_cost_vs_accuracy,
    "db_correctness_by_class":       build_db_correctness_by_class,
    "db_correctness_overall":        build_db_correctness_overall,
    "db_vs_sonnet_whole_proteome":   build_db_vs_sonnet_whole_proteome,
    "ensemble_vs_best_db_vs_sonnet": build_ensemble,
    "deep_dive_final_categories":    build_deep_dive_final_categories,
    "curator_vs_agent_reason":       build_curator_vs_agent_reason,
    "zero_db_rescues_by_triage":     build_zero_db_rescues,
    "topology_coverage_by_source":   build_topology_coverage_by_source,
    "bench_topology_vs_universe":    build_bench_topology_vs_universe,
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
