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
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import (
    COLORS,
    SEQUENTIAL_PALETTES,
    save_figure,
    setup_plotting_style,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data/analysis/figures"
SLUG = "curator_vs_agent_reason"

BENCH_TSV = ROOT / "data/eval/triage_benchmark_v1.tsv"
PRED_TSV = ROOT / "data/processed/triage_bench/mainbench_canonical_v2.tsv"
REPS_TSV = ROOT / "data/processed/triage_bench/mainbench_replicates_v2.tsv"
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
    "extracellular_face_protein":   "extracell. face\n(other YES)",
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


# Panel-a configs — every (model, variant) cell available on
# mainbench. 10 total: Haiku×4 + Sonnet×4 + Opus×2.
CONFIGS_A = [
    ("claude-haiku-4-5",  "naive",        "Haiku 4.5 (naive)"),
    ("claude-haiku-4-5",  "ncbi",         "Haiku 4.5 (NCBI)"),
    ("claude-haiku-4-5",  "pubmed_ncbi",  "Haiku 4.5 (PubMed)"),
    ("claude-haiku-4-5",  "web_ncbi",     "Haiku 4.5 (web)"),
    ("claude-sonnet-4-6", "naive",        "Sonnet 4.6 (naive)"),
    ("claude-sonnet-4-6", "ncbi",         "Sonnet 4.6 (NCBI)"),
    ("claude-sonnet-4-6", "pubmed_ncbi",  "Sonnet 4.6 (PubMed)"),
    ("claude-sonnet-4-6", "web_ncbi",     "Sonnet 4.6 (web)"),
    ("claude-opus-4-8",   "naive",        "Opus 4.8 (naive)"),
    ("claude-opus-4-8",   "ncbi",         "Opus 4.8 (NCBI)"),
]
# Panel-b configs — 2 Sonnet variants + best Haiku + best Opus.
# Best Haiku = web_ncbi (73.5% reason; verified by inspecting all 4
# Haiku variants). Best Opus = ncbi (only naive + ncbi available for
# Opus).
CONFIGS_B = [
    ("claude-haiku-4-5",  "web_ncbi",     "Haiku 4.5 (web — best)"),
    ("claude-sonnet-4-6", "ncbi",         "Sonnet 4.6 (NCBI)"),
    ("claude-sonnet-4-6", "pubmed_ncbi",  "Sonnet 4.6 (PubMed)"),
    ("claude-opus-4-8",   "ncbi",         "Opus 4.8 (NCBI)"),
]


def _all_preds() -> dict[tuple[str, str], dict[str, str]]:
    needed = {(m, v) for (m, v, _) in CONFIGS_A} | {(m, v) for (m, v, _) in CONFIGS_B}
    out: dict[tuple[str, str], dict[str, str]] = {k: {} for k in needed}
    with open(PRED_TSV) as f:
        for r in csv.DictReader(f, delimiter="\t"):
            key = (r["model"], r["prompt_variant"])
            if key in out:
                out[key][r["gene_symbol"]] = r["predicted_reason"]
    return out


def _all_rep_preds() -> dict[tuple[str, str, int], dict[str, str]]:
    """Per-replicate predictions: {(model, variant, replicate): {gene:
    predicted_reason}}. Drives the per-bar replicate dots + SEM error
    bars in panel a. mainbench_replicates_v2.tsv has 3 reps per cell
    for every (model, variant) in CONFIGS_A; missing-cell guard below
    just yields fewer dots."""
    needed = {(m, v) for (m, v, _) in CONFIGS_A}
    out: dict[tuple[str, str, int], dict[str, str]] = {}
    with open(REPS_TSV) as f:
        for r in csv.DictReader(f, delimiter="\t"):
            key = (r["model"], r["prompt_variant"])
            if key not in needed:
                continue
            rep = int(r["replicate"])
            out.setdefault((*key, rep), {})[r["gene_symbol"]] = r["predicted_reason"]
    return out


def _bucket(reason: str) -> str:
    yes = {"classical_surface_receptor", "gpi_anchored", "multipass_with_exposed_loops",
           "extracellular_face_protein", "stable_complex_partner"}
    ctx = {"cell_state_induced", "tissue_restricted_surface", "lysosomal_exocytosis",
           "dual_localization", "stable_surface_attachment", "other"}
    no  = {"cytoplasmic", "nuclear", "mitochondrial_internal", "endomembrane_resident",
           "nuclear_envelope", "secreted_only", "inner_leaflet_anchored",
           "pmhc_only_intracellular"}
    if reason in yes:
        return "yes"
    if reason in ctx:
        return "ctx"
    if reason in no:
        return "no"
    return "?"


# Brand-family ramps come from the project's plotting config
# (SEQUENTIAL_PALETTES[hue], deep → light). For 4 prompt variants
# (naive → ncbi → pubmed_ncbi → web_ncbi) we walk indices [4,3,2,1]
# (light → dark, skipping the very-darkest [0] and very-lightest [5]
# so contrast stays even across model groups). Opus has only 2
# variants → indices [3,2].
_HAIKU_RAMP  = [SEQUENTIAL_PALETTES["amber"][i]    for i in (4, 3, 2, 1)]
_SONNET_RAMP = [SEQUENTIAL_PALETTES["teal"][i]     for i in (4, 3, 2, 1)]
_OPUS_RAMP   = [SEQUENTIAL_PALETTES["lavender"][i] for i in (3, 2)]


def _config_color_for(model: str, variant: str, panel: str = "a") -> str:
    """Brand-family color per config: Haiku → amber ramp, Sonnet →
    teal ramp, Opus → lavender ramp — all from
    ``_plotting_config.SEQUENTIAL_PALETTES``. Each variant gets a
    darker step within its model family (naive → ncbi → pubmed → web)."""
    if model == "claude-haiku-4-5":
        idx = {"naive": 0, "ncbi": 1, "pubmed_ncbi": 2, "web_ncbi": 3}.get(variant, 1)
        return _HAIKU_RAMP[idx]
    if model == "claude-sonnet-4-6":
        idx = {"naive": 0, "ncbi": 1, "pubmed_ncbi": 2, "web_ncbi": 3}.get(variant, 1)
        return _SONNET_RAMP[idx]
    if model == "claude-opus-4-8":
        idx = {"naive": 0, "ncbi": 1}.get(variant, 1)
        return _OPUS_RAMP[idx]
    return COLORS["neutral"]


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

    # 3-row layout: (a) bucket-strict accuracy, (b) per-reason
    # accuracy, (c) Sonnet/ncbi confusion matrix. Each row is its own
    # full-width axes so the per-bucket and per-reason bar groups have
    # room to breathe.
    import matplotlib.gridspec as gridspec
    fig = plt.figure(figsize=(18, 28))
    # Nested gridspec: outer separates the (a+b) cluster from c so we
    # can give a↔b a tighter hspace than b↔c. Eliminates the wasted
    # whitespace between panel a and panel b without crowding the
    # confusion matrix below.
    outer = fig.add_gridspec(
        nrows=2, ncols=1, height_ratios=[1.7, 2.1], hspace=0.55,
    )
    top = outer[0].subgridspec(
        nrows=2, ncols=1, height_ratios=[0.7, 1.0], hspace=0.20,
    )
    ax_bucket = fig.add_subplot(top[0])
    ax_perreason = fig.add_subplot(top[1])
    ax_matrix = fig.add_subplot(outer[1])

    # ─────── Helpers ───────
    def _strict_bucket_match(pred_r: str, gt_r: str) -> bool:
        return _bucket(pred_r) == _bucket(gt_r)

    def _draw_grouped(ax, configs, x_groups, group_acc, *, bar_w=None,
                       overall_idx=0, label="(%)", show_legend=True,
                       rep_acc=None):
        """Render one config-grouped bar chart.

        ``configs``: list of (model, variant, label) tuples — one bar
            per config per group.
        ``x_groups``: list of group labels (x-tick labels). The first
            element (index = overall_idx) is the "Overall" group; a
            dotted vertical separator gets drawn right after it.
        ``group_acc``: {config_key: {group_label: (n_match, n_total)}}.
            Pooled-across-reps fallback used when no per-rep data is
            supplied (or the cell has no replicates).
        ``rep_acc``: optional {(model, variant): {group_label:
            [pct_rep1, pct_rep2, pct_rep3]}}. When supplied, the bar
            HEIGHT is the mean of the per-rep accuracies (NOT the
            pooled-across-reps cell) — so the SEM cap + dots sit
            centred on the bar's top. Mirrors the recipe in
            ``make_db_correctness_by_class.py``.
        """
        n_cfg = len(configs)
        if bar_w is None:
            bar_w = 0.85 / n_cfg  # group width = 0.85 to leave room
        x = np.arange(len(x_groups))
        ink = COLORS["dark"]
        for i, (mod, var, lab) in enumerate(configs):
            vals = []
            for g in x_groups:
                rep_vals = (
                    rep_acc[(mod, var)].get(g, [])
                    if rep_acc is not None and (mod, var) in rep_acc
                    else []
                )
                if rep_vals:
                    # Mean-of-reps bar height so dots+SEM align.
                    vals.append(float(np.mean(rep_vals)))
                else:
                    m_, t_ = group_acc[(mod, var)].get(g, (0, 0))
                    vals.append(100 * m_ / t_ if t_ else 0)
            bar_x = x + (i - (n_cfg - 1) / 2) * bar_w
            ax.bar(bar_x, vals, width=bar_w,
                   label=lab, color=_config_color_for(mod, var),
                   edgecolor="none", zorder=2)
            if rep_acc is not None and (mod, var) in rep_acc:
                # SEM error bar + per-rep dots overlaid on each bar.
                # Same recipe as make_db_correctness_by_class.
                for k, g in enumerate(x_groups):
                    rep_vals = rep_acc[(mod, var)].get(g, [])
                    if len(rep_vals) < 2:
                        continue
                    arr = np.asarray(rep_vals, dtype=float)
                    mean = float(arr.mean())
                    sem = float(arr.std(ddof=1) / np.sqrt(len(arr)))
                    bx = bar_x[k]
                    ax.errorbar(
                        bx, mean, yerr=sem, fmt="none", ecolor=ink,
                        elinewidth=1.0, capsize=2.5, capthick=1.0, zorder=5,
                    )
                    # Symmetric jitter — matches canonical formula
                    # in db_correctness_by_class.
                    n_arr = len(arr)
                    for kp, av in enumerate(arr):
                        jitter = (kp - (n_arr - 1) / 2) * (bar_w * 0.22)
                        ax.scatter(
                            bx + jitter, av, s=14, color=ink,
                            edgecolor="white", linewidth=0.4, zorder=6,
                            alpha=0.9,
                        )
        ax.set_xticks(x)
        ax.set_xticklabels(x_groups, fontsize=10)
        ax.set_ylim(0, 109)
        ax.set_ylabel(label)
        # Dotted separator between the Overall group and the per-
        # category bars — matches the pattern in
        # make_db_correctness_by_class.py.
        if 0 <= overall_idx < len(x_groups):
            sep_x = x[overall_idx] + 0.5
            ax.axvline(sep_x, color=COLORS["neutral"], lw=1.2, ls=":",
                       alpha=0.8, zorder=0)
        sns.despine(ax=ax, top=True, right=True)
        if show_legend:
            ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.35),
                      ncols=min(5, n_cfg), frameon=False, fontsize=9)

    # ─────── (a) per-bucket strict accuracy ───────
    BUCKETS_PA = ["yes", "ctx", "no"]
    BUCKET_LABEL_PA = {"yes": "Yes", "ctx": "Contextual", "no": "No"}

    def _bucket_acc_for_pred_map(pred_map: dict[str, str]) -> dict[str, tuple[int, int]]:
        """One pass of bucket-strict accuracy bookkeeping for the
        given gene→predicted_reason map (used both for the pooled bar
        and for each individual replicate)."""
        acc = {"Overall": [0, 0]} | {BUCKET_LABEL_PA[b]: [0, 0] for b in BUCKETS_PA}
        for gene, gt_r in curator.items():
            if gene not in pred_map:
                continue
            pred_r = pred_map[gene]
            gt_b = _bucket(gt_r)
            if gt_b not in ("yes", "ctx", "no"):
                continue
            ok = _strict_bucket_match(pred_r, gt_r)
            acc["Overall"][1] += 1
            if ok:
                acc["Overall"][0] += 1
            lab = BUCKET_LABEL_PA[gt_b]
            acc[lab][1] += 1
            if ok:
                acc[lab][0] += 1
        return {k: tuple(v) for k, v in acc.items()}

    # Compute overall + per-bucket accuracy for ALL 10 configs (pooled
    # across reps — same as the bar height).
    bucket_acc: dict[tuple[str, str], dict[str, tuple[int, int]]] = {}
    for (mod, var, _label) in CONFIGS_A:
        bucket_acc[(mod, var)] = _bucket_acc_for_pred_map(all_preds[(mod, var)])

    # Per-replicate bucket accuracy → drives the dot + SEM overlay
    # in _draw_grouped. {(model, variant): {group_label: [pct1, ...]}}
    rep_preds = _all_rep_preds()
    rep_bucket_acc: dict[tuple[str, str], dict[str, list[float]]] = {}
    for (mod, var, _label) in CONFIGS_A:
        per_rep: dict[str, list[float]] = {}
        for (m_, v_, rep), pmap in rep_preds.items():
            if (m_, v_) != (mod, var):
                continue
            acc = _bucket_acc_for_pred_map(pmap)
            for g, (n_match, n_total) in acc.items():
                per_rep.setdefault(g, []).append(
                    100.0 * n_match / n_total if n_total else 0.0
                )
        rep_bucket_acc[(mod, var)] = per_rep

    groups_a = ["Overall", "Yes", "Contextual", "No"]
    _draw_grouped(ax_bucket, CONFIGS_A, groups_a, bucket_acc,
                   bar_w=0.08, overall_idx=0,
                   label="Bucket-strict accuracy (%)",
                   show_legend=True,
                   rep_acc=rep_bucket_acc)
    ax_bucket.text(0.0, 1.05, "a", transform=ax_bucket.transAxes,
                   fontsize=22, fontweight="bold", va="bottom")

    # ─────── (b) per-reason exact-match accuracy ───────
    # Compute reason frequencies + per-config per-reason accuracy
    # across CONFIGS_B (4 configs — 2 Sonnet + best Haiku + best
    # Opus).
    reason_n: dict[str, int] = {}
    reason_acc: dict[tuple[str, str], dict[str, tuple[int, int]]] = {
        (m, v): {} for (m, v, _) in CONFIGS_B
    }
    overall_b: dict[tuple[str, str], list[int]] = {
        (m, v): [0, 0] for (m, v, _) in CONFIGS_B
    }
    for gene, gt_r in curator.items():
        reason_n[gt_r] = reason_n.get(gt_r, 0) + 1
        for (mod, var, _label) in CONFIGS_B:
            if gene not in all_preds[(mod, var)]:
                continue
            pred_r = all_preds[(mod, var)][gene]
            overall_b[(mod, var)][1] += 1
            if pred_r == gt_r:
                overall_b[(mod, var)][0] += 1
            row = reason_acc[(mod, var)].setdefault(gt_r, [0, 0])
            row[1] += 1
            if pred_r == gt_r:
                row[0] += 1
    # Show ALL reasons present on the bench (n ≥ 1). Order matches
    # panel c's confusion matrix: REASONS_ORDERED is the canonical
    # yes → contextual → no bucket order, so reading panel b
    # left-to-right walks the same bucket sequence as panel c's
    # rows/cols (and the panel-b x-tick labels are already colored by
    # bucket below to reinforce that grouping).
    reasons = [r for r in REASONS_ORDERED if r in reason_n]
    enum_reasons = set(REASONS_ORDERED)
    absent_from_bench = sorted(enum_reasons - set(reason_n.keys()))
    # Build group_acc for the renderer — "Overall" first, then one
    # entry per reason (label = short name + n).
    short = {r: LABEL_SHORT.get(r, r).replace("\n", " ") for r in reasons}
    reason_labels = [f"{short[r]}\n(n={reason_n[r]})" for r in reasons]
    groups_b = ["Overall\n(n=147)"] + reason_labels
    group_acc_b: dict[tuple[str, str], dict[str, tuple[int, int]]] = {}
    for (mod, var, _label) in CONFIGS_B:
        m_, t_ = overall_b[(mod, var)]
        gb: dict[str, tuple[int, int]] = {"Overall\n(n=147)": (m_, t_)}
        for r, label in zip(reasons, reason_labels, strict=True):
            row = reason_acc[(mod, var)].get(r, [0, 0])
            gb[label] = tuple(row)
        group_acc_b[(mod, var)] = gb
    _draw_grouped(ax_perreason, CONFIGS_B, groups_b, group_acc_b,
                   bar_w=0.16, overall_idx=0,
                   label="Exact-reason accuracy (%)",
                   show_legend=True)
    # Annotate the Overall bar group with each config's exact-reason
    # accuracy % so the headline 87% claim is readable on-figure.
    # Bar layout: x positions sit at (i - (n-1)/2) * bar_w around x=0.
    for i, (mod, var, _lab) in enumerate(CONFIGS_B):
        m_, t_ = overall_b[(mod, var)]
        if not t_:
            continue
        pct = 100 * m_ / t_
        x_pos = (i - (len(CONFIGS_B) - 1) / 2) * 0.16
        ax_perreason.text(
            x_pos, pct + 1.4, f"{pct:.0f}%",
            ha="center", va="bottom", fontsize=10,
            color=COLORS["dark"], fontweight="semibold",
        )
    # Re-rotate x-labels (per-reason labels are too long horizontally)
    # + color each label by its bucket (yes/contextual/no), matching
    # the tick coloring on panel c's confusion matrix.
    pb_tick_buckets = [None] + [_bucket(r) for r in reasons]
    bucket_to_color = {"yes": BUCKET_COLOR["yes"],
                       "ctx": BUCKET_COLOR["contextual"],
                       "no":  BUCKET_COLOR["no"]}
    for tick, b in zip(ax_perreason.get_xticklabels(),
                       pb_tick_buckets, strict=True):
        tick.set_rotation(35)
        tick.set_ha("right")
        tick.set_rotation_mode("anchor")
        tick.set_fontsize(9)
        if b in bucket_to_color:
            tick.set_color(bucket_to_color[b])
            tick.set_fontweight("semibold")
    # Annotation: explicit list of TriageReason enum values with no
    # bench representative. Stops the reader from wondering "where are
    # the missing 3?" — the closed enum has 19 values; this panel
    # shows the {len(reasons)} bench-present ones.
    n_present = len(reasons)
    n_enum = len(enum_reasons)
    absent_str = ", ".join(absent_from_bench) if absent_from_bench else "none"
    ax_perreason.text(
        0.5, -0.42,
        f"Showing {n_present} of {n_enum} TriageReason enum values "
        f"(present on bench, n ≥ 1). Absent from bench: {absent_str}.",
        transform=ax_perreason.transAxes, ha="center", va="top",
        fontsize=10, style="italic", color=COLORS["neutral"],
    )
    ax_perreason.text(0.0, 1.05, "b", transform=ax_perreason.transAxes,
                      fontsize=22, fontweight="bold", va="bottom")

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
    # Legend sits BELOW the "Agent predicted_reason" x-axis label —
    # bbox_to_anchor y was -0.09 (clashed with rotated tick labels),
    # then -0.18 (overlapped the x-axis label itself); now -0.26 so
    # the legend has its own row underneath the entire x-axis stack:
    # tick labels → axis label → legend, top-to-bottom.
    ax.legend(
        handles=handles,
        loc="upper center", bbox_to_anchor=(0.5, -0.26),
        ncols=4, frameon=False, fontsize=14,
    )

    # Agreement-stat subtitle dropped per user — the matrix + the
    # legend already convey the data shape; the redundant text was
    # noise. (Bar charts in panels a/b carry the same overall-
    # accuracy number as their leftmost bar group.)

    sns.despine(ax=ax, top=False, right=False, left=False, bottom=False)
    return fig, [ax_bucket, ax_perreason, ax_matrix]


def main() -> None:
    fig, _ = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"))


if __name__ == "__main__":
    main()
