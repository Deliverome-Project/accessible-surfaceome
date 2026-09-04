"""Deep-dive final categorization — two panels.

**a.** The deep-dive cohort placed on a five-tier confidence spectrum —
``canonical`` (strict gold-standard surface), ``likely`` (broader passes-likely
surface), then the below-likely genes split by the deep-dive's tentative
surface call: ``low`` (low/moderate accessibility but weak evidence — maybe
surface), ``uncertain``, and ``no`` (leaned not-surface).

**b.** The two cross-cutting surface facets — cell-type restricted and
cell-state induced (split oncogenic vs. other) — counted by surface-call
REASON and broken out across the three populated tiers (canonical / likely /
low). Counting by reason rather than the evidence-gated facet keeps
weak-evidence genes that still carry a surface call: the ``low`` tier
contributes 463 cell-type-restricted and 156 induced genes that the gated
facet drops. Totals across the three tiers: cell-type restricted 1,314;
induced 600 (416 oncogenic, 184 other).

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

# Panel-b: the cross-cutting surface facets counted by surface-call REASON
# (option B), broken out across the three populated tiers. Three stacked
# categories per tier: cell-type restricted (tissue_restricted_surface),
# induced-oncogenic (cell_state_induced / lysosomal_exocytosis with an
# oncogenic trigger) and induced-other (any other induction trigger). Counting
# by reason keeps weak-evidence surface calls that land in the `low` tier,
# which the evidence-gated facet would drop.
_PANELB_TIERS = ["canonical", "likely", "low"]
_INDUCED_REASONS = {"cell_state_induced", "lysosomal_exocytosis"}
_PANELB_CATS: list[tuple[str, str]] = [
    ("Cell-type restricted", "#3D6B60"),  # teal
    ("Induced — oncogenic", "#B5522E"),   # rust
    ("Induced — other", "#D08A3E"),       # amber
]


def _panelb_category(reason: str, trigger: str) -> str | None:
    """Map a (surface_call_reason, induction_trigger) pair to one of the three
    Panel-b categories, or ``None`` if the reason carries no cross-cutting
    facet."""
    if reason == "tissue_restricted_surface":
        return "Cell-type restricted"
    if reason in _INDUCED_REASONS:
        return "Induced — oncogenic" if trigger == "oncogenic" else "Induced — other"
    return None


def _read() -> dict[str, dict[str, int]]:
    """Aggregate the PER-GENE table (one row per deep-dived gene, browsable)
    into ``{category: {subcategory: n_genes}}`` — the figure counts rows."""
    out: dict[str, dict[str, int]] = {}
    with open(DATA_TSV) as f:
        for row in csv.DictReader(f, delimiter="\t"):
            sub = out.setdefault(row["category"], {})
            sub[row["subcategory"]] = sub.get(row["subcategory"], 0) + 1
    return out


def _read_tier_categories() -> dict[str, dict[str, int]]:
    """Panel b: the tier × surface-facet-by-reason cross-tab.

    Returns ``{tier: {category_label: n_genes}}`` for the three populated tiers,
    counting by ``surface_call_reason`` (option B) so the low-tier weak-evidence
    surface calls are retained (they carry a reason but fail the evidence gate
    the ``facet`` column requires)."""
    out = {t: {c: 0 for c, _ in _PANELB_CATS} for t in _PANELB_TIERS}
    with open(DATA_TSV) as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["category"] not in out:
                continue
            cat = _panelb_category(row["surface_call_reason"],
                                   row["induction_trigger"])
            if cat:
                out[row["category"]][cat] += 1
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

    fig, (axA, axB) = plt.subplots(
        1, 2, figsize=(18, 7),
        gridspec_kw={"width_ratios": [1.5, 1.3], "wspace": 0.18},
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

    # ── Panel b: surface facets by REASON, across the three populated tiers ──
    # Cell-type restricted and cell-state induced (split oncogenic vs. other)
    # counted by surface-call reason (option B), so weak-evidence surface calls
    # in the `low` tier are retained. One horizontal stacked bar per tier
    # (canonical / likely / low), matching panel a's confidence spectrum.
    tier_cats = _read_tier_categories()
    y_pos = list(range(len(_PANELB_TIERS)))[::-1]  # canonical at top
    row_totals = [sum(tier_cats[t].values()) for t in _PANELB_TIERS]
    bar_max = max(row_totals)
    for t, y in zip(_PANELB_TIERS, y_pos):
        left = 0.0
        for label, color in _PANELB_CATS:
            n = tier_cats[t][label]
            if n <= 0:
                continue
            axB.barh(y, n, left=left, height=0.62, color=color,
                     edgecolor="white", linewidth=1.0)
            if n >= bar_max * 0.06:
                axB.text(left + n / 2, y, f"{n:,}", va="center", ha="center",
                         fontsize=13, fontweight="bold", color="white")
            left += n
        axB.text(left + bar_max * 0.012, y, f"{left:,.0f}", va="center",
                 ha="left", fontsize=15, fontweight="bold", color=COLORS["dark"])

    axB.set_yticks(y_pos)
    axB.set_yticklabels(_PANELB_TIERS, fontsize=16)
    axB.set_xlabel("Proteins (by surface-call reason)")
    axB.set_xlim(0, bar_max * 1.15)
    axB.set_ylim(-0.7, len(_PANELB_TIERS) - 0.3)
    sns.despine(ax=axB, top=True, right=True)

    handles = [mpatches.Patch(color=color, label=label)
               for label, color in _PANELB_CATS]
    axB.legend(handles=handles, title="Surface facet (by reason)",
               loc="upper right", bbox_to_anchor=(1.0, 1.0), frameon=False,
               fontsize=12, title_fontsize=13, handlelength=1.1,
               handletextpad=0.5, labelspacing=0.35)
    _panel_label(axB, "b")

    fig.tight_layout()
    return fig, (axA, axB)


def main() -> None:
    fig, _ = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"), gist_url=GIST_URL)


if __name__ == "__main__":
    main()
