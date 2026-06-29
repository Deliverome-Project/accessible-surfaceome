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


def _build_matrix() -> tuple[np.ndarray, int, int, dict[tuple[int, int], list[str]]]:
    """Build the (curator_reason × agent_reason) count matrix AND
    a {(i, j): [gene, gene, ...]} index of which specific bench
    genes fell into each off-diagonal cell. Off-diagonal cells are
    the disagreements worth surfacing by name on the figure;
    diagonal cells often have 10+ genes and stay count-only."""
    curator = _load_curator_reasons()
    agent = _load_agent_predictions()
    n = len(REASONS_ORDERED)
    m = np.zeros((n, n), dtype=int)
    cell_genes: dict[tuple[int, int], list[str]] = {}
    n_joined = 0
    n_match = 0
    idx_of = {r: i for i, r in enumerate(REASONS_ORDERED)}
    for gene, c_reason in curator.items():
        if gene not in agent:
            continue
        a_reason = agent[gene]
        if c_reason not in idx_of or a_reason not in idx_of:
            continue
        i, j = idx_of[c_reason], idx_of[a_reason]
        m[i, j] += 1
        cell_genes.setdefault((i, j), []).append(gene)
        n_joined += 1
        if c_reason == a_reason:
            n_match += 1
    return m, n_joined, n_match, cell_genes


def _bucket_boundaries() -> list[int]:
    bounds: list[int] = []
    prev = None
    for i, r in enumerate(REASONS_ORDERED):
        b = BUCKET[r]
        if prev is not None and b != prev:
            bounds.append(i)
        prev = b
    return bounds


CONFIGS = [
    ("claude-haiku-4-5",   "ncbi",        "Haiku 4.5"),
    ("claude-sonnet-4-6",  "ncbi",        "Sonnet 4.6 (NCBI)"),
    ("claude-sonnet-4-6",  "pubmed_ncbi", "Sonnet 4.6 (PubMed)"),
    ("claude-opus-4-8",    "ncbi",        "Opus 4.8"),
]


def _all_preds() -> dict[tuple[str, str], dict[str, str]]:
    out: dict[tuple[str, str], dict[str, str]] = {(m, v): {} for (m, v, _) in CONFIGS}
    with open(PRED_TSV) as f:
        for r in csv.DictReader(f, delimiter="\t"):
            key = (r["model"], r["prompt_variant"])
            if key in out:
                out[key][r["gene_symbol"]] = r["predicted_reason"]
    return out


def _bucket(reason: str) -> str:
    yes = {"classical_surface_receptor", "gpi_anchored", "multipass_with_exposed_loops",
           "extracellular_face_protein", "stable_complex_partner"}
    ctx = {"cell_state_induced", "tissue_restricted_surface", "lysosomal_exocytosis",
           "dual_localization", "stable_surface_attachment", "other"}
    no  = {"cytoplasmic", "nuclear", "mitochondrial_internal", "endomembrane_resident",
           "nuclear_envelope", "secreted_only", "inner_leaflet_anchored",
           "pmhc_only_intracellular"}
    if reason in yes: return "yes"
    if reason in ctx: return "ctx"
    if reason in no:  return "no"
    return "?"


def _config_color(i: int) -> str:
    """Distinct color per config in the bar charts. Haiku gets the
    light/neutral end, Opus the darker end of the brand palette."""
    return ["#9C8C88", "#3D6B60", "#2E7A55", "#5848A8"][i]


