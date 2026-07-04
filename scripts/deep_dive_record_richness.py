"""Deep-dive record richness across five axes, faceted by deep-dive tier.

Five-panel violin showing the *real* per-gene distribution along the axes that
characterise *how much information* a single deep dive captures. Every panel is
faceted by the deep-dive **tier** (canonical / likely / low / no) — so the
reader can see how record richness scales with confidence rather than a coarse
non-surface-vs-surface split. Each violin is the real distribution of that
tier's genes; there is no synthesised fan.

The five axes
-------------
a. **Papers found** — the discovery-corpus size (EuropePMC + PubTator NER +
   gene2pubmed union). Tiers: canonical, likely, low, no.

b. **Papers selected** — unique papers read full-text into the evidence list.
   Tiers: canonical, likely, low, no.

c. **Papers with extracellular evidence** — selected papers carrying an
   experimental extracellular / surface-method tag. Tiers: canonical, likely,
   low (the "no" tier is dropped — non-surface proteins carry little
   extracellular evidence by definition).

d. **LLM filters with evidence** — how many of the ~20 LLM filter facets carry a
   positive/non-default (evidence-backed) determination; the LLM analogue of e.
   Tiers: canonical, likely, low.

e. **Deterministic features populated (0–7)** — how many of the seven
   deterministic structural/topology features are present. Tiers: canonical,
   likely, low.

The ``uncertain`` tier (n=9) is dropped everywhere as too small to show a
distribution.

Why per-panel violins?
----------------------
Each axis has a very different scale (papers in the hundreds vs feature counts
0–6) so a shared Y axis would compress the small axes into the baseline. Five
small per-panel violins (one Y axis each) let each real distribution speak for
itself.

Data source
-----------
Reads the bundled per-figure TSV at
``data/processed/figures/deep_dive_record_richness.tsv`` (one row per deep-dived
gene: the five real per-gene axes + the deep-dive ``tier``).

PRELIMINARY — 1,175 of ~5,128 swept, pre-QA-fix.

Run::

    uv run python scripts/deep_dive_record_richness.py

# Reproduction: https://gist.github.com/beccajcarlson/35119ea2bca9585c7245d247334b8c01
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import (
    COLORS,
    save_figure,
    setup_plotting_style,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data/analysis/figures"
SLUG = "deep_dive_record_richness"
# In-repo per-figure TSV: one row per deep-dived gene, carrying the five real
# per-gene axes + the deep-dive `tier`.
DATA_TSV = ROOT / "data/processed/figures/deep_dive_record_richness.tsv"

# Published reproduction gist (embedded into output PNG Source / PDF Subject
# metadata via save_figure(gist_url=...)).
GIST_URL = "https://gist.github.com/beccajcarlson/35119ea2bca9585c7245d247334b8c01"

# Tier colors — MUST match Fig 5. canonical=green, likely=teal, low=amber,
# no=muted warm-grey. `uncertain` is dropped everywhere (n=9, too small).
TIER_COLORS = {
    "canonical": "#2E7A55",
    "likely":    "#3D6B60",
    "low":       "#C99A5B",
    "no":        "#9C8C88",
}

# Five-panel specs: (tsv_key, subtitle, tiers-to-show).
# Panels a/b keep the "no" tier; c/d/e drop it (non-surface genes carry
# little extracellular evidence by definition).
_FOUR = ["canonical", "likely", "low", "no"]
_THREE = ["canonical", "likely", "low"]
PANELS = [
    ("papers_found",       "Papers found (discovery corpus)",          _FOUR),
    ("papers_selected",    "Papers selected (into evidence list)",     _FOUR),
    ("papers_with_ec",     "Papers with extracellular evidence",       _THREE),
    ("n_filters_evidence", "LLM filters with evidence",                _THREE),
    ("n_det_features",     "Deterministic features populated (0-7)",   _THREE),
]

FIGSIZE = (25, 6.5)


def _load_real_values() -> pd.DataFrame:
    """Read the bundled per-figure TSV (one row per deep-dived gene)."""
    return pd.read_csv(DATA_TSV, sep="\t")


def _draw_panel(ax: plt.Axes, data: pd.DataFrame, key: str,
                tiers: list[str]) -> None:
    """Real violins, one per tier, in tier colors. Median line inside each
    violin + a faint real-value point strip so the reader sees the actual n."""
    sub = data[data["tier"].isin(tiers)].copy()
    sub = sub[["tier", key]].dropna()
    sub[key] = sub[key].astype(float)

    palette = {t: TIER_COLORS[t] for t in tiers}
    sns.violinplot(
        data=sub, x="tier", y=key, order=tiers, hue="tier",
        hue_order=tiers, palette=palette, legend=False,
        inner="quartile", cut=0, density_norm="width",
        linewidth=1.2, saturation=1.0, ax=ax,
    )
    # Soften the violin bodies + recolor the inner quartile lines so the
    # median (middle line) reads as a solid tick and the quartiles as faint.
    for coll in ax.collections:
        coll.set_alpha(0.35)
    for line in ax.lines:
        line.set_color(COLORS["dark"])
        line.set_alpha(0.9)
        line.set_linewidth(1.4)

    # Faint real-value point strip on top so the actual per-tier n is visible.
    sns.stripplot(
        data=sub, x="tier", y=key, order=tiers, hue="tier",
        hue_order=tiers, palette=palette, legend=False,
        size=2.2, alpha=0.28, jitter=0.18, ax=ax,
    )

    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.margins(y=0.04)


def make_plot() -> tuple[plt.Figure, list[plt.Axes]]:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    plt.rcParams.update({
        # Each subplot uses a TITLE (axes.titlesize) as its subtitle so the
        # per-panel description renders at a readable size; the tier names
        # occupy the x-tick labels.
        "font.size": 18, "axes.labelsize": 20, "axes.titlesize": 16,
        "axes.titleweight": "semibold", "axes.titlepad": 12,
        "xtick.labelsize": 14, "ytick.labelsize": 18, "legend.fontsize": 14,
    })

    data = _load_real_values()
    n_real_total = len(data)

    fig, axes = plt.subplots(1, 5, figsize=FIGSIZE)
    panel_letters = ["a", "b", "c", "d", "e"]

    for idx, (ax, (key, subtitle, tiers)) in enumerate(
        zip(axes, PANELS, strict=True)
    ):
        _draw_panel(ax, data, key, tiers)

        # ``setup_plotting_style`` monkey-patches ``Axes.set_title`` (and
        # ``Figure.suptitle``) to NO-OPS, so a ``set_title`` subtitle silently
        # vanishes. Render the per-panel subtitle as centered text just above
        # each panel instead so the reader can see what each panel shows.
        ax.text(
            0.5, 1.03, subtitle, transform=ax.transAxes,
            ha="center", va="bottom", fontsize=15, fontweight="semibold",
            color=COLORS["dark"],
        )

        # Subpanel letter (lowercase, ExtraBold) at the panel's upper-left,
        # baseline-aligned with the subtitle — figure_subpanel_labels memory.
        ax.text(
            -0.14, 1.03, panel_letters[idx],
            transform=ax.transAxes, ha="left", va="bottom",
            fontsize=22, fontweight=800, color=COLORS["dark"],
        )

        sns.despine(ax=ax, top=True, right=True)

    # suptitle is monkey-patched to a no-op; use fig.text for the figure title.
    fig.text(
        0.5, 0.995, "Deep-dive record richness scales with confidence tier",
        ha="center", va="top", fontsize=18, fontweight="semibold",
        color=COLORS["dark"],
    )

    fig.text(
        0.5, 0.02,
        f"Real per-gene distributions from the {n_real_total} deep dives, faceted "
        f"by deep-dive tier (median line inside each violin; faint dots = the real "
        f"per-tier values). Panels a/b keep the 'no' tier; panels c-e drop it since "
        f"non-surface proteins carry little extracellular evidence by definition. "
        f"The 'uncertain' tier (n=9) is dropped everywhere as too small to plot. "
        f"PRELIMINARY - {n_real_total} of ~5,128 swept, pre-QA-fix.",
        ha="center", va="bottom", fontsize=10, style="italic",
        color=COLORS["neutral"], wrap=True,
    )

    fig.tight_layout(rect=(0, 0.05, 1, 0.96))
    return fig, list(axes)


def main() -> None:
    fig, _ = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"),
                gist_url=GIST_URL)


if __name__ == "__main__":
    main()
