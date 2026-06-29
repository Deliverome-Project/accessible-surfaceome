# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=1.26",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``triage_vs_deep_dive_reason.{pdf,png}`` from the public repo.

**MOCK supplementary figure.** For each gene in the deep-dive cohort,
we have two reason calls drawn from the SAME closed enum
``TriageReason`` (in ``src/accessible_surfaceome/tools/_shared/models.py``):
one emitted by the triage agent (``triage_run.reason`` in D1) and one
emitted by the deep-dive agent (``filters.surface_call_reason`` in the
per-gene record). This figure visualises agreement / disagreement
between them — a confusion matrix with both axes drawn from the same
19-value enum.

The 19 reasons collapse into 3 triage buckets in ``models.py``:

  * _YES_REASONS        — classical_surface_receptor, gpi_anchored,
                          multipass_with_exposed_loops,
                          extracellular_face_protein, stable_complex_partner
  * _CONTEXTUAL_REASONS — cell_state_induced, tissue_restricted_surface,
                          lysosomal_exocytosis, dual_localization,
                          stable_surface_attachment
  * _NO_REASONS         — cytoplasmic, nuclear, mitochondrial_internal,
                          endomembrane_resident, nuclear_envelope,
                          secreted_only, pmhc_only_intracellular

Counts are placeholder estimates pending the v2 deep-dive sweep joining
onto the ``triage_run`` table. Heavy diagonal + small off-diagonal
spread is the expected shape. Swap ``_MOCK_COUNTS`` for a public-D1
SELECT once the v2 sweep completes.

Visual styling matches the in-repo `_plotting_config` (Deliverome
categorical palette + Manrope-when-available). Inlined so the gist
runs standalone — ``uv run make_triage_vs_deep_dive_reason.py``.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

# Published reproduction gist — embedded into output PNG Source / PDF
# Subject metadata (mirrors save_figure in _plotting_config.py).
GIST_URL = "https://gist.github.com/beccajcarlson/d8763d79859db70ffef660251a9bb83e"

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
                except Exception:  # noqa: BLE001
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
        "axes.labelsize": 22,
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
        "xtick.labelsize": 14,
        "ytick.labelsize": 14,
        "xtick.color": BRAND_INK,
        "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "legend.fontsize": 16,
        "patch.edgecolor": "none",
        "patch.linewidth": 0.0,
    })


# Top-10 reasons by display frequency in the existing deep-dive cohort.
# Ordering = bucket-by-bucket, then by within-bucket frequency.
REASONS_ORDERED = [
    # YES bucket
    "classical_surface_receptor",
    "multipass_with_exposed_loops",
    "gpi_anchored",
    "stable_complex_partner",
    # CONTEXTUAL bucket
    "stable_surface_attachment",
    "cell_state_induced",
    "tissue_restricted_surface",
    "dual_localization",
    # NO bucket
    "cytoplasmic",
    "endomembrane_resident",
]
BUCKET = {
    "classical_surface_receptor":   "yes",
    "multipass_with_exposed_loops": "yes",
    "gpi_anchored":                 "yes",
    "stable_complex_partner":       "yes",
    "stable_surface_attachment":    "contextual",
    "cell_state_induced":           "contextual",
    "tissue_restricted_surface":    "contextual",
    "dual_localization":            "contextual",
    "cytoplasmic":                  "no",
    "endomembrane_resident":        "no",
}
BUCKET_COLOR = {
    "yes":        "#2E7A55",
    "contextual": "#C07830",
    "no":         "#6F5D5A",
}
DIAGONAL_HIGHLIGHT = "#BC3C4C"  # maroon — diagonal border

# Short tick labels (full enum names wrap badly).
LABEL_SHORT = {
    "classical_surface_receptor":   "classical\nsurf rcptr",
    "multipass_with_exposed_loops": "multipass\nexp loops",
    "gpi_anchored":                 "GPI\nanchored",
    "stable_complex_partner":       "stable cplx\npartner",
    "stable_surface_attachment":    "stable surf\nattachment",
    "cell_state_induced":           "cell-state\ninduced",
    "tissue_restricted_surface":    "tissue\nrestricted",
    "dual_localization":            "dual\nlocalization",
    "cytoplasmic":                  "cytoplasmic",
    "endomembrane_resident":        "endomem\nresident",
}

