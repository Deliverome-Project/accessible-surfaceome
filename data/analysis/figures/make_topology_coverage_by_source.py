# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "pandas>=2.2",
#   "seaborn>=0.13",
#   "httpx>=0.27",
# ]
# ///
"""Reproduce ``topology_coverage_by_source.{pdf,png}`` from the public repo.

For every protein in the cohort-tightened v3 candidate-surfaceome
universe (6,588 proteins = candidate_universe_v3 + v3_dropped, the
post-Sonnet-no-trim union intersected with the HGNC-anchored
protein-coding cohort), 9 binary topology features are scored per
inclusion source. Each panel shows what fraction of the universe is
captured by `(source ∩ feature)` — DBs render as bars colored by the
project's M1-DB palette plus Claude-orange for Sonnet.

Panels (3×3):
  Row 1: GPI-anchored | 7TM GPCR | Multi-pass TM (non-GPCR)
  Row 2: Single-pass TM | Likely secreted (SP + no TM + no anchor) |
         Inner-leaflet lipidated (prenyl/myr, no TM/SP)
  Row 3: No TM, no signal | Glycosylation site | TM without signal
         peptide (DeepTMHMM class)

Feature-coverage denominators are the v3 universe (= proteins with
≥1 yes vote across the 6 sources). Bar height for source S on
feature F:
    100 × |S-included ∩ F-positive| / 6,588

The 9 features are a deliberate mix:
  • 7 hand-picked architecture classes (GPI / 7TM-GPCR / multi-pass
    TM / single-pass TM / signal-only-secreted / inner-leaflet
    lipidated / no-TM-no-signal) — keyword-derived from UniProt's
    `Lipidation`, `Signal`, `Topological domain`, `G-protein
    coupled receptor`, etc. annotations.
  • 1 sequence-level discriminator (`up_has_glyc`, the
    presence-or-not of any UniProt-annotated glycosylation site)
    that's the strongest non-architecture differentiator across
    sources.
  • 1 ML-prediction class (`deeptm_TM_NO_SP`, the DeepTMHMM
    "TM-only" classification — most-pass TM + Type II/III single-
    pass with internal signal-anchor instead of cleaved SP).

Inner-leaflet lipidated = (Prenylation OR Myristate UniProt
keyword) AND tm_count == 0 AND signal_count == 0 — captures Ras-
family GTPases, Src-family kinases, RhoA-class proteins whose
cytoplasmic-facing anchor makes them inaccessible from the
extracellular side. The panel exists to show which sources mis-
attribute them as "surface" (GO + HPA carry small positives;
SURFY / CSPA / Sonnet correctly under-include).

Visual styling matches the in-repo `_plotting_config` (Deliverome
categorical palette + Manrope-when-available + whitegrid + despine
+ transparent facecolor at 300 DPI). The styling block is inlined
so the gist stays self-contained.

Standalone — ``uv run make_topology_coverage_by_source.py``.
"""
from __future__ import annotations

import io
from pathlib import Path

import httpx
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"

# Published reproduction gist (embedded into the output PNG's Source
# tEXt chunk + PDF's Subject info field; pattern matches every other
# figure gist). Read back with `exiftool figure.png | grep Source`,
# or in Python: `from PIL import Image; Image.open(p).info["Source"]`.
# Set to "TBD" until `gh gist create` populates it; the canonical
# generator's `# Reproduction:` line stays the source of truth for
# the published URL.
GIST_URL = "https://gist.github.com/beccajcarlson/95b0f4cdcaf6a6b91f57539cd1515a25"

# Per-protein feature table built by the canonical audit script. One
# row per universe protein with the 6 source-inclusion flags and the
# 9 topology binary features used by this figure. ~2.8 MB plain TSV
# (non-LFS so raw.githubusercontent.com serves text, not a pointer).
FEATURES_TSV = (
    f"{BASE}/data/analysis/db_vs_sonnet_inclusion/per_protein_features.tsv"
)

# ──── Inline brand styling — sentinel: brand-style-v3 ────
# Mirrors src/accessible_surfaceome/audit/_plotting_config.py so the gist
# stays self-contained (no in-repo imports — Substack readers run it
# standalone). Kept in sync via tests/test_figure_gists_styling.py.
BRAND_PALETTE = [
    "#BC3C4C",  # maroon-light
    "#3D6B60",  # teal-mid
    "#F4AA28",  # amber-bright
    "#8878C8",  # lavender-bright
    "#6E1428",  # maroon-dark
    "#7AAB9F",  # teal-light
]
BRAND_SEQUENTIAL = {
    "maroon":   ["#3E0A18", "#6E1428", "#922038", "#BC3C4C", "#F0A098", "#FDE8E6"],
    "teal":     ["#152E28", "#244840", "#3D6B60", "#4D8A80", "#7AAB9F", "#CCE8E4"],
    "amber":    ["#5A2608", "#8C4210", "#C07830", "#F4AA28", "#F4C070", "#FAECD4"],
    "lavender": ["#1E1450", "#3A2888", "#5848A8", "#8878C8", "#A090D4", "#E4E0F8"],
}
BRAND_CLAUDE_ORANGE = "#d87851"
BRAND_INK = "#1F1718"
BRAND_NEUTRAL = "#6F5D5A"
BRAND_GRID = "#E6DAD4"


