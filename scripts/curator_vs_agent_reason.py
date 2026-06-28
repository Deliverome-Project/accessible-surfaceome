"""Curator vs agent ``TriageReason`` agreement on SurfaceBench.

Per-gene comparison of the manual curator's ground-truth ``reason``
(from ``data/eval/triage_benchmark_v1.tsv``) against the production
triage agent's ``predicted_reason`` (from
``data/processed/triage_bench/mainbench_canonical_v2.tsv``, filtered
to ``model=claude-sonnet-4-6`` ``prompt_variant=ncbi``, n=147 genes).
Both reasons are drawn from the same closed 19-value ``TriageReason``
enum — so the diagonal of the matrix is exact-reason agreement, and
the within-bucket / cross-bucket off-diagonals tell different stories:

  * within-bucket reassignments (e.g. agent said ``gpi_anchored`` where
    curator said ``classical_surface_receptor``) — the agent and curator
    agree at the YES level but disagree at the reason level
  * cross-bucket flips (e.g. curator says ``cell_state_induced``
    (contextual), agent says ``cytoplasmic`` (no)) — verdict-level
    disagreement, the cells that matter most

Headline: ~84% exact reason agreement; the matrix shows which reason
classes carry the residual disagreement.

Run:
    uv run python scripts/curator_vs_agent_reason.py
"""
from __future__ import annotations

import csv
from collections import defaultdict
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
SLUG = "curator_vs_agent_reason"

BENCH_TSV = ROOT / "data/eval/triage_benchmark_v1.tsv"
PRED_TSV = ROOT / "data/processed/triage_bench/mainbench_canonical_v2.tsv"
PROD_MODEL = "claude-sonnet-4-6"
PROD_VARIANT = "ncbi"