# ── MOCK 10×10 confusion-matrix counts ──────────────────────────────────
# Rows = triage reason; cols = deep-dive reason. Hand-tuned so the
# diagonal sums roughly match the placeholder bucket totals in
# ``deep_dive_final_categories.py``. Off-diagonal cells encode realistic-
# shape disagreement:
#   • within-bucket reassignments are MODERATE
#   • cross-bucket flips are RARE — the interesting cells to highlight.
_MOCK_COUNTS: dict[str, dict[str, int]] = {
    # ───── triage = YES bucket ─────
    "classical_surface_receptor": {
        "classical_surface_receptor": 1380, "multipass_with_exposed_loops": 60,
        "gpi_anchored":               18,   "stable_complex_partner":       42,
        "stable_surface_attachment":  35,   "cell_state_induced":           28,
        "tissue_restricted_surface":  55,   "dual_localization":            22,
        "cytoplasmic":                14,   "endomembrane_resident":         8,
    },
    "multipass_with_exposed_loops": {
        "classical_surface_receptor": 45,   "multipass_with_exposed_loops": 685,
        "gpi_anchored":               5,    "stable_complex_partner":       18,
        "stable_surface_attachment":  12,   "cell_state_induced":           15,
        "tissue_restricted_surface":  22,   "dual_localization":             8,
        "cytoplasmic":                 6,   "endomembrane_resident":         4,
    },
    "gpi_anchored": {
        "classical_surface_receptor": 8,    "multipass_with_exposed_loops":  2,
        "gpi_anchored":               265,  "stable_complex_partner":        4,
        "stable_surface_attachment":  18,   "cell_state_induced":            3,
        "tissue_restricted_surface":  10,   "dual_localization":             5,
        "cytoplasmic":                 1,   "endomembrane_resident":         2,
    },
    "stable_complex_partner": {
        "classical_surface_receptor": 28,   "multipass_with_exposed_loops":  6,
        "gpi_anchored":               2,    "stable_complex_partner":       155,
        "stable_surface_attachment":  20,   "cell_state_induced":            5,
        "tissue_restricted_surface":  8,    "dual_localization":            10,
        "cytoplasmic":                 4,   "endomembrane_resident":         3,
    },
    # ───── triage = CONTEXTUAL bucket ─────
    "stable_surface_attachment": {
        "classical_surface_receptor": 12,   "multipass_with_exposed_loops":  4,
        "gpi_anchored":               6,    "stable_complex_partner":       18,
        "stable_surface_attachment":  295,  "cell_state_induced":           14,
        "tissue_restricted_surface":  22,   "dual_localization":            25,
        "cytoplasmic":                 5,   "endomembrane_resident":         8,
    },
    "cell_state_induced": {
        "classical_surface_receptor": 8,    "multipass_with_exposed_loops":  3,
        "gpi_anchored":               2,    "stable_complex_partner":        4,
        "stable_surface_attachment":  18,   "cell_state_induced":           475,
        "tissue_restricted_surface":  25,   "dual_localization":            32,
        "cytoplasmic":                10,   "endomembrane_resident":         6,
    },
    "tissue_restricted_surface": {
        "classical_surface_receptor": 25,   "multipass_with_exposed_loops":  8,
        "gpi_anchored":               6,    "stable_complex_partner":        7,
        "stable_surface_attachment":  20,   "cell_state_induced":           30,
        "tissue_restricted_surface":  385,  "dual_localization":            15,
        "cytoplasmic":                 5,   "endomembrane_resident":         4,
    },
    "dual_localization": {
        "classical_surface_receptor": 10,   "multipass_with_exposed_loops":  3,
        "gpi_anchored":               2,    "stable_complex_partner":        5,
        "stable_surface_attachment":  18,   "cell_state_induced":           22,
        "tissue_restricted_surface":  12,   "dual_localization":           175,
        "cytoplasmic":                 8,   "endomembrane_resident":        10,
    },
    # ───── triage = NO bucket ─────
    "cytoplasmic": {
        "classical_surface_receptor":  5,   "multipass_with_exposed_loops":  2,
        "gpi_anchored":                1,   "stable_complex_partner":        2,
        "stable_surface_attachment":   8,   "cell_state_induced":           10,
        "tissue_restricted_surface":   4,   "dual_localization":             6,
        "cytoplasmic":               195,   "endomembrane_resident":        22,
    },
    "endomembrane_resident": {
        "classical_surface_receptor":  3,   "multipass_with_exposed_loops":  1,
        "gpi_anchored":                1,   "stable_complex_partner":        1,
        "stable_surface_attachment":  15,   "cell_state_induced":            8,
        "tissue_restricted_surface":   3,   "dual_localization":             5,
        "cytoplasmic":                18,   "endomembrane_resident":       145,
    },
}


