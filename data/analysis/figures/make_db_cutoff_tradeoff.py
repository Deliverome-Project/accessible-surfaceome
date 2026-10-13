# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "pandas>=2.2",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``db_cutoff_tradeoff.{pdf,png}`` (Supplementary Figure 1).

Five per-source subplots showing the universe-size / accuracy
trade-off across cutoff variants for each surface DB. Reads a tiny
precomputed-points TSV: the copy bundled next to this script in the
gist first, falling back to the in-repo copy only when that is missing
(no network fetch), so the gist stays small and self-contained.

Visual styling matches the in-repo `_plotting_config` (Deliverome
categorical palette + Manrope-when-available, per-DB sequential ramps
from BRAND_SEQUENTIAL). Inlined so the gist runs standalone.

Standalone — ``uv run make_db_cutoff_tradeoff.py``.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator
from matplotlib.transforms import offset_copy


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

    Matplotlib's LogLocator(subs=(1,2,5), numticks=N) auto-falls-back to
    half-decade positions when the range is narrow, but does so without
    bound (GO ended up with 7 ticks at 1.5k/2k/2.5k/3k/3.5k/4k/4.5k —
    visually crowded). This helper bounds the output deterministically.
    """
    import math
    lo_dec = math.floor(math.log10(lo))
    hi_dec = math.ceil(math.log10(hi))
    def gen(subs):
        out = []
        for d in range(lo_dec - 1, hi_dec + 1):
            for s in subs:
                t = s * 10 ** d
                if lo <= t <= hi and t not in out:
                    out.append(t)
        return out
    ticks = gen((1, 2, 5))
    if len(ticks) < min_ticks:
        ticks = gen((1, 1.5, 2, 3, 5, 7))
    return ticks

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"
POINTS_URL = (
    f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
    f"/data/processed/triage_bench/db_cutoff_tradeoff_points.tsv"
)

# Published reproduction gist (embedded into output PNG Source / PDF
# Subject metadata — mirrors save_figure in _plotting_config.py).
GIST_URL = "https://gist.github.com/beccajcarlson/f9319af882e372194bd30640c0cbf2ed"

# ──── Inline brand styling — sentinel: brand-style-v3 ────
# Mirrors src/accessible_surfaceome/audit/_plotting_config.py so the gist
# stays self-contained. Kept in sync via tests/test_figure_gists_styling.py.
BRAND_PALETTE = [
    "#BC3C4C",  # maroon-light
    "#3D6B60",  # teal-mid
    "#F4AA28",  # amber-bright
    "#8878C8",  # lavender-bright
    "#6E1428",  # maroon-dark
    "#7AAB9F",  # teal-light
]
BRAND_SEQUENTIAL = {
    "maroon":   ["#3E0A18", "#6E1428", "#922038", "#BC3C4C", "#F0A098", "#FDE8E6"],
    "teal":     ["#152E28", "#244840", "#3D6B60", "#4D8A80", "#7AAB9F", "#CCE8E4"],
    "amber":    ["#5A2608", "#8C4210", "#C07830", "#F4AA28", "#F4C070", "#FAECD4"],
    "lavender": ["#1E1450", "#3A2888", "#5848A8", "#8878C8", "#A090D4", "#E4E0F8"],
}
BRAND_CLAUDE_ORANGE = "#d87851"
BRAND_INK = "#1F1718"
BRAND_NEUTRAL = "#6F5D5A"
BRAND_GRID = "#E6DAD4"


def _register_brand_fonts() -> None:
    candidates = [
        Path(__file__).resolve().parents[3] / "assets" / "fonts",
        Path.cwd() / "assets" / "fonts",
    ]
    for fonts_dir in candidates:
        if fonts_dir.is_dir():
            for path in sorted(list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf"))):
                try:
                    fm.fontManager.addfont(str(path))
                except Exception:  # noqa: BLE001
                    continue
            return


def _apply_brand_style() -> None:
    """Inline equivalent of `setup_plotting_style`. Sentinel: brand-style-v3.
    v2: bumped sizes ~25% + explicit medium weight (avoids ExtraLight default
    that matplotlib picks from the Manrope variable file). Companion to the
    static Manrope-{Regular,Medium,SemiBold,Bold}.ttf files in assets/fonts/."""
    _register_brand_fonts()
    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=1.0)
    plt.rcParams.update({
        "savefig.dpi": 600,
        "savefig.bbox": "tight",
        "figure.facecolor": "none",
        "savefig.facecolor": "none",
        "font.family": ["Manrope", "DejaVu Sans"],
        "font.sans-serif": ["Manrope", "Outfit", "DejaVu Sans", "Liberation Sans", "Arial"],
        "font.weight": "semibold",
        "font.size": 16,
        "axes.labelsize": 18,
        "axes.labelweight": "semibold",
        "axes.titlesize": 0,
        "axes.titlepad": 0,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "axes.edgecolor": BRAND_GRID,
        "axes.labelcolor": BRAND_INK,
        "axes.facecolor": "none",
        "text.color": BRAND_INK,
        "grid.alpha": 0.35,
        "grid.linestyle": "-",
        "grid.linewidth": 0.7,
        "grid.color": BRAND_GRID,
        "xtick.labelsize": 16,
        "ytick.labelsize": 16,
        "xtick.color": BRAND_INK,
        "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "legend.fontsize": 16,
        "patch.edgecolor": "none",
        "patch.linewidth": 0.0,
    })


GROUP_ORDER = ["UniProt", "GO", "HPA", "SURFY", "CSPA"]
# Per-DB sequential ramps, dark → light = strict → permissive. Pulled
# from BRAND_SEQUENTIAL so the visual identity matches the rest of the
# figure set.
GROUP_RAMP = {
    "UniProt": [BRAND_SEQUENTIAL["maroon"][i]   for i in (1, 2, 3, 4)],
    "GO":      [BRAND_SEQUENTIAL["teal"][i]     for i in (1, 2, 4)],
    "HPA":     [BRAND_SEQUENTIAL["amber"][i]    for i in (1, 3, 4)],
    "SURFY":   [BRAND_SEQUENTIAL["lavender"][i] for i in (1, 2, 3, 4)],
    "CSPA":    [BRAND_SEQUENTIAL["maroon"][i]   for i in (1, 3, 4)],  # CSPA is maroon-family too — distinct from UniProt by darkness pattern
}
RECOMMENDED_EDGE = BRAND_SEQUENTIAL["teal"][1]  # teal-deep
CANONICAL_EDGE = BRAND_INK

# Short labels match the canonical generator.
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


def _fetch_tsv(url: str) -> pd.DataFrame:
    """Bundled-only: the gist HEAD commit SHA is the SWHID for the
    whole reproduction unit (script + data + README), so we must
    never read a *different* TSV than what's bundled. Sibling-first
    (gist case); fall back to the in-repo TSV path (dev case). No
    network fetch — a missing sibling in a gist is a hard error."""
    sibling = Path(__file__).parent / Path(url).name
    if sibling.is_file():
        return pd.read_csv(sibling, sep="\t")
    local = Path(__file__).resolve().parents[3] / url[len(f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/"):]
    if local.is_file():
        return pd.read_csv(local, sep="\t")
    raise FileNotFoundError(
        f"TSV not found at sibling ({sibling.name}) or local ({local}). "
        f"In a gist, the bundled TSV must sit next to this script."
    )


def main() -> None:
    _apply_brand_style()
    df = _fetch_tsv(POINTS_URL)

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

    out_pdf = Path("db_cutoff_tradeoff.pdf")
    out_png = Path("db_cutoff_tradeoff.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=600, metadata={"Source": GIST_URL})
    print(f"Wrote {out_pdf} + {out_png}  ({len(df)} cutoff variants across {df['group'].nunique()} DBs)")


if __name__ == "__main__":
    main()
