"""Triage → deep-dive comparison, two panels (Supplementary S12).

For each gene that has BOTH a triage record and a deep-dive record, we have the
triage-stage call (from the genome-wide Sonnet triage run) and the deep-dive's
evidence-anchored call. This figure shows how the two relate:

**Panel a — verdict flow.** A 100%-stacked bar, one bar per triage verdict
(``yes`` / ``contextual`` / ``no``), each split by the deep-dive's 5-tier
call (``canonical`` / ``likely`` / ``low`` / ``uncertain`` / ``no``, from
``_dd_assign_bucket``). Reads as: given triage said X, where did the
evidence-anchored deep dive land? Triage-``yes`` genes overwhelmingly confirm
as canonical/likely surface; triage-``no`` genes mostly stay ``no`` but a
minority get rescued up to likely/low; triage-``contextual`` spreads across the
middle tiers.

**Panel b — reason confusion matrix.** The triage reason (rows) against the
deep-dive ``surface_call_reason`` (columns), both drawn from the same closed
``TriageReason`` enum (in ``src/accessible_surfaceome/tools/_shared/models.py``).
The 19 reasons collapse into 3 verdict buckets in ``models.py`` (yes /
contextual / no); the diagonal (highlighted in maroon) is exact reason-level
agreement, thick separators mark the bucket boundaries, and tick labels are
colored by bucket so a cross-bucket flip is visible at a glance.

**Real data.** Built from the per-figure TSV
``data/processed/figures/triage_vs_deep_dive_reason.tsv`` — one row per gene
with both a triage and a deep-dive record (n≈1,197). The triage verdict/reason
come from D1's genome-wide Sonnet triage run; the deep-dive reason/tier come
from the deep-dive export. The same TSV backs the gist mirror
(``data/analysis/figures/make_triage_vs_deep_dive_reason.py``).

PRELIMINARY — ~1,197 of ~5,128 swept, pre-QA-fix. ~50% of genes land on the
reason diagonal; the rest split into same-bucket relabels and cross-bucket
flips.

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
# triage hit. Columns: gene_symbol, uniprot_acc, triage_verdict,
# triage_reason, deep_dive_reason, deep_dive_tier. Same file the gist mirror
# bundles.
DATA_TSV = ROOT / "data/processed/figures/triage_vs_deep_dive_reason.tsv"
SLUG = "triage_vs_deep_dive_reason"

# ── Panel a: triage verdicts (rows/bars) × deep-dive tiers (stack segments) ──
TRIAGE_VERDICT_ORDER = ["yes", "contextual", "no"]
TRIAGE_VERDICT_LABEL = {
    "yes":        "triage: yes",
    "contextual": "triage: contextual",
    "no":         "triage: no",
}
# 5-tier deep-dive spectrum (best → worst) with the canonical tier colors
# shared across every deep-dive figure (see deep_dive_final_categories).
DD_TIER_ORDER = ["canonical", "likely", "low", "uncertain", "no"]
DD_TIER_COLOR = {
    "canonical": "#2E7A55",  # success green — strict tier
    "likely":    "#3D6B60",  # teal-mid — broader tier
    "low":       "#C99A5B",  # amber-tan — low/moderate access, weak evidence
    "uncertain": "#C7BDB6",  # light warm grey — ambiguous
    "no":        "#9C8C88",  # lifted neutral — leaned not-surface
}
DD_TIER_LABEL = {
    "canonical": "canonical",
    "likely":    "likely",
    "low":       "low",
    "uncertain": "uncertain",
    "no":        "no",
}

# ── Panel b: the shared 19-value TriageReason vocabulary ──
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
    """Read the per-figure TSV (triage_verdict, triage_reason,
    deep_dive_reason, deep_dive_tier) — one row per gene."""
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


def _draw_verdict_flow(ax: plt.Axes, df: pd.DataFrame) -> None:
    """Panel a — 100%-stacked horizontal bars: one bar per triage verdict,
    each split by the deep-dive tier composition (fraction), with the raw
    count annotated inside each meaningful segment."""
    ct = pd.crosstab(df["triage_verdict"], df["deep_dive_tier"])
    ct = ct.reindex(index=TRIAGE_VERDICT_ORDER, columns=DD_TIER_ORDER, fill_value=0)
    totals = ct.sum(axis=1)
    frac = ct.div(totals.replace(0, np.nan), axis=0).fillna(0.0)

    y_pos = np.arange(len(TRIAGE_VERDICT_ORDER))[::-1]  # yes on top
    for yi, verdict in zip(y_pos, TRIAGE_VERDICT_ORDER):
        left = 0.0
        for tier in DD_TIER_ORDER:
            w = float(frac.loc[verdict, tier])
            if w <= 0:
                continue
            ax.barh(yi, w, left=left, height=0.62,
                    color=DD_TIER_COLOR[tier], edgecolor="white", linewidth=0.8)
            n = int(ct.loc[verdict, tier])
            if w >= 0.05:  # annotate segments wide enough to hold a label
                txt_color = "white" if tier in ("canonical", "likely") else COLORS["dark"]
                ax.text(left + w / 2, yi, f"{w * 100:.0f}%\n({n})",
                        ha="center", va="center", fontsize=11,
                        color=txt_color, fontweight="semibold")
            left += w

    ax.set_yticks(y_pos)
    ax.set_yticklabels([f"{TRIAGE_VERDICT_LABEL[v]}\n(n={int(totals[v])})"
                        for v in TRIAGE_VERDICT_ORDER])
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0", "25", "50", "75", "100%"])
    ax.set_xlabel("Deep-dive tier composition (per triage verdict)")
    ax.set_title("Verdict flow: triage call → deep-dive tier",
                 fontsize=16, fontweight="semibold", pad=12)

    handles = [mpatches.Patch(facecolor=DD_TIER_COLOR[t], edgecolor="none",
                              label=DD_TIER_LABEL[t]) for t in DD_TIER_ORDER]
    ax.legend(handles=handles, title="deep-dive tier", loc="upper center",
              bbox_to_anchor=(0.5, -0.14), ncols=5, frameon=False,
              fontsize=12, title_fontsize=13)
    sns.despine(ax=ax, top=True, right=True)


def _draw_reason_matrix(ax: plt.Axes, m: np.ndarray) -> None:
    """Panel b — the 19×19 triage × deep-dive reason confusion matrix."""
    n = m.shape[0]
    cmap = sns.light_palette("#3D6B60", as_cmap=True)
    sns.heatmap(
        m, ax=ax, cmap=cmap, square=True, linewidths=0.5, linecolor="#FFFFFF",
        annot=True, fmt="d", annot_kws={"fontsize": 10, "color": "#1F1718"},
        cbar_kws={"label": "genes", "shrink": 0.45, "pad": 0.02, "aspect": 25},
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
        ax.axhline(b, color="#1F1718", lw=2.0, alpha=0.85)
        ax.axvline(b, color="#1F1718", lw=2.0, alpha=0.85)
    for i in range(n):
        ax.add_patch(mpatches.Rectangle(
            (i, i), 1, 1, fill=False, edgecolor=DIAGONAL_HIGHLIGHT,
            lw=2.5, zorder=10,
        ))
    ax.set_xlabel("Deep-dive surface_call_reason", labelpad=10)
    ax.set_ylabel("Triage\nsurface_call_reason", labelpad=10)
    ax.set_title("Reason confusion: triage reason × deep-dive reason",
                 fontsize=16, fontweight="semibold", pad=12)

    handles = [
        mpatches.Patch(facecolor=BUCKET_COLOR[b], edgecolor="none",
                       label=f"{b}-bucket reasons")
        for b in ("yes", "contextual", "no")
    ]
    handles.append(
        mpatches.Patch(facecolor="none", edgecolor=DIAGONAL_HIGHLIGHT,
                       lw=2.5, label="diagonal (reason agrees)")
    )
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.12),
              ncols=4, frameon=False, fontsize=12)


def make_plot() -> tuple[plt.Figure, list[plt.Axes]]:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    plt.rcParams.update({
        "font.size": 18, "axes.labelsize": 20, "axes.titlesize": 16,
        "xtick.labelsize": 12, "ytick.labelsize": 14, "legend.fontsize": 13,
    })
    df = _load_pairs()
    m = _build_matrix(df)

    fig = plt.figure(figsize=(24, 13))
    # Panel a (verdict flow) is a short 3-bar chart; panel b (matrix) is a big
    # square — give b most of the width. Extra top/bottom margin for the
    # per-panel legends that sit below each axes.
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.85], wspace=0.32)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])

    _draw_verdict_flow(ax_a, df)
    _draw_reason_matrix(ax_b, m)

    # Subpanel letters (lowercase, ExtraBold) at upper-left of each panel.
    for ax, letter in ((ax_a, "a"), (ax_b, "b")):
        ax.text(-0.08, 1.05, letter, transform=ax.transAxes,
                ha="left", va="top", fontsize=24, fontweight=800,
                color=COLORS["dark"])

    cohort_n = int(m.sum())
    on_diag = int(np.trace(m))
    fig.text(
        0.5, 0.02,
        f"n = {cohort_n} genes with both a triage and a deep-dive record "
        f"({on_diag}/{cohort_n} on the reason diagonal, {100 * on_diag / cohort_n:.0f}%). "
        f"PRELIMINARY — ~1,197 of ~5,128 swept, pre-QA-fix; widens as the sweep grows.",
        ha="center", va="bottom", fontsize=12, style="italic", color=COLORS["neutral"],
    )

    fig.tight_layout(rect=(0, 0.04, 1, 0.98))
    return fig, [ax_a, ax_b]


def main() -> None:
    fig, _ = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"))


if __name__ == "__main__":
    main()
