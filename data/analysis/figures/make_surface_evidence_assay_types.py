# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "pandas>=2.2",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``surface_evidence_assay_types.{pdf,png}`` — which experiments
established the surface calls, and how often each one stood alone.

Panel a is prevalence: genes with at least one *supporting* surface-expression
claim from each assay. Panel b is the share of those genes for which the assay
was the only primary-tier assay supporting the call — pull it and the call has
no direct experimental support left.

Panel b is the one worth reading. Prevalence mostly tracks how common a
technique is in the literature; standing alone tracks how much weight the
catalog places on it. Surfaceome mass spec is 7th by prevalence but 1st among
intact-cell assays by standing alone, because a surfaceome hit is often the
only published experiment that put a probe on the outside of that protein.
Surface biotinylation is the mirror image — it almost never appears without
corroboration.

Scope (each filter changes the answer, so all are stated):
  * ``claim_type='surface_expression'`` only — tissue-expression and topology
    rows reuse the same assay vocabulary but say nothing about the surface.
  * ``direction='supports'`` only — an assay arguing against surface
    localization is not evidence the call rests on.
  * genes in a surface-positive tier (canonical / likely / low), so "only
    assay" means only assay behind a real surface call.
  * assays under 50 genes dropped — a percentage over 26 genes is noise.

The bundled sibling TSV is produced by ``scripts/build_figure_tsvs.py``
(``build_surface_evidence_assay_types``) from the deep-dive D1 export, so this
mirror renders the same dataset as the in-repo canonical.

Standalone — ``uv run make_surface_evidence_assay_types.py``.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"  # pin to a commit SHA at publication for immutable citation
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
# Single per-figure TSV: one row per evidence_type with genes_used,
# genes_sole, genes_sole_primary and their percentages. Gist bundles this
# TSV next to the script; the figure reads ONLY from the sibling.
DATA_TSV = f"{BASE}/data/processed/figures/surface_evidence_assay_types.tsv"

# Published reproduction gist (embedded into output PNG Source / PDF
# Subject metadata — mirrors save_figure in _plotting_config.py).
GIST_URL = "https://gist.github.com/beccajcarlson/141184baa53bc889d2c08692b931982b"

# ──── Inline brand styling — sentinel: brand-style-v3 ────
# Mirrors src/accessible_surfaceome/audit/_plotting_config.py so the gist
# stays self-contained (no in-repo imports — Substack readers run it
# standalone). Kept in sync via tests/test_figure_canonical_mirror_sync.py.
BRAND_INK = "#1F1718"
BRAND_PALETTE = [
    "#BC3C4C",  # maroon-light
    "#3D6B60",  # teal-mid
    "#F4AA28",  # amber-bright
    "#8878C8",  # lavender-bright
    "#6E1428",  # maroon-dark
    "#7AAB9F",  # teal-light
]
BRAND_NEUTRAL = "#6F5D5A"
BRAND_GRID = "#E6DAD4"

MIN_GENES = 50

# Assays that put a probe on an intact cell, vs everything else. The split
# is the point of the figure: a call resting on a direct assay is a
# different object from one resting on a review assertion.
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

COLOR_DIRECT = "#3D6B60"    # teal-mid — direct surface assay
COLOR_INDIRECT = "#C7BDB6"  # warm grey — everything else


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
                except Exception:  # noqa: BLE001
                    continue
            return


def _apply_brand_style() -> None:
    """Inline equivalent of ``setup_plotting_style``. Sentinel: brand-style-v3."""
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
        "font.size": 16,
        "axes.labelsize": 18,
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
        "xtick.labelsize": 15,
        "ytick.labelsize": 15,
        "xtick.color": BRAND_INK,
        "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "legend.fontsize": 15,
        "patch.edgecolor": "none",
        "patch.linewidth": 0.0,
    })


def _fetch_tsv(url: str) -> pd.DataFrame:
    """Bundled-only: the gist HEAD commit SHA is the SWHID for the whole
    reproduction unit (script + data + README), so we must never read a
    *different* TSV than what's bundled. Sibling-first (gist case); fall
    back to the in-repo TSV path (dev case). No network fetch."""
    sibling = Path(__file__).parent / Path(url).name
    if sibling.is_file():
        return pd.read_csv(sibling, sep="\t")
    local = Path(__file__).resolve().parents[3] / url[len(BASE) + 1:]
    if local.is_file():
        return pd.read_csv(local, sep="\t")
    raise FileNotFoundError(
        f"TSV not found at sibling ({sibling.name}) or local ({local}). "
        f"In a gist, the bundled TSV must sit next to this script."
    )


def _panel_label(ax, letter: str) -> None:
    ax.text(-0.02, 1.04, letter, transform=ax.transAxes, fontsize=26,
            fontweight=800, va="bottom", ha="right", color=BRAND_INK)


def main() -> None:
    _apply_brand_style()

    df = _fetch_tsv(DATA_TSV)
    df = df[df["genes_used"] >= MIN_GENES].copy()
    df["label"] = df["evidence_type"].map(
        lambda t: LABEL.get(t, t.replace("_", " ").capitalize())
    )
    df["is_direct"] = df["evidence_type"].isin(DIRECT_SURFACE_ASSAYS)
    df = df.sort_values("genes_used", ascending=True).reset_index(drop=True)
    colors = [COLOR_DIRECT if d else COLOR_INDIRECT for d in df["is_direct"]]

    fig, (ax_a, ax_b) = plt.subplots(
        1, 2, figsize=(17, 8), sharey=True,
        gridspec_kw={"width_ratios": [1.35, 1.0], "wspace": 0.08},
    )

    ax_a.barh(df["label"], df["genes_used"], color=colors, edgecolor="none")
    for y, n in enumerate(df["genes_used"]):
        ax_a.text(n + 40, y, f"{n:,}", va="center", ha="left",
                  fontsize=13, color=BRAND_NEUTRAL)
    ax_a.set_xlabel("Genes with supporting\nsurface evidence")
    ax_a.set_xlim(0, df["genes_used"].max() * 1.16)

    ax_b.barh(df["label"], df["pct_sole_primary"], color=colors, edgecolor="none")
    for y, p in enumerate(df["pct_sole_primary"]):
        ax_b.text(p + 0.12, y, f"{p:.1f}%", va="center", ha="left",
                  fontsize=13, color=BRAND_NEUTRAL)
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
        ha="center", va="top", fontsize=13, style="italic", color=BRAND_NEUTRAL,
    )
    fig.tight_layout()

    # Embed the gist URL into the artifacts (PNG Source tEXt / PDF Subject)
    # so a figure dragged into Substack or Slack still says where it came
    # from. Mirrors save_figure(gist_url=...) in _plotting_config.py.
    out = Path(__file__).parent / "surface_evidence_assay_types"
    fig.savefig(f"{out}.pdf", bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(f"{out}.png", bbox_inches="tight", dpi=600,
                metadata={"Source": GIST_URL})
    print(f"  wrote {out}.pdf + {out}.png  ({len(df)} assays)")


if __name__ == "__main__":
    main()
