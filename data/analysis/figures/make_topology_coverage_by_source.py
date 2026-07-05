# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "pandas>=2.2",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``topology_coverage_by_source.{pdf,png}`` from the public repo.

Supp Fig 9 — a single **bubble matrix** of surface inclusion sources (rows) ×
topology features (columns). For every gene in the FULL any-yes-vote universe
(Sonnet yes/contextual incl. the PubMed rescue OR any optimized-DB vote; 960
zero-DB Sonnet rescues), 9 binary topology features are scored per source. Each
cell's dot encodes BOTH metrics at once:

  • dot AREA  ∝ within-source enrichment — % of that source's OWN calls carrying
    the feature  (``|source ∩ feature| / |source|``)
  • dot COLOR = coverage — % of the whole surface universe those represent
    (``|source ∩ feature| / |universe|``)

CSPA × glycosylation is a large, pale dot (~75% of its own calls, but a small
slice of the universe — its N-glycocapture chemistry); SURFY/UniProt show the
same glyco enrichment at larger scale (dark); the zero-DB Sonnet rescues are
dominated by likely-secreted + glycosylated contextual-surface proteins the
classical-topology DBs miss (and carry no GPCR / GPI).

Reads the dedicated per-figure TSV (built by scripts/build_figure_tsvs.py from
scripts/export_s9_full_universe_features.py): src_* source flags, optimized
cutoffs, n_sources_optimized, and the 9 topology features on full coverage.

Visual styling matches the in-repo `_plotting_config`, inlined so the gist runs
standalone — ``uv run make_topology_coverage_by_source.py``.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.lines as mlines
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap, Normalize

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"

GIST_URL = "https://gist.github.com/beccajcarlson/95b0f4cdcaf6a6b91f57539cd1515a25"

FEATURES_TSV = (
    f"{BASE}/data/processed/figures/topology_coverage_by_source.tsv"
)

# ──── Inline brand styling — sentinel: brand-style-v3 ────
BRAND_PALETTE = [
    "#BC3C4C", "#3D6B60", "#F4AA28", "#8878C8", "#6E1428", "#7AAB9F",
]
BRAND_SEQUENTIAL = {
    "maroon":   ["#3E0A18", "#6E1428", "#922038", "#BC3C4C", "#F0A098", "#FDE8E6"],
    "teal":     ["#152E28", "#244840", "#3D6B60", "#4D8A80", "#7AAB9F", "#CCE8E4"],
    "amber":    ["#5A2608", "#8C4210", "#C07830", "#F4AA28", "#F4C070", "#FAECD4"],
    "lavender": ["#1E1450", "#3A2888", "#5848A8", "#8878C8", "#A090D4", "#E4E0F8"],
}
BRAND_INK = "#1F1718"
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
                except Exception:  # noqa: BLE001 — best-effort
                    continue
            return


def _apply_brand_style() -> None:
    """Inline equivalent of `setup_plotting_style`. Sentinel: brand-style-v3."""
    _register_brand_fonts()
    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=1.0)
    plt.rcParams.update({
        "savefig.dpi": 600,
        "savefig.bbox": "tight",
        "figure.facecolor": "none",
        "savefig.facecolor": "none",
        "font.family": "sans-serif",
        "font.sans-serif": ["Manrope", "Outfit", "DejaVu Sans", "Liberation Sans", "Arial"],
        "font.weight": "medium",
        "font.size": 18,
        "axes.labelsize": 18,
        "axes.titlesize": 0,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": BRAND_GRID,
        "axes.labelcolor": BRAND_INK,
        "axes.facecolor": "none",
        "text.color": BRAND_INK,
        "grid.alpha": 0.35,
        "grid.linestyle": "-",
        "grid.linewidth": 0.7,
        "grid.color": BRAND_GRID,
        "xtick.labelsize": 16,
        "ytick.labelsize": 17,
        "xtick.color": BRAND_INK,
        "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "legend.fontsize": 14,
        "patch.edgecolor": "none",
        "patch.linewidth": 0.0,
    })


# Columns (features) — the 9 topology classes.
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

# Rows (sources), top-to-bottom.
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
SOURCE_COL = {
    "sonnet":  "src_sonnet",
    "uniprot": "uniprot_optimized",
    "surfy":   "src_surfy",
    "cspa":    "cspa_optimized",
    "go":      "src_go",
    "hpa":     "src_hpa",
}

_S_SCALE = 26.0
_S_FLOOR = 18.0
_SIZE_LEGEND = [10, 40, 80]


