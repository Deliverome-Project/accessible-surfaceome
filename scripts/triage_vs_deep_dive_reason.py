"""Triage reason × deep-dive reason confusion matrix (MOCK supplementary).

For each gene in the deep-dive cohort, we have two reason calls drawn from the
SAME closed enum ``TriageReason`` (in
``src/accessible_surfaceome/tools/_shared/models.py``): one emitted by the
triage agent (``triage_run.reason`` in D1) and one emitted by the deep-dive
agent (``filters.surface_call_reason`` in the per-gene record). This figure
visualises agreement / disagreement between them — a confusion matrix with
both axes drawn from the same 19-value enum.

The 19 reasons collapse into 3 triage buckets in ``models.py``:

  • _YES_REASONS        — classical_surface_receptor, gpi_anchored,
                          multipass_with_exposed_loops,
                          extracellular_face_protein, stable_complex_partner
  • _CONTEXTUAL_REASONS — cell_state_induced, tissue_restricted_surface,
                          lysosomal_exocytosis, dual_localization,
                          stable_surface_attachment
  • _NO_REASONS         — cytoplasmic, nuclear, mitochondrial_internal,
                          endomembrane_resident, nuclear_envelope,
                          secreted_only, pmhc_only_intracellular

Visualisation:

  • rows  = triage reason (top → bottom: yes-bucket, contextual-bucket,
            no-bucket; ordered within bucket by display frequency)
  • cols  = deep-dive reason (same ordering left → right)
  • cell  = number of genes with that (triage, deep-dive) pair, annotated
            inline; greyscale-sequential intensity by count
  • axis ticks coloured by their reason's bucket
            (yes=green, contextual=amber, no=neutral) — quick eyeball of
            cross-bucket flow
  • diagonal (perfect reason-level agreement) outlined in maroon
  • thick bucket-boundary lines between yes/contextual/no on each axis

**MOCK — counts are placeholder estimates** pending the v2 deep-dive sweep
joining onto the ``triage_run`` table. Heavy diagonal + small off-diagonal
spread is the expected shape (deep-dive mostly confirms the triage reason;
within-bucket reassignments outnumber cross-bucket flips). Swap
``_MOCK_COUNTS`` for a public-D1 SELECT:

    SELECT t.reason AS triage_reason,
           json_extract(a.annotation_json, '$.filters.surface_call_reason')
             AS dd_reason,
           COUNT(*) AS n
    FROM triage_run_public t
    JOIN surface_annotation a ON a.gene_symbol = t.gene_symbol
    WHERE t.run_id = 'genome_full_sonnet_ncbi_v1'
    GROUP BY 1, 2;

Supplementary figure — canonical generator only, no gist mirror.

Run:
    uv run python scripts/triage_vs_deep_dive_reason.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import (
    COLORS,
    save_figure,
    setup_plotting_style,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data/analysis/figures"
SLUG = "triage_vs_deep_dive_reason"

# Top-10 reasons by display frequency in the existing deep-dive cohort.
# Ordering = bucket-by-bucket, then by within-bucket frequency. Full
# 19-value matrix would be 3.6x larger and mostly empty cells (e.g.
# pmhc_only_intracellular, nuclear_envelope are rare); the top-10
# subset captures > 95% of the cohort.
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

# Short tick labels (full enum names wrap badly). Two-line breaks
# chosen at natural word boundaries.
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
# ``deep_dive_final_categories.py`` (~2,900 canonical, ~700 likely,
# ~550 cell-state, ~450 cell-type-restricted, ~400 below-threshold).
# Off-diagonal cells encode realistic-shape disagreement:
#   • within-bucket reassignments (deep-dive switches between two
#     yes-reasons or between two no-reasons) are MODERATE
#   • cross-bucket flips (triage yes → deep-dive no, or vice versa)
#     are RARE — the interesting cells to highlight in the paper
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
    """Materialise _MOCK_COUNTS into an n×n integer ndarray, ordered per
    REASONS_ORDERED on both axes."""
    n = len(REASONS_ORDERED)
    m = np.zeros((n, n), dtype=int)
    for i, tr in enumerate(REASONS_ORDERED):
        row = _MOCK_COUNTS.get(tr, {})
        for j, dd in enumerate(REASONS_ORDERED):
            m[i, j] = row.get(dd, 0)
    return m


def _bucket_boundaries() -> list[int]:
    """Return the row/col indices BETWEEN bucket changes (for separator lines)."""
    boundaries: list[int] = []
    prev_bucket = None
    for i, reason in enumerate(REASONS_ORDERED):
        b = BUCKET[reason]
        if prev_bucket is not None and b != prev_bucket:
            boundaries.append(i)
        prev_bucket = b
    return boundaries


def make_plot() -> tuple[plt.Figure, plt.Axes]:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    plt.rcParams.update({
        "font.size": 18, "axes.labelsize": 22, "axes.titlesize": 0,
        "xtick.labelsize": 14, "ytick.labelsize": 14, "legend.fontsize": 16,
    })
    m = _build_matrix()
    n = m.shape[0]

    fig, ax = plt.subplots(figsize=(15, 13))

    # Use a sequential greyscale that pops the diagonal without
    # over-saturating the off-diagonal cells. Light at low counts so
    # the inline count labels stay legible across the whole matrix.
    cmap = sns.light_palette("#3D6B60", as_cmap=True)
    sns.heatmap(
        m, ax=ax, cmap=cmap, square=True, linewidths=0.5, linecolor="#FFFFFF",
        annot=True, fmt="d", annot_kws={"fontsize": 12, "color": "#1F1718"},
        cbar_kws={"label": "genes", "shrink": 0.55, "pad": 0.02, "aspect": 25},
        xticklabels=[LABEL_SHORT[r] for r in REASONS_ORDERED],
        yticklabels=[LABEL_SHORT[r] for r in REASONS_ORDERED],
    )

    # Color each tick label by its reason's bucket so the reader can
    # see at a glance whether triage / deep-dive landed in the same
    # bucket (label colors match) or flipped (label colors differ).
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

    # Diagonal highlight — maroon edge on each (i, i) cell. Done as
    # rectangle patches because seaborn.heatmap doesn't expose
    # per-cell edgecolor.
    for i in range(n):
        rect = mpatches.Rectangle(
            (i, i), 1, 1, fill=False, edgecolor=DIAGONAL_HIGHLIGHT,
            lw=2.5, zorder=10,
        )
        ax.add_patch(rect)

    ax.set_xlabel("Deep-dive surface_call_reason", labelpad=12)
    ax.set_ylabel("Triage\nsurface_call_reason", labelpad=12)

    # Bucket legend — three swatches anchored under the figure (the
    # axis-tick colors carry the meaning, this just spells out the
    # mapping for first-time readers).
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
        ha="center", va="top", fontsize=12, style="italic", color=COLORS["neutral"],
    )

    sns.despine(ax=ax, top=False, right=False, left=False, bottom=False)
    fig.tight_layout()
    return fig, ax


def main() -> None:
    fig, _ = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"))


if __name__ == "__main__":
    main()
