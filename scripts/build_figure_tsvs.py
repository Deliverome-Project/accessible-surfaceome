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


BUILDERS: dict[str, callable] = {
    "benchmark_cost_vs_accuracy":    build_cost_vs_accuracy,
    "db_correctness_by_class":       build_db_correctness_by_class,
    "db_correctness_overall":        build_db_correctness_overall,
    "db_vs_sonnet_whole_proteome":   build_db_vs_sonnet_whole_proteome,
    "ensemble_vs_best_db_vs_sonnet": build_ensemble,
    "deep_dive_final_categories":    build_deep_dive_final_categories,
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
