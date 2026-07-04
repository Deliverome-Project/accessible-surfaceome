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
SLUG = "deep_dive_vs_sonnet_benchmark"
DATA_TSV = ROOT / "data/processed/figures/deep_dive_vs_sonnet_benchmark.tsv"
GIST_URL = ""  # filled at figure promotion

_SONNET_COLOR = "#C85A2E"   # Sonnet — deeper orange
_BUCKET_ORDER = ["yes", "contextual", "no"]
_BUCKET_LABEL = {"yes": "yes\n(surface)", "contextual": "contextual",
                 "no": "no\n(not surface)"}

# The deep-dive accuracy bar is stacked by the tier it assigned to the correctly
# classified genes, so the confidence breakdown shows. Tier colours are EXACTLY
# Figure 5a's (deep_dive_final_categories) five-tier spectrum, so the two figures
# read as one palette.
_TIER_ORDER = ["canonical", "likely", "low", "uncertain", "no"]
_TIER_COLOR = {
    "canonical": "#2E7A55",  # success green — strict tier
    "likely":    "#3D6B60",  # teal-mid — broader tier
    "low":       "#C99A5B",  # amber-tan — low/moderate, weak evidence
    "uncertain": "#C7BDB6",  # light warm-grey — ambiguous
    "no":        "#9C8C88",  # lifted neutral — leaned not-surface
}
_TIER_LABEL = {"canonical": "canonical", "likely": "likely", "low": "low",
               "uncertain": "uncertain", "no": "no"}


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


def _sonnet_replicate_accs(rows: list[dict]) -> list[float]:
    """Per-replicate soft-credit accuracy (%) over the given genes — one value
    per replicate with data (the mainbench Sonnet+NCBI triage ran 3 replicates)."""
    accs = []
    for col in ("sonnet_correct_r1", "sonnet_correct_r2", "sonnet_correct_r3"):
        vals = [int(row[col]) for row in rows if str(row.get(col, "")) != ""]
        if vals:
            accs.append(100.0 * sum(vals) / len(vals))
    return accs


def _draw_sonnet(ax, rows: list[dict], x: float, width: float) -> None:
    """Sonnet+NCBI bar = MEAN of the per-replicate accuracies; one dot per
    replicate + SEM ACROSS replicates (not a 0/1 dot per gene)."""
    accs = _sonnet_replicate_accs(rows)
    if not accs:
        return
    mean = sum(accs) / len(accs)
    sem = float(np.std(accs, ddof=1)) / (len(accs) ** 0.5) if len(accs) > 1 else 0.0
    ax.bar(x, mean, width=width, color=_SONNET_COLOR, zorder=2)
    ax.errorbar(x, mean, yerr=sem, fmt="none", ecolor=COLORS["dark"],
                elinewidth=1.4, capsize=5, zorder=4)
    jx = _RNG.uniform(-width * 0.20, width * 0.20, size=len(accs))
    ax.scatter(x + jx, accs, s=26, color=COLORS["dark"], alpha=0.75,
               edgecolor="white", linewidth=0.5, zorder=5)
    ax.text(x, mean + sem + 2, f"{mean:.0f}", ha="center", va="bottom",
            fontsize=14, color=_SONNET_COLOR, fontweight="bold")


def _draw_deep_dive(ax, rows: list[dict], x: float, width: float) -> None:
    """Deep-dive accuracy bar, STACKED by the tier of the correctly-classified
    genes (canonical/likely/low green shades + grey for uncertain/no), so the
    confidence breakdown of the calls is visible. Stack height == accuracy."""
    from collections import Counter
    n = len(rows)
    dd, _, _ = _stats(rows, "deep_dive_correct")
    counts = Counter(r["deep_dive_tier"] for r in rows
                     if int(r["deep_dive_correct"]) == 1)
    bottom = 0.0
    for t in _TIER_ORDER:
        h = 100.0 * counts.get(t, 0) / n if n else 0.0
        if h <= 0:
            continue
        ax.bar(x, h, bottom=bottom, width=width, color=_TIER_COLOR[t], zorder=2)
        bottom += h
    ax.text(x, dd + 2, f"{dd:.0f}", ha="center", va="bottom", fontsize=14,
            color=COLORS["dark"], fontweight="bold")


def make_plot() -> tuple[plt.Figure, tuple[plt.Axes, plt.Axes]]:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    plt.rcParams.update({
        "font.size": 18, "axes.labelsize": 18, "axes.titlesize": 0,
        "xtick.labelsize": 15, "ytick.labelsize": 15, "legend.fontsize": 15,
    })
    rows = _load()

    fig, (axA, axB) = plt.subplots(
        1, 2, figsize=(13, 6),
        gridspec_kw={"width_ratios": [0.8, 1.5], "wspace": 0.28},
    )

    # ── Panel a: overall ────────────────────────────────────────────────────
    width = 0.6
    _draw_deep_dive(axA, rows, -width / 2, width)
    _draw_sonnet(axA, rows, width / 2, width)
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
        _draw_deep_dive(axB, sub, bi - bwidth / 2, bwidth)
        _draw_sonnet(axB, sub, bi + bwidth / 2, bwidth)
    axB.set_xticks(range(len(_BUCKET_ORDER)))
    axB.set_xticklabels([f"{_BUCKET_LABEL[b]}\nn={bucket_n[b]}"
                         for b in _BUCKET_ORDER])
    axB.set_ylabel("Soft-credit accuracy (%)")
    axB.set_ylim(0, 112)
    axB.set_xlim(-0.6, len(_BUCKET_ORDER) - 0.4)
    # Legend: deep-dive tier stack (canonical/likely/low/uncertain-no) + Sonnet.
    # Short labels under a "deep-dive tier" header so it fits the empty
    # upper-right (over the low 'no' bucket) without clipping the taller bars.
    handles = [mpatches.Patch(color=_TIER_COLOR[t], label=_TIER_LABEL[t])
               for t in _TIER_ORDER]
    handles.append(mpatches.Patch(color=_SONNET_COLOR, label="Sonnet+NCBI"))
    # Just outside the top-right so it clears the tall bars + Sonnet dots.
    axB.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1.0),
               frameon=False, fontsize=11, title="deep-dive tier / Sonnet",
               title_fontsize=11, labelspacing=0.35, handlelength=1.2)
    sns.despine(ax=axB, top=True, right=True)
    _panel_label(axB, "b")

    fig.tight_layout(rect=(0, 0, 0.84, 1))
    return fig, (axA, axB)


def main() -> None:
    fig, _ = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"),
                gist_url=GIST_URL)


if __name__ == "__main__":
    main()
