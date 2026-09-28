"""How common each experimental assay is in the surface-evidence ledger,
and how often it was the only thing holding a surface call up.

Two questions a reader of the catalog has but cannot currently answer:
which experiments actually established these surface calls, and which calls
rest on a single kind of experiment. The catalog exposes ``evidence_grade``
(how direct / how many methods) but never names the assay, so "direct,
single method" hides whether that method was flow cytometry or a surfaceome
mass-spec hit.

Panel a is prevalence — genes with at least one supporting surface-expression
claim from each assay. Panel b is the share of those genes for which the
assay was the ONLY primary-tier assay supporting the call: pull it and the
call has no direct experimental support left. That second number is the
interesting one, because prevalence mostly tracks how common a technique is
in the literature, while standing alone tracks how much weight the catalog
is putting on it.

Scope, all applied upstream or here and worth stating because each one
changes the answer:

* ``claim_type = 'surface_expression'`` only. Tissue-expression and topology
  rows reuse the same assay vocabulary but say nothing about whether the
  protein reaches the surface; counting them inflates every assay uniformly.
* ``direction = 'supports'`` only. An assay arguing *against* surface
  localization is not evidence the call rests on.
* Genes in a surface-positive tier (canonical / likely / low), so "decisive"
  means decisive for an actual surface call.
* Assays under ``MIN_GENES`` genes are dropped — a 12% sole rate over 26
  genes is noise, and plotting it next to a rate over 2,796 invites a
  comparison the data cannot support.

# Reproduction: https://gist.github.com/beccajcarlson/141184baa53bc889d2c08692b931982b
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

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

# Below this the percentage in panel b is dominated by its denominator.
MIN_GENES = 50

# Assays that put a probe on an intact cell and therefore speak directly to
# surface accessibility, vs everything else (reviews, functional readouts,
# structures, transcript measurements). The split is the point of the figure:
# a call resting on a direct assay is a different object from one resting on
# a review assertion, even at the same evidence_grade.
DIRECT_SURFACE_ASSAYS = {
    "flow_cytometry",
    "surface_biotinylation",
    "mass_spec_surfaceome",
    "immunofluorescence",
    "immunohistochemistry",
}

LABEL = {
    "functional_assay": "Functional assay",
    "immunofluorescence": "Immunofluorescence",
    "review_assertion": "Review assertion",
    "flow_cytometry": "Flow cytometry",
    "immunohistochemistry": "Immunohistochemistry",
    "western_blot": "Western blot",
    "mass_spec_surfaceome": "Surfaceome mass spec",
    "loss_of_function_phenotype": "Loss-of-function",
    "surface_biotinylation": "Surface biotinylation",
    "cryo_em": "Cryo-EM",
    "computational_prediction": "Computational prediction",
    "crystal_structure": "Crystal structure",
    "orthology": "Orthology",
    "db_annotation": "Database annotation",
}

COLOR_DIRECT = COLORS["secondary"]    # teal — direct surface assay
COLOR_INDIRECT = "#C7BDB6"            # warm grey — everything else


def load() -> pd.DataFrame:
    df = pd.read_csv(DATA_TSV, sep="\t")
    df = df[df["genes_used"] >= MIN_GENES].copy()
    df["label"] = df["evidence_type"].map(lambda t: LABEL.get(t, t.replace("_", " ").capitalize()))
    df["is_direct"] = df["evidence_type"].isin(DIRECT_SURFACE_ASSAYS)
    return df.sort_values("genes_used", ascending=True).reset_index(drop=True)


def _panel_label(ax, letter: str) -> None:
    ax.text(-0.02, 1.04, letter, transform=ax.transAxes, fontsize=26,
            fontweight=800, va="bottom", ha="right", color=COLORS["dark"])


def make_plot() -> tuple[plt.Figure, tuple[plt.Axes, plt.Axes]]:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    plt.rcParams.update({
        "font.size": 16, "axes.labelsize": 18, "axes.titlesize": 0,
        "xtick.labelsize": 15, "ytick.labelsize": 15, "legend.fontsize": 15,
    })
    df = load()
    colors = [COLOR_DIRECT if d else COLOR_INDIRECT for d in df["is_direct"]]

    fig, (ax_a, ax_b) = plt.subplots(
        1, 2, figsize=(17, 8), sharey=True,
        gridspec_kw={"width_ratios": [1.35, 1.0], "wspace": 0.08},
    )

    ax_a.barh(df["label"], df["genes_used"], color=colors, edgecolor="none")
    for y, (n, rows) in enumerate(zip(df["genes_used"], df["n_rows"], strict=True)):
        ax_a.text(n + 40, y, f"{n:,}", va="center", ha="left",
                  fontsize=13, color=COLORS["neutral"])
    ax_a.set_xlabel("Genes with supporting\nsurface evidence")
    ax_a.set_xlim(0, df["genes_used"].max() * 1.16)

    ax_b.barh(df["label"], df["pct_sole_primary"], color=colors, edgecolor="none")
    for y, p in enumerate(df["pct_sole_primary"]):
        ax_b.text(p + 0.12, y, f"{p:.1f}%", va="center", ha="left",
                  fontsize=13, color=COLORS["neutral"])
    ax_b.set_xlabel("Share of those genes where it was\nthe only assay supporting the call")
    ax_b.set_xlim(0, max(df["pct_sole_primary"].max() * 1.22, 1))

    for ax in (ax_a, ax_b):
        sns.despine(ax=ax, top=True, right=True)
        ax.grid(axis="y", visible=False)

    handles = [
        plt.Rectangle((0, 0), 1, 1, color=COLOR_DIRECT),
        plt.Rectangle((0, 0), 1, 1, color=COLOR_INDIRECT),
    ]
    ax_a.legend(handles, ["Probes an intact cell", "Indirect / not cell-surface specific"],
                loc="lower right", frameon=False, fontsize=14,
                bbox_to_anchor=(1.0, 0.02))

    _panel_label(ax_a, "a")
    _panel_label(ax_b, "b")

    fig.text(
        0.5, -0.02,
        f"Supporting surface-expression claims only, over genes in a surface-positive tier; "
        f"assays under {MIN_GENES} genes omitted. \"Only assay\" counts primary-tier support.",
        ha="center", va="top", fontsize=13, style="italic", color=COLORS["neutral"],
    )
    fig.tight_layout()
    return fig, (ax_a, ax_b)


def main() -> None:
    fig, _ = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"))


if __name__ == "__main__":
    main()
