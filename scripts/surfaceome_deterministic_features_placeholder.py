# Reproduction: https://gist.github.com/beccajcarlson/57cf3cc3db903ab39bc0ba315ce5e4d5
"""Deterministic-feature distributions across the deep-dived surfaceome,
faceted by the REAL deep-dive surface-accessibility tier.

Each deep-dived gene carries a ``group`` from the deep-dive verdict logic
(``_dd_assign_bucket``): ``canonical`` / ``likely`` / ``low`` / ``uncertain``
/ ``no``. This figure collapses that spectrum into three comparison facets:

  - ``canonical``   — group == 'canonical' (high-confidence surface)
  - ``likely``      — group == 'likely'
  - ``below-likely`` — group ∈ {low, uncertain, no} (weak-to-negative)

Genes not yet deep-dived carry ``group == 'pending'`` and are EXCLUDED from
this per-tier comparison — they have no deep-dive tier to compare.

3×3 panel grid of deterministic features compared across the three tiers.
Features:

  - DeepTMHMM canonical    : TM count, signal peptide, N/C-term ext
  - DeepTMHMM isoforms     : alternative-isoform topology change
  - Schweke 2024           : homo-oligomer state
  - Ensembl Compara        : mouse + cyno one-to-one high-confidence
                             ortholog presence

PRELIMINARY — ~1,197 of ~5,128 candidate genes deep-dived so far, and the
below-likely tier is weak-evidence-inflated by the pretrim bug; treat the
per-tier rates as provisional until the sweep completes and the QA fix lands.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
from accessible_surfaceome.audit._plotting_config import save_figure, setup_plotting_style  # noqa: E402


# === Facet definitions: three real deep-dive tiers ===
# The 5-tier deep-dive spectrum collapsed to three comparison facets. Tier
# colors follow the canonical deep-dive spectrum shared across every deep-dive
# figure (see deep_dive_final_categories): green (canonical) → teal (likely) →
# neutral (below-likely). Genes still in the `pending` tier (not yet
# deep-dived) are excluded before this map is applied.
GROUPS = ["canonical", "likely", "below_likely"]
GROUP_LABEL = {
    "canonical":    "canonical",
    "likely":       "likely",
    "below_likely": "below-likely\n(low / uncertain / no)",
}
GROUP_COLOR = {
    "canonical":    "#2E7A55",  # success green — high-confidence surface
    "likely":       "#3D6B60",  # teal-mid — likely surface
    "below_likely": "#9C8C88",  # lifted neutral — weak-to-negative tiers
}

# Raw deep-dive tiers that collapse into the `below_likely` facet.
BELOW_LIKELY_TIERS = ("low", "uncertain", "no")


def assign_facet(group: str) -> str | None:
    """Map a raw deep-dive tier to one of the three comparison facets.

    Returns ``None`` for ``pending`` (not yet deep-dived) or any tier
    outside the known spectrum, so those rows are dropped from the
    per-tier comparison.
    """
    if group == "canonical":
        return "canonical"
    if group == "likely":
        return "likely"
    if group in BELOW_LIKELY_TIERS:
        return "below_likely"
    return None

OUT_DIR = REPO_ROOT / "data/analysis/figures"


DATA_TSV = REPO_ROOT / "data/processed/figures/surfaceome_deterministic_features_placeholder.tsv"


def load_data() -> pd.DataFrame:
    """Load the pre-joined single TSV the figure renders from.

    The join (per_protein_features Sonnet-positive subset × DeepTMHMM
    canonical × alt-isoform-topology flag × Schweke homo-oligomer ×
    Ensembl-Compara mouse/cyno ortholog flags × deep-dive tier) is
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

    fig, axes = plt.subplots(3, 3, figsize=(15, 12))
    axes = axes.flatten()

    # --- Panel definitions ---
    # Each is (column, kind, label) where kind ∈ {boxplot, frac, frac_bool}
    panels = [
        ("tm_helix_count",                   "boxplot",   "Number of TM helices"),
        ("protein_length",                   "boxplot",   "Protein length (residues)"),
        ("has_signal_peptide",               "frac_bool", "% with signal peptide"),
        ("n_term_extracellular",             "frac_bool", "% N-terminus extracellular"),
        ("c_term_extracellular",             "frac_bool", "% C-terminus extracellular"),
        ("mouse_has_one2one_high_confidence","frac_bool", "% with mouse 1:1 ortholog (high-conf)"),
        ("cyno_has_one2one_high_confidence", "frac_bool", "% with cyno 1:1 ortholog (high-conf)"),
        ("schweke_homomer",                  "frac_bool", "% homo-oligomer (Schweke 2024)"),
        ("alt_iso_diff_topo",                "frac_bool", "% with alt isoform of different topology"),
    ]

    for ax, (col, kind, label) in zip(axes, panels):
        if kind == "boxplot":
            data = []
            for g in GROUPS:
                vals = feats.loc[feats["facet"] == g, col].dropna().tolist()
                data.append(vals)
            bp = ax.boxplot(
                data, labels=[GROUP_LABEL[g] for g in GROUPS], patch_artist=True,
                medianprops=dict(color="white", linewidth=1.5),
                showfliers=False,
            )
            for patch, g in zip(bp["boxes"], GROUPS):
                patch.set_facecolor(GROUP_COLOR[g])
                patch.set_edgecolor("none")
            ax.set_ylabel(label, fontsize=11)
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
            colors = [GROUP_COLOR[g] for g in GROUPS]
            ax.bar(range(len(GROUPS)), ys, color=colors, edgecolor="none")
            for i, (y, n_) in enumerate(zip(ys, ns)):
                ax.text(i, y + 1.5, f"{y:.0f}%\nn={n_}", ha="center", va="bottom",
                        fontsize=9, color=colors[i], weight="semibold")
            ax.set_ylim(0, 110)
            ax.set_xticks(range(len(GROUPS)))
            ax.set_xticklabels([GROUP_LABEL[g] for g in GROUPS],
                               rotation=30, fontsize=8, ha="right")
            ax.set_ylabel(label, fontsize=10)

        sns.despine(ax=ax, top=True, right=True)
        if kind == "boxplot":
            ax.tick_params(axis="x", rotation=30)
            for tl in ax.get_xticklabels():
                tl.set_fontsize(8)
                tl.set_horizontalalignment("right")

    # Single legend at top — the three real deep-dive tiers (pending excluded).
    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, color=GROUP_COLOR[g],
                      label=GROUP_LABEL[g].replace("\n", " "))
        for g in GROUPS
    ]
    fig.legend(
        handles=legend_handles, loc="upper center", ncol=3, frameon=False,
        bbox_to_anchor=(0.5, 1.02), fontsize=10,
        title="Deep-dive surface-accessibility tier (pending genes excluded)",
        title_fontsize=11,
    )

    plt.tight_layout(rect=(0, 0, 1, 0.97))
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
