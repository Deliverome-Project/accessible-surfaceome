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

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"
POINTS_URL = (
    f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
    f"/data/processed/triage_bench/db_cutoff_tradeoff_points.tsv"
)

# Published reproduction gist (embedded into output PNG Source / PDF
# Subject metadata — mirrors save_figure in _plotting_config.py).
GIST_URL = "https://gist.github.com/beccajcarlson/f9319af882e372194bd30640c0cbf2ed"

# ──── Inline brand styling — sentinel: brand-style-v1 ────
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
            for ttf in sorted(fonts_dir.glob("*.ttf")):
                try:
                    fm.fontManager.addfont(str(ttf))
                except Exception:  # noqa: BLE001
                    continue
            return


def _apply_brand_style() -> None:
    """Inline equivalent of `setup_plotting_style`. Sentinel: brand-style-v1."""
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
        "font.size": 17,
        "axes.labelsize": 19,
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

    # Taller figure now that per-variant info moved to caption blocks
    # below each panel — needs vertical room for the captions.
    fig, axes = plt.subplots(2, 3, figsize=(13, 11))
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
                ha="left", va="top", fontsize=19, fontweight="bold",
                color=ramp[0])
        ax.set_ylim(25, 102)
        xs = [p["size"] for p in pts]
        if xs:
            ax.set_xlim(max(40, min(xs) / 1.8), max(xs) * 1.8)
        sns.despine(ax=ax, top=True, right=True)

        # Per-panel caption block — one line per cutoff variant, marker
        # char doubles as the visual key for matching to on-plot points.
        # Monospace so columns align; tiny enough that even DejaVu Sans
        # Mono fallback reads cleanly on systems without a brand mono.
        ax.text(
            0.0, -0.30, "\n".join(caption_lines),
            transform=ax.transAxes,
            ha="left", va="top",
            fontsize=12, color=BRAND_INK,
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
    legend_ax.legend(handles=handles, loc="upper center", fontsize=16,
                     frameon=False, title="Marker shape",
                     title_fontsize=17)
    legend_ax.text(
        0.5, 0.10,
        "Per-source missing rule:\n"
        "UniProt / GO / SURFY / CSPA absence → predict 'no'.\n"
        "HPA absence → abstain.",
        transform=legend_ax.transAxes, ha="center", va="bottom",
        fontsize=13, color=BRAND_NEUTRAL,
    )

    fig.supxlabel("Universe size — proteins this filter would admit "
                  "(log scale; lower = stricter)", fontsize=16, y=0.02,
                  color=BRAND_INK)
    fig.supylabel("Accuracy on 147-gene benchmark (%)", fontsize=16, x=0.005,
                  color=BRAND_INK)
    plt.tight_layout(rect=[0.015, 0.03, 1, 0.985])
    # Add vertical space between row 1 panels (which have captions below
    # them) and row 2 panels (whose top edge would otherwise crash into
    # row 1's caption).
    plt.subplots_adjust(hspace=0.55)

    out_pdf = Path("db_cutoff_tradeoff.pdf")
    out_png = Path("db_cutoff_tradeoff.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=300, metadata={"Source": GIST_URL})
    print(f"Wrote {out_pdf} + {out_png}  ({len(df)} cutoff variants across {df['group'].nunique()} DBs)")


if __name__ == "__main__":
    main()
