# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``triage_vs_deep_dive_reason.{pdf,png}`` — the 19×19
confusion matrix of the triage agent's first-pass
``surface_call_reason`` (rows) against the deep-dive synthesizer's
re-derived ``surface_call_reason`` (columns) on the 20-gene cohort
of currently-published deep-dive records.

Both axes draw from the same closed ``TriageReason`` enum, so the
diagonal (highlighted in maroon) is exact reason-level agreement
and off-diagonal cells split into within-bucket reassignments
(same Yes/Contextual/No bucket, different reason) and cross-bucket
flips (the cells that matter most for verdict-level drift).

The deep-dive cohort is small (n=20 as of this draft); MOCK
caption: rebuild once the v2 deep-dive sweep covers the cohort.

Standalone — ``uv run make_triage_vs_deep_dive_reason.py``.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"  # pin to a commit SHA at publication
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
# Single per-figure TSV: one row per gene with a deep-dive record AND
# a triage hit. Columns: gene_symbol, uniprot_acc, triage_reason,
# deep_dive_reason. Built by scripts/build_figure_tsvs.py.
DATA_TSV = f"{BASE}/data/processed/figures/triage_vs_deep_dive_reason.tsv"

# Filled at gist-creation time; the placeholder is harmless until then.
GIST_URL = "https://gist.github.com/beccajcarlson/152a4d8b4a1d156e2afaa73d205294b6"

# ──── Inline brand styling — sentinel: brand-style-v3 ────
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
BUCKET_COLOR = {"yes": "#2E7A55", "contextual": "#C07830", "no": "#6F5D5A"}
DIAGONAL_HIGHLIGHT = "#BC3C4C"

REASONS_ORDERED = [
    # YES
    "classical_surface_receptor", "multipass_with_exposed_loops",
    "gpi_anchored", "extracellular_face_protein", "stable_complex_partner",
    # CONTEXTUAL
    "stable_surface_attachment", "cell_state_induced",
    "tissue_restricted_surface", "lysosomal_exocytosis", "dual_localization",
    # NO
    "cytoplasmic", "nuclear", "mitochondrial_internal", "endomembrane_resident",
    "nuclear_envelope", "secreted_only", "inner_leaflet_anchored",
    "pmhc_only_intracellular", "other",
]
BUCKET = {r: "yes" for r in REASONS_ORDERED[:5]}
BUCKET.update({r: "contextual" for r in REASONS_ORDERED[5:10]})
BUCKET.update({r: "no" for r in REASONS_ORDERED[10:]})

LABEL_SHORT = {
    "classical_surface_receptor":   "classical\nsurf rcptr",
    "multipass_with_exposed_loops": "multipass\nexp loops",
    "gpi_anchored":                 "GPI\nanchored",
    "extracellular_face_protein":   "ECF\nprotein",
    "stable_complex_partner":       "stable cplx\npartner",
    "stable_surface_attachment":    "stable surf\nattachment",
    "cell_state_induced":           "cell-state\ninduced",
    "tissue_restricted_surface":    "tissue\nrestricted",
    "lysosomal_exocytosis":         "lysosomal\nexocytosis",
    "dual_localization":            "dual\nlocalization",
    "cytoplasmic":                  "cytoplasmic",
    "nuclear":                      "nuclear",
    "mitochondrial_internal":       "mito\ninternal",
    "endomembrane_resident":        "endomem\nresident",
    "nuclear_envelope":             "nuclear\nenvelope",
    "secreted_only":                "secreted\nonly",
    "inner_leaflet_anchored":       "inner leaflet\nanchored",
    "pmhc_only_intracellular":      "pMHC\nonly",
    "other":                        "other",
}


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
    _register_brand_fonts()
    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=1.0)
    plt.rcParams.update({
        "figure.facecolor": "none", "savefig.facecolor": "none",
        "font.family": "sans-serif",
        "font.sans-serif": ["Manrope", "Outfit", "DejaVu Sans", "Liberation Sans", "Arial"],
        "font.weight": "medium", "font.size": 14,
        "axes.labelsize": 18, "axes.labelweight": "medium",
        "axes.titlesize": 0, "axes.titlepad": 0,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "axes.axisbelow": True,
        "axes.edgecolor": BRAND_GRID, "axes.labelcolor": BRAND_INK,
        "axes.facecolor": "none", "text.color": BRAND_INK,
        "grid.alpha": 0.35, "grid.linestyle": "-",
        "grid.linewidth": 0.7, "grid.color": BRAND_GRID,
        "xtick.labelsize": 11, "ytick.labelsize": 11,
        "xtick.color": BRAND_INK, "ytick.color": BRAND_INK,
        "legend.frameon": False, "legend.fontsize": 13,
        "patch.edgecolor": "none", "patch.linewidth": 0.0,
        "savefig.dpi": 600, "savefig.bbox": "tight",
    })


