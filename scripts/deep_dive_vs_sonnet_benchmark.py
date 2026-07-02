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


def _acc(rows: list[dict], key: str) -> float:
    return 100.0 * sum(int(r[key]) for r in rows) / len(rows) if rows else 0.0


def _panel_label(ax, letter: str) -> None:
    ax.text(-0.02, 1.06, letter, transform=ax.transAxes, fontsize=26,
            fontweight=800, va="bottom", ha="right", color=COLORS["dark"])


def _bars(ax, dd: float, son: float, x: float, width: float,
          label: bool) -> None:
    ax.bar(x - width / 2, dd, width=width, color=_DD_COLOR,
           label="deep dive" if label else None)
    ax.bar(x + width / 2, son, width=width, color=_SONNET_COLOR,
           label="Sonnet+NCBI" if label else None)
    ax.text(x - width / 2, dd + 1.5, f"{dd:.0f}", ha="center", va="bottom",
            fontsize=14, color=_DD_COLOR, fontweight="bold")
    ax.text(x + width / 2, son + 1.5, f"{son:.0f}", ha="center", va="bottom",
            fontsize=14, color=_SONNET_COLOR, fontweight="bold")


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
    _bars(axA, _acc(rows, "deep_dive_correct"), _acc(rows, "sonnet_correct"),
          0.0, width, label=False)
    axA.set_xticks([-width / 2, width / 2])
    axA.set_xticklabels(["deep\ndive", "Sonnet\n+NCBI"])
    axA.set_ylabel("Soft-credit accuracy (%)")
    axA.set_ylim(0, 112)
    axA.set_xlim(-0.7, 0.7)
    axA.text(0.5, 1.02, f"Overall (n={n})", transform=axA.transAxes,
             ha="center", va="bottom", fontsize=15, style="italic",
             color=COLORS["neutral"])
    sns.despine(ax=axA, top=True, right=True)
    _panel_label(axA, "a")

    # ── Panel b: by ground-truth bucket ─────────────────────────────────────
    bwidth = 0.38
    bucket_n = {bk: sum(1 for r in rows if r["ground_truth_verdict"] == bk)
                for bk in _BUCKET_ORDER}
    for bi, bk in enumerate(_BUCKET_ORDER):
        sub = [r for r in rows if r["ground_truth_verdict"] == bk]
        _bars(axB, _acc(sub, "deep_dive_correct"), _acc(sub, "sonnet_correct"),
              float(bi), bwidth, label=(bi == 0))
    axB.set_xticks(range(len(_BUCKET_ORDER)))
    axB.set_xticklabels([f"{_BUCKET_LABEL[b]}\nn={bucket_n[b]}"
                         for b in _BUCKET_ORDER])
    axB.set_ylabel("Soft-credit accuracy (%)")
    axB.set_ylim(0, 112)
    axB.set_xlim(-0.6, len(_BUCKET_ORDER) - 0.4)
    axB.text(0.5, 1.02, "By ground-truth bucket", transform=axB.transAxes,
             ha="center", va="bottom", fontsize=15, style="italic",
             color=COLORS["neutral"])
    axB.legend(loc="lower left", frameon=False, fontsize=14)
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
