"""SurfaceBench topology distribution vs the full any-yes universe.

Side-by-side grouped barplot over the same 9 topology categories the
``topology_coverage_by_source`` 3×3 figure breaks out, with two hues:

  • **any-yes universe** (n=6,588) — the full "≥1 source voted yes"
    cohort the per-protein-features TSV materialises
  • **SurfaceBench** (n=146 of 147 that join into the features TSV) —
    the 147-protein hand-curated benchmark deliberately enriched for
    cases where the five gating databases disagree

The figure surfaces the **bench enrichment bias** the methods section
flags: the bench is *not* a random topological sample of the surfaceome.
DB-confusing classes (GPI-anchored, single-pass TM with ambiguous
orientation, inner-leaflet lipidated, glycosylation-positive) are
over-represented; the DBs-agree-easily class (multi-pass TM) is
under-represented. SurfaceBench accuracy is therefore a *lower bound*
on expected full-proteome accuracy, not a representative point estimate.

Bench bars carry Wilson 95% binomial confidence intervals to make the
small-n classes (Likely secreted n=4, No-TM/no-signal n=6) read as
noisier than they would as bare bars.

Run:
    uv run python scripts/bench_topology_vs_universe.py
"""
from __future__ import annotations

import csv
import io
import math
import urllib.request
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import (
    COLORS,
    save_figure,
    setup_plotting_style,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data/analysis/figures"
SLUG = "bench_topology_vs_universe"

BENCH_TSV = ROOT / "data/eval/triage_benchmark_v1.tsv"
FEATURES_URL = (
    "https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/"
    "main/data/analysis/db_vs_sonnet_inclusion/per_protein_features.tsv"
)

# 9 categories — mirrors the topology_coverage_by_source 3×3 grid in
# data/analysis/figures/make_topology_coverage_by_source.py.
FEATURES: list[tuple[str, str]] = [
    ("topo_gpi_anchored",            "GPI-\nanchored"),
    ("topo_gpcr_7tm",                "7TM\nGPCR"),
    ("topo_multi_pass_tm",           "Multi-pass\nTM"),
    ("topo_single_pass_tm",          "Single-pass\nTM"),
    ("topo_signal_only_secreted",    "Likely\nsecreted"),
    ("topo_inner_leaflet_lipidated", "Inner-leaflet\nlipidated"),
    ("topo_no_tm_no_signal",         "No TM /\nno signal"),
    ("up_has_glyc",                  "Glyc.\nsite"),
    ("deeptm_TM_NO_SP",              "TM w/o\nSP"),
]

COLOR_UNIVERSE = "#3D6B60"   # teal-mid — neutral reference
COLOR_BENCH = "#BC3C4C"      # maroon-light — highlighted subset


def _feature_positive(row: dict, col: str) -> bool:
    """The per_protein_features.tsv writes booleans as ``'1.0'`` /
    ``'0.0'`` strings, with blanks for the ~2,578 rows that lack a
    DeepTMHMM prediction. Match both string forms; treat blank as
    negative for the % calculation (consistent with the existing
    topology_coverage_by_source semantics)."""
    return row.get(col, "") in {"1", "1.0"}


def _wilson_95_ci(n_pos: int, n: int) -> tuple[float, float]:
    """Wilson 95% confidence interval for a binomial proportion.
    Reliable down to single-digit counts, unlike the Wald interval.
    Returns half-widths (low, high) in percentage points."""
    if n == 0:
        return (0.0, 0.0)
    z = 1.96
    p = n_pos / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4 * n * n)) / denom
    low = max(0.0, center - half)
    high = min(1.0, center + half)
    return (100 * (p - low), 100 * (high - p))


def _fetch_universe() -> list[dict]:
    print(f"  fetching {FEATURES_URL} …")
    text = urllib.request.urlopen(FEATURES_URL, timeout=60).read().decode()
    rows = list(csv.DictReader(io.StringIO(text), delimiter="\t"))
    print(f"    {len(rows):,} rows")
    return rows