def _register_brand_fonts() -> None:
    """Register Manrope from the repo's ``assets/fonts/`` when running
    inside a checkout. External readers without the repo fall back
    to the next entry in ``font.sans-serif`` — typically DejaVu Sans
    — without erroring."""
    candidates = [
        Path(__file__).resolve().parents[3] / "assets" / "fonts",  # repo checkout
        Path.cwd() / "assets" / "fonts",                            # cwd run
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
    """Inline equivalent of `setup_plotting_style` — kept self-contained
    so the gist runs without the in-repo plotting module. Sentinel:
    brand-style-v3."""
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
        "font.size": 20,
        "axes.labelsize": 20,
        "axes.labelweight": "medium",
        "axes.titlesize": 0,
        "axes.titlepad": 0,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "axes.edgecolor": BRAND_GRID,
        "axes.labelcolor": BRAND_INK,
        "axes.facecolor": "none",
        "text.color": BRAND_INK,
        "grid.alpha": 0.35,
        "grid.linestyle": "-",
        "grid.linewidth": 0.7,
        "grid.color": BRAND_GRID,
        "xtick.labelsize": 20,
        "ytick.labelsize": 20,
        "xtick.color": BRAND_INK,
        "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "legend.fontsize": 20,
        "patch.edgecolor": "none",
        "patch.linewidth": 0.0,
    })


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

# Panel x-axis order: Sonnet first (implicit reference), then DBs
# in the order matching make_db_correctness_by_class.py for cross-
# figure visual consistency.
SOURCE_ORDER = ["sonnet", "uniprot", "surfy", "cspa", "go", "hpa"]
SOURCE_COLORS = {
    "sonnet":  BRAND_CLAUDE_ORANGE,
    "uniprot": BRAND_PALETTE[0],  # maroon-light
    "surfy":   BRAND_PALETTE[3],  # lavender-bright
    "cspa":    BRAND_PALETTE[4],  # maroon-dark
    "go":      BRAND_PALETTE[1],  # teal-mid
    "hpa":     BRAND_PALETTE[2],  # amber-bright
}
SOURCE_COL = {
    "sonnet":  "src_sonnet",
    "uniprot": "src_uniprot",
    "surfy":   "src_surfy",
    "cspa":    "src_cspa",
    "go":      "src_go",
    "hpa":     "src_hpa",
}


def _fetch_tsv(url: str) -> pd.DataFrame:
    print(f"  fetching {url} …")
    r = httpx.get(url, timeout=60.0, follow_redirects=True)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), sep="\t")
    print(f"    {len(df):,} rows × {len(df.columns)} cols")
    return df


def main() -> None:
    _apply_brand_style()
    df = _fetch_tsv(FEATURES_TSV)
    universe_size = int(len(df))

    n_feat = len(FEATURES)
    ncols = 3
    nrows = (n_feat + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(16, 3.6 * nrows))
    axes = axes.reshape(-1)

    for ax, (feat_col, label) in zip(axes, FEATURES):
        rates_pct = []
        for src_name in SOURCE_ORDER:
            src_col = SOURCE_COL[src_name]
            mask = df[src_col] == 1
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

    out_dir = Path.cwd()
    pdf_path = out_dir / "topology_coverage_by_source.pdf"
    png_path = out_dir / "topology_coverage_by_source.png"
    # PNG gets Source tEXt chunk; PDF gets Subject info field. Two
    # explicit savefig calls (rather than a single loop with a ternary)
    # so tests/test_figure_gists_styling.py can string-match
    # `metadata={"Source": GIST_URL}` and `metadata={"Subject": GIST_URL}`
    # verbatim — that's its drift-guard against gist files losing the
    # metadata embed.
    fig.savefig(png_path, format="png", dpi=600, bbox_inches="tight",
                metadata={"Source": GIST_URL})
    print(f"  saved {png_path}")
    fig.savefig(pdf_path, format="pdf", dpi=600, bbox_inches="tight",
                metadata={"Subject": GIST_URL})
    print(f"  saved {pdf_path}")


if __name__ == "__main__":
    main()
