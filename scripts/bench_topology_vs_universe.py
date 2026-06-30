"""SurfaceBench topology distribution vs Sonnet 2-tier yes/contextual.

Side-by-side grouped barplot over the same 9 topology categories the
``topology_coverage_by_source`` 3×3 figure breaks out, with two hues:

  • **Sonnet 2-tier yes/contextual universe** (n=4,426) — the genes
    the production pipeline calls accessible after the
    Sonnet+NCBI sweep plus the Sonnet+PubMed rescue lane
    (NCBI=no → PubMed=yes/contextual flips, ~177 genes recovered).
    This is what the catalog *actually ships*, NOT the full
    "any-DB-voted-yes" union the topology figure also breaks out.
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

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import (
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


def _binomial_p_two_sided(n_pos: int, n: int, p_null: float) -> float:
    """Exact 2-tailed binomial test: under H₀ n_pos ~ Binomial(n, p_null),
    return P(|deviation| >= observed). The standard recipe summed by
    SciPy: sum binomial PMF values whose mass <= the observed-point's
    mass. Reliable at small n (vs the normal approximation z-test) and
    no external dep — manual loop over n+1 outcomes."""
    if n == 0 or not (0.0 <= p_null <= 1.0):
        return 1.0
    # Compute binomial PMF for k=0..n
    # P(K=k) = C(n,k) * p^k * (1-p)^(n-k)
    # Build PMF via log-space to avoid overflow at large n
    from math import lgamma, log, exp
    log_p = log(p_null) if p_null > 0 else float("-inf")
    log_q = log(1 - p_null) if p_null < 1 else float("-inf")
    pmfs = []
    for k in range(n + 1):
        log_binom = lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1)
        # Edge cases: p_null in {0, 1}
        if p_null == 0:
            pmf = 1.0 if k == 0 else 0.0
        elif p_null == 1:
            pmf = 1.0 if k == n else 0.0
        else:
            pmf = exp(log_binom + k * log_p + (n - k) * log_q)
        pmfs.append(pmf)
    obs_pmf = pmfs[n_pos]
    # Sum all PMFs <= observed (the standard "method of small p-values")
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


def _is_sonnet_2tier_yc(r: dict) -> bool:
    """Sonnet 2-tier yes/contextual: NCBI sweep verdict ∈ {yes,
    contextual} OR (NCBI=no AND PubMed-rescue verdict ∈ {yes,
    contextual}). This is what the catalog actually ships as the
    "accessible surfaceome" — the 177 PubMed-rescue flips that
    promote NCBI's no-calls to yes/contextual when a second pass
    with PubMed retrieval finds supporting evidence."""
    ncbi = (r.get("sonnet_verdict") or "").strip().lower()
    if ncbi in ("yes", "contextual"):
        return True
    pubmed = (r.get("pubmed_verdict") or "").strip().lower()
    return pubmed in ("yes", "contextual")


def _compute_distribution() -> tuple[
    list[tuple[str, str]], list[float], list[float], list[tuple[float, float]],
    list[float], int, int,
]:
    all_rows = _fetch_universe()
    # Filter to Sonnet 2-tier yes/contextual rather than the broader
    # "any source voted yes" union the per-protein-features TSV
    # materialises. This is the catalog's actual published set.
    rows = [r for r in all_rows if _is_sonnet_2tier_yc(r)]
    bench_accs = _load_bench_accs()
    bench_rows = [r for r in rows if r.get("uniprot_accession") in bench_accs]
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
        # H₀: bench n_pos ~ Binomial(n_bench, p_universe). 2-tailed
        # exact binomial test. Bonferroni-correct across n_tests
        # classes (cap at 1.0).
        p_raw = _binomial_p_two_sided(n_b, n_bench, p_universe)
        bench_pvals_bonf.append(min(1.0, p_raw * n_tests))
    return (
        FEATURES, universe_pct, bench_pct, bench_ci,
        bench_pvals_bonf, n_universe, n_bench,
    )


def make_plot() -> tuple[plt.Figure, plt.Axes]:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    plt.rcParams.update({
        "font.size": 18, "axes.labelsize": 20, "axes.titlesize": 0,
        "xtick.labelsize": 14, "ytick.labelsize": 16, "legend.fontsize": 14,
    })
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
    # CI on bench only — the universe is a population, not a sample,
    # so a CI on its percentage isn't meaningful.
    yerr = np.array(ci).T  # shape (2, n) → lower then upper
    ax.bar(
        x + width / 2, bench, width=width, color=COLOR_BENCH,
        edgecolor="none", label=f"SurfaceBench  (n = {n_b})",
        yerr=yerr, error_kw={"ecolor": "#1F1718", "lw": 1.2, "capsize": 4},
        zorder=3,
    )

    # Δ-pp annotation + Bonferroni-corrected significance stars
    # above each pair. Bonferroni divides α across the 9 classes —
    # an honest correction since we're doing one test per class.
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

    sns.despine(ax=ax, top=True, right=True)
    fig.tight_layout()
    return fig, ax


def _write_caption(
    n_universe: int, n_bench: int, pvals_bonf: list[float],
    feats: list[tuple[str, str]], universe_pct: list[float], bench_pct: list[float],
) -> str:
    """Build a numbers-checked caption draft from the computed values
    and return it as a string. ``main`` prints this to the console as
    a convenience; it is NOT written to disk. The authoritative
    manuscript caption is the hand-verified
    ``bench_topology_vs_universe.caption.md`` (de-jargoned + accuracy-
    checked), which a re-render must never overwrite."""
    n_sig = sum(1 for p in pvals_bonf if p < 0.05)
    # Top 3 over- and under-represented classes for the caption body
    deltas = sorted(
        ((name, b - u, p) for (_, name), u, b, p in zip(feats, universe_pct, bench_pct, pvals_bonf, strict=True)),
        key=lambda t: t[1], reverse=True,
    )
    # Use the full APA star ramp (_star), NOT a single '*' — a class at
    # p < 0.001 must read '***'. And only surface classes that actually
    # reach significance, so the auto-text doesn't headline a
    # non-significant top-delta class.
    over = [f"{n.replace(chr(10), ' ')} (+{d:.1f} pp {_star(p)})"
            for n, d, p in deltas[:3] if d > 0 and p < 0.05]
    under = [f"{n.replace(chr(10), ' ')} ({d:+.1f} pp {_star(p)})"
             for n, d, p in deltas[-3:] if d < 0 and p < 0.05]

    caption = (
        f"**Figure caption.** Topology composition of SurfaceBench "
        f"(n = {n_bench} of 147 that join into the per-protein features TSV) "
        f"compared against the Sonnet 2-tier yes/contextual universe "
        f"(n = {n_universe:,}), the genes the production pipeline ships "
        f"as accessible after the NCBI sweep + PubMed rescue lane. "
        f"Bars show the % of each subset that carries the topological "
        f"feature; error bars on SurfaceBench are Wilson 95% binomial "
        f"confidence intervals (the universe is a population, not a "
        f"sample, so no CI). Per-class p-values are computed by an "
        f"exact 2-tailed binomial test of the bench count against the "
        f"universe proportion under H₀, Bonferroni-corrected across "
        f"the 9 topology classes (* p < 0.05, ** p < 0.01, *** p < 0.001); "
        f"{n_sig} of 9 classes reach significance. "
        f"The bench is enriched for {', '.join(over)} "
        f"and depleted for {', '.join(under)}; this reflects its "
        f"deliberate selection for DB-disagreement cases, so "
        f"bench-derived accuracy estimates are a lower bound on "
        f"expected full-universe accuracy."
    )
    return caption


def main() -> None:
    fig, _ = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"))
    # NOTE: this script deliberately does NOT write a caption file.
    # The manuscript caption lives at
    # ``data/analysis/figures/bench_topology_vs_universe.caption.md``
    # and is hand-maintained (accuracy-verified + de-jargoned), like
    # every other figure's caption — re-rendering the figure must not
    # touch it. ``_write_caption`` is retained as a helper for anyone
    # who wants to print a numbers-checked draft to the console.
    feats, univ, bench, _ci, pvals, n_u, n_b = _compute_distribution()
    print()
    print(_write_caption(n_u, n_b, pvals, feats, univ, bench))


if __name__ == "__main__":
    main()
