# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "pandas>=2.2",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``surface_evidence_assay_types.{pdf,png}`` — which methods
established the surface calls, and how often each one stood alone as the only
direct evidence.

Source is each deep-dive record's ``surface_evidence.methods`` block: one row
per experiment, judged **direct** (an antibody or probe reached the protein
from outside an intact cell) or **supporting** (places it at the plasma
membrane without showing the outside is reachable). Panel a counts genes with
direct evidence from each method (solid) and genes where it only reached the
supporting level (light). Panel b is the share of direct-evidence genes for
which the method was the only direct one. Color is assay family. Genes are
restricted to the canonical and likely deep-dive tiers.

The bundled sibling TSV is produced by ``scripts/build_figure_tsvs.py``
(``build_surface_evidence_assay_types``), which holds the category rules, so
this mirror renders the same dataset as the in-repo canonical.

Standalone — ``uv run make_surface_evidence_assay_types.py``.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.colors import to_rgb
from matplotlib.legend_handler import HandlerTuple

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"  # pin to a commit SHA at publication for immutable citation
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
# Single per-figure TSV: one row per method category. Gist bundles this TSV
# next to the script; the figure reads ONLY from the sibling.
DATA_TSV = f"{BASE}/data/processed/figures/surface_evidence_assay_types.tsv"

# Published reproduction gist (embedded into output PNG Source / PDF
# Subject metadata — mirrors save_figure in _plotting_config.py).
GIST_URL = "https://gist.github.com/beccajcarlson/141184baa53bc889d2c08692b931982b"

# ──── Inline brand styling — sentinel: brand-style-v3 ────
# Mirrors src/accessible_surfaceome/audit/_plotting_config.py so the gist
# stays self-contained (no in-repo imports — Substack readers run it
# standalone). Kept in sync via tests/test_figure_canonical_mirror_sync.py.
BRAND_INK = "#1F1718"
BRAND_PALETTE = [
    "#BC3C4C",  # maroon-light
    "#3D6B60",  # teal-mid
    "#F4AA28",  # amber-bright
    "#8878C8",  # lavender-bright
    "#6E1428",  # maroon-dark
    "#7AAB9F",  # teal-light
]
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
    """Inline equivalent of ``setup_plotting_style``. Sentinel: brand-style-v3."""
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
        "font.size": 14,
        "axes.labelsize": 15.5,
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
        "xtick.labelsize": 14,
        "ytick.labelsize": 15,
        "xtick.color": BRAND_INK,
        "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "legend.fontsize": 13.5,
        "patch.edgecolor": "none",
        "patch.linewidth": 0.0,
    })


def _fetch_tsv(url: str) -> pd.DataFrame:
    """Bundled-only: the gist HEAD commit SHA is the SWHID for the whole
    reproduction unit (script + data + README), so we must never read a
    *different* TSV than what's bundled. Sibling-first (gist case); fall
    back to the in-repo TSV path (dev case). No network fetch."""
    sibling = Path(__file__).parent / Path(url).name
    if sibling.is_file():
        return pd.read_csv(sibling, sep="\t")
    local = Path(__file__).resolve().parents[3] / url[len(BASE) + 1:]
    if local.is_file():
        return pd.read_csv(local, sep="\t")
    raise FileNotFoundError(
        f"TSV not found at sibling ({sibling.name}) or local ({local}). "
        f"In a gist, the bundled TSV must sit next to this script."
    )


# Below this many direct genes the panel-b share is dominated by its
# denominator (immunohistochemistry has 2), so it is printed as a count.
MIN_DIRECT_GENES = 25

LABEL = {
    "functional_surface_assay": "Functional surface assay",
    "flow_cytometry": "Flow cytometry",
    "immunofluorescence": "Immunofluorescence",
    "immunohistochemistry": "Immunohistochemistry",
    "surface_biotin_pulldown": "Surface biotin pulldown",
    "proximity_labeling": "Proximity labeling",
    "cell_surface_capture_ms": "Cell-surface capture MS",
    "other": "Other",
}
# Short gloss printed under the two catch-all labels.
DESC = {
    "functional_surface_assay": "toxin, antibody, ADC or CAR-T acting on\nlive cells; radioligand binding; shedding",
    "other": "cell-surface ELISA, CITE-seq tags,\nimmuno-EM, impermeable crosslinkers",
}
FAMILY_LABEL = {
    "imaging_cytometry": "Imaging and cytometry",
    "labeling_capture": "Surface labeling or capture",
    "functional": "Functional surface assay",
    "other": "Other",
}
FAMILY_COLOR = {
    "imaging_cytometry": "#3D6B60",  # teal-mid
    "labeling_capture": "#BC3C4C",   # maroon-light
    "functional": "#F4AA28",         # amber-bright
    "other": "#8878C8",              # lavender-bright
}


def tint(color: str, f: float = 0.6) -> tuple[float, float, float]:
    """Lighter shade of ``color`` for the supporting-only segment."""
    r, g, b = to_rgb(color)
    return (r + (1 - r) * f, g + (1 - g) * f, b + (1 - b) * f)


