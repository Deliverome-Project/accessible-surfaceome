"""Deep-dive final categorization — two panels.

**a.** The deep-dive cohort placed on a five-tier confidence spectrum —
``canonical`` (strict gold-standard surface), ``likely`` (broader passes-likely
surface), then the below-likely genes split by the deep-dive's tentative
surface call: ``low`` (low/moderate accessibility but weak evidence — maybe
surface), ``uncertain``, and ``no`` (leaned not-surface).

**b.** The composition of the ``likely`` tier: WHY those calls are only likely,
as a sorted horizontal bar chart over the cell-type + cell-state reasons.

Bucket predicates are ported from ``viewer/lib/catalog-presets.ts`` in
``scripts/build_figure_tsvs.py`` (``_dd_passes_*``); canonical/likely == the
catalog presets, and the low/uncertain/no split of the negatives is a
figure-only refinement (the presets don't cover the negatives).

**PRELIMINARY** — ~1,197 of ~5,128 swept, pre-QA-fix. Nearly all below-likely
genes (low/uncertain/no) carry weak/conflicting evidence — partly the
pretrim-cap recall bug that deletes foundational literature — so those three
tiers are tentative leans on thin evidence, and the cell-state ``oncogenic``
share is inflated by tumour-associated over-flagging; re-render after the full
sweep + QA fixes.

# Reproduction:
#   Public gist (reader-side standalone, PyPA inline-script-metadata deps):
#   https://gist.github.com/beccajcarlson/c2441f8d0314c5524463bc85a3e86612
#   Reader-side mirror: data/analysis/figures/make_deep_dive_final_categories.py

Run:
    uv run python scripts/deep_dive_final_categories.py
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
SLUG = "deep_dive_final_categories"
GIST_URL = "https://gist.github.com/beccajcarlson/c2441f8d0314c5524463bc85a3e86612"

DATA_TSV = ROOT / "data/processed/figures/deep_dive_final_categories.tsv"

# Panel-a tier colours — a confidence spectrum from surface (green) to
# not-surface (neutral).
_COLOR_CANONICAL = "#2E7A55"   # brand success green — strict tier
_COLOR_LIKELY = "#3D6B60"      # teal-mid — broader tier
_COLOR_LOW = "#C99A5B"         # amber-tan — low/moderate access, weak evidence
_COLOR_UNCERTAIN = "#C7BDB6"   # light warm grey — ambiguous
_COLOR_NO = "#9C8C88"          # lifted neutral — leaned not-surface

# Per-reason colour + label for the Panel-b breakdown of `likely`.
_LIKELY_COLORS: dict[str, str] = {
    "cell_type_restricted":      "#BC3C4C",
    "cell_state_oncogenic":      "#5A2608",
    "cell_state_immune":         "#8C4210",
    "cell_state_stress_hypoxia": "#C07830",
    "cell_state_cell_death":     "#E0952F",
    "cell_state_infection":      "#EFC178",
    "cell_state_other":          "#D8A24A",
    "likely_other":              "#3D6B60",
}
_LIKELY_LABELS: dict[str, str] = {
    "cell_type_restricted":      "cell-type restricted",
    "cell_state_oncogenic":      "cell-state · oncogenic",
    "cell_state_immune":         "cell-state · immune",
    "cell_state_stress_hypoxia": "cell-state · stress/hypoxia",
    "cell_state_cell_death":     "cell-state · cell death",
    "cell_state_infection":      "cell-state · infection",
    "cell_state_other":          "cell-state · other",
    "likely_other":              "likely (residual)",
}


def _read() -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    with open(DATA_TSV) as f:
        for row in csv.DictReader(f, delimiter="\t"):
            out.setdefault(row["category"], {})[row["subcategory"]] = int(row["n_genes"])
    return out


def _panel_label(ax, letter: str) -> None:
    ax.text(-0.02, 1.06, letter, transform=ax.transAxes, fontsize=26,
            fontweight=800, va="bottom", ha="right", color=COLORS["dark"])


def make_plot() -> tuple[plt.Figure, tuple[plt.Axes, plt.Axes]]:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    plt.rcParams.update({
        "font.size": 20, "axes.labelsize": 20, "axes.titlesize": 0,
        "xtick.labelsize": 20, "ytick.labelsize": 20, "legend.fontsize": 20,
    })
    data = _read()
    canon = sum(data.get("canonical", {}).values())
    likely = data.get("likely", {})
    likely_total = sum(likely.values())
    low_total = sum(data.get("low", {}).values())
    unc_total = sum(data.get("uncertain", {}).values())
    no_total = sum(data.get("no", {}).values())
    cohort_n = canon + likely_total + low_total + unc_total + no_total

    fig, (axA, axB) = plt.subplots(
        1, 2, figsize=(18, 7),
        gridspec_kw={"width_ratios": [1.25, 1.4], "wspace": 0.60},
    )

    # ── Panel a: the five-tier confidence spectrum ──────────────────────────
    tiers = [
        ("canonical\n(strict)", canon, _COLOR_CANONICAL),
        ("likely", likely_total, _COLOR_LIKELY),
        ("low", low_total, _COLOR_LOW),
        ("uncertain", unc_total, _COLOR_UNCERTAIN),
        ("no", no_total, _COLOR_NO),
    ]
    tier_max = max(t[1] for t in tiers)
    for i, (label, n, color) in enumerate(tiers):
        axA.bar(i, n, width=0.74, color=color, edgecolor="none")
        axA.text(i, n + tier_max * 0.02, f"{n:,}", ha="center", va="bottom",
                 fontsize=17, fontweight="bold", color=COLORS["dark"])
    axA.set_xticks(range(len(tiers)))
    axA.set_xticklabels([t[0] for t in tiers], fontsize=15)
    axA.set_ylabel("Proteins in\ndeep-dive cohort")
    axA.set_ylim(0, tier_max * 1.16)
    axA.set_xlim(-0.6, len(tiers) - 0.4)
    sns.despine(ax=axA, top=True, right=True)
    _panel_label(axA, "a")

    # ── Panel b: composition of `likely`, sorted horizontal ─────────────────
    items = sorted(likely.items(), key=lambda kv: kv[1])  # ascending → biggest on top
    ys = list(range(len(items)))
    b_max = max((n for _, n in items), default=1)
    for y, (key, n) in zip(ys, items):
        axB.barh(y, n, color=_LIKELY_COLORS.get(key, "#999999"),
                 edgecolor="#1F1718", linewidth=0.4)
        axB.text(n + b_max * 0.012, y, f"{n:,}", va="center", ha="left",
                 fontsize=15, color=COLORS["dark"])
    axB.set_yticks(ys)
    axB.set_yticklabels([_LIKELY_LABELS.get(k, k) for k, _ in items], fontsize=15)
    axB.set_xlabel("Proteins")
    axB.set_xlim(0, b_max * 1.14)
    axB.set_ylim(-0.6, len(items) - 0.4)
    axB.text(0.0, 1.06, f"composition of the {likely_total:,} 'likely' calls",
             transform=axB.transAxes, fontsize=15, style="italic",
             color=COLORS["neutral"], va="bottom", ha="left")
    sns.despine(ax=axB, top=True, right=True)
    _panel_label(axB, "b")

    fig.text(
        0.5, -0.02,
        f"PRELIMINARY — {cohort_n:,} of ~5,128 swept, pre-QA-fix "
        f"(low/uncertain/no are weak-evidence tentative leans, inflated by the "
        f"pretrim-cap bug; cell-state 'oncogenic' by tumour-associated over-flagging).",
        ha="center", va="top", fontsize=12, style="italic", color=COLORS["neutral"],
    )

    fig.tight_layout()
    return fig, (axA, axB)


def main() -> None:
    fig, _ = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"), gist_url=GIST_URL)


if __name__ == "__main__":
    main()
