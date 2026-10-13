"""Which methods established the surface calls, and how often each one
stood alone as the only direct evidence.

Two questions a reader of the catalog has but cannot answer from the
evidence grade alone: which experiments showed the protein is on the
surface, and which calls rest on a single kind of experiment. The grade
says how many direct methods a gene has; this figure names them.

Source is the record's ``surface_evidence.methods`` block (one row per
experiment), not the evidence ledger's ``evidence_type``. The ledger names
the technique in a quote, so it counts permeabilized immunofluorescence and
whole-cell proteomics as surface assays; the methods block judges each
experiment as

* **direct** — an antibody or probe reached the protein from outside an
  intact cell (live or non-permeabilized staining of an extracellular
  epitope or tag, membrane-impermeable labeling, a functional readout that
  needs surface access), or
* **supporting** — places the protein at the plasma membrane without
  showing the outside is reachable (membrane-rim staining, fluorescent
  fusions, membranous IHC; sectioning exposes intracellular epitopes, so
  IHC is never direct).

Panel a counts genes with direct evidence from each method (solid) and
genes where that method only reached the supporting level (light). Panel b
is the share of direct-evidence genes for which the method was the ONLY
direct method: remove it and the gene has no direct surface evidence left.

Color is assay family: imaging and cytometry; surface labeling or capture;
functional surface assays; other. Genes are restricted to the canonical and
likely deep-dive tiers; ``low`` (weak evidence, unlikely surface) is left out. The category rules live in
``scripts/build_figure_tsvs.py:build_surface_evidence_assay_types``.

# Reproduction: https://gist.github.com/beccajcarlson/141184baa53bc889d2c08692b931982b
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.colors import to_rgb
from matplotlib.legend_handler import HandlerTuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from accessible_surfaceome.audit._plotting_config import (  # noqa: E402
    COLORS,
    save_figure,
    setup_plotting_style,
)

SLUG = "surface_evidence_assay_types"
DATA_TSV = ROOT / "data/processed/figures/surface_evidence_assay_types.tsv"
OUT_DIR = ROOT / "data/analysis/figures"
GIST_URL = "https://gist.github.com/beccajcarlson/141184baa53bc889d2c08692b931982b"

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
    "imaging_cytometry": COLORS["secondary"],   # teal
    "labeling_capture": COLORS["primary"],      # maroon
    "functional": COLORS["accent"],             # amber
    "other": COLORS["quaternary"],              # lavender
}


def tint(color: str, f: float = 0.6) -> tuple[float, float, float]:
    """Lighter shade of ``color`` for the supporting-only segment."""
    r, g, b = to_rgb(color)
    return (r + (1 - r) * f, g + (1 - g) * f, b + (1 - b) * f)


def load() -> pd.DataFrame:
    df = pd.read_csv(DATA_TSV, sep="\t")
    df["label"] = df["method"].map(LABEL)
    df["color"] = df["family"].map(FAMILY_COLOR)
    df["pct_plot"] = df["pct_sole_direct"].where(df["genes_direct"] >= MIN_DIRECT_GENES, 0.0)
    # Rows follow panel b, highest at the top; barh draws index 0 at the
    # bottom, hence ascending. Direct count breaks ties.
    return df.sort_values(["pct_plot", "genes_direct"]).reset_index(drop=True)


def _panel_label(ax, letter: str) -> None:
    ax.text(-0.02, 1.02, letter, transform=ax.transAxes, fontsize=24,
            fontweight=800, va="bottom", ha="right", color=COLORS["dark"])


def make_plot() -> tuple[plt.Figure, tuple[plt.Axes, plt.Axes]]:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    plt.rcParams.update({
        "font.size": 14, "axes.labelsize": 15.5, "axes.titlesize": 0,
        "xtick.labelsize": 14, "ytick.labelsize": 15, "legend.fontsize": 13.5,
    })
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
                  va="center", ha="left", fontsize=13, color=COLORS["neutral"])
    ax_a.set_xlim(0, total.max() * 1.3)
    ax_a.set_xlabel("Genes called canonical or likely\n(direct + supporting only)")

    ax_b.barh(df["y"], df["pct_plot"], height=height, color=df["color"])
    for _, r in df.iterrows():
        text = (f"{r.pct_sole_direct:.1f}%" if r.genes_direct >= MIN_DIRECT_GENES
                else f"{r.genes_direct} direct genes")
        ax_b.text(r.pct_plot + 0.5, r.y, text, va="center", ha="left",
                  fontsize=13, color=COLORS["neutral"])
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
                          fontsize=13, color=COLORS["neutral"], linespacing=1.15)

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
    legend.get_title().set_color(COLORS["neutral"])
    return fig, (ax_a, ax_b)


def main() -> None:
    fig, _ = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"), gist_url=GIST_URL)


if __name__ == "__main__":
    main()