def _build_matrix() -> np.ndarray:
    n = len(REASONS_ORDERED)
    m = np.zeros((n, n), dtype=int)
    for i, tr in enumerate(REASONS_ORDERED):
        row = _MOCK_COUNTS.get(tr, {})
        for j, dd in enumerate(REASONS_ORDERED):
            m[i, j] = row.get(dd, 0)
    return m


def _bucket_boundaries() -> list[int]:
    boundaries: list[int] = []
    prev_bucket = None
    for i, reason in enumerate(REASONS_ORDERED):
        b = BUCKET[reason]
        if prev_bucket is not None and b != prev_bucket:
            boundaries.append(i)
        prev_bucket = b
    return boundaries


def main() -> None:
    _apply_brand_style()
    m = _build_matrix()
    n = m.shape[0]

    fig, ax = plt.subplots(figsize=(15, 13))

    # Sequential greyscale that pops the diagonal without over-saturating
    # the off-diagonal cells.
    cmap = sns.light_palette("#3D6B60", as_cmap=True)
    sns.heatmap(
        m, ax=ax, cmap=cmap, square=True, linewidths=0.5, linecolor="#FFFFFF",
        annot=True, fmt="d", annot_kws={"fontsize": 12, "color": "#1F1718"},
        cbar_kws={"label": "genes", "shrink": 0.55, "pad": 0.02, "aspect": 25},
        xticklabels=[LABEL_SHORT[r] for r in REASONS_ORDERED],
        yticklabels=[LABEL_SHORT[r] for r in REASONS_ORDERED],
    )

    # Color each tick label by its reason's bucket so the reader can see
    # at a glance whether triage / deep-dive landed in the same bucket.
    for tick, reason in zip(ax.get_xticklabels(), REASONS_ORDERED, strict=True):
        tick.set_color(BUCKET_COLOR[BUCKET[reason]])
        tick.set_fontweight("semibold")
    for tick, reason in zip(ax.get_yticklabels(), REASONS_ORDERED, strict=True):
        tick.set_color(BUCKET_COLOR[BUCKET[reason]])
        tick.set_fontweight("semibold")
    ax.tick_params(axis="x", rotation=0, pad=4)
    ax.tick_params(axis="y", rotation=0, pad=4)

    # Bucket-boundary separators (thick lines between yes / contextual / no).
    for b in _bucket_boundaries():
        ax.axhline(b, color="#1F1718", lw=2.0, alpha=0.85)
        ax.axvline(b, color="#1F1718", lw=2.0, alpha=0.85)

    # Diagonal highlight — maroon edge on each (i, i) cell.
    for i in range(n):
        rect = mpatches.Rectangle(
            (i, i), 1, 1, fill=False, edgecolor=DIAGONAL_HIGHLIGHT,
            lw=2.5, zorder=10,
        )
        ax.add_patch(rect)

    ax.set_xlabel("Deep-dive surface_call_reason", labelpad=12)
    ax.set_ylabel("Triage\nsurface_call_reason", labelpad=12)

    # Bucket legend.
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
        handles=handles,
        loc="upper center", bbox_to_anchor=(0.5, -0.10),
        ncols=4, frameon=False, fontsize=13,
    )

    cohort_n = int(m.sum())
    fig.text(
        0.5, -0.02,
        f"MOCK — placeholder counts; rebuild once the v2 deep-dive sweep "
        f"lands and joins onto triage_run (cohort n = {cohort_n:,})",
        ha="center", va="top", fontsize=12, style="italic", color=BRAND_NEUTRAL,
    )

    sns.despine(ax=ax, top=False, right=False, left=False, bottom=False)
    fig.tight_layout()

    out_pdf = Path("triage_vs_deep_dive_reason.pdf")
    out_png = Path("triage_vs_deep_dive_reason.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=600, metadata={"Source": GIST_URL})
    print(f"Wrote {out_pdf} + {out_png}  (cohort n = {cohort_n:,})")


if __name__ == "__main__":
    main()
