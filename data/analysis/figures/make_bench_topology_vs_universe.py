# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``bench_topology_vs_universe.{pdf,png}`` from the public repo.

Side-by-side grouped barplot over the same 9 topology categories the
``topology_coverage_by_source`` 3×3 figure breaks out, with two hues:

  • **Sonnet 2-tier yes/contextual universe** (n=4,426) — the genes
    the production pipeline calls accessible after the Sonnet+NCBI
    sweep plus the Sonnet+PubMed rescue lane. This is what the catalog
    *actually ships*, NOT the broader "any source voted yes" union.
  • **SurfaceBench** (n=146 of 147 that join into the features TSV) —
    the 147-protein hand-curated benchmark deliberately enriched for
    cases where the five gating databases disagree

Surfaces the **bench enrichment bias**: DB-confusing classes
(GPI-anchored, single-pass TM with ambiguous orientation, inner-leaflet
lipidated, glycosylation-positive) are over-represented; the
DBs-agree-easily class (multi-pass TM) is under-represented.

Bench bars carry Wilson 95% binomial confidence intervals; significance
stars are 2-tailed exact binomial test of bench vs universe proportion,
Bonferroni-corrected across 9 classes.

Visual styling matches the in-repo `_plotting_config` (Deliverome
categorical palette + Manrope-when-available). Inlined so the gist
runs standalone — ``uv run make_bench_topology_vs_universe.py``.
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"

# Published reproduction gist — embedded into output PNG Source / PDF
# Subject metadata (mirrors save_figure in _plotting_config.py).
GIST_URL = "https://gist.github.com/beccajcarlson/676b9e5ab9112191a96560ca6fdb17d6"

# Single bundled per-figure TSV — sibling-first per PR #86; clone the gist
# or run from the in-repo dev tree so this resolves next to this script.
# One row per protein in the Sonnet 2-tier yes/contextual universe
# (~4,426 of the 6,589-row per_protein_features TSV), carrying all 9
# topology flags + an ``is_bench`` boolean marking the 146 of 147 bench
# members that join in by uniprot_accession. The figure derives both
# bars (universe + bench) from this single TSV.
DATA_TSV = f"{BASE}/data/processed/figures/bench_topology_vs_universe.tsv"

# ──── Inline brand styling — sentinel: brand-style-v3 ────
# Mirrors src/accessible_surfaceome/audit/_plotting_config.py so the gist
# stays self-contained (no in-repo imports — Substack readers run it
# standalone). Kept in sync via tests/test_figure_gists_styling.py.
BRAND_PALETTE = [
    "#BC3C4C",  # maroon-light
    "#3D6B60",  # teal-mid
    "#F4AA28",  # amber-bright
    "#8878C8",  # lavender-bright
    "#6E1428",  # maroon-dark
    "#7AAB9F",  # teal-light
]
BRAND_INK = "#1F1718"
BRAND_NEUTRAL = "#6F5D5A"
BRAND_GRID = "#E6DAD4"


def _register_brand_fonts() -> None:
    candidates = [
        Path(__file__).resolve().parents[3] / "assets" / "fonts",
        Path.cwd() / "assets" / "fonts",
    ]
    for fonts_dir in candidates:
        if fonts_dir.is_dir():
            for path in sorted(list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf"))):
                try:
                    fm.fontManager.addfont(str(path))
                except Exception:  # noqa: BLE001
                    continue
            return


def _apply_brand_style() -> None:
    """Inline equivalent of `setup_plotting_style`. Sentinel: brand-style-v3."""
    _register_brand_fonts()
    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=1.0)
    plt.rcParams.update({
        "savefig.dpi": 600,
        "savefig.bbox": "tight",
        "figure.facecolor": "none",
        "savefig.facecolor": "none",
        "font.family": "sans-serif",
        "font.sans-serif": ["Manrope", "Outfit", "DejaVu Sans", "Liberation Sans", "Arial"],
        "font.weight": "medium",
        "font.size": 18,
        "axes.labelsize": 20,
        "axes.labelweight": "medium",
        "axes.titlesize": 0,
        "axes.titlepad": 0,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "axes.edgecolor": BRAND_GRID,
        "axes.labelcolor": BRAND_INK,
        "axes.facecolor": "none",
        "text.color": BRAND_INK,
        "grid.alpha": 0.35,
        "grid.linestyle": "-",
        "grid.linewidth": 0.7,
        "grid.color": BRAND_GRID,
        "xtick.labelsize": 14,
        "ytick.labelsize": 16,
        "xtick.color": BRAND_INK,
        "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "legend.fontsize": 14,
        "patch.edgecolor": "none",
        "patch.linewidth": 0.0,
    })


# 9 categories — mirrors the topology_coverage_by_source 3×3 grid.
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


def _fetch_tsv(url: str) -> pd.DataFrame:
    """Read the bundled sibling TSV next to this script.

    Per the PR #86 bundled-only convention: each gist is a self-contained
    reproduction unit (script + bundled TSVs) cited as ``swh:1:rev:<sha>``
    of the gist HEAD commit. A missing sibling is a hard error — the
    raw.githubusercontent.com fallback was removed so the gist can't
    silently render against a different TSV than what it bundled.

    Run from a clone of the gist (or with the bundled TSV next to this
    script in the in-repo dev tree) and it Just Works.
    """
    sibling = Path(__file__).parent / Path(url).name
    if sibling.is_file():
        return pd.read_csv(sibling, sep="\t")
    # In-repo dev fallback — resolve the URL path relative to the repo
    # root so canonical-mirror parity tests pass without re-bundling.
    if url.startswith(BASE + "/"):
        local = Path(__file__).resolve().parents[3] / url[len(BASE) + 1:]
        if local.is_file():
            return pd.read_csv(local, sep="\t")
    raise FileNotFoundError(
        f"Bundled TSV not found next to script: {sibling}. "
        f"This script reads only the bundled sibling — clone the gist "
        f"or run the canonical generator from the repo's in-repo dev tree."
    )