def _fetch_tsv(url: str) -> pd.DataFrame:
    """Sibling-only: bundled TSV must sit next to this script. No
    network fetch — the gist is the single citable reproduction unit."""
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


def _build_matrix(df: pd.DataFrame) -> np.ndarray:
    n = len(REASONS_ORDERED)
    m = np.zeros((n, n), dtype=int)
    idx_of = {r: i for i, r in enumerate(REASONS_ORDERED)}
    for _, row in df.iterrows():
        t = row.get("triage_reason")
        d = row.get("deep_dive_reason")
        if t in idx_of and d in idx_of:
            m[idx_of[t], idx_of[d]] += 1
    return m


def _bucket_boundaries() -> list[int]:
    bounds: list[int] = []
    prev = None
    for i, r in enumerate(REASONS_ORDERED):
        b = BUCKET[r]
        if prev is not None and b != prev:
            bounds.append(i)
        prev = b
    return bounds


def main() -> None:
    _apply_brand_style()
    df = _fetch_tsv(DATA_TSV)
    m = _build_matrix(df)
    n = m.shape[0]

    fig, ax = plt.subplots(figsize=(15, 13))
    cmap = sns.light_palette("#3D6B60", as_cmap=True)
    sns.heatmap(
        m, ax=ax, cmap=cmap, square=True, linewidths=0.5, linecolor="#FFFFFF",
        annot=True, fmt="d", annot_kws={"fontsize": 12, "color": BRAND_INK},
        cbar_kws={"label": "genes", "shrink": 0.55, "pad": 0.02, "aspect": 25},
        xticklabels=[LABEL_SHORT[r] for r in REASONS_ORDERED],
        yticklabels=[LABEL_SHORT[r] for r in REASONS_ORDERED],
    )

    for tick, reason in zip(ax.get_xticklabels(), REASONS_ORDERED, strict=True):
        tick.set_color(BUCKET_COLOR[BUCKET[reason]])
        tick.set_fontweight("semibold")
    for tick, reason in zip(ax.get_yticklabels(), REASONS_ORDERED, strict=True):
        tick.set_color(BUCKET_COLOR[BUCKET[reason]])
        tick.set_fontweight("semibold")
    ax.tick_params(axis="x", rotation=0, pad=4)
    ax.tick_params(axis="y", rotation=0, pad=4)

    for b in _bucket_boundaries():
        ax.axhline(b, color=BRAND_INK, lw=2.0, alpha=0.85)
        ax.axvline(b, color=BRAND_INK, lw=2.0, alpha=0.85)

    for i in range(n):
        ax.add_patch(mpatches.Rectangle(
            (i, i), 1, 1, fill=False, edgecolor=DIAGONAL_HIGHLIGHT,
            lw=2.5, zorder=10,
        ))

    ax.set_xlabel("Deep-dive surface_call_reason", labelpad=12)
    ax.set_ylabel("Triage\nsurface_call_reason", labelpad=12)

    handles = [
        mpatches.Patch(facecolor=BUCKET_COLOR[b], edgecolor="none",
                       label=f"{b}-bucket reasons")
        for b in ("yes", "contextual", "no")
    ]
    handles.append(
        mpatches.Patch(facecolor="none", edgecolor=DIAGONAL_HIGHLIGHT,
                       lw=2.5, label="diagonal (reason agrees)")
    )
    ax.legend(
        handles=handles, loc="upper center",
        bbox_to_anchor=(0.5, -0.18), ncols=4, frameon=False, fontsize=13,
    )

    cohort_n = int(m.sum())
    fig.text(
        0.5, -0.02,
        f"MOCK — n = {cohort_n} deep-dive records; rebuild once the "
        f"v2 sweep covers the candidate cohort genome-wide.",
        ha="center", va="top", fontsize=12, style="italic", color=BRAND_NEUTRAL,
    )

    sns.despine(ax=ax, top=False, right=False, left=False, bottom=False)
    fig.tight_layout()

    out_pdf = Path("triage_vs_deep_dive_reason.pdf")
    out_png = Path("triage_vs_deep_dive_reason.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=600, metadata={"Source": GIST_URL})
    print(f"Wrote {out_pdf} + {out_png} (cohort n={cohort_n})")


if __name__ == "__main__":
    main()
