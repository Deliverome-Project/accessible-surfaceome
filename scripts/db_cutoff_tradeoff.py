"""Supp Fig 3 — DB cutoff recalibration tradeoff.

Five per-source subplots showing the universe-size / accuracy trade-off
across cutoff variants for each surface DB. The figure legitimately plots
BOTH initial (canonical ◆) and optimized (recommended ★) cutoff points —
this IS the recalibration tradeoff visualization.

DATA SOURCE — reads ``data/processed/triage_bench/db_cutoff_tradeoff_points.tsv``
(precomputed points; do NOT recompute here — the TSV is the single source of
truth shared with the gist mirror
``data/analysis/figures/make_db_cutoff_tradeoff.py``).

Run: ``uv run python scripts/db_cutoff_tradeoff.py``
# Reproduction: https://gist.github.com/beccajcarlson/f9319af882e372194bd30640c0cbf2ed
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator

from accessible_surfaceome.audit._plotting_config import save_figure, setup_plotting_style

REPO = Path(__file__).resolve().parents[1]
DATA_TSV = REPO / "data/processed/triage_bench/db_cutoff_tradeoff_points.tsv"
OUT_DIR = REPO / "data/analysis/figures"
GIST_URL = "https://gist.github.com/beccajcarlson/f9319af882e372194bd30640c0cbf2ed"

# ──── Brand tokens ────────────────────────────────────────────────────────────
BRAND_INK = "#1F1718"
BRAND_NEUTRAL = "#6F5D5A"
BRAND_SEQUENTIAL = {
    "maroon":   ["#3E0A18", "#6E1428", "#922038", "#BC3C4C", "#F0A098", "#FDE8E6"],
    "teal":     ["#152E28", "#244840", "#3D6B60", "#4D8A80", "#7AAB9F", "#CCE8E4"],
    "amber":    ["#5A2608", "#8C4210", "#C07830", "#F4AA28", "#F4C070", "#FAECD4"],
    "lavender": ["#1E1450", "#3A2888", "#5848A8", "#8878C8", "#A090D4", "#E4E0F8"],
}

GROUP_ORDER = ["UniProt", "GO", "HPA", "SURFY", "CSPA"]
# Per-DB sequential ramps, light → dark = strict → permissive.
GROUP_RAMP = {
    "UniProt": [BRAND_SEQUENTIAL["maroon"][i]   for i in (1, 2, 3, 4)],
    "GO":      [BRAND_SEQUENTIAL["teal"][i]     for i in (1, 2, 4)],
    "HPA":     [BRAND_SEQUENTIAL["amber"][i]    for i in (1, 3, 4)],
    "SURFY":   [BRAND_SEQUENTIAL["lavender"][i] for i in (1, 2, 3, 4)],
    "CSPA":    [BRAND_SEQUENTIAL["maroon"][i]   for i in (1, 3, 4)],
}
RECOMMENDED_EDGE = BRAND_SEQUENTIAL["teal"][1]  # teal-deep
CANONICAL_EDGE = BRAND_INK

SHORT_LABEL = {
    "UniProt strict-only\n(4 subcell terms)":              "strict-4",
    "UniProt baseline":                                    "canonical",
    "UniProt TM-or-signal-or-surface\n(topology proxy)":   "TM+signal",
    "UniProt permissive\n(incl. plain Cell membrane)":     "permissive",
    "GO experimental+curated":                             "exp+curated",
    "GO baseline":                                         "canonical",
    "GO permissive\n(incl. IEA-only)":                     "+ IEA",
    "HPA Enhanced-only\n(strictest tier)":                 "Enhanced",
    "HPA baseline":                                        "canonical",
    "HPA + Uncertain tier":                                "+ Uncertain",
    "SURFY score>0.9":                                     ">0.9",
    "SURFY score>0.7":                                     ">0.7",
    "SURFY score>0.5":                                     ">0.5",
    "SURFY baseline":                                      "canonical",
    "CSPA high-conf only":                                 "HC-only",
    "CSPA baseline":                                       "canonical",
    "CSPA + unspecific":                                   "+ unspecific",
}


def _log_tick_label(x: float, _pos: int) -> str:
    """Human-readable label for log-scale x-axis ticks.

    Examples: 100 → "100", 200 → "200", 500 → "500", 1000 → "1k",
    1500 → "1.5k", 2000 → "2k", 5000 → "5k", 10000 → "10k". Half-decimal
    precision in the "k" range so 1k / 1.5k / 2k are visually distinct.
    """
    if x < 1000:
        return f"{int(x)}"
    k = x / 1000
    if abs(k - round(k)) < 0.05:
        return f"{int(round(k))}k"
    return f"{k:.1f}k"


def _nice_log_ticks(lo: float, hi: float, *, min_ticks: int = 3) -> list[float]:
    """Pick ≥``min_ticks`` "round" log-spaced tick positions within [lo, hi].

    Tier 1: 1×, 2×, 5× per decade (the standard log-axis choice). This
    covers wide ranges nicely (HPA 60→4400 gets 100/200/500/1k/2k).

    Tier 2: 1×, 1.5×, 2×, 3×, 5×, 7× per decade. Falls back to this finer
    grid when the panel's range is too narrow for tier 1 to land
    ``min_ticks`` inside it (CSPA 577→2686 gets 1k/1.5k/2k, GO 1015→4603
    gets 1.5k/2k/3k/5k).
    """
    lo_dec = math.floor(math.log10(lo))
    hi_dec = math.ceil(math.log10(hi))

    def gen(subs: tuple[float, ...]) -> list[float]:
        out: list[float] = []
        for d in range(lo_dec - 1, hi_dec + 1):
            for s in subs:
                t = s * 10**d
                if lo <= t <= hi and t not in out:
                    out.append(t)
        return out

    ticks = gen((1, 2, 5))
    if len(ticks) < min_ticks:
        ticks = gen((1, 1.5, 2, 3, 5, 7))
    return ticks


def main() -> None:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    # Match the gist mirror's layout fingerprint (tests/test_figure_canonical_mirror_sync).
    plt.rcParams.update({
        "axes.labelsize": 20,
        "xtick.labelsize": 20,
        "ytick.labelsize": 20,
        "legend.fontsize": 20,
        "axes.titlesize": 0,
        "font.size": 20,
    })

    df = pd.read_csv(DATA_TSV, sep="\t")

    # Wider + taller than v2's (13, 11): v2's panels were noticeably taller
    # than wide (≈4.3"w × 5.5"h each). (19, 13) gives ≈6.3"w × 6.5"h —
    # near-square. Extra height also makes room for the per-panel caption
    # block to breathe under v2's larger caption fontsize.
    fig, axes = plt.subplots(2, 3, figsize=(19, 13))
    axes_flat = axes.flatten()

    for gi, group in enumerate(GROUP_ORDER):
        ax = axes_flat[gi]
        pts = df[df["group"] == group].sort_values("size").to_dict("records")
        ramp = GROUP_RAMP.get(group, [BRAND_NEUTRAL])

        # Strictness-ladder line.
        ax.plot(
            [p["size"] for p in pts],
            [p["acc"] * 100 for p in pts],
            color=ramp[0],
            linewidth=1.6,
            alpha=0.5,
            zorder=2,
        )

        caption_lines = []
        for idx, p in enumerate(pts):
            color = ramp[min(idx, len(ramp) - 1)]
            if p.get("recommended"):
                marker, msize, edge = "*", 480, RECOMMENDED_EDGE
                marker_char = "★"
            elif p.get("canonical"):
                marker, msize, edge = "D", 200, CANONICAL_EDGE
                marker_char = "◆"
            else:
                marker, msize, edge = "o", 130, "white"
                marker_char = "●"
            ax.scatter(
                p["size"],
                p["acc"] * 100,
                marker=marker,
                s=msize,
                color=color,
                edgecolor=edge,
                linewidth=1.6,
                zorder=4,
            )
            short = SHORT_LABEL.get(p["label"], p["label"]).replace("\n", " ")
            caption_lines.append(
                f"{marker_char}  {short:<14}  n={int(p['size']):>5,}   +{p['pos'] * 100:.0f}/-{p['neg'] * 100:.0f}"
            )

        ax.set_xscale("log")
        ax.text(
            0.02,
            0.97,
            group,
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=20,
            fontweight="bold",
            color=ramp[0],
        )
        ax.set_ylim(25, 102)
        xs = [p["size"] for p in pts]
        if xs:
            ax.set_xlim(max(40, min(xs) / 1.8), max(xs) * 1.8)
        # Tick set must be computed AFTER set_xlim so the adaptive locator
        # sees the actual panel range — narrow ranges fall back to a finer
        # 1×/1.5×/2×/3×/5×/7× per-decade grid to guarantee ≥3 labels.
        lo, hi = ax.get_xlim()
        tick_positions = _nice_log_ticks(lo, hi, min_ticks=3)
        ax.xaxis.set_major_locator(FixedLocator(tick_positions))
        ax.xaxis.set_major_formatter(FuncFormatter(_log_tick_label))
        ax.xaxis.set_minor_locator(NullLocator())
        sns.despine(ax=ax, top=True, right=True)

        # Per-panel caption block — one line per cutoff variant, marker
        # char doubles as the visual key for matching to on-plot points.
        # Monospace so columns align; tiny enough that even DejaVu Sans
        # Mono fallback reads cleanly on systems without a brand mono.
        ax.text(
            0.0,
            -0.30,
            "\n".join(caption_lines),
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=15,
            color=BRAND_INK,
            family="monospace",
        )

    # 6th cell: marker-shape key + missing-rule footnote.
    legend_ax = axes_flat[5]
    legend_ax.axis("off")
    handles = [
        plt.Line2D(
            [],
            [],
            marker="o",
            linestyle="",
            color=BRAND_NEUTRAL,
            markersize=11,
            markeredgecolor="white",
            markeredgewidth=1.4,
            label="Alternative cutoff (not used)",
        ),
        plt.Line2D(
            [],
            [],
            marker="D",
            linestyle="",
            color=BRAND_NEUTRAL,
            markersize=12,
            markeredgecolor=CANONICAL_EDGE,
            markeredgewidth=1.4,
            label="Canonical (current merge rule)",
        ),
        plt.Line2D(
            [],
            [],
            marker="*",
            linestyle="",
            color=BRAND_NEUTRAL,
            markersize=20,
            markeredgecolor=RECOMMENDED_EDGE,
            markeredgewidth=1.4,
            label="Recommended after trade-off audit",
        ),
    ]
    legend_ax.legend(
        handles=handles,
        loc="upper center",
        fontsize=20,
        frameon=False,
        title="Marker shape",
        title_fontsize=20,
    )

    fig.supxlabel(
        "Universe size — proteins this filter would admit "
        "(log scale; lower = stricter)",
        fontsize=20,
        y=0.02,
        color=BRAND_INK,
    )
    # supylabel y defaults to 0.5 (figure midline) which is what reads as
    # "centered" against the supxlabel's default x=0.5. Earlier overrides
    # to 0.54 (axes-content midpoint) and the dynamic equivalent were
    # technically correct but visually off — keep the matplotlib default.
    # x=0.02 just keeps the rotated label off the canvas-left edge under
    # brand-style-v3's larger axes.labelsize.
    fig.supylabel(
        "Accuracy on\n147-gene benchmark (%)",
        fontsize=20,
        x=0.02,
        color=BRAND_INK,
    )
    plt.tight_layout(rect=[0.04, 0.03, 1, 0.985])
    # Vertical gap between row-1 panels (with caption blocks BELOW them at
    # axes-y=-0.30, extending further for the longest panel — 6 variants
    # × ~22pt line height) and row-2 panels. Without this, row-1 captions
    # crash into row-2 axes / row-2 captions extend into the supxlabel.
    # Bumped 0.95 → 1.40 to give room for the now-larger (19, 13) figure +
    # the recommended-cutoff line (★) below the canonical line (◆) in
    # each panel.
    plt.subplots_adjust(hspace=1.40)

    save_figure(fig, "db_cutoff_tradeoff", OUT_DIR, gist_url=GIST_URL)
    print(
        f"Wrote db_cutoff_tradeoff.{{pdf,png}} to {OUT_DIR}  "
        f"({len(df)} cutoff variants across {df['group'].nunique()} DBs)"
    )


if __name__ == "__main__":
    main()
