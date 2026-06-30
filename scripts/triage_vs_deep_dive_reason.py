"""Triage reason × deep-dive reason confusion matrix (Supplementary).

For each gene that has BOTH a triage record and a deep-dive record, we have
two reason calls drawn from the SAME closed enum ``TriageReason`` (in
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
                          secreted_only, inner_leaflet_anchored,
                          pmhc_only_intracellular, other

Visualisation:

  • rows  = triage reason (top → bottom: yes-bucket, contextual-bucket,
            no-bucket; ordered within bucket to match the enum)
  • cols  = deep-dive reason (same ordering left → right)
  • cell  = number of genes with that (triage, deep-dive) pair, annotated
            inline; greyscale-sequential intensity by count
  • axis ticks coloured by their reason's bucket
            (yes=green, contextual=amber, no=neutral) — quick eyeball of
            cross-bucket flow
  • diagonal (perfect reason-level agreement) outlined in maroon
  • thick bucket-boundary lines between yes/contextual/no on each axis

**Real data, small n.** The matrix is built from the per-figure TSV
``data/processed/figures/triage_vs_deep_dive_reason.tsv`` — one row per gene
that currently has both a triage and a deep-dive record (n=20 as of this
draft). 10/20 land on the diagonal (exact reason agreement); the remaining
10 split into same-bucket relabels and cross-bucket flips. This is the same
data the gist mirror (``data/analysis/figures/make_triage_vs_deep_dive_reason.py``)
renders — keep them in sync. The matrix will widen as the v2 deep-dive sweep
covers more of the candidate cohort; re-run this script to refresh.

Run:
    uv run python scripts/triage_vs_deep_dive_reason.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import (
    COLORS,
    save_figure,
    setup_plotting_style,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data/analysis/figures"
# Single per-figure TSV: one row per gene with a deep-dive record AND a
# triage hit. Columns: gene_symbol, uniprot_acc, triage_reason,
# deep_dive_reason. Same file the gist mirror bundles.
DATA_TSV = ROOT / "data/processed/figures/triage_vs_deep_dive_reason.tsv"
SLUG = "triage_vs_deep_dive_reason"

# Full 19-value TriageReason vocabulary, ordered bucket-by-bucket
# (yes → contextual → no) to match the enum in models.py. Both axes use
# this exact ordering so the diagonal is exact reason-level agreement and
# the thick separators fall on the yes/contextual/no boundaries.
REASONS_ORDERED = [
    # YES bucket
    "classical_surface_receptor",
    "multipass_with_exposed_loops",
    "gpi_anchored",
    "extracellular_face_protein",
    "stable_complex_partner",
    # CONTEXTUAL bucket
    "stable_surface_attachment",
    "cell_state_induced",
    "tissue_restricted_surface",
    "lysosomal_exocytosis",
    "dual_localization",
    # NO bucket
    "cytoplasmic",
    "nuclear",
    "mitochondrial_internal",
    "endomembrane_resident",
    "nuclear_envelope",
    "secreted_only",
    "inner_leaflet_anchored",
    "pmhc_only_intracellular",
    "other",
]
BUCKET = {r: "yes" for r in REASONS_ORDERED[:5]}
BUCKET.update({r: "contextual" for r in REASONS_ORDERED[5:10]})
BUCKET.update({r: "no" for r in REASONS_ORDERED[10:]})
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


def _load_pairs() -> pd.DataFrame:
    """Read the per-figure TSV of (triage_reason, deep_dive_reason) pairs."""
    return pd.read_csv(DATA_TSV, sep="\t")


def _build_matrix(df: pd.DataFrame) -> np.ndarray:
    """Materialise the (triage, deep-dive) reason pairs into an n×n integer
    ndarray, ordered per REASONS_ORDERED on both axes."""
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
    df = _load_pairs()
    m = _build_matrix(df)
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
    on_diag = int(np.trace(m))
    fig.text(
        0.5, -0.02,
        f"n = {cohort_n} genes with both a triage and a deep-dive record "
        f"({on_diag}/{cohort_n} on the diagonal). Matrix widens as the v2 "
        f"deep-dive sweep covers more of the candidate cohort.",
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
