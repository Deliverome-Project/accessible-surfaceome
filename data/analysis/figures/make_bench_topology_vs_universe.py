# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``bench_topology_vs_universe.{pdf,png}`` — SurfaceBench
topology composition vs the Sonnet 2-tier yes/contextual universe.

Side-by-side grouped barplot over 9 topology categories with two
hues:

  * **Sonnet 2-tier yes/contextual universe** — the genes the
    production pipeline calls accessible after the Sonnet+NCBI
    sweep plus the Sonnet+PubMed rescue lane. This is what the
    catalog *actually ships*, not the broader "any-DB-voted-yes"
    union.
  * **SurfaceBench** — the 147-protein hand-curated benchmark, of
    which 97 are members of the Sonnet 2-tier yes/contextual
    universe.

The figure surfaces the **bench enrichment bias**: the bench is
*not* a random topological sample. Three classes reach Bonferroni-
corrected significance (p < 0.05 after 9-test correction):
GPI-anchored (+14.5 pp), glycosylation-positive (+20.1 pp), and
multi-pass TM (-11.0 pp). Bench bars carry Wilson 95% binomial
confidence intervals to make the small-n classes read as noisier
than they would as bare bars.

SurfaceBench accuracy is therefore a *lower bound* on expected
full-proteome accuracy, not a representative point estimate.

Standalone — ``uv run make_bench_topology_vs_universe.py``.
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
BRANCH = "main"  # pin to a commit SHA at publication for immutable citation
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
# Single per-figure TSV: one row per gene in the Sonnet 2-tier
# yes/contextual universe with is_bench + 9 topology booleans
# denormalized in. Produced by scripts/build_figure_tsvs.py. Gist
# bundles this TSV next to the script; the figure reads only from
# the sibling — no other URLs.
_TSV = f"{BASE}/data/processed/figures/bench_topology_vs_universe.tsv"

# Published reproduction gist (embedded into output PNG Source /
# PDF Subject metadata — mirrors save_figure in _plotting_config.py).
# Filled at gist-creation time; the placeholder stays harmless until then.
GIST_URL = "https://gist.github.com/beccajcarlson/f724dd328f48566a354f0294109a7337"

# ──── Inline brand styling — sentinel: brand-style-v3 ────
BRAND_INK = "#1F1718"
BRAND_PALETTE = [
    "#BC3C4C",  # maroon-light
    "#3D6B60",  # teal-mid
    "#F4AA28",  # amber-bright
    "#8878C8",  # lavender-bright
    "#6E1428",  # maroon-dark
    "#7AAB9F",  # teal-light
]
BRAND_NEUTRAL = "#6F5D5A"
BRAND_GRID = "#E6DAD4"
COLOR_UNIVERSE = "#C7BDB6"   # light warm-grey — neutral reference
COLOR_BENCH = "#3D6B60"      # teal-mid — highlighted subset


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
        "font.size": 18, "axes.labelsize": 20, "axes.titlesize": 0,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": BRAND_GRID, "axes.labelcolor": BRAND_INK,
        "axes.facecolor": "none",
        "text.color": BRAND_INK,
        "grid.alpha": 0.35, "grid.linestyle": "-", "grid.linewidth": 0.7,
        "grid.color": BRAND_GRID,
        "xtick.labelsize": 14, "ytick.labelsize": 16,
        "xtick.color": BRAND_INK, "ytick.color": BRAND_INK,
        "legend.frameon": False, "legend.fontsize": 14,
        "patch.edgecolor": "none", "patch.linewidth": 0.0,
    })


# 9 categories — mirrors the topology_coverage_by_source 3x3 grid
# at data/analysis/figures/make_topology_coverage_by_source.py.
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


def _fetch_tsv(url: str) -> pd.DataFrame:
    """Bundled-only: the gist HEAD commit SHA is the SWHID for the
    whole reproduction unit (script + data + README), so we must
    never read a *different* TSV than what's bundled. Sibling-first
    (gist case); fall back to the in-repo TSV path (dev case). No
    network fetch — a missing sibling in a gist is a hard error."""
    sibling = Path(__file__).parent / Path(url).name
    if sibling.is_file():
        return pd.read_csv(sibling, sep="\t")
    local = Path(__file__).resolve().parents[3] / url[len(BASE) + 1:]
    if local.is_file():
        return pd.read_csv(local, sep="\t")
    raise FileNotFoundError(
        f"TSV not found at sibling ({sibling.name}) or local ({local}). "
        f"In a gist, the bundled TSV must sit next to this script."
    )


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


def _binomial_p_two_sided(n_pos: int, n: int, p_null: float) -> float:
    """Exact 2-tailed binomial test: under H0 n_pos ~ Binomial(n, p_null),
    return P(|deviation| >= observed). The standard recipe summed by
    SciPy: sum binomial PMF values whose mass <= the observed-point's
    mass. Reliable at small n (vs the normal approximation z-test) and
    no external dep — manual loop over n+1 outcomes."""
    if n == 0 or not (0.0 <= p_null <= 1.0):
        return 1.0
    from math import exp, lgamma, log
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
    # Sum all PMFs <= observed (the "method of small p-values")
    return sum(p for p in pmfs if p <= obs_pmf + 1e-12)


def _star(p: float) -> str:
    """APA-style p-value significance stars. Bonferroni-corrected
    inline via the n_tests multiplier in the caller (each test is
    one of 9 topology classes)."""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "ns"