def make_plot() -> tuple[plt.Figure, list[plt.Axes]]:
    """3-subplot composite:
      (a) per-bucket strict accuracy across the 4 frontier configs
      (b) per-reason accuracy across the same 4 configs
      (c) the Sonnet/ncbi curator×agent confusion matrix (existing).

    Bucket-strict means: predicted reason's bucket must equal curator
    reason's bucket — no soft-credit for yes→contextual matches.
    """
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    plt.rcParams.update({
        "font.size": 16, "axes.labelsize": 18, "axes.titlesize": 0,
        "xtick.labelsize": 11, "ytick.labelsize": 11, "legend.fontsize": 12,
    })
    m, n_joined, n_match, cell_genes = _build_matrix()
    n = m.shape[0]
    curator = _load_curator_reasons()
    all_preds = _all_preds()

    # Build a 2-row figure: row 1 = (a) + (b) side-by-side; row 2 = (c)
    import matplotlib.gridspec as gridspec
    fig = plt.figure(figsize=(17, 22))
    gs = gridspec.GridSpec(
        nrows=2, ncols=2, height_ratios=[0.9, 2.1], width_ratios=[1.0, 1.6],
        hspace=0.32, wspace=0.22,
    )
    ax_bucket = fig.add_subplot(gs[0, 0])
    ax_perreason = fig.add_subplot(gs[0, 1])
    ax_matrix = fig.add_subplot(gs[1, :])

    # ─────── (a) per-bucket strict accuracy ───────
    # Local var names use _PA suffix to avoid shadowing the module-
    # level BUCKET / BUCKET_COLOR (which panel c reads via tick-label
    # coloring; those use the long "contextual" key not "ctx").
    BUCKETS_PA = ["yes", "ctx", "no"]
    BUCKET_LABEL_PA = {"yes": "Yes", "ctx": "Contextual", "no": "No"}
    BUCKET_COLOR_PA = {"yes": "#2E7A55", "ctx": "#C07830", "no": "#6F5D5A"}
    bucket_acc: dict[tuple[str,str], dict[str, list[int]]] = {}  # config → bucket → [match, total]
    for (mod, var, _label) in CONFIGS:
        acc = {b: [0, 0] for b in BUCKETS_PA}
        for gene, gt_r in curator.items():
            if gene not in all_preds[(mod, var)]:
                continue
            pred_r = all_preds[(mod, var)][gene]
            gt_b = _bucket(gt_r); pred_b = _bucket(pred_r)
            if gt_b in acc:
                acc[gt_b][1] += 1
                if pred_b == gt_b:
                    acc[gt_b][0] += 1
        bucket_acc[(mod, var)] = acc

    n_cfg = len(CONFIGS)
    bar_w = 0.20
    x_b = np.arange(len(BUCKETS_PA))
    for i, (mod, var, label) in enumerate(CONFIGS):
        vals = []
        for b in BUCKETS_PA:
            mtch, tot = bucket_acc[(mod, var)][b]
            vals.append(100 * mtch / tot if tot else 0)
        ax_bucket.bar(x_b + (i - (n_cfg - 1) / 2) * bar_w, vals, width=bar_w,
                      label=label, color=_config_color(i), edgecolor="none")
    ax_bucket.set_xticks(x_b)
    ax_bucket.set_xticklabels([BUCKET_LABEL_PA[b] for b in BUCKETS_PA])
    ax_bucket.set_ylim(0, 105)
    ax_bucket.set_ylabel("Bucket-strict accuracy (%)")
    ax_bucket.legend(loc="lower center", bbox_to_anchor=(0.5, -0.32),
                     ncols=2, frameon=False, fontsize=10)
    ax_bucket.text(0.02, 1.02, "a", transform=ax_bucket.transAxes,
                   fontsize=22, fontweight="bold", va="bottom")
    sns.despine(ax=ax_bucket, top=True, right=True)

    # ─────── (b) per-reason accuracy across configs ───────
    # Per-reason: which reasons curator used at least 2 times (n≥2).
    reason_n: dict[str, int] = {}
    reason_acc: dict[str, dict[tuple[str,str], list[int]]] = {}
    for gene, gt_r in curator.items():
        reason_n[gt_r] = reason_n.get(gt_r, 0) + 1
        reason_acc.setdefault(gt_r, {(m,v): [0,0] for (m,v,_) in CONFIGS})
        for (mod, var, _label) in CONFIGS:
            if gene in all_preds[(mod, var)]:
                pred_r = all_preds[(mod, var)][gene]
                reason_acc[gt_r][(mod, var)][1] += 1
                if pred_r == gt_r:
                    reason_acc[gt_r][(mod, var)][0] += 1
    # Filter to reasons with n≥2, sort by n descending (most frequent
    # reasons leftmost so the eye reads "common cases first").
    reasons = [r for r in reason_n if reason_n[r] >= 2]
    reasons.sort(key=lambda r: -reason_n[r])
    n_r = len(reasons)
    x_r = np.arange(n_r)
    for i, (mod, var, label) in enumerate(CONFIGS):
        vals = []
        for r in reasons:
            mtch, tot = reason_acc[r][(mod, var)]
            vals.append(100 * mtch / tot if tot else 0)
        ax_perreason.bar(x_r + (i - (n_cfg - 1) / 2) * bar_w, vals, width=bar_w,
                          label=label, color=_config_color(i), edgecolor="none")
    short = {r: LABEL_SHORT.get(r, r).replace("\n", " ") for r in reasons}
    n_labels = [f"{short[r]}\n(n={reason_n[r]})" for r in reasons]
    ax_perreason.set_xticks(x_r)
    ax_perreason.set_xticklabels(n_labels, fontsize=8.5)
    for tick in ax_perreason.get_xticklabels():
        tick.set_rotation(35); tick.set_ha("right"); tick.set_rotation_mode("anchor")
    ax_perreason.set_ylim(0, 105)
    ax_perreason.set_ylabel("Exact-reason accuracy (%)")
    ax_perreason.text(0.02, 1.02, "b", transform=ax_perreason.transAxes,
                      fontsize=22, fontweight="bold", va="bottom")
    sns.despine(ax=ax_perreason, top=True, right=True)

    # ─────── (c) confusion matrix (Sonnet/ncbi) ───────
    ax = ax_matrix
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

    # Label OFF-DIAGONAL non-zero cells with the specific bench gene
    # names that fell into each. The diagonal cells often have 10+
    # genes (cytoplasmic n=11, classical_surface_receptor n=27) — too
    # many to label legibly, so they stay count-only. The off-diagonal
    # cells are the disagreements worth surfacing by name.
    for (i, j), genes in cell_genes.items():
        if i == j or not genes:
            continue
        # Gene-name strip below the count (offset y slightly downward
        # from the cell centre). seaborn's count text sits at the
        # cell's centre; we add a smaller second text right below.
        name_str = ", ".join(genes)
        if len(name_str) > 22:
            # 22 chars fits 2-3 typical gene symbols at this fontsize;
            # for longer lists, two-line wrap stays readable.
            name_str = name_str.replace(", ", ",\n", 1) if len(genes) >= 2 else name_str
        ax.text(j + 0.5, i + 0.78, name_str,
                ha="center", va="top",
                fontsize=6.5, color="#3a2122",
                fontstyle="italic", zorder=11)

    ax.set_xlabel("Agent predicted_reason  (Sonnet 4.6 + NCBI)", labelpad=12)
    ax.set_ylabel("Curator\nground_truth_reason", labelpad=12)
    ax.text(-0.04, 1.02, "c", transform=ax.transAxes,
            fontsize=22, fontweight="bold", va="bottom")

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
    return fig, [ax_bucket, ax_perreason, ax_matrix]


def main() -> None:
    fig, _ = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"))


if __name__ == "__main__":
    main()
