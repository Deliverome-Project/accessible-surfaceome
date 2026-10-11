"""Supplementary Figure 4 — DB cutoff recalibration tradeoff.

Five per-source subplots showing the universe-size / accuracy trade-off
across cutoff variants for each surface DB. The figure legitimately plots
BOTH the original pre-audit rule (◆, "Original rule") and the rule adopted
after the benchmark audit (★, "Adopted after benchmark audit"; UniProt and
CSPA only; the candidate-universe vote now uses these) — this IS the
recalibration tradeoff visualization. Circles are other cutoffs evaluated
and not adopted.

DATA SOURCE — reads ``data/processed/triage_bench/db_cutoff_tradeoff_points.tsv``
(precomputed points; do NOT recompute here — the TSV is the single source of
truth shared with the gist mirror
``data/analysis/figures/make_db_cutoff_tradeoff.py``). The TSV is a committed
artifact; regenerate it deliberately with ``_dump_db_cutoff_tradeoff_points``
in ``scripts/figures/triage_bench_db_barplot.py``. HPA abstains on benchmark
proteins it has no data for, so its panel is scored on the 98 it covers.

Run: ``uv run python scripts/figures/db_cutoff_tradeoff.py``
# Reproduction: https://gist.github.com/beccajcarlson/f9319af882e372194bd30640c0cbf2ed
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator
from matplotlib.transforms import offset_copy

from accessible_surfaceome.audit._plotting_config import save_figure, setup_plotting_style

REPO = Path(__file__).resolve().parents[2]
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
# Per-DB sequential ramps, dark → light = strict → permissive.
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
    "UniProt baseline":                                    "original",
    "UniProt TM-or-signal-or-surface\n(topology proxy)":   "TM+signal",
    "UniProt permissive\n(incl. plain Cell membrane)":     "permissive",
    "GO experimental+curated":                             "exp+curated",
    "GO baseline":                                         "original",
    "GO permissive\n(incl. IEA-only)":                     "+ IEA",
    "HPA Enhanced-only\n(strictest tier)":                 "Enhanced",
    "HPA baseline":                                        "original",
    "HPA + Uncertain tier":                                "+ Uncertain",
    "SURFY score>0.9":                                     ">0.9",
    "SURFY score>0.7":                                     ">0.7",
    "SURFY score>0.5":                                     ">0.5",
    "SURFY baseline":                                      "original",
    "CSPA high-conf only":                                 "HC-only",
    "CSPA baseline":                                       "original",
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
        "axes.labelsize": 18,
        "xtick.labelsize": 16,
        "ytick.labelsize": 16,
        "legend.fontsize": 16,
        "axes.titlesize": 0,
        "font.size": 16,
    })

    df = pd.read_csv(DATA_TSV, sep="\t")

    # Sized for print at ~7 in wide (fonts here are ~2x their printed size).
    fig, axes = plt.subplots(2, 3, figsize=(14, 11))
    axes_flat = axes.flatten()

    # Per-panel key under each axes: one row per cutoff variant, its marker
    # drawn in the point's own colour. Columns: short label, universe size,
    # +% surface proteins recovered / -% non-surface proteins correctly
    # excluded. Placed in points from the axes' bottom-left corner, with
    # fixed columns so the numbers align.
    key_fs = 14
    key_line_pt = key_fs * 1.5
    # Clears the x tick labels AND the per-panel x axis title beneath
    # them; the title was added when the figure-level supxlabel was
    # dropped, and at -48 the key's first row landed on top of it.
    key_top_pt = -80
    key_x_pt = {"marker": 6, "label": 18, "n": 192, "acc": 202}

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

        for idx, p in enumerate(pts):
            color = ramp[min(idx, len(ramp) - 1)]
            if p.get("recommended"):
                marker, msize, edge = "*", 380, RECOMMENDED_EDGE
            elif p.get("canonical"):
                marker, msize, edge = "D", 160, CANONICAL_EDGE
            else:
                marker, msize, edge = "o", 100, "white"
            ax.scatter(
                p["size"],
                p["acc"] * 100,
                marker=marker,
                s=msize,
                color=color,
                edgecolor=edge,
                linewidth=1.4,
                zorder=4,
            )

            y_pt = key_top_pt - idx * key_line_pt

            def _at(x_pt: float, y_pt: float = y_pt, ax=ax):
                return offset_copy(ax.transAxes, fig=fig, x=x_pt, y=y_pt, units="points")

            ax.scatter(
                [0], [0], marker=marker, s=max(msize * 0.35, 60), color=color,
                edgecolor=edge, linewidth=1.0, transform=_at(key_x_pt["marker"]),
                clip_on=False, zorder=5,
            )
            short = SHORT_LABEL.get(p["label"], p["label"]).replace("\n", " ")
            for col, text, ha in (
                ("label", short, "left"),
                ("n", f"n={int(p['size']):,}", "right"),
                ("acc", f"+{p['pos'] * 100:.0f}/-{p['neg'] * 100:.0f}", "left"),
            ):
                ax.text(
                    0, 0, text, transform=_at(key_x_pt[col]),
                    ha=ha, va="center", fontsize=key_fs, color=BRAND_INK,
                )

        ax.set_xscale("log")
        ax.text(
            0.03,
            0.97,
            group,
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=18,
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

    # 6th cell: marker-shape key.
    legend_ax = axes_flat[5]
    legend_ax.axis("off")
    handles = [
        plt.Line2D(
            [],
            [],
            marker="o",
            linestyle="",
            color=BRAND_NEUTRAL,
            markersize=10,
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
            markersize=10,
            markeredgecolor=CANONICAL_EDGE,
            markeredgewidth=1.4,
            label="Original rule",
        ),
        plt.Line2D(
            [],
            [],
            marker="*",
            linestyle="",
            color=BRAND_NEUTRAL,
            markersize=17,
            markeredgecolor=RECOMMENDED_EDGE,
            markeredgewidth=1.4,
            label="Adopted after\nbenchmark audit",
        ),
    ]
    legend_ax.legend(
        handles=handles,
        loc="upper left",
        fontsize=16,
        frameon=False,
        title="Marker shape",
        title_fontsize=18,
        alignment="left",
        labelspacing=0.9,
    )

    # Per-panel axis titles rather than fig.supxlabel/supylabel. Each
    # subplot carries its own key block underneath, so the panels are not a
    # contiguous grid: supylabel centres on the FIGURE, which put the y title
    # in the gap between the two rows instead of beside the axes, and
    # supxlabel sat below the second row's key — nowhere near the top row's
    # x axis, leaving those three panels effectively untitled. Short titles
    # keep the repetition quiet; the caption carries the full definition.
    # No fontsize/fontweight/color here on purpose: axes.labelsize (18),
    # axes.labelweight (semibold) and axes.labelcolor (#1F1718, identical to
    # BRAND_INK) all come from the shared type scale, so these titles track it
    # if it moves again. Hardcoding 16 here would quietly undercut the scale.
    for ax in axes_flat[:len(GROUP_ORDER)]:
        ax.set_xlabel("Universe size (proteins)", labelpad=6)
        ax.set_ylabel("Accuracy (%)", labelpad=6)
    # tight_layout counts the per-panel key text, so the row gap and
    # bottom margin make room for it.
    plt.tight_layout(rect=[0.03, 0.025, 1, 1], h_pad=1.5)

    save_figure(fig, "db_cutoff_tradeoff", OUT_DIR, gist_url=GIST_URL)
    print(
        f"Wrote db_cutoff_tradeoff.{{pdf,png}} to {OUT_DIR}  "
        f"({len(df)} cutoff variants across {df['group'].nunique()} DBs)"
    )


if __name__ == "__main__":
    main()