def _compute_distribution(data: pd.DataFrame) -> tuple[
    list[float], list[float], list[tuple[float, float]],
    list[float], int, int,
]:
    """Per-class universe % + bench % + bench Wilson 95% CI half-widths
    + Bonferroni-corrected bench-vs-universe binomial p-values."""
    # Union TSV: universe = in_universe rows (4,426); bench = is_bench rows
    # (99 ground-truth yes/contextual benchmark genes, incl. 3 outside the
    # universe). See the canonical scripts/bench_topology_vs_universe.py.
    rows = data[data["in_universe"].astype(bool)]
    bench_rows = data[data["is_bench"].astype(bool)]
    n_universe = len(rows)
    n_bench = len(bench_rows)

    n_tests = len(FEATURES)  # Bonferroni denominator for 9 classes
    universe_pct: list[float] = []
    bench_pct: list[float] = []
    bench_ci: list[tuple[float, float]] = []
    bench_pvals_bonf: list[float] = []
    for col, _label in FEATURES:
        # Per-figure TSV stores topology flags as ints (1/0); blank/NaN
        # treated as negative (matches the canonical's _feature_positive
        # semantics for missing DeepTMHMM predictions).
        col_int = pd.to_numeric(rows[col], errors="coerce").fillna(0).astype(int)
        col_b = pd.to_numeric(bench_rows[col], errors="coerce").fillna(0).astype(int)
        n_u = int(col_int.sum())
        n_b = int(col_b.sum())
        p_universe = n_u / n_universe
        universe_pct.append(100.0 * p_universe)
        bench_pct.append(100.0 * n_b / n_bench)
        bench_ci.append(_wilson_95_ci(n_b, n_bench))
        # H0: bench n_pos ~ Binomial(n_bench, p_universe). 2-tailed
        # exact binomial test. Bonferroni-correct across n_tests
        # classes (cap at 1.0).
        p_raw = _binomial_p_two_sided(n_b, n_bench, p_universe)
        bench_pvals_bonf.append(min(1.0, p_raw * n_tests))
    return universe_pct, bench_pct, bench_ci, bench_pvals_bonf, n_universe, n_bench


def main() -> None:
    _apply_brand_style()
    data = _fetch_tsv(_TSV)
    univ, bench, ci, pvals, n_u, n_b = _compute_distribution(data)
    n = len(FEATURES)

    fig, ax = plt.subplots(figsize=(15, 8))
    width = 0.40
    x = np.arange(n)

    ax.bar(
        x - width / 2, univ, width=width, color=COLOR_UNIVERSE,
        edgecolor="none",
        label=f"Sonnet 2-tier yes/contextual  (n = {n_u:,})",
        zorder=3,
    )
    # CI on bench only — the universe is a population, not a sample,
    # so a CI on its percentage isn't meaningful.
    yerr = np.array(ci).T  # shape (2, n) — lower then upper
    ax.bar(
        x + width / 2, bench, width=width, color=COLOR_BENCH,
        edgecolor="none", label=f"SurfaceBench  (n = {n_b})",
        yerr=yerr, error_kw={"ecolor": BRAND_INK, "lw": 1.2, "capsize": 4},
        zorder=3,
    )

    # Delta-pp annotation + Bonferroni-corrected significance stars
    # above each pair. Bonferroni divides alpha across the 9 classes —
    # an honest correction since we're doing one test per class.
    for i, (u, b, (_lo, hi), p) in enumerate(zip(univ, bench, ci, pvals, strict=True)):
        delta = b - u
        sign = "+" if delta >= 0 else "−"
        y_text = max(u, b + hi) + 1.6
        star = _star(p)
        # Color/weight encode SIGNIFICANCE, not magnitude: a class that
        # clears the Bonferroni gate (star != "ns") is dark ink + bold;
        # a non-significant class is neutral gray + normal weight, so a
        # large-but-ns delta (e.g. a +11.8 pp shift at p=0.125) doesn't
        # read as "significant" the way a bold label would. Dark neutral
        # (not the bench color) so the annotations carry no red/highlight.
        significant = star != "ns"
        color = BRAND_INK if significant else BRAND_NEUTRAL
        weight = "bold" if significant else "normal"
        label = f"{sign}{abs(delta):.1f} pp"
        if star != "ns":
            label += f"  {star}"
        ax.text(
            i, y_text, label,
            ha="center", va="bottom",
            fontsize=12, color=color, fontweight=weight,
        )

    ax.set_xticks(x)
    ax.set_xticklabels([name for _, name in FEATURES])
    ax.set_ylabel("% of subset")
    ax.set_ylim(0, max(max(univ), max(bench)) + 12)
    ax.set_xlabel("")

    # Upper-LEFT: the left side of the plot is empty (GPI / 7TM bars are
    # short there), whereas the tall Glyc.-site bar + its "+20.5 pp ***"
    # label collides with an upper-right legend.
    ax.legend(
        loc="upper left", bbox_to_anchor=(0.01, 0.99),
        frameon=False, fontsize=14,
    )

    sns.despine(ax=ax, top=True, right=True)
    fig.tight_layout()

    out_pdf = Path("bench_topology_vs_universe.pdf")
    out_png = Path("bench_topology_vs_universe.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=600, metadata={"Source": GIST_URL})
    n_sig = sum(1 for p in pvals if p < 0.05)
    print(f"Wrote {out_pdf} + {out_png}  "
          f"(universe n={n_u:,}; bench n={n_b}; {n_sig}/9 classes significant)")


if __name__ == "__main__":
    main()
