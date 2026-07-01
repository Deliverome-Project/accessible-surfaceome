# Reproduction: https://gist.github.com/beccajcarlson/57cf3cc3db903ab39bc0ba315ce5e4d5
"""Placeholder figure: deterministic feature distributions across the
Sonnet-positive surfaceome, grouped by three hues — triage_yes,
deep_dive_high_conf, deep_dive_likely_surface.

The deep-dive hues are MOCKED from Sonnet verdicts for now (will be
replaced once the deep-dive runs over the full surfaceome):

    triage_yes               = Sonnet verdict == 'yes'   (n=2,528)
    deep_dive_high_conf      = Sonnet verdict == 'yes' AND high-confidence
                               (placeholder for the deep-dive high-conf
                               surface bucket)
    deep_dive_likely_surface = Sonnet verdict == 'contextual'  (n=1,721)

3×3 panel grid of deterministic features each compared across the three
buckets. Features sourced from:

  - DeepTMHMM canonical    : TM count, signal peptide, N/C-term ext,
                             ECD-length proxy (protein_length - SP)
  - DeepTMHMM isoforms     : alternative-isoform topology change
  - Schweke 2024           : homo-oligomer state
  - Ensembl Compara        : mouse + cyno one-to-one high-confidence
                             ortholog presence
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


# === Group definitions (placeholders — replace with deep-dive when ready) ===
GROUPS = ["triage_yes", "deep_dive_high_conf", "deep_dive_likely_surface"]
GROUP_LABEL = {
    "triage_yes":               "Triage yes",
    "deep_dive_high_conf":      "Deep dive — high-conf surface",
    "deep_dive_likely_surface": "Deep dive — likely surface",
}
# Sequential teal: darker = more confident (same convention as the ADC-source
# stacking in positive_control_db_coverage_bars).
GROUP_COLOR = {
    "triage_yes":               "#7AAB9F",  # teal-light
    "deep_dive_high_conf":      "#244840",  # teal-darkest
    "deep_dive_likely_surface": "#4D8A80",  # teal-medium
}

OUT_DIR = REPO_ROOT / "data/analysis/figures"


DATA_TSV = REPO_ROOT / "data/processed/figures/surfaceome_deterministic_features_placeholder.tsv"


def load_data() -> pd.DataFrame:
    """Load the pre-joined single TSV the figure renders from.

    The join (per_protein_features Sonnet-positive subset × DeepTMHMM
    canonical × alt-isoform-topology flag × Schweke homo-oligomer ×
    Ensembl-Compara mouse/cyno ortholog flags × bucket assignment) is
    materialised once by
    ``scripts/build_figure_tsvs.py::build_surfaceome_deterministic_features_placeholder``
    into ``data/processed/figures/surfaceome_deterministic_features_placeholder.tsv``.
    This keeps the gist a single-TSV reproduction unit per the
    single-TSV-per-gist invariant (tests/test_gist_single_tsv.py).
    """
    feats = pd.read_csv(DATA_TSV, sep="\t")
    print(f"Sonnet-positive surfaceome: {len(feats)}")
    print(feats["group"].value_counts().to_string())
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
                vals = feats.loc[feats["group"] == g, col].dropna().tolist()
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
                sub = feats[feats["group"] == g][col]
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
            ax.set_xticklabels([GROUP_LABEL[g].replace(" — ", "\n") for g in GROUPS],
                               rotation=0, fontsize=9, ha="center")
            ax.set_ylabel(label, fontsize=10)

        sns.despine(ax=ax, top=True, right=True)
        if kind == "boxplot":
            ax.tick_params(axis="x", rotation=15)
            for tl in ax.get_xticklabels():
                tl.set_fontsize(9)
                tl.set_horizontalalignment("right")

    # Single legend at top — explains the 3 placeholder groups
    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, color=GROUP_COLOR[g], label=GROUP_LABEL[g])
        for g in GROUPS
    ]
    fig.legend(
        handles=legend_handles, loc="upper center", ncol=3, frameon=False,
        bbox_to_anchor=(0.5, 1.02), fontsize=11,
        title="Surfaceome bucket (deep-dive hues MOCKED from Sonnet for now)",
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
