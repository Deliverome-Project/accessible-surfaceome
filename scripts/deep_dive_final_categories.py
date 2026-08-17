"""Deep-dive final categorization — two panels.

**a.** The deep-dive cohort placed on a five-tier confidence spectrum —
``canonical`` (strict gold-standard surface), ``likely`` (broader passes-likely
surface), then the below-likely genes split by the deep-dive's tentative
surface call: ``low`` (low/moderate accessibility but weak evidence — maybe
surface), ``uncertain``, and ``no`` (leaned not-surface).

**b.** Cell-state modulation across the three surface tiers (canonical /
likely / low) as a 100%-stacked bar — state-gated (surface only when induced,
``low_endogenous_expression`` true) vs constitutive baseline (surface at rest
and further modulated, the ICAM1 class). State-dependence is a FACET, not a
tier, so it recurs across tiers; the split is monotonic with confidence
(canonical skews constitutive, low skews state-gated).

Bucket predicates delegate to ``accessible_surfaceome.release.catalog_presets``
via ``scripts/build_figure_tsvs.py`` (``_dd_passes_*``); canonical/likely == the
catalog presets, and the low/uncertain/no split of the negatives is a
figure-only refinement (the presets don't cover the negatives).

Full deep-dive cohort (5,130 genes); canonical uses the PR #130 gate.

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

import matplotlib.patches as mpatches
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

# Panel-b cell-state split. state-dependence is a FACET, not a tier, so it
# recurs across every surface tier: Panel b asks, within each of canonical /
# likely / low, how many proteins are surface only when induced (state-gated,
# low_endogenous_expression True) vs constitutive at rest and merely further
# modulated (the ICAM1 class, low_endogenous_expression False).
_CS_TIERS = ["canonical", "likely", "low"]
_CS_COLORS: dict[str, str] = {
    "constitutive": "#2E7A55",  # green — constitutive baseline (further-inducible)
    "state_gated":  "#C07830",  # amber — surface only when induced
}
_CS_LABELS: dict[str, str] = {
    "constitutive": "constitutive baseline (further-inducible)",
    "state_gated":  "state-gated (surface only when induced)",
}


def _read() -> dict[str, dict[str, int]]:
    """Aggregate the PER-GENE table (one row per deep-dived gene, browsable)
    into ``{category: {subcategory: n_genes}}`` — the figure counts rows."""
    out: dict[str, dict[str, int]] = {}
    with open(DATA_TSV) as f:
        for row in csv.DictReader(f, delimiter="\t"):
            sub = out.setdefault(row["category"], {})
            sub[row["subcategory"]] = sub.get(row["subcategory"], 0) + 1
    return out


def _read_cellstate() -> dict[str, dict[str, int]]:
    """Per surface tier, split genes into state-gated vs constitutive-baseline
    on ``low_endogenous_expression`` (1 → surface only when induced off a
    low/absent baseline; 0 → constitutive at rest). Returns
    ``{tier: {"constitutive": n, "state_gated": n}}`` for canonical/likely/low."""
    agg = {t: {"constitutive": 0, "state_gated": 0} for t in _CS_TIERS}
    with open(DATA_TSV) as f:
        for row in csv.DictReader(f, delimiter="\t"):
            tier = row["category"]
            if tier not in agg:
                continue
            cls = "state_gated" if row.get("low_endogenous_expression") == "1" \
                else "constitutive"
            agg[tier][cls] += 1
    return agg


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
        gridspec_kw={"width_ratios": [1.5, 1.2], "wspace": 0.60},
    )

    # ── Panel a: the five-tier confidence spectrum ──────────────────────────
    tiers = [
        ("canonical\n(strict)", canon, _COLOR_CANONICAL),
        ("likely", likely_total, _COLOR_LIKELY),
        ("low", low_total, _COLOR_LOW),
        ("no", no_total, _COLOR_NO),
        ("uncertain", unc_total, _COLOR_UNCERTAIN),
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

    # ── Panel b: cell-state modulation across the surface tiers ─────────────
    # 100%-stacked bar per tier — state-gated vs constitutive-baseline — so the
    # cross-tier gradient is visible: cell-state variation is not confined to
    # `likely` (canonical carries a large state-gated share too), but higher-
    # confidence tiers skew constitutive while lower tiers skew state-gated.
    cs = _read_cellstate()
    order = [t for t in _CS_TIERS if sum(cs[t].values()) > 0]
    ys = list(range(len(order)))[::-1]  # canonical on top
    for y, tier in zip(ys, order):
        d = cs[tier]
        total = d["constitutive"] + d["state_gated"]
        left = 0.0
        for cls in ("constitutive", "state_gated"):
            frac = d[cls] / total
            axB.barh(y, frac, left=left, height=0.66, color=_CS_COLORS[cls],
                     edgecolor="white", linewidth=1.2)
            if frac > 0.07:
                axB.text(left + frac / 2, y, f"{d[cls]:,}\n{frac * 100:.0f}%",
                         va="center", ha="center", fontsize=13,
                         fontweight="bold", color="white")
            left += frac
    axB.set_yticks(ys)
    axB.set_yticklabels(order, fontsize=16)
    axB.set_xlim(0, 1)
    axB.set_ylim(-0.6, len(order) - 0.4)
    axB.set_xlabel("Share of tier")
    axB.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    axB.set_xticklabels(["0", "25", "50", "75", "100%"])
    axB.text(0.0, 1.15,
             "Cell-state modulation spans every tier — "
             "surface only when induced vs constitutive baseline",
             transform=axB.transAxes, fontsize=15, style="italic",
             color=COLORS["neutral"], va="bottom", ha="left")
    handles = [mpatches.Patch(color=_CS_COLORS[c], label=_CS_LABELS[c])
               for c in ("constitutive", "state_gated")]
    axB.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.005),
               ncol=1, frameon=False, fontsize=12, handlelength=1.2,
               handletextpad=0.5, labelspacing=0.3)
    sns.despine(ax=axB, top=True, right=True, left=True)
    _panel_label(axB, "b")

    fig.text(
        0.5, -0.02,
        f"Full deep-dive cohort (n={cohort_n:,}); canonical uses the PR #130 gate. "
        f"(b) State-dependence is a facet, not a tier: cell-state variation spans "
        f"canonical / likely / low — higher-confidence tiers skew constitutive-"
        f"baseline (ICAM1-class), lower tiers state-gated. low / uncertain / no "
        f"(panel a) remain weak-evidence tentative leans.",
        ha="center", va="top", fontsize=12, style="italic", color=COLORS["neutral"],
    )

    fig.tight_layout()
    return fig, (axA, axB)


def main() -> None:
    fig, _ = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"), gist_url=GIST_URL)


if __name__ == "__main__":
    main()