def _load_bench_accs() -> set[str]:
    accs: set[str] = set()
    with open(BENCH_TSV) as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r.get("uniprot_acc"):
                accs.add(r["uniprot_acc"])
    return accs


def _compute_distribution() -> tuple[
    list[tuple[str, str]], list[float], list[float], list[tuple[float, float]],
    int, int,
]:
    rows = _fetch_universe()
    bench_accs = _load_bench_accs()
    bench_rows = [r for r in rows if r.get("uniprot_accession") in bench_accs]
    n_universe = len(rows)
    n_bench = len(bench_rows)

    universe_pct: list[float] = []
    bench_pct: list[float] = []
    bench_ci: list[tuple[float, float]] = []
    for col, _ in FEATURES:
        n_u = sum(1 for r in rows if _feature_positive(r, col))
        n_b = sum(1 for r in bench_rows if _feature_positive(r, col))
        universe_pct.append(100.0 * n_u / n_universe)
        bench_pct.append(100.0 * n_b / n_bench)
        bench_ci.append(_wilson_95_ci(n_b, n_bench))
    return FEATURES, universe_pct, bench_pct, bench_ci, n_universe, n_bench


def make_plot() -> tuple[plt.Figure, plt.Axes]:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    plt.rcParams.update({
        "font.size": 18, "axes.labelsize": 20, "axes.titlesize": 0,
        "xtick.labelsize": 14, "ytick.labelsize": 16, "legend.fontsize": 14,
    })
    feats, univ, bench, ci, n_u, n_b = _compute_distribution()
    n = len(feats)

    fig, ax = plt.subplots(figsize=(15, 8))
    width = 0.40
    x = np.arange(n)

    ax.bar(
        x - width / 2, univ, width=width, color=COLOR_UNIVERSE,
        edgecolor="none", label=f"any-yes universe  (n = {n_u:,})",
        zorder=3,
    )
    # CI on bench only — the universe is a population, not a sample,
    # so a CI on its percentage isn't meaningful.
    yerr = np.array(ci).T  # shape (2, n) → lower then upper
    ax.bar(
        x + width / 2, bench, width=width, color=COLOR_BENCH,
        edgecolor="none", label=f"SurfaceBench  (n = {n_b})",
        yerr=yerr, error_kw={"ecolor": "#1F1718", "lw": 1.2, "capsize": 4},
        zorder=3,
    )

    # Δ-pp annotation above each pair (with bench bar's upper CI for
    # vertical clearance).
    for i, (u, b, (_, hi)) in enumerate(zip(univ, bench, ci, strict=True)):
        delta = b - u
        sign = "+" if delta >= 0 else "−"
        color = "#1F1718" if abs(delta) < 5 else COLOR_BENCH
        weight = "normal" if abs(delta) < 5 else "bold"
        y_text = max(u, b + hi) + 1.6
        ax.text(
            i, y_text, f"{sign}{abs(delta):.1f} pp",
            ha="center", va="bottom",
            fontsize=12, color=color, fontweight=weight,
        )

    ax.set_xticks(x)
    ax.set_xticklabels([name for _, name in feats])
    ax.set_ylabel("% of subset")
    ax.set_ylim(0, max(max(univ), max(bench)) + 12)
    ax.set_xlabel("")

    ax.legend(
        loc="upper right", bbox_to_anchor=(0.99, 0.99),
        frameon=False, fontsize=14,
    )

    fig.text(
        0.5, -0.02,
        "Bench is selected for DB disagreement and is NOT a random topological sample: "
        "GPI-anchored / lipidated / single-pass classes are over-represented (DBs disagree on these); "
        "multi-pass TM is under-represented (DBs agree on these). "
        "Bench-accuracy is therefore a lower bound on full-universe accuracy. "
        "Error bars: Wilson 95% binomial CI.",
        ha="center", va="top", fontsize=11, style="italic", color=COLORS["neutral"],
        wrap=True,
    )

    sns.despine(ax=ax, top=True, right=True)
    fig.tight_layout()
    return fig, ax


def main() -> None:
    fig, _ = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"))


if __name__ == "__main__":
    main()
