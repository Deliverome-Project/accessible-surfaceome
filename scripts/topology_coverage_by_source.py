"""Canonical generator for ``topology_coverage_by_source.{pdf,png}``.

Supplementary Figure 9 — a per-source × per-topology-class coverage
grid. For every protein in the cohort-tightened v3 candidate-surfaceome
universe (6,588 proteins = candidate_universe_v3 + v3_dropped, the
post-Sonnet-no-trim union intersected with the HGNC-anchored
protein-coding cohort), 9 binary topology features are scored per
inclusion source. Each panel shows what fraction of the universe is
captured by ``(source ∩ feature)``.

Reads the dedicated per-figure TSV
``data/processed/figures/topology_coverage_by_source.tsv`` (built by
``scripts/build_figure_tsvs.py``). That TSV carries the 9 ``topo_*``
feature columns, the ``src_*`` per-source inclusion flags, and the
bench-optimized cutoff columns ``uniprot_optimized`` / ``cspa_optimized``
/ ``n_sources_optimized``.

Per-source bars — cutoff convention:
  • UniProt and CSPA bars use the **bench-optimized cutoffs**
    (``uniprot_optimized`` / ``cspa_optimized``), consistent with the
    accuracy figures — NOT the initial ``src_uniprot`` / ``src_cspa``
    flags.
  • GO, HPA, SURFY, and Sonnet bars use their ``src_*`` flags unchanged.
  • The ``sonnet_only`` (zero-DB rescue) subset is Sonnet-positive
    proteins that NO database flags under the optimized cutoffs
    (``src_sonnet == 1`` AND ``n_sources_optimized == 0``).

Panels (3×3):
  Row 1: GPI-anchored | 7TM GPCR | Multi-pass TM (non-GPCR)
  Row 2: Single-pass TM | Likely secreted (SP + no TM + no anchor) |
         Inner-leaflet lipidated (prenyl/myr, no TM/SP)
  Row 3: No TM, no signal | Glycosylation site | TM without signal
         peptide (DeepTMHMM class)

Bar height for source S on feature F:
    100 × |S-included ∩ F-positive| / 6,588

This is the **canonical generator** (centralized ``_plotting_config``
styling, in-repo TSV path). The standalone reader-side mirror is
``data/analysis/figures/make_topology_coverage_by_source.py`` — keep the
layout fingerprint in sync (see CLAUDE.md "Canonical generator vs gist
mirror"; drift-guarded by tests/test_figure_canonical_mirror_sync.py).

# Reproduction: https://gist.github.com/beccajcarlson/95b0f4cdcaf6a6b91f57539cd1515a25
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import (
    save_figure,
    setup_plotting_style,
)

REPO = Path(__file__).resolve().parents[1]
# Dedicated per-figure TSV (built by scripts/build_figure_tsvs.py). One
# row per universe protein with the src_* inclusion flags, the
# bench-optimized cutoff columns, and the 9 topology binary features.
FEATURES_TSV = REPO / "data/processed/figures/topology_coverage_by_source.tsv"
# Final-figure output dir — every promoted figure lands here so the
# Zenodo deposit, the published gists, and the readers' figure folder
# are all the same path.
FIGURES_DIR = REPO / "data/analysis/figures"
GIST_URL = "https://gist.github.com/beccajcarlson/95b0f4cdcaf6a6b91f57539cd1515a25"

# Panel order + display labels. Layout is 3×3 — 9 features = clean grid.
# Hand-picked architectures + glyc + DeepTMHMM TM-only class.
FEATURES: list[tuple[str, str]] = [
    ("topo_gpi_anchored",            "GPI-anchored\n(outer leaflet)"),
    ("topo_gpcr_7tm",                "7TM GPCR"),
    ("topo_multi_pass_tm",           "Multi-pass TM\n(non-GPCR)"),
    ("topo_single_pass_tm",          "Single-pass TM\n(Type I/II/III)"),
    ("topo_signal_only_secreted",    "Likely secreted\n(SP + no TM + no anchor)"),
    ("topo_inner_leaflet_lipidated", "Inner-leaflet lipidated\n(prenyl/myristoyl + no TM/SP)"),
    ("topo_no_tm_no_signal",         "No TM, no signal\n(peripheral / cytosolic)"),
    ("up_has_glyc",                  "Glycosylation site\n(UniProt feature)"),
    ("deeptm_TM_NO_SP",              "TM without signal peptide\n(DeepTMHMM class)"),
]

# Panel x-axis order: Sonnet first (implicit reference), then DBs in
# uniprot / surfy / cspa / go / hpa order, matching
# make_db_correctness_by_class.py for cross-figure visual consistency.
# ``sonnet_only`` = the zero-DB rescue subset (Sonnet-positive,
# n_sources_optimized == 0). Sits right after sonnet so the rescue
# subset reads as a visible delta off the full Sonnet bar; success-green
# signals "rescue" (matches the zero_db_rescues_by_triage figure).
SOURCE_ORDER = ["sonnet", "sonnet_only", "uniprot", "surfy", "cspa", "go", "hpa"]
SOURCE_COLORS = {
    "sonnet":      "#d87851",  # Claude-orange
    "sonnet_only": "#2E7A55",  # success green — zero-DB rescue subset
    "uniprot": "#BC3C4C",  # maroon-light
    "surfy":   "#8878C8",  # lavender-bright
    "cspa":    "#6E1428",  # maroon-dark
    "go":      "#3D6B60",  # teal-mid
    "hpa":     "#F4AA28",  # amber-bright
}
# Per-source column mapping. UniProt + CSPA use the bench-OPTIMIZED
# cutoffs (consistent with the accuracy figures); the other DBs and
# Sonnet use their initial src_* flags unchanged.
SOURCE_COL = {
    "sonnet":  "src_sonnet",
    "uniprot": "uniprot_optimized",
    "surfy":   "src_surfy",
    "cspa":    "cspa_optimized",
    "go":      "src_go",
    "hpa":     "src_hpa",
}


def main() -> None:
    # font_scale=1.0 keeps the rcParams-derived tick labels at the
    # project floor; the explicit overrides below pin the figure's font
    # sizes (and keep the layout fingerprint in lockstep with the gist
    # mirror — drift-guarded by tests/test_figure_canonical_mirror_sync.py).
    setup_plotting_style(font_scale=1.0)
    plt.rcParams.update({
        "font.size": 20,
        "axes.labelsize": 20,
        "axes.titlesize": 0,
        "xtick.labelsize": 20,
        "ytick.labelsize": 20,
        "legend.fontsize": 20,
    })

    df = pd.read_csv(FEATURES_TSV, sep="\t")
    universe_size = int(len(df))

    n_feat = len(FEATURES)
    ncols = 3
    nrows = (n_feat + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(16, 3.6 * nrows))
    axes = axes.reshape(-1)

    # Pre-compute the sonnet_only mask once (per-panel iteration would
    # recompute it 9× for no benefit). Zero-DB rescue under the
    # OPTIMIZED cutoffs: Sonnet positive AND no DB voted yes once the
    # bench-optimized UniProt/CSPA thresholds are applied.
    sonnet_only_mask = (df[SOURCE_COL["sonnet"]] == 1) & (df["n_sources_optimized"] == 0)

    for ax, (feat_col, label) in zip(axes, FEATURES):
        rates_pct = []
        for src_name in SOURCE_ORDER:
            if src_name == "sonnet_only":
                mask = sonnet_only_mask
            else:
                mask = df[SOURCE_COL[src_name]] == 1
            feat = pd.to_numeric(df.loc[mask, feat_col], errors="coerce")
            n_pos = int((feat == 1).sum())
            rates_pct.append(100.0 * n_pos / universe_size)
        colors = [SOURCE_COLORS[s] for s in SOURCE_ORDER]
        ax.bar(range(len(SOURCE_ORDER)), rates_pct, color=colors, edgecolor="white")
        ax.set_xticks(range(len(SOURCE_ORDER)))
        ax.set_xticklabels(SOURCE_ORDER, rotation=35, ha="right")
        ax.set_ylabel("% of any-yes-vote\nuniverse")
        ax.set_xlabel("")
        ax.text(
            0.0, 1.04, label,
            transform=ax.transAxes,
            ha="left", va="bottom",
            fontsize=14, weight="bold",
        )
        sns.despine(ax=ax, top=True, right=True)
    for ax in axes[n_feat:]:
        ax.axis("off")
    fig.tight_layout()

    save_figure(
        fig, "topology_coverage_by_source",
        output_dir=FIGURES_DIR,
        formats=("pdf", "png"),
        gist_url=GIST_URL,
    )
    plt.close(fig)


if __name__ == "__main__":
    main()