def _fetch_tsv(url: str) -> pd.DataFrame:
    """Bundled-only: sibling-first (gist case); fall back to the in-repo TSV
    path (dev case). No network fetch."""
    sibling = Path(__file__).parent / Path(url).name
    if sibling.is_file():
        return pd.read_csv(sibling, sep="\t")
    if url.startswith(BASE + "/"):
        local = Path(__file__).resolve().parents[3] / url[len(BASE) + 1:]
        if local.is_file():
            return pd.read_csv(local, sep="\t")
    raise FileNotFoundError(
        f"TSV not found at sibling ({sibling.name}) or in-repo path. "
        f"In a gist, the bundled TSV must sit next to this script."
    )


def main() -> None:
    _apply_brand_style()
    df = _fetch_tsv(FEATURES_TSV)
    universe = int(len(df))
    sonnet_only_mask = (df[SOURCE_COL["sonnet"]] == 1) & (df["n_sources_optimized"] == 0)

    def _mask(src: str) -> pd.Series:
        return sonnet_only_mask if src == "sonnet_only" else (df[SOURCE_COL[src]] == 1)

    nrows, ncols = len(SOURCE_ORDER), len(FEATURES)
    xs, ys, sizes, covs = [], [], [], []
    for i, src in enumerate(SOURCE_ORDER):
        m = _mask(src)
        n_src = int(m.sum())
        y = nrows - 1 - i
        for j, (feat_col, _) in enumerate(FEATURES):
            n = int((pd.to_numeric(df.loc[m, feat_col], errors="coerce") == 1).sum())
            if n == 0 or n_src == 0:
                continue
            enrichment = 100.0 * n / n_src
            xs.append(j)
            ys.append(y)
            sizes.append(max(enrichment * _S_SCALE, _S_FLOOR))
            covs.append(100.0 * n / universe)

    fig, ax = plt.subplots(figsize=(17, 8.5))
    cmap = LinearSegmentedColormap.from_list("coverage", BRAND_SEQUENTIAL["teal"][::-1])
    norm = Normalize(vmin=0.0, vmax=max(covs))
    sc = ax.scatter(xs, ys, s=sizes, c=covs, cmap=cmap, norm=norm,
                    edgecolor=BRAND_INK, linewidth=0.6, alpha=0.95, zorder=3)

    ax.set_xticks(range(ncols))
    ax.set_xticklabels([lab for _, lab in FEATURES], rotation=35, ha="right")
    ax.set_yticks(range(nrows))
    ax.set_yticklabels([SOURCE_LABEL[s] for s in reversed(SOURCE_ORDER)])
    ax.set_xlim(-0.6, ncols - 0.4)
    ax.set_ylim(-0.6, nrows - 0.4)
    ax.set_axisbelow(True)
    ax.grid(True, which="major", color=BRAND_GRID, linewidth=0.7, alpha=0.6, zorder=0)
    sns.despine(ax=ax, top=True, right=True, left=True, bottom=True)
    ax.tick_params(length=0)

    cbar = fig.colorbar(sc, ax=ax, shrink=0.5, pad=0.015,
                        anchor=(0.0, 1.0), panchor=(0.0, 1.0))
    cbar.set_label("Coverage\n(% of surface universe)", fontsize=14)
    cbar.ax.tick_params(labelsize=12)
    cbar.outline.set_visible(False)  # ty: ignore  # Colorbar.outline is a Spine

    handles = [
        mlines.Line2D([], [], marker="o", linestyle="none",
                      markersize=2.0 * (ref * _S_SCALE / 3.14159) ** 0.5,
                      markerfacecolor="#B9C9C4", markeredgecolor=BRAND_INK,
                      markeredgewidth=0.6, label=f"{ref}%")
        for ref in _SIZE_LEGEND
    ]
    leg = ax.legend(handles=handles, title="Enrichment\n(% of source's own calls)",
                    loc="upper left", bbox_to_anchor=(1.015, 0.44),
                    labelspacing=3.4, borderpad=1.0, handletextpad=1.8,
                    frameon=False, fontsize=13, title_fontsize=13)
    leg._legend_box.align = "left"  # ty: ignore[unresolved-attribute]

    fig.tight_layout()

    out_dir = Path.cwd()
    pdf_path = out_dir / "topology_coverage_by_source.pdf"
    png_path = out_dir / "topology_coverage_by_source.png"
    fig.savefig(png_path, format="png", dpi=600, bbox_inches="tight",
                metadata={"Source": GIST_URL})
    print(f"  saved {png_path}")
    fig.savefig(pdf_path, format="pdf", dpi=600, bbox_inches="tight",
                metadata={"Subject": GIST_URL})
    print(f"  saved {pdf_path}")


if __name__ == "__main__":
    main()
