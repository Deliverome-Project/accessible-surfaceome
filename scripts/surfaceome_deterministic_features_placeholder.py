# Reproduction: https://gist.github.com/beccajcarlson/57cf3cc3db903ab39bc0ba315ce5e4d5
"""Deterministic-feature distributions across the deep-dived surfaceome,
faceted by the REAL deep-dive surface-accessibility tier.

Each deep-dived gene carries a ``group`` from the deep-dive verdict logic
(``_dd_assign_bucket``): ``canonical`` / ``likely`` / ``low`` / ``uncertain``
/ ``no``. This figure keeps the top two tiers as-is and collapses the two
weakest tiers into a single facet, giving FOUR comparison facets:

  - ``canonical``     — group == 'canonical' (high-confidence surface)
  - ``likely``        — group == 'likely'
  - ``low``           — group == 'low' (low/moderate accessibility, weak evidence)
  - ``uncertain / no`` — group ∈ {uncertain, no} (ambiguous-to-negative)

Genes not yet deep-dived carry ``group == 'pending'`` and are EXCLUDED from
this per-tier comparison — they have no deep-dive tier to compare. (``pending``
is already absent from the bundled TSV, which holds only deep-dived genes.)

3×3 panel grid of deterministic features compared across the four tiers.
The two CONTINUOUS features are shown as violins; the nine BOOLEAN features
as per-facet fraction bars (% of genes carrying the feature) — a violin of a
0/1 value is meaningless.

Features:

  - Topology (from the deep-dive record): TM-helix count, protein length,
    signal peptide, N/C-term extracellular, alt-isoform topology change
  - Schweke 2024           : homo-oligomer state
  - Ensembl Compara        : mouse + cyno 1:1 ortholog presence

Topology + every deterministic feature here is sourced from the deep-dive
RECORDS (full coverage per deep-dived gene), which fixes the prior
DeepTMHMM-M1-only coverage bias where the low / uncertain / no tiers were
70-94% missing.

PRELIMINARY — a partial sweep of the ~5,128 candidate genes; treat the
per-tier rates as provisional until the sweep completes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

REPO_ROOT = Path(__file__).resolve().parents[1]
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
GROUPS = ["canonical", "likely", "low", "uncertain_no"]
GROUP_LABEL = {
    "canonical":    "canonical",
    "likely":       "likely",
    "low":          "low",
    "uncertain_no": "uncertain /\nno",
}
GROUP_COLOR = {
    "canonical":    "#2E7A55",  # success green — high-confidence surface
    "likely":       "#3D6B60",  # teal-mid — likely surface
    "low":          "#C99A5B",  # amber-tan — low/moderate access, weak evidence
    "uncertain_no": "#9C8C88",  # lifted neutral — ambiguous-to-negative tiers
}

# Raw deep-dive tiers that collapse into the `uncertain_no` facet.
UNCERTAIN_NO_TIERS = ("uncertain", "no")


def assign_facet(group: str) -> str | None:
    """Map a raw deep-dive tier to one of the four comparison facets.

    Returns ``None`` for ``pending`` (not yet deep-dived) or any tier
    outside the known spectrum, so those rows are dropped from the
    per-tier comparison.
    """
    if group == "canonical":
        return "canonical"
    if group == "likely":
        return "likely"
    if group == "low":
        return "low"
    if group in UNCERTAIN_NO_TIERS:
        return "uncertain_no"
    return None


OUT_DIR = REPO_ROOT / "data/analysis/figures"


DATA_TSV = REPO_ROOT / "data/processed/figures/surfaceome_deterministic_features_placeholder.tsv"


def load_data() -> pd.DataFrame:
    """Load the pre-joined single TSV the figure renders from.

    The join (deep-dive tier × record-sourced topology [TM count, length,
    signal peptide, N/C-term extracellular, alt-isoform topology] × Schweke
    homo-oligomer × Ensembl-Compara mouse/cyno 1:1 ortholog flags) is
    materialised once by
    ``scripts/build_figure_tsvs.py::build_surfaceome_deterministic_features_placeholder``
    into ``data/processed/figures/surfaceome_deterministic_features_placeholder.tsv``.
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


def _panel_label(ax: plt.Axes, letter: str) -> None:
    """Lowercase small-multiple panel label, Manrope ExtraBold (weight 800)."""
    ax.text(-0.02, 1.08, letter, transform=ax.transAxes, fontsize=15,
            fontweight=800, va="bottom", ha="right", color=COLORS["dark"])


