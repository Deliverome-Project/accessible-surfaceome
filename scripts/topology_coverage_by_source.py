"""Canonical generator for ``topology_coverage_by_source.{pdf,png}``.

Supplementary Figure 9 — a single **bubble matrix** of surface inclusion
sources (rows) × topology features (columns). For every protein in the
cohort-tightened v3 candidate-surfaceome universe (the any-yes-vote union
intersected with the HGNC-anchored protein-coding cohort), 9 binary topology
features are scored per inclusion source. Each cell carries one dot encoding
BOTH metrics that the earlier coverage-bar grid could only show one of:

  • **dot AREA ∝ within-source enrichment** — % of that source's OWN calls
    that carry the feature  (``|source ∩ feature| / |source|``)
  • **dot COLOR = coverage** — % of the whole surface universe those proteins
    represent  (``|source ∩ feature| / |universe|``)

The two metrics differ only by denominator, so putting them in the same cell
lets a reader cross-reference them directly. The headline it renders: **CSPA ×
glycosylation is a large, pale dot** — intrinsically glyco-dominated (~75% of
its own calls) yet only a small slice of the universe (~11%), reflecting its
N-glycocapture chemistry; SURFY and UniProt show the same glyco enrichment at
larger scale (dark, high-coverage); the zero-DB Sonnet rescues are glyco- and
transmembrane-DEPLETED (near-empty row), consistent with contextual-surface
rather than classically-structured membrane proteins.

Reads the dedicated per-figure TSV
``data/processed/figures/topology_coverage_by_source.tsv``. That TSV carries the
9 ``topo_*`` feature columns, the ``src_*`` per-source inclusion flags, and the
bench-optimized cutoff columns ``uniprot_optimized`` / ``cspa_optimized`` /
``n_sources_optimized``.

Cutoff convention (unchanged from the bar version):
  • UniProt and CSPA use the **bench-optimized cutoffs** (``uniprot_optimized``
    / ``cspa_optimized``), consistent with the accuracy figures — NOT the
    initial ``src_uniprot`` / ``src_cspa`` flags.
  • GO CC, HPA, SURFY, and Sonnet use their ``src_*`` flags unchanged.
  • ``sonnet_only`` (zero-DB rescue) = Sonnet-positive proteins that NO database
    flags under the optimized cutoffs (``src_sonnet == 1`` AND
    ``n_sources_optimized == 0``).

This is the **canonical generator** (centralized ``_plotting_config`` styling,
in-repo TSV path). The standalone reader-side mirror is
``data/analysis/figures/make_topology_coverage_by_source.py`` — keep the layout
fingerprint in sync (see CLAUDE.md "Canonical generator vs gist mirror";
drift-guarded by tests/test_figure_canonical_mirror_sync.py).

# Reproduction: https://gist.github.com/beccajcarlson/95b0f4cdcaf6a6b91f57539cd1515a25
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.lines as mlines
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap, Normalize

from accessible_surfaceome.audit._plotting_config import (
    COLORS,
    SEQUENTIAL_PALETTES,
    save_figure,
    setup_plotting_style,
)

REPO = Path(__file__).resolve().parents[1]
FEATURES_TSV = REPO / "data/processed/figures/topology_coverage_by_source.tsv"
FIGURES_DIR = REPO / "data/analysis/figures"
GIST_URL = "https://gist.github.com/beccajcarlson/95b0f4cdcaf6a6b91f57539cd1515a25"

# Columns (features) — the same 9 topology classes the bar grid used.
FEATURES: list[tuple[str, str]] = [
    ("topo_gpi_anchored",            "GPI-anchored"),
    ("topo_gpcr_7tm",                "7TM GPCR"),
    ("topo_multi_pass_tm",           "Multi-pass TM"),
    ("topo_single_pass_tm",          "Single-pass TM"),
    ("topo_signal_only_secreted",    "Likely secreted"),
    ("topo_inner_leaflet_lipidated", "Inner-leaflet\nlipidated"),
    ("topo_no_tm_no_signal",         "No TM,\nno signal"),
    ("up_has_glyc",                  "Glycosylation"),
    ("deeptm_TM_NO_SP",              "TM without\nsignal peptide"),
]

# Rows (sources), top-to-bottom. Sonnet first (reference), then the zero-DB
# rescue subset, then the five DBs.
SOURCE_ORDER = ["sonnet", "sonnet_only", "uniprot", "surfy", "cspa", "go", "hpa"]
SOURCE_LABEL = {
    "sonnet":      "Sonnet",
    "sonnet_only": "Sonnet-only\n(zero-DB)",
    "uniprot":     "UniProt",
    "surfy":       "SURFY",
    "cspa":        "CSPA",
    "go":          "GO CC",
    "hpa":         "HPA",
}
# UniProt + CSPA use the bench-OPTIMIZED cutoffs; other DBs + Sonnet use their
# initial src_* flags unchanged.
SOURCE_COL = {
    "sonnet":  "src_sonnet",
    "uniprot": "uniprot_optimized",
    "surfy":   "src_surfy",
    "cspa":    "cspa_optimized",
    "go":      "src_go",
    "hpa":     "src_hpa",
}

# Enrichment (%) → scatter marker area (points²). Area-linear in the value so
# perception tracks magnitude: an 80% dot fills its cell without overrunning it
# and a small-but-nonzero dot stays visible via ``_S_FLOOR``.
_S_SCALE = 26.0
_S_FLOOR = 18.0
# Reference enrichments for the size legend.
_SIZE_LEGEND = [10, 40, 80]


def main() -> None:
    setup_plotting_style(font_scale=1.0)
    plt.rcParams.update({
        "font.size": 18,
        "axes.labelsize": 18,
        "axes.titlesize": 0,
        "xtick.labelsize": 16,
        "ytick.labelsize": 17,
        "legend.fontsize": 14,
    })

    df = pd.read_csv(FEATURES_TSV, sep="\t")
    universe = int(len(df))
    sonnet_only_mask = (df[SOURCE_COL["sonnet"]] == 1) & (df["n_sources_optimized"] == 0)

    def _mask(src: str) -> pd.Series:
        return sonnet_only_mask if src == "sonnet_only" else (df[SOURCE_COL[src]] == 1)

    nrows, ncols = len(SOURCE_ORDER), len(FEATURES)
    xs, ys, sizes, covs = [], [], [], []
    for i, src in enumerate(SOURCE_ORDER):
        m = _mask(src)
        n_src = int(m.sum())
        y = nrows - 1 - i  # first source at the top
        for j, (feat_col, _) in enumerate(FEATURES):
            n = int((pd.to_numeric(df.loc[m, feat_col], errors="coerce") == 1).sum())
            if n == 0 or n_src == 0:
                continue  # truly absent → empty cell (reads as depletion)
            enrichment = 100.0 * n / n_src
            xs.append(j)
            ys.append(y)
            sizes.append(max(enrichment * _S_SCALE, _S_FLOOR))
            covs.append(100.0 * n / universe)

    fig, ax = plt.subplots(figsize=(17, 8.5))
    cmap = LinearSegmentedColormap.from_list("coverage", SEQUENTIAL_PALETTES["teal"][::-1])
    norm = Normalize(vmin=0.0, vmax=max(covs))
    sc = ax.scatter(xs, ys, s=sizes, c=covs, cmap=cmap, norm=norm,
                    edgecolor=COLORS["dark"], linewidth=0.6, alpha=0.95, zorder=3)

    # Faint grid guides so the eye tracks rows/cols across the sparse matrix.
    ax.set_xticks(range(ncols))
    ax.set_xticklabels([lab for _, lab in FEATURES], rotation=35, ha="right")
    ax.set_yticks(range(nrows))
    ax.set_yticklabels([SOURCE_LABEL[s] for s in reversed(SOURCE_ORDER)])
    ax.set_xlim(-0.6, ncols - 0.4)
    ax.set_ylim(-0.6, nrows - 0.4)
    ax.set_axisbelow(True)
    ax.grid(True, which="major", color=COLORS.get("grid", "#E6DAD4"),
            linewidth=0.7, alpha=0.6, zorder=0)
    sns.despine(ax=ax, top=True, right=True, left=True, bottom=True)
    ax.tick_params(length=0)

    # Coverage colorbar — shrunk + top-anchored so the size legend can sit in
    # the right margin BELOW it without collision.
    cbar = fig.colorbar(sc, ax=ax, shrink=0.5, pad=0.015,
                        anchor=(0.0, 1.0), panchor=(0.0, 1.0))
    cbar.set_label("Coverage\n(% of surface universe)", fontsize=14)
    cbar.ax.tick_params(labelsize=12)
    cbar.outline.set_visible(False)  # ty: ignore  # Colorbar.outline is a Spine

    # Size legend — dot AREA ∝ within-source enrichment. Line2D ``markersize``
    # is a DIAMETER in points while scatter ``s`` is an AREA in points², so
    # match with markersize = 2·√(s/π). Lower-right, below the colorbar.
    handles = [
        mlines.Line2D([], [], marker="o", linestyle="none",
                      markersize=2.0 * (ref * _S_SCALE / 3.14159) ** 0.5,
                      markerfacecolor="#B9C9C4", markeredgecolor=COLORS["dark"],
                      markeredgewidth=0.6, label=f"{ref}%")
        for ref in _SIZE_LEGEND
    ]
    leg = ax.legend(handles=handles, title="Enrichment\n(% of source's own calls)",
                    loc="upper left", bbox_to_anchor=(1.015, 0.44),
                    labelspacing=3.4, borderpad=1.0, handletextpad=1.8,
                    frameon=False, fontsize=13, title_fontsize=13)
    leg._legend_box.align = "left"  # ty: ignore[unresolved-attribute]

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