def load() -> pd.DataFrame:
    df = _fetch_tsv(DATA_TSV)
    df["label"] = df["method"].map(LABEL)
    df["color"] = df["family"].map(FAMILY_COLOR)
    df["pct_plot"] = df["pct_sole_direct"].where(df["genes_direct"] >= MIN_DIRECT_GENES, 0.0)
    # Rows follow panel b, highest at the top; barh draws index 0 at the
    # bottom, hence ascending. Direct count breaks ties.
    return df.sort_values(["pct_plot", "genes_direct"]).reset_index(drop=True)


def _panel_label(ax, letter: str) -> None:
    ax.text(-0.02, 1.02, letter, transform=ax.transAxes, fontsize=24,
            fontweight=800, va="bottom", ha="right", color=BRAND_INK)


def make_plot() -> tuple[plt.Figure, tuple[plt.Axes, plt.Axes]]:
    _apply_brand_style()
    df = load()
    fig, (ax_a, ax_b) = plt.subplots(
        1, 2, figsize=(15, 6.2), sharey=True,
        gridspec_kw={"width_ratios": [1.45, 1.0], "wspace": 0.06},
    )
    height = 0.58
    total = df["genes_direct"] + df["genes_supporting_only"]
    # Row positions. A glossed label is a three-line block centered on its
    # bar, so it gets extra room on both sides.
    gap = [0.55 if m in DESC else 0.0 for m in df["method"]]
    ys = [0.0]
    for i in range(1, len(df)):
        ys.append(ys[-1] + 1.0 + gap[i - 1] + gap[i])
    df["y"] = ys

    ax_a.barh(df["y"], df["genes_direct"], height=height, color=df["color"])
    ax_a.barh(df["y"], df["genes_supporting_only"], left=df["genes_direct"],
              height=height, color=[tint(c) for c in df["color"]])
    for _, r in df.iterrows():
        ax_a.text(r.genes_direct + r.genes_supporting_only + 30, r.y,
                  f"{r.genes_direct:,} + {r.genes_supporting_only:,}",
                  va="center", ha="left", fontsize=13, color=BRAND_NEUTRAL)
    ax_a.set_xlim(0, total.max() * 1.3)
    ax_a.set_xlabel("Genes called canonical or likely\n(direct + supporting only)")

    ax_b.barh(df["y"], df["pct_plot"], height=height, color=df["color"])
    for _, r in df.iterrows():
        text = (f"{r.pct_sole_direct:.1f}%" if r.genes_direct >= MIN_DIRECT_GENES
                else f"{r.genes_direct} direct genes")
        ax_b.text(r.pct_plot + 0.5, r.y, text, va="center", ha="left",
                  fontsize=13, color=BRAND_NEUTRAL)
    ax_b.set_xlim(0, df["pct_plot"].max() * 1.3)
    ax_b.set_xlabel("Share of direct-evidence genes where\nit was the only direct method")

    # Two-line tick labels for the catch-all categories: the name, then a
    # muted gloss underneath, both right-aligned against the axis.
    ax_a.set_yticks(df["y"],
                    [lbl + "\n\n" if m in DESC else lbl for m, lbl in zip(df["method"], df["label"], strict=True)])
    for m, y in zip(df["method"], df["y"], strict=True):
        if m in DESC:
            ax_a.annotate(DESC[m], xy=(0, y), xycoords=("axes fraction", "data"),
                          xytext=(-12, -3), textcoords="offset points", ha="right", va="top",
                          fontsize=13, color=BRAND_NEUTRAL, linespacing=1.15)

    ax_a.set_ylim(-0.6 - gap[0], df["y"].max() + 0.6 + gap[-1])
    for ax in (ax_a, ax_b):
        sns.despine(ax=ax, top=True, right=True)
        ax.grid(axis="y", visible=False)
    _panel_label(ax_a, "a")
    _panel_label(ax_b, "b")

    handles = [(plt.Rectangle((0, 0), 1, 1, color=FAMILY_COLOR[f]),
                plt.Rectangle((0, 0), 1, 1, color=tint(FAMILY_COLOR[f]))) for f in FAMILY_LABEL]
    legend = fig.legend(
        handles, list(FAMILY_LABEL.values()),
        handler_map={tuple: HandlerTuple(ndivide=None, pad=0)},
        title="Solid = direct (reached from outside an intact cell)    "
              "Light = supporting only (at the membrane, outside not shown)",
        loc="lower center", bbox_to_anchor=(0.55, 0.96), ncol=4, frameon=False,
        fontsize=13.5, title_fontsize=13.5, handlelength=2.4, columnspacing=1.6,
    )
    legend.get_title().set_color(BRAND_NEUTRAL)
    return fig, (ax_a, ax_b)


def main() -> None:
    fig, _ = make_plot()
    # Embed the gist URL into the artifacts (PNG Source tEXt / PDF Subject)
    # so a figure dragged into Substack or Slack still says where it came
    # from. Mirrors save_figure(gist_url=...) in _plotting_config.py.
    out = Path(__file__).parent / "surface_evidence_assay_types"
    fig.savefig(f"{out}.pdf", bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(f"{out}.png", bbox_inches="tight", dpi=600, metadata={"Source": GIST_URL})
    print(f"  wrote {out}.pdf + {out}.png")


if __name__ == "__main__":
    main()
