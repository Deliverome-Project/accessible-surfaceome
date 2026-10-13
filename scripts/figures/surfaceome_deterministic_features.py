# Reproduction: https://gist.github.com/beccajcarlson/57cf3cc3db903ab39bc0ba315ce5e4d5
"""Deterministic-feature distributions across the deep-dived surfaceome,
faceted by the REAL deep-dive surface-accessibility tier.

Each deep-dived gene carries a ``group`` from the deep-dive verdict logic
(``_dd_assign_bucket``): ``canonical`` / ``likely`` / ``low`` / ``uncertain``
/ ``no``. This figure keeps the top two tiers as-is and collapses the two
weakest into a single facet, then adds a FIFTH facet — the full Sonnet
dual-triage surface pool — giving FIVE comparison facets:

  - ``canonical``      — group == 'canonical' (high-confidence surface)
  - ``likely``         — group == 'likely'
  - ``low``            — group == 'low' (low/moderate accessibility, weak evidence)
  - ``uncertain / no`` — group ∈ {uncertain, no} (ambiguous-to-negative)
  - ``Sonnet dual triage`` — every gene the two-stage Sonnet triage
    (``genome_full_sonnet_ncbi_v2`` plus the four PubMed rescue lanes) called
    yes/contextual (all 4,628, each with topology). A DIFFERENT category from the tiers: broader, and its det
    features come from the genome-wide D1 tables (``topology_public``,
    ``compara_*``, ``schweke_homomer_public``, ``surface_bind_*``) rather than
    the deep-dive records, since most of these genes are not deep-dived. Same
    DeepTMHMM / Compara / Schweke computation, ~100% topology coverage so the
    three continuous axes stay unbiased. Lets the reader compare the curated
    deep-dive tiers against everything the triage flags surface.

Genes not yet deep-dived carry ``group == 'pending'`` and are EXCLUDED from the
deep-dive tiers — they have no tier to compare. (``pending`` is already absent
from the bundled TSV.)

4×3 panel grid of deterministic features compared across the five facets.
The three CONTINUOUS features are shown as violins; the nine BOOLEAN features
as per-facet fraction bars (% of genes carrying the feature) — a violin of a
0/1 value is meaningless.

Features:

  - Topology (from the deep-dive record): TM-helix count, protein length,
    ECD length, signal peptide, N/C-term extracellular, alt-isoform
    topology change
  - Schweke 2024           : homo-oligomer state
  - Ensembl Compara        : mouse + cyno 1:1 ortholog presence, concerning
    paralog (ECD 40%+ identity)
  - Surface-bind sites     : 1+ extracellular surface-bind site

Topology + every deterministic feature here is sourced from the deep-dive
RECORDS (full coverage per deep-dived gene), which fixes the prior
DeepTMHMM-M1-only coverage bias where the low / uncertain / no tiers were
70-94% missing.

Computed over the completed deep-dive sweep of 5,332 genes (pending
excluded).
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
from accessible_surfaceome.audit._plotting_config import (  # noqa: E402
    COLORS,
    save_figure,
    setup_plotting_style,
)


# === Facet definitions: four real deep-dive tiers ===
# The 5-tier deep-dive spectrum collapsed to four comparison facets by
# pooling only the two weakest tiers (uncertain + no). Tier colours follow
# the canonical deep-dive confidence spectrum shared across every deep-dive
# figure (see deep_dive_final_categories): green (canonical) → teal (likely)
# → amber-tan (low) → neutral (uncertain/no). Genes still in the `pending`
# tier (not yet deep-dived) are excluded before this map is applied.
GROUPS = ["canonical", "likely", "low", "uncertain_no", "sonnet_dual_triage"]
GROUP_LABEL = {
    "canonical":    "canonical",
    "likely":       "likely",
    "low":          "low",
    "uncertain_no": "uncertain / no",
    "sonnet_dual_triage": "Sonnet dual triage",
}
GROUP_COLOR = {
    "canonical":    "#2E7A55",  # success green — high-confidence surface
    "likely":       "#3D6B60",  # teal-mid — likely surface
    "low":          "#C99A5B",  # amber-tan — low/moderate access, weak evidence
    "uncertain_no": "#9C8C88",  # lifted neutral — ambiguous-to-negative tiers
    "sonnet_dual_triage": "#d87851",  # Sonnet terracotta — the full triage pool
}

# Raw deep-dive tiers that collapse into the `uncertain_no` facet.
UNCERTAIN_NO_TIERS = ("uncertain", "no")


def assign_facet(group: str) -> str | None:
    """Map a raw ``group`` value to one of the five comparison facets.

    The four leftmost facets are deep-dive tiers (from the records). The fifth,
    ``sonnet_dual_triage``, is the FULL Sonnet dual-triage surface pool — a
    different category (broader; det features from the genome-wide D1 tables,
    not the records), placed rightmost so the reader compares the curated
    deep-dive tiers against everything the triage flags surface.

    Returns ``None`` for ``pending`` (not yet deep-dived) or any value outside
    the known spectrum, so those rows are dropped from the comparison.
    """
    if group == "canonical":
        return "canonical"
    if group == "likely":
        return "likely"
    if group == "low":
        return "low"
    if group in UNCERTAIN_NO_TIERS:
        return "uncertain_no"
    if group == "sonnet_dual_triage":
        return "sonnet_dual_triage"
    return None


OUT_DIR = REPO_ROOT / "data/analysis/figures"


DATA_TSV = REPO_ROOT / "data/processed/figures/surfaceome_deterministic_features.tsv"


def load_data() -> pd.DataFrame:
    """Load the pre-joined single TSV the figure renders from.

    The join (deep-dive tier × record-sourced topology [TM count, protein
    length, ECD length, signal peptide, N/C-term extracellular, alt-isoform
    topology] × Schweke homo-oligomer × Ensembl-Compara mouse/cyno 1:1
    ortholog + concerning-paralog flags × extracellular surface-bind site,
    unioned with the Sonnet-pool rows) is
    materialised once by
    ``scripts/build_figure_tsvs.py::build_surfaceome_deterministic_features``
    into ``data/processed/figures/surfaceome_deterministic_features.tsv``.
    This keeps the gist a single-TSV reproduction unit per the
    single-TSV-per-gist invariant (tests/test_gist_single_tsv.py).

    The raw per-gene ``group`` tier is collapsed to a ``facet`` column;
    ``pending`` (not yet deep-dived) rows map to NaN and are dropped so the
    figure only compares deep-dived tiers.
    """
    feats = pd.read_csv(DATA_TSV, sep="\t")
    print(f"Deep-dive tier universe (all groups): {len(feats)}")
    print(feats["group"].value_counts().to_string())
    feats["facet"] = feats["group"].map(assign_facet)
    feats = feats[feats["facet"].notna()].copy()
    print(f"\nDeep-dived genes compared (pending excluded): {len(feats)}")
    print(feats["facet"].value_counts().reindex(GROUPS).to_string())
    return feats


def _panel_label(ax: plt.Axes, letter: str, title: str) -> None:
    """Panel letter (Manrope ExtraBold, weight 800) + the panel's metric as a
    title above the axes — frees the y-label column so value labels fit."""
    n_extra = title.count("\n")
    ax.annotate(title, xy=(0, 1), xycoords="axes fraction", xytext=(0, 8),
                textcoords="offset points", fontsize=18, va="bottom", ha="left",
                color=COLORS["dark"])
    ax.annotate(letter, xy=(0, 1), xycoords="axes fraction",
                xytext=(-10, 8 + 21.5 * n_extra), textcoords="offset points",
                fontsize=25, fontweight=800, va="bottom", ha="right", color=COLORS["dark"])


def render(feats: pd.DataFrame) -> Path:
    setup_plotting_style(font_scale=1.0)
    plt.rcParams.update({
        "font.size":       15,
        "axes.labelsize":  18,
        "axes.titlesize":  0,
        "xtick.labelsize": 16.5,
        "ytick.labelsize": 16.5,
        "legend.fontsize": 16.5,
    })

    facet_labels = [GROUP_LABEL[g] for g in GROUPS]
    facet_colors = [GROUP_COLOR[g] for g in GROUPS]

    fig, axes = plt.subplots(4, 3, figsize=(15, 14.5))
    axes = axes.flatten()

    # --- Panel definitions ---
    # Each is (column, kind, label) where kind ∈ {violin, frac_bool}.
    # Continuous features → violins; boolean 0/1 features → fraction bars.
    # Fourth element is the fixed y-axis range so the panels read on a common,
    # honest scale: the three continuous violins get feature-appropriate caps
    # (a: TM-helix count 0–30, b: protein length 0–7k, c: ECD length 0–5k) and
    # every boolean fraction panel (d–l) is pinned to a true 0–100%.
    panels = [
        ("tm_helix_count",      "violin",    "Number of TM helices", (0, 30)),
        ("protein_length",      "violin",    "Protein length (residues)", (0, 7000)),
        ("ecd_length_residues", "violin",    "ECD length (residues)", (0, 5000)),
        ("has_signal_peptide",  "frac_bool", "% with signal peptide", (0, 100)),
        ("n_term_extracellular", "frac_bool", "% N-terminus extracellular", (0, 100)),
        ("c_term_extracellular", "frac_bool", "% C-terminus extracellular", (0, 100)),
        ("mouse_has_one2one",   "frac_bool", "% with mouse 1:1 ortholog", (0, 100)),
        ("cyno_has_one2one",    "frac_bool", "% with cyno 1:1 ortholog", (0, 100)),
        ("schweke_homomer",     "frac_bool", "% homo-oligomer (Schweke 2024)", (0, 100)),
        ("alt_iso_diff_topo",   "frac_bool", "% with alt isoform of\ndifferent topology", (0, 100)),
        ("has_concerning_paralog", "frac_bool", "% concerning paralog\n(ECD 40%+ id)", (0, 100)),
        ("has_ec_surface_bind_site", "frac_bool", "% with 1+ extracellular\nsurface-bind site", (0, 100)),
    ]

    letters = "abcdefghijkl"
    for ax, letter, (col, kind, label, ylim) in zip(axes, letters, panels):
        if kind == "violin":
            data = [
                feats.loc[feats["facet"] == g, col].astype(float).dropna().tolist()
                for g in GROUPS
            ]
            positions = list(range(len(GROUPS)))
            parts = ax.violinplot(
                data, positions=positions, showmedians=True,
                showextrema=False, widths=0.82,
            )
            for body, color in zip(parts["bodies"], facet_colors):
                body.set_facecolor(color)
                body.set_edgecolor("none")
                body.set_alpha(0.9)
            if "cmedians" in parts:
                parts["cmedians"].set_color("white")
                parts["cmedians"].set_linewidth(1.6)
            ax.set_xticks(positions)
            ax.set_xticklabels(facet_labels, rotation=35, ha="right", rotation_mode="anchor")
            ax.set_xlim(-0.6, len(GROUPS) - 0.4)
            ax.set_ylim(*ylim)
        elif kind == "frac_bool":
            ys = []
            ns = []
            for g in GROUPS:
                sub = feats[feats["facet"] == g][col]
                sub_clean = pd.to_numeric(sub, errors="coerce").dropna()
                n = len(sub_clean)
                positive = (sub_clean.astype(int) == 1).sum()
                ys.append(100 * positive / n if n else 0)
                ns.append(n)
            ax.bar(range(len(GROUPS)), ys, color=facet_colors, edgecolor="none")
            # True 0–100 axis (spine + ticks stop at 100); headroom above it so
            # every value+n label sits above its bar without clipping.
            for i, (y, n_) in enumerate(zip(ys, ns)):
                ax.text(i, y + 1.5, f"{y:.0f}%\nn={n_}", ha="center", va="bottom",
                        fontsize=13.5, color=facet_colors[i])
            ax.set_ylim(ylim[0], ylim[1] * 1.15)
            ax.set_yticks(range(0, 101, 25))
            ax.spines["left"].set_bounds(*ylim)
            ax.set_xlim(-0.5, len(GROUPS) - 0.5)
            ax.set_xticks(range(len(GROUPS)))
            ax.set_xticklabels(facet_labels, rotation=35, ha="right", rotation_mode="anchor")

        ax.tick_params(axis="x", labelsize=16.5)
        for tl in ax.get_xticklabels():
            tl.set_horizontalalignment("right")
        sns.despine(ax=ax, top=True, right=True)
        # Tier names only under the bottom row; the legend keys the colours.
        if letter not in letters[-3:]:
            ax.tick_params(axis="x", labelbottom=False)
        _panel_label(ax, letter, label)

    # 12 panels fill the 4×3 grid; hide any spare cell if a panel is dropped.
    for extra in axes[len(panels):]:
        extra.set_visible(False)

    plt.tight_layout(rect=(0, 0, 1, 0.96), w_pad=0.4)

    # Single legend at top — the four deep-dive tier facets + the Sonnet dual-triage pool.
    # Drawn after tight_layout and anchored just under the rect top (0.96)
    # so it sits just above row 1 rather than floating over a gap.
    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, color=GROUP_COLOR[g],
                      label=GROUP_LABEL[g].replace("\n", " "))
        for g in GROUPS
    ]
    fig.legend(
        handles=legend_handles, loc="lower center", ncol=5, frameon=False,
        bbox_to_anchor=(0.5, 0.945), fontsize=16.5,
        title="Deep-dive tier / Sonnet dual-triage pool", title_fontsize=18,
    )
    save_figure(fig, "surfaceome_deterministic_features", OUT_DIR,
                formats=("pdf", "png"), gist_url="https://gist.github.com/beccajcarlson/57cf3cc3db903ab39bc0ba315ce5e4d5")
    plt.close(fig)
    return OUT_DIR / "surfaceome_deterministic_features.pdf"


def main() -> None:
    feats = load_data()
    out = render(feats)
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