def _feature_positive(row: dict, col: str) -> bool:
    """per_protein_features.tsv writes booleans as ``'1.0'`` / ``'0.0'``
    strings, with blanks for the ~2,578 rows that lack a DeepTMHMM
    prediction. Match both string forms; treat blank as negative."""
    val = row.get(col, "")
    return val in {"1", "1.0"} or val == 1 or val == 1.0


def _wilson_95_ci(n_pos: int, n: int) -> tuple[float, float]:
    """Wilson 95% confidence interval for a binomial proportion.
    Reliable down to single-digit counts. Returns half-widths (low,
    high) in percentage points."""
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


def _binomial_p_two_sided(n_pos: int, n: int, p_null: float) -> float:
    """Exact 2-tailed binomial test. No SciPy — log-space PMF loop."""
    if n == 0 or not (0.0 <= p_null <= 1.0):
        return 1.0
    from math import lgamma, log, exp
    log_p = log(p_null) if p_null > 0 else float("-inf")
    log_q = log(1 - p_null) if p_null < 1 else float("-inf")
    pmfs = []
    for k in range(n + 1):
        log_binom = lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1)
        if p_null == 0:
            pmf = 1.0 if k == 0 else 0.0
        elif p_null == 1:
            pmf = 1.0 if k == n else 0.0
        else:
            pmf = exp(log_binom + k * log_p + (n - k) * log_q)
        pmfs.append(pmf)
    obs_pmf = pmfs[n_pos]
    return sum(p for p in pmfs if p <= obs_pmf + 1e-12)


def _star(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "ns"


def _compute_distribution() -> tuple[
    list[tuple[str, str]], list[float], list[float], list[tuple[float, float]],
    list[float], int, int,
]:
    rows_df = _fetch_tsv(DATA_TSV)
    rows = rows_df.to_dict(orient="records")
    # The pre-joined TSV already has is_bench=1 marking the 146 bench
    # members; the universe is every row (pre-filtered to Sonnet 2-tier
    # yes/contextual at build time).
    bench_rows = [r for r in rows if str(r.get("is_bench", "0")) in {"1", "1.0"}]
    n_universe = len(rows)
    n_bench = len(bench_rows)

    n_tests = len(FEATURES)  # Bonferroni denominator for 9 classes
    universe_pct: list[float] = []
    bench_pct: list[float] = []
    bench_ci: list[tuple[float, float]] = []
    bench_pvals_bonf: list[float] = []
    for col, _ in FEATURES:
        n_u = sum(1 for r in rows if _feature_positive(r, col))
        n_b = sum(1 for r in bench_rows if _feature_positive(r, col))
        p_universe = n_u / n_universe
        universe_pct.append(100.0 * p_universe)
        bench_pct.append(100.0 * n_b / n_bench)
        bench_ci.append(_wilson_95_ci(n_b, n_bench))
        p_raw = _binomial_p_two_sided(n_b, n_bench, p_universe)
        bench_pvals_bonf.append(min(1.0, p_raw * n_tests))
    return (
        FEATURES, universe_pct, bench_pct, bench_ci,
        bench_pvals_bonf, n_universe, n_bench,
    )


def main() -> None:
    _apply_brand_style()
    feats, univ, bench, ci, pvals, n_u, n_b = _compute_distribution()
    n = len(feats)

    fig, ax = plt.subplots(figsize=(15, 8))
    width = 0.40
    x = np.arange(n)

    ax.bar(
        x - width / 2, univ, width=width, color=COLOR_UNIVERSE,
        edgecolor="none",
        label=f"Sonnet 2-tier yes/contextual  (n = {n_u:,})",
        zorder=3,
    )
    yerr = np.array(ci).T  # shape (2, n)
    ax.bar(
        x + width / 2, bench, width=width, color=COLOR_BENCH,
        edgecolor="none", label=f"SurfaceBench  (n = {n_b})",
        yerr=yerr, error_kw={"ecolor": "#1F1718", "lw": 1.2, "capsize": 4},
        zorder=3,
    )

    # Δ-pp annotation + Bonferroni-corrected significance stars.
    for i, (u, b, (_, hi), p) in enumerate(zip(univ, bench, ci, pvals, strict=True)):
        delta = b - u
        sign = "+" if delta >= 0 else "−"
        color = "#1F1718" if abs(delta) < 5 else COLOR_BENCH
        weight = "normal" if abs(delta) < 5 else "bold"
        y_text = max(u, b + hi) + 1.6
        star = _star(p)
        label = f"{sign}{abs(delta):.1f} pp"
        if star != "ns":
            label += f"  {star}"
        ax.text(
            i, y_text, label,
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
        "Error bars: Wilson 95% binomial CI. "
        "Significance: 2-tailed exact binomial test of bench vs universe proportion, "
        "Bonferroni-corrected across 9 classes (* p<0.05, ** p<0.01, *** p<0.001).",
        ha="center", va="top", fontsize=11, style="italic", color=BRAND_NEUTRAL,
        wrap=True,
    )

    sns.despine(ax=ax, top=True, right=True)
    fig.tight_layout()

    out_pdf = Path("bench_topology_vs_universe.pdf")
    out_png = Path("bench_topology_vs_universe.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=600, metadata={"Source": GIST_URL})
    print(f"Wrote {out_pdf} + {out_png}  (universe n={n_u:,}, bench n={n_b})")


if __name__ == "__main__":
    main()
