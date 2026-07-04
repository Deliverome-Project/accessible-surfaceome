"""Deep-dive vs Sonnet+NCBI accuracy on SurfaceBench (deep-dived genes).

New Supp figure: for the SurfaceBench genes deep-dived so far (the intersection,
n=27 of 147), how the evidence-anchored deep dive scores against the curated
ground truth, next to the Sonnet+NCBI triage on the SAME genes. Soft-credit
accuracy — a contextually-surface protein counts correct when called surface.

**a.** Overall accuracy — deep dive vs Sonnet+NCBI on the deep-dived bench genes.
**b.** Accuracy per ground-truth bucket (yes / contextual / no).

Reads the bundled per-figure TSV (one row per deep-dived bench gene with both
predictors' soft-credit correctness); the figure aggregates.

PRELIMINARY — 27 of 147 bench genes deep-dived; the 'no' bucket is n=2.

Run::

    uv run python scripts/deep_dive_vs_sonnet_benchmark.py

# Reproduction: (gist created at figure promotion)
"""
from __future__ import annotations

import csv
from pathlib import Path

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
SLUG = "deep_dive_vs_sonnet_benchmark"
DATA_TSV = ROOT / "data/processed/figures/deep_dive_vs_sonnet_benchmark.tsv"
GIST_URL = ""  # filled at figure promotion

_DD_COLOR = "#2E7A55"       # deep dive — success green
_SONNET_COLOR = "#d87851"   # Sonnet — Claude-orange
_BUCKET_ORDER = ["yes", "contextual", "no"]
_BUCKET_LABEL = {"yes": "yes\n(surface)", "contextual": "contextual",
                 "no": "no\n(not surface)"}


def _load() -> list[dict]:
    with open(DATA_TSV) as f:
        return list(csv.DictReader(f, delimiter="\t"))


_RNG = np.random.default_rng(0)  # deterministic jitter


def _stats(rows: list[dict], key: str) -> tuple[float, float, list[float]]:
    """Soft-credit accuracy (%), its binomial SEM (%), and the per-gene 0/100
    correctness values (for the jittered dots)."""
    vals = [int(r[key]) for r in rows]
    n = len(vals)
    if n == 0:
        return 0.0, 0.0, []
    p = sum(vals) / n
    sem = 100.0 * ((p * (1 - p)) ** 0.5) / (n ** 0.5)
    return 100.0 * p, sem, [100.0 * v for v in vals]


def _panel_label(ax, letter: str) -> None:
    ax.text(-0.02, 1.06, letter, transform=ax.transAxes, fontsize=26,
            fontweight=800, va="bottom", ha="right", color=COLORS["dark"])


def _bars(ax, rows: list[dict], x: float, width: float, label: bool) -> None:
    """Deep-dive + Sonnet+NCBI accuracy bars at x. Sonnet also carries an SEM
    error bar + the individual per-gene correctness dots (jittered), so its
    uncertainty — and how it overlaps the deep-dive bar — is visible."""
    dd, _, _ = _stats(rows, "deep_dive_correct")
    son, son_sem, son_pts = _stats(rows, "sonnet_correct")
    ax.bar(x - width / 2, dd, width=width, color=_DD_COLOR,
           label="deep dive" if label else None, zorder=2)
    ax.bar(x + width / 2, son, width=width, color=_SONNET_COLOR,
           label="Sonnet+NCBI" if label else None, zorder=2)
    ax.errorbar(x + width / 2, son, yerr=son_sem, fmt="none",
                ecolor=COLORS["dark"], elinewidth=1.4, capsize=5, zorder=4)
    if son_pts:
        jx = _RNG.uniform(-width * 0.26, width * 0.26, size=len(son_pts))
        ax.scatter(x + width / 2 + jx, son_pts, s=16, color=COLORS["dark"],
                   alpha=0.4, edgecolor="none", zorder=5)
    ax.text(x - width / 2, dd + 2, f"{dd:.0f}", ha="center", va="bottom",
            fontsize=14, color=_DD_COLOR, fontweight="bold")
    ax.text(x + width / 2, son + son_sem + 2, f"{son:.0f}", ha="center",
            va="bottom", fontsize=14, color=_SONNET_COLOR, fontweight="bold")


def make_plot() -> tuple[plt.Figure, tuple[plt.Axes, plt.Axes]]:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    plt.rcParams.update({
        "font.size": 18, "axes.labelsize": 18, "axes.titlesize": 0,
        "xtick.labelsize": 15, "ytick.labelsize": 15, "legend.fontsize": 15,
    })
    rows = _load()
    n = len(rows)

    fig, (axA, axB) = plt.subplots(
        1, 2, figsize=(13, 6),
        gridspec_kw={"width_ratios": [0.8, 1.5], "wspace": 0.28},
    )

    # ── Panel a: overall ────────────────────────────────────────────────────
    width = 0.6
    _bars(axA, rows, 0.0, width, label=False)
    axA.set_xticks([-width / 2, width / 2])
    axA.set_xticklabels(["deep\ndive", "Sonnet\n+NCBI"])
    axA.set_ylabel("Soft-credit accuracy (%)")
    axA.set_ylim(0, 112)
    axA.set_xlim(-0.7, 0.7)
    sns.despine(ax=axA, top=True, right=True)
    _panel_label(axA, "a")

    # ── Panel b: by ground-truth bucket ─────────────────────────────────────
    bwidth = 0.38
    bucket_n = {bk: sum(1 for r in rows if r["ground_truth_verdict"] == bk)
                for bk in _BUCKET_ORDER}
    for bi, bk in enumerate(_BUCKET_ORDER):
        sub = [r for r in rows if r["ground_truth_verdict"] == bk]
        _bars(axB, sub, float(bi), bwidth, label=(bi == 0))
    axB.set_xticks(range(len(_BUCKET_ORDER)))
    axB.set_xticklabels([f"{_BUCKET_LABEL[b]}\nn={bucket_n[b]}"
                         for b in _BUCKET_ORDER])
    axB.set_ylabel("Soft-credit accuracy (%)")
    axB.set_ylim(0, 112)
    axB.set_xlim(-0.6, len(_BUCKET_ORDER) - 0.4)
    axB.legend(loc="upper right", frameon=False, fontsize=14)
    sns.despine(ax=axB, top=True, right=True)
    _panel_label(axB, "b")

    fig.text(
        0.5, -0.02,
        f"Deep dive vs Sonnet+NCBI triage on the {n} SurfaceBench genes "
        f"deep-dived so far (of 147). Soft-credit: a contextually-surface protein "
        f"counts correct when called surface. PRELIMINARY — small n, especially "
        f"the 'no' bucket (n=2); widens as the sweep covers more bench genes.",
        ha="center", va="top", fontsize=11, style="italic",
        color=COLORS["neutral"], wrap=True,
    )
    fig.tight_layout()
    return fig, (axA, axB)


def main() -> None:
    fig, _ = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"),
                gist_url=GIST_URL)


if __name__ == "__main__":
    main()
