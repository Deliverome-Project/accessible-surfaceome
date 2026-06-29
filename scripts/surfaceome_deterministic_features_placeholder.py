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
import numpy as np
import pandas as pd
import seaborn as sns

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
from accessible_surfaceome.audit._plotting_config import save_figure, setup_plotting_style


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


def load_data() -> pd.DataFrame:
    """Load per_protein_features (sonnet-positive subset) + join orthologs
    + isoform-topology-change flag."""
    feats = pd.read_csv(
        REPO_ROOT / "data/analysis/db_vs_sonnet_inclusion/per_protein_features.tsv",
        sep="\t",
    )
    # Filter to Sonnet-positive (the surfaceome as defined by Sonnet)
    feats = feats[feats["sonnet_verdict"].isin(["yes", "contextual"])].copy()

    # DeepTMHMM canonical — TM count, signal peptide, N/C-term ext, length
    dt = pd.read_csv(
        REPO_ROOT / "data/processed/deeptmhmm/deeptmhmm_human_canonical.tsv",
        sep="\t",
    )
    dt_keep = ["uniprot_accession", "protein_length", "tm_helix_count",
               "has_signal_peptide", "signal_peptide_length",
               "n_term_extracellular", "c_term_extracellular"]
    feats = feats.merge(
        dt[dt_keep].rename(columns={"uniprot_accession": "uniprot_accession"}),
        on="uniprot_accession", how="left",
    )

    # DeepTMHMM isoforms — flag genes with ≥1 isoform whose topology differs
    # from the canonical (use TM count + label match as the simple proxy)
    iso = pd.read_csv(
        REPO_ROOT / "data/processed/deeptmhmm/deeptmhmm_human_isoforms.tsv",
        sep="\t",
    )
    # Strip isoform suffix to get the canonical acc
    iso["canonical_acc"] = iso["uniprot_accession"].str.split("-").str[0]
    iso_by_canon = iso.groupby("canonical_acc").agg(
        iso_n=("uniprot_accession", "count"),
        iso_tm_counts=("tm_helix_count", lambda x: set(x.dropna().astype(int))),
        iso_labels=("deeptmhmm_label", lambda x: set(x.dropna())),
    ).reset_index()
    iso_by_canon = iso_by_canon.rename(columns={"canonical_acc": "uniprot_accession"})
    feats = feats.merge(iso_by_canon, on="uniprot_accession", how="left")

    def alt_iso_diff_topology(row):
        if pd.isna(row.get("iso_n")) or row.get("iso_n", 0) == 0:
            return None
        canon_tm = row.get("tm_helix_count")
        if pd.isna(canon_tm):
            return None
        iso_tms = row.get("iso_tm_counts")
        if iso_tms is None or not isinstance(iso_tms, set):
            return 0
        # Different TM count between any isoform and the canonical = topology change
        return int(any(t != int(canon_tm) for t in iso_tms if not pd.isna(t)))

    feats["alt_iso_diff_topo"] = feats.apply(alt_iso_diff_topology, axis=1)

    # Ensembl Compara — mouse + cyno one-to-one high-confidence ortholog flags
    cmp = pd.read_csv(
        REPO_ROOT
        / "data/external/ensembl_compara_surfaceome_expressed/compara_mouse_cyno_one2one_highconf_by_gene.csv"
    )
    cmp_keep = cmp[["resolver_resolved_gene_symbol",
                    "mouse_has_one2one_high_confidence",
                    "cyno_has_one2one_high_confidence"]].rename(
        columns={"resolver_resolved_gene_symbol": "gene_symbol"}
    )
    feats = feats.merge(cmp_keep, on="gene_symbol", how="left")

    # === Assign groups ===
    def group_of(row):
        if row["sonnet_verdict"] == "yes":
            if str(row.get("sonnet_confidence", "")).lower() == "high":
                return "deep_dive_high_conf"   # placeholder
            return "triage_yes"
        if row["sonnet_verdict"] == "contextual":
            return "deep_dive_likely_surface"
        return None

    feats["group"] = feats.apply(group_of, axis=1)
    feats = feats.dropna(subset=["group"])

    print(f"Sonnet-positive surfaceome: {len(feats)}")
    print(feats["group"].value_counts().to_string())
    return feats


def render(feats: pd.DataFrame) -> Path:
    setup_plotting_style(font_scale=1.0)
    plt.rcParams.update({
        "font.size":       12,
        "axes.labelsize":  12,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
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
            bars = ax.bar(range(len(GROUPS)), ys, color=colors, edgecolor="none")
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
                formats=("pdf", "png"))
    plt.close(fig)
    return OUT_DIR / "surfaceome_deterministic_features_placeholder.pdf"


def main() -> None:
    feats = load_data()
    out = render(feats)
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
