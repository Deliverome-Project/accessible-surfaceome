"""Deep-dive final categorization — two panels.

**a.** The deep-dive cohort placed on a five-tier confidence spectrum —
``canonical`` (strict gold-standard surface), ``likely`` (broader passes-likely
surface), then the below-likely genes split by the deep-dive's tentative
surface call: ``low`` (low/moderate accessibility but weak evidence — maybe
surface), ``uncertain``, and ``no`` (leaned not-surface). A slim strip under
each bar splits the tier by the call's confidence (high / moderate / low),
which applies to the call in either direction — the ``no`` tier carries it too.

**b.** The two cross-cutting surface facets — cell-type restricted and
cell-state induced (split oncogenic vs. other) — counted by surface-call
REASON and broken out across the three populated tiers (canonical / likely /
low). Counting by reason rather than the evidence-gated facet keeps
weak-evidence genes that still carry a surface call: the ``low`` tier
contributes 471 cell-type-restricted and 178 induced genes that the gated
facet drops (the gated column totals 852 and 454 respectively). Totals
across the three tiers on the 5,332-record cohort: cell-type restricted
1,323 (852 likely + 471 low); induced 632 (434 oncogenic, 198 other).

Bucket predicates delegate to ``accessible_surfaceome.release.catalog_presets``
via ``scripts/build_figure_tsvs.py`` (``_dd_passes_*``); canonical/likely == the
catalog presets, and the low/uncertain/no split of the negatives is a
figure-only refinement (the presets don't cover the negatives).

Full deep-dive cohort (5,332 genes); canonical uses the PR #130 gate.

# Reproduction:
#   Public gist (reader-side standalone, PyPA inline-script-metadata deps):
#   https://gist.github.com/beccajcarlson/c2441f8d0314c5524463bc85a3e86612
#   Reader-side mirror: data/analysis/figures/make_deep_dive_final_categories.py

Run:
    uv run python scripts/figures/deep_dive_final_categories.py
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.transforms import ScaledTranslation, blended_transform_factory
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import (
    COLORS,
    save_figure,
    setup_plotting_style,
)

ROOT = Path(__file__).resolve().parents[2]
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

# Panel a's confidence strip: the share of each tier's calls made at high /
# moderate / low confidence. Confidence is certainty in the call in EITHER
# direction, so the `no` tier carries it too (a reviewer asked exactly this).
# Neutral greys, darker = more confident, so the strip never competes with the
# tier colours above it.
_CONFIDENCES: list[tuple[str, str]] = [
    ("high", "#5B4E4B"),
    ("moderate", "#A3958F"),
    ("low", "#DDD3CD"),
]

# Panel-b: the cross-cutting surface facets counted by surface-call REASON
# (option B), broken out across the three populated tiers. Three stacked
# categories per tier: cell-type restricted (tissue_restricted_surface),
# induced-oncogenic (cell_state_induced / lysosomal_exocytosis with an
# oncogenic trigger) and induced-other (any other induction trigger). Counting
# by reason keeps weak-evidence surface calls that land in the `low` tier,
# which the evidence-gated facet would drop.
_PANELB_TIERS = ["canonical", "likely", "low"]
_TIER_LABEL_COLORS = {
    "canonical": _COLOR_CANONICAL,
    "likely": _COLOR_LIKELY,
    "low": _COLOR_LOW,
}
_INDUCED_REASONS = {"cell_state_induced", "lysosomal_exocytosis"}
_PANELB_CATS: list[tuple[str, str]] = [
    ("Cell-type restricted", "#5848A8"),    # lavender-mid
    ("Induced — oncogenic", "#BC3C4C"),     # maroon-light
    ("Induced — other", "#F4AA28"),         # amber-bright
    ("Other surface reason", "#E6DAD4"),    # warm neutral
]
# Hues panel a does not use (its tiers are green / teal / tan / greys), so the
# two panels' colours never read as the same category. Segment counts are
# printed in white on the dark hues and in ink on the light ones.
_PANELB_LIGHT = {"Induced — other", "Other surface reason"}


def _panelb_category(reason: str, trigger: str) -> str:
    """Map a (surface_call_reason, induction_trigger) pair to its Panel-b
    category: one of the three cross-cutting facets, or the neutral remainder
    for every other surface-call reason."""
    if reason == "tissue_restricted_surface":
        return "Cell-type restricted"
    if reason in _INDUCED_REASONS:
        return "Induced — oncogenic" if trigger == "oncogenic" else "Induced — other"
    # Any other surface-call reason (classical receptor, multipass, GPI,
    # dual localization, ...) — so each bar totals to its panel-a tier.
    return "Other surface reason"


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


def _read_confidence() -> dict[str, dict[str, int]]:
    """Panel a strip: ``{tier: {confidence: n_genes}}`` from the per-gene TSV."""
    out: dict[str, dict[str, int]] = {}
    with open(DATA_TSV) as f:
        for row in csv.DictReader(f, delimiter="\t"):
            conf = out.setdefault(row["category"], {})
            conf[row["confidence"]] = conf.get(row["confidence"], 0) + 1
    return out


def _panel_label(ax, letter: str) -> None:
    ax.text(-0.02, 1.06, letter, transform=ax.transAxes, fontsize=27,
            fontweight=800, va="bottom", ha="right", color=COLORS["dark"])



# Which tiers roll up to one surface call. `uncertain` is deliberately NOT
# folded in with `no`: all 55 carry evidence_grade=weak, state_dependence
# =unclear, a median of 0 selected papers (39 of 55 have none), and are
# mostly orphan ORFs. The agent declined to call them, which is a different
# statement from calling them non-surface, and a bracket reading "not
# surface" over them would assert something the evidence does not support.
_TIER_GROUPS = [
    ((0, 2), "surface"),
    ((3, 3), "undetermined"),
    ((4, 4), "not\nsurface"),  # wrapped: one line collides with "undetermined"
]


def _tier_group_brackets(ax) -> None:
    """Draw grouping brackets under panel a's tick labels.

    x in data coords (so the bracket tracks the bars); y a fixed number of
    points below the bottom of ``ax`` (the confidence strip, which carries the
    tick labels), so the brackets clear the labels whatever the strip's
    height. Drawn with clip_on=False because they live outside the axes box.
    """
    def below(points: float):
        return blended_transform_factory(ax.transData, ax.transAxes) + ScaledTranslation(
            0, -points / 72, ax.figure.dpi_scale_trans)

    def segment(xa, pa, xb, pb):
        ax.annotate("", xy=(xb, 0), xycoords=below(pb), xytext=(xa, 0),
                    textcoords=below(pa), annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=COLORS["neutral"], lw=1.4,
                                    shrinkA=0, shrinkB=0))

    y_bar, y_txt, tick = 45, 53, 6
    for (i0, i1), label in _TIER_GROUPS:
        x0, x1 = i0 - 0.37, i1 + 0.37
        segment(x0, y_bar, x1, y_bar)
        for x in (x0, x1):
            segment(x, y_bar, x, y_bar - tick)
        ax.text((x0 + x1) / 2, 0, label, transform=below(y_txt), ha="center",
                va="top", fontsize=16, color=COLORS["neutral"])


def make_plot() -> tuple[plt.Figure, tuple[plt.Axes, plt.Axes]]:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    plt.rcParams.update({
        "font.size": 20, "axes.labelsize": 20, "axes.titlesize": 0,
        "xtick.labelsize": 18, "ytick.labelsize": 18, "legend.fontsize": 18,
    })
    data = _read()
    canon = sum(data.get("canonical", {}).values())
    likely = data.get("likely", {})
    likely_total = sum(likely.values())
    low_total = sum(data.get("low", {}).values())
    unc_total = sum(data.get("uncertain", {}).values())
    no_total = sum(data.get("no", {}).values())

    fig = plt.figure(figsize=(18, 6.6))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.45, 1.35], wspace=0.18)
    # Panel a = the tier bars over a slim confidence strip that carries the
    # tick labels; panel b spans the full height.
    gsA = gs[0, 0].subgridspec(2, 1, height_ratios=[1, 0.13], hspace=0.06)
    axA = fig.add_subplot(gsA[0])
    axS = fig.add_subplot(gsA[1], sharex=axA)
    axB = fig.add_subplot(gs[0, 1])

    # ── Panel a: the five-tier confidence spectrum ──────────────────────────
    tiers = [
        ("canonical", canon, _COLOR_CANONICAL),
        ("likely", likely_total, _COLOR_LIKELY),
        ("low", low_total, _COLOR_LOW),
        # `uncertain` sits BETWEEN the positive and negative sides, not at
        # the end: it is the least-confident point on the axis, and
        # confidence rises outward from it in both directions (reviewer
        # note). Putting it last implied it was a weaker `no`, which it is
        # not — the agent declined to call these, it did not call them
        # negative.
        ("uncertain", unc_total, _COLOR_UNCERTAIN),
        ("no", no_total, _COLOR_NO),
    ]
    tier_max = max(t[1] for t in tiers)
    for i, (label, n, color) in enumerate(tiers):
        axA.bar(i, n, width=0.74, color=color, edgecolor="none")
        axA.text(i, n + tier_max * 0.02, f"{n:,}", ha="center", va="bottom",
                 fontsize=16.5, color=COLORS["dark"])
    axA.set_ylabel("Proteins in\ndeep-dive cohort")
    # Panel b labels its axis and panel a did not, which reads as an
    # oversight when the two sit side by side (reviewer note). "Surface
    # tier" rather than "confidence tier": canonical / likely / low are
    # confidence in a surface call, but `no` and `uncertain` are the
    # absence of one, so calling the whole axis a confidence scale would
    # mislabel two of its five categories.
    axA.set_ylim(0, tier_max * 1.16)
    axA.set_xlim(-0.6, len(tiers) - 0.4)
    axA.tick_params(axis="x", labelbottom=False, length=0)
    sns.despine(ax=axA, top=True, right=True)
    _panel_label(axA, "a")

    # Confidence strip: one 100% bar per tier, the same width as the bar
    # above it, split high / moderate / low. No numbers in the segments: the
    # `no` tier's high share (35%) is too narrow to hold one legibly, and the
    # counts are in the legend text.
    conf = _read_confidence()
    for i, (label, _n, _color) in enumerate(tiers):
        counts = conf.get(label, {})
        total = sum(counts.values()) or 1
        left = i - 0.37
        for name, shade in _CONFIDENCES:
            w = 0.74 * counts.get(name, 0) / total
            if w <= 0:
                continue
            axS.barh(0, w, left=left, height=0.86, color=shade,
                     edgecolor="white", linewidth=1.0)
            left += w
    axS.set_ylim(-0.5, 0.5)
    axS.set_yticks([0], ["call\nconfidence"], fontsize=14)
    axS.set_xticks(range(len(tiers)), [t[0] for t in tiers])
    # The three surface tiers take their bar colour, here and in panel b, so
    # the reader can match the two panels' bars by label colour alone.
    for tick, (name, _n, color) in zip(axS.get_xticklabels(), tiers):
        if name in _TIER_LABEL_COLORS:
            tick.set_color(color)
    axS.tick_params(axis="both", length=0)
    axS.grid(False)
    sns.despine(ax=axS, left=True, bottom=True)
    axS.set_xlabel("Deep-dive surface tier", labelpad=84)
    _tier_group_brackets(axS)
    axA.legend(
        handles=[mpatches.Patch(color=shade, label=name) for name, shade in _CONFIDENCES],
        title="Call confidence (strip)", loc="upper right", frameon=False,
        fontsize=15.5, title_fontsize=15.5, handlelength=1.1, labelspacing=0.3,
    )

    # ── Panel b: surface facets by REASON, across the three populated tiers ──
    # Cell-type restricted and cell-state induced (split oncogenic vs. other)
    # counted by surface-call reason (option B), so weak-evidence surface calls
    # in the `low` tier are retained. One vertical stacked bar per tier
    # (canonical / likely / low), matching panel a's confidence spectrum.
    tier_cats = _read_tier_categories()
    # Vertical, tiers left to right in panel a's order and on panel a's y
    # scale, so each stacked bar sits beside the panel-a bar it decomposes.
    x_pos = list(range(len(_PANELB_TIERS)))
    col_totals = [sum(tier_cats[t].values()) for t in _PANELB_TIERS]
    bar_max = max(col_totals)
    for t, x in zip(_PANELB_TIERS, x_pos):
        bottom = 0.0
        for label, color in _PANELB_CATS:
            n = tier_cats[t][label]
            if n <= 0:
                continue
            axB.bar(x, n, bottom=bottom, width=0.62, color=color,
                    edgecolor="white", linewidth=1.0)
            if n >= bar_max * 0.06:
                axB.text(x, bottom + n / 2, f"{n:,}", va="center", ha="center",
                         fontsize=15.5,
                         color=COLORS["dark"] if label in _PANELB_LIGHT else "white")
            bottom += n
        axB.text(x, bottom + bar_max * 0.015, f"{bottom:,.0f}", va="bottom",
                 ha="center", fontsize=16.5, color=COLORS["dark"])
    axB.set_xticks(x_pos)
    axB.set_xticklabels(_PANELB_TIERS)
    for tick, name in zip(axB.get_xticklabels(), _PANELB_TIERS):
        tick.set_color(_TIER_LABEL_COLORS[name])
    axB.set_ylabel("Proteins (by surface-call reason)")
    axB.set_xlabel("Deep-dive surface tier")
    axB.set_ylim(axA.get_ylim())
    axB.set_yticks([t for t in axA.get_yticks() if t <= axA.get_ylim()[1]])
    axB.set_xlim(-0.6, len(_PANELB_TIERS) - 0.4)
    sns.despine(ax=axB, top=True, right=True)

    # Listed top-down in the order the segments stack (top of bar first).
    handles = [mpatches.Patch(color=color, label=label)
               for label, color in reversed(_PANELB_CATS)]
    # Above the plot area, clear of the bars and their totals (>= 13 pt floor).
    axB.legend(handles=handles, title="Surface-call reason",
               loc="lower right", bbox_to_anchor=(1.0, 1.0), frameon=False,
               fontsize=15.5, title_fontsize=16.5, handlelength=1.0,
               handletextpad=0.4, labelspacing=0.22)
    _panel_label(axB, "b")

    fig.tight_layout()

    # Panel b shares panel a's plot frame (same top and bottom, same y range)
    # so the bars compare directly; its tier labels and axis title stay close
    # under its own bars.
    pa, pb = axA.get_position(), axB.get_position()
    axB.set_position([pb.x0, pa.y0, pb.width, pa.height])
    return fig, (axA, axB)


def main() -> None:
    fig, _ = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"), gist_url=GIST_URL)


if __name__ == "__main__":
    main()