def render(feats: pd.DataFrame) -> Path:
    setup_plotting_style(font_scale=1.0)
    plt.rcParams.update({
        "font.size":       12,
        "axes.labelsize":  12,
        "axes.titlesize":  0,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "legend.fontsize": 11,
    })

    n_total = len(feats)
    facet_labels = [GROUP_LABEL[g] for g in GROUPS]
    facet_colors = [GROUP_COLOR[g] for g in GROUPS]

    fig, axes = plt.subplots(4, 3, figsize=(15, 16))
    axes = axes.flatten()

    # --- Panel definitions ---
    # Each is (column, kind, label) where kind ∈ {violin, frac_bool}.
    # Continuous features → violins; boolean 0/1 features → fraction bars.
    panels = [
        ("tm_helix_count",      "violin",    "Number of\nTM helices"),
        ("protein_length",      "violin",    "Protein length\n(residues)"),
        ("has_signal_peptide",  "frac_bool", "% with signal peptide"),
        ("n_term_extracellular", "frac_bool", "% N-terminus extracellular"),
        ("c_term_extracellular", "frac_bool", "% C-terminus extracellular"),
        ("mouse_has_one2one",   "frac_bool", "% with mouse 1:1 ortholog"),
        ("cyno_has_one2one",    "frac_bool", "% with cyno 1:1 ortholog"),
        ("schweke_homomer",     "frac_bool", "% homo-oligomer (Schweke 2024)"),
        ("alt_iso_diff_topo",   "frac_bool", "% with alt isoform of different topology"),
        ("has_surface_bind_site", "frac_bool", "% with 1+ surface-bind site"),
        ("has_concerning_paralog", "frac_bool", "% concerning paralog\n(ECD 40%+ id)"),
    ]

    letters = "abcdefghijk"
    for ax, letter, (col, kind, label) in zip(axes, letters, panels):
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
            ax.set_xticklabels(facet_labels)
            ax.set_ylabel(label, fontsize=11)
            ax.set_xlim(-0.6, len(GROUPS) - 0.4)
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
            for i, (y, n_) in enumerate(zip(ys, ns)):
                ax.text(i, y + 1.5, f"{y:.0f}%\nn={n_}", ha="center", va="bottom",
                        fontsize=9, color=facet_colors[i], weight="semibold")
            ax.set_ylim(0, 118)
            ax.set_xticks(range(len(GROUPS)))
            ax.set_xticklabels(facet_labels)
            ax.set_ylabel(label, fontsize=10)

        ax.tick_params(axis="x", labelsize=9)
        for tl in ax.get_xticklabels():
            tl.set_horizontalalignment("center")
        sns.despine(ax=ax, top=True, right=True)
        _panel_label(ax, letter)

    # Hide the unused grid cell (11 panels in a 4×3 / 12-slot grid).
    for extra in axes[len(panels):]:
        extra.set_visible(False)

    # Single legend at top — the four real deep-dive tiers (pending excluded).
    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, color=GROUP_COLOR[g],
                      label=GROUP_LABEL[g].replace("\n", " "))
        for g in GROUPS
    ]
    fig.legend(
        handles=legend_handles, loc="upper center", ncol=4, frameon=False,
        bbox_to_anchor=(0.5, 1.02), fontsize=10,
        title="Deep-dive surface-accessibility tier (pending genes excluded)",
        title_fontsize=11,
    )

    fig.text(
        0.5, -0.01,
        f"PRELIMINARY — record-sourced deterministic features across "
        f"{n_total:,} deep-dived genes (partial sweep of ~5,128 candidates; "
        f"pending genes excluded). Violins: continuous features; bars: "
        f"% of genes with the boolean feature.",
        ha="center", va="top", fontsize=10, style="italic", color=COLORS["neutral"],
    )

    plt.tight_layout(rect=(0, 0, 1, 0.96))
    save_figure(fig, "surfaceome_deterministic_features_placeholder", OUT_DIR,
                formats=("pdf", "png"), gist_url="https://gist.github.com/beccajcarlson/57cf3cc3db903ab39bc0ba315ce5e4d5")
    plt.close(fig)
    return OUT_DIR / "surfaceome_deterministic_features_placeholder.pdf"


def main() -> None:
    feats = load_data()
    out = render(feats)
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