# Display order — yes → contextual → no, matching the existing
# triage_vs_deep_dive_reason supp figure. Reasons absent from this
# audit (e.g. ``stable_complex_partner`` n=1) are still rendered so
# the axes match the rest of the figure family.
REASONS_ORDERED = [
    # YES
    "classical_surface_receptor",
    "multipass_with_exposed_loops",
    "gpi_anchored",
    "extracellular_face_protein",
    "stable_complex_partner",
    # CONTEXTUAL
    "stable_surface_attachment",
    "cell_state_induced",
    "tissue_restricted_surface",
    "lysosomal_exocytosis",
    "dual_localization",
    # NO
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
BUCKET_COLOR = {"yes": "#2E7A55", "contextual": "#C07830", "no": "#6F5D5A"}
DIAGONAL_HIGHLIGHT = "#BC3C4C"

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


def _load_curator_reasons() -> dict[str, str]:
    out: dict[str, str] = {}
    with open(BENCH_TSV) as f:
        for r in csv.DictReader(f, delimiter="\t"):
            out[r["gene_symbol"]] = r["ground_truth_reason"]
    return out


def _load_agent_predictions() -> dict[str, str]:
    """Production Sonnet 4.6 + NCBI predictions only (one row per gene)."""
    out: dict[str, str] = {}
    with open(PRED_TSV) as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["model"] != PROD_MODEL or r["prompt_variant"] != PROD_VARIANT:
                continue
            out[r["gene_symbol"]] = r["predicted_reason"]
    return out


def _build_matrix() -> tuple[np.ndarray, int, int]:
    curator = _load_curator_reasons()
    agent = _load_agent_predictions()
    n = len(REASONS_ORDERED)
    m = np.zeros((n, n), dtype=int)
    n_joined = 0
    n_match = 0
    idx_of = {r: i for i, r in enumerate(REASONS_ORDERED)}
    for gene, c_reason in curator.items():
        if gene not in agent:
            continue
        a_reason = agent[gene]
        if c_reason not in idx_of or a_reason not in idx_of:
            continue
        m[idx_of[c_reason], idx_of[a_reason]] += 1
        n_joined += 1
        if c_reason == a_reason:
            n_match += 1
    return m, n_joined, n_match


def _bucket_boundaries() -> list[int]:
    bounds: list[int] = []
    prev = None
    for i, r in enumerate(REASONS_ORDERED):
        b = BUCKET[r]
        if prev is not None and b != prev:
            bounds.append(i)
        prev = b
    return bounds


def make_plot() -> tuple[plt.Figure, plt.Axes]:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    plt.rcParams.update({
        "font.size": 18, "axes.labelsize": 22, "axes.titlesize": 0,
        "xtick.labelsize": 12, "ytick.labelsize": 12, "legend.fontsize": 14,
    })
    m, n_joined, n_match = _build_matrix()
    n = m.shape[0]

    fig, ax = plt.subplots(figsize=(17, 15))
    cmap = sns.light_palette("#3D6B60", as_cmap=True)
    sns.heatmap(
        m, ax=ax, cmap=cmap, square=True, linewidths=0.5, linecolor="#FFFFFF",
        annot=True, fmt="d", annot_kws={"fontsize": 11, "color": "#1F1718"},
        cbar_kws={"label": "genes", "shrink": 0.55, "pad": 0.02, "aspect": 25},
        # X-tick labels go to single-line (no internal "\n") since
        # we're rotating them to 40° below — wrapped + rotated reads
        # as a stair-step and overlaps with cells.
        xticklabels=[LABEL_SHORT[r].replace("\n", " ") for r in REASONS_ORDERED],
        yticklabels=[LABEL_SHORT[r] for r in REASONS_ORDERED],
    )
    # Hide zero cells so the eye lands on real agreement / disagreement.
    for txt in ax.texts:
        if txt.get_text() == "0":
            txt.set_text("")

    for tick, reason in zip(ax.get_xticklabels(), REASONS_ORDERED, strict=True):
        tick.set_color(BUCKET_COLOR[BUCKET[reason]])
        tick.set_fontweight("semibold")
    for tick, reason in zip(ax.get_yticklabels(), REASONS_ORDERED, strict=True):
        tick.set_color(BUCKET_COLOR[BUCKET[reason]])
        tick.set_fontweight("semibold")
    # X labels at 40° (slanted) so the wider single-line strings
    # don't collide with each other at column boundaries. Align
    # right-anchored so the rotation pivots on the tick line.
    for tick in ax.get_xticklabels():
        tick.set_rotation(40)
        tick.set_ha("right")
        tick.set_rotation_mode("anchor")
    ax.tick_params(axis="x", pad=4)
    ax.tick_params(axis="y", rotation=0, pad=4)

    for b in _bucket_boundaries():
        ax.axhline(b, color="#1F1718", lw=2.0, alpha=0.85)
        ax.axvline(b, color="#1F1718", lw=2.0, alpha=0.85)

    for i in range(n):
        rect = mpatches.Rectangle(
            (i, i), 1, 1, fill=False, edgecolor=DIAGONAL_HIGHLIGHT,
            lw=2.5, zorder=10,
        )
        ax.add_patch(rect)

    ax.set_xlabel("Agent predicted_reason  (Sonnet 4.6 + NCBI)", labelpad=12)
    ax.set_ylabel("Curator\nground_truth_reason", labelpad=12)

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
        loc="upper center", bbox_to_anchor=(0.5, -0.09),
        ncols=4, frameon=False, fontsize=14,
    )

    pct = 100.0 * n_match / n_joined if n_joined else 0.0
    fig.text(
        0.5, -0.015,
        f"Exact-reason agreement: {n_match}/{n_joined}  ({pct:.1f}%)   "
        f"·   data: SurfaceBench v1 × mainbench_canonical_v2 (Sonnet 4.6 / NCBI variant)",
        ha="center", va="top", fontsize=13, color=COLORS["neutral"],
    )

    sns.despine(ax=ax, top=False, right=False, left=False, bottom=False)
    fig.tight_layout()
    return fig, ax


def main() -> None:
    fig, _ = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"))


if __name__ == "__main__":
    main()
