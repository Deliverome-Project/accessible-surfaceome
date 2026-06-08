# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "pandas>=2.2",
#   "seaborn>=0.13",
#   "httpx>=0.27",
# ]
# ///
"""Reproduce ``db_cutoff_tradeoff.{pdf,png}`` from the public repo.

Five per-source subplots showing the universe-size / accuracy
trade-off across cutoff variants for each surface DB. Reads a tiny
precomputed-points TSV (raw-fetched), so the gist stays small.

Visual styling matches the in-repo `_plotting_config` (Deliverome
categorical palette + Manrope-when-available, per-DB sequential ramps
from BRAND_SEQUENTIAL). Inlined so the gist runs standalone.

Standalone — ``uv run make_db_cutoff_tradeoff.py``.
"""
from __future__ import annotations

import io
from pathlib import Path

import httpx
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator


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
    static Manrope-{regular,medium,semibold,bold}.otf files in assets/fonts/."""
    _register_brand_fonts()
    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=1.0)
    plt.rcParams.update({
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "figure.facecolor": "none",
        "savefig.facecolor": "none",
        "font.family": "sans-serif",
        "font.sans-serif": ["Manrope", "Outfit", "DejaVu Sans", "Liberation Sans", "Arial"],
        "font.weight": "medium",
        "font.size": 21,
        "axes.labelsize": 25,
        "axes.labelweight": "medium",
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
        "xtick.labelsize": 20,
        "ytick.labelsize": 20,
        "xtick.color": BRAND_INK,
        "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "legend.fontsize": 20,
        "patch.edgecolor": "none",
        "patch.linewidth": 0.0,
    })


GROUP_ORDER = ["UniProt", "GO", "HPA", "SURFY", "CSPA"]
# Per-DB sequential ramps, light → dark = strict → permissive. Pulled
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


def _fetch_tsv(url: str) -> pd.DataFrame:
    local = Path(__file__).resolve().parents[3] / url[len(f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/"):]
    if local.is_file():
        return pd.read_csv(local, sep="\t")
    r = httpx.get(url, timeout=30)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text), sep="\t")


def main() -> None:
    _apply_brand_style()
    df = _fetch_tsv(POINTS_URL)

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
        ax.plot([p["size"] for p in pts], [p["acc"] * 100 for p in pts],
                color=ramp[0], linewidth=1.6, alpha=0.5, zorder=2)

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
            ax.scatter(p["size"], p["acc"] * 100,
                       marker=marker, s=msize, color=color,
                       edgecolor=edge, linewidth=1.6, zorder=4)
            short = SHORT_LABEL.get(p["label"], p["label"]).replace("\n", " ")
            caption_lines.append(
                f"{marker_char}  {short:<14}  n={int(p['size']):>5,}   +{p['pos']*100:.0f}/-{p['neg']*100:.0f}"
            )

        ax.set_xscale("log")
        ax.text(0.02, 0.97, group, transform=ax.transAxes,
                ha="left", va="top", fontsize=24, fontweight="bold",
                color=ramp[0])
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
            0.0, -0.30, "\n".join(caption_lines),
            transform=ax.transAxes,
            ha="left", va="top",
            fontsize=15, color=BRAND_INK,
            family="monospace",
        )

    # 6th cell: marker-shape key + missing-rule footnote.
    legend_ax = axes_flat[5]
    legend_ax.axis("off")
    handles = [
        plt.Line2D([], [], marker="o", linestyle="", color=BRAND_NEUTRAL,
                   markersize=11, markeredgecolor="white",
                   markeredgewidth=1.4, label="Alternative cutoff (not used)"),
        plt.Line2D([], [], marker="D", linestyle="", color=BRAND_NEUTRAL,
                   markersize=12, markeredgecolor=CANONICAL_EDGE,
                   markeredgewidth=1.4, label="Canonical (current merge rule)"),
        plt.Line2D([], [], marker="*", linestyle="", color=BRAND_NEUTRAL,
                   markersize=20, markeredgecolor=RECOMMENDED_EDGE,
                   markeredgewidth=1.4, label="Recommended after trade-off audit"),
    ]
    legend_ax.legend(handles=handles, loc="upper center", fontsize=20,
                     frameon=False, title="Marker shape",
                     title_fontsize=21)

    fig.supxlabel("Universe size — proteins this filter would admit "
                  "(log scale; lower = stricter)", fontsize=20, y=0.02,
                  color=BRAND_INK)
    # supylabel y defaults to 0.5 (figure midline) which is what reads as
    # "centered" against the supxlabel's default x=0.5. Earlier overrides
    # to 0.54 (axes-content midpoint) and the dynamic equivalent were
    # technically correct but visually off — keep the matplotlib default.
    # x=0.02 just keeps the rotated label off the canvas-left edge under
    # brand-style-v3's larger axes.labelsize.
    fig.supylabel("Accuracy on\n147-gene benchmark (%)", fontsize=20,
                  x=0.02, color=BRAND_INK)
    plt.tight_layout(rect=[0.04, 0.03, 1, 0.985])
    # Vertical gap between row-1 panels (with caption blocks BELOW them at
    # axes-y=-0.30, extending further for the longest panel — 6 variants
    # × ~22pt line height) and row-2 panels. Without this, row-1 captions
    # crash into row-2 axes / row-2 captions extend into the supxlabel.
    # Bumped 0.95 → 1.40 to give room for the now-larger (19, 13) figure +
    # the recommended-cutoff line (★) below the canonical line (◆) in
    # each panel.
    plt.subplots_adjust(hspace=1.40)

    out_pdf = Path("db_cutoff_tradeoff.pdf")
    out_png = Path("db_cutoff_tradeoff.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=300, metadata={"Source": GIST_URL})
    print(f"Wrote {out_pdf} + {out_png}  ({len(df)} cutoff variants across {df['group'].nunique()} DBs)")


if __name__ == "__main__":
    main()
