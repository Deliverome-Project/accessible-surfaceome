"""Aggregate the 4-variant × 2-replicate sub-benchmark runs into summary plots.

Reads ``data/eval/triage_subbench_v1/<variant>/<gene>_run<N>.json`` and the
sub-benchmark TSV ground truth, then emits:

1. data/analysis/triage_bench/subbench_accuracy_by_variant.{pdf,png}
   Variant accuracy bars (one cluster per model: Haiku, Sonnet),
   coloured in 4 shades of Claude orange (lightest = least context,
   darkest = most context).

2. data/analysis/triage_bench/subbench_per_protein.{pdf,png}
   Per-protein × per-variant correctness grid, 2 columns (one per model),
   with proteins on Y and variants on X. Filled = correct, hatched = wrong,
   labeled with the prediction. Lets the reader see which proteins each
   variant misses.

3. data/analysis/triage_bench/subbench_cost_vs_accuracy.{pdf,png}
   Cost (USD) on X vs accuracy on Y for each (model, variant) cell.
   Helps visualise the cost/accuracy frontier across 8 cells.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import (
    COLORS,
    save_figure,
    setup_plotting_style,
)


ROOT = Path("/Users/rebeccacarlson/Git/accessible-surfaceome/.claude/worktrees/optimistic-goldwasser-ea19aa")
SUBBENCH_TSV = ROOT / "data/eval/triage_subbench_v1.tsv"
RUNS_DIR = ROOT / "data/eval/triage_subbench_v1"
OUT_DIR = ROOT / "data/analysis/triage_bench"

# Variant order = "amount of context" axis. Each variant gets a darker
# shade of Claude orange as the context augmentation increases.
VARIANT_ORDER = ["naive", "ncbi", "web_naive", "web_ncbi"]
VARIANT_LABEL = {
    "naive":     "naive\n(no resolver, no web)",
    "ncbi":      "NCBI gene\n(resolver, no web)",
    "web_naive": "web only\n(no resolver)",
    "web_ncbi":  "web + NCBI\n(both)",
}
# Sequential Claude-orange shades — lightest to darkest. Base Claude
# orange is #d87851; the 4 shades step around it in luminance.
CLAUDE_ORANGE_SHADES = {
    "naive":     "#f1c4ab",  # tint 50%
    "ncbi":      "#d87851",  # base — matches the main barplot
    "web_naive": "#a85b3f",  # shade 25%
    "web_ncbi":  "#7a3b25",  # shade 50%
}

MODEL_ORDER = ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-7"]
MODEL_LABEL = {
    "claude-haiku-4-5":  "Haiku 4.5",
    "claude-sonnet-4-6": "Sonnet 4.6",
    "claude-opus-4-7":   "Opus 4.7",
}
# Distinct scatter markers per model — keeps the cost-vs-accuracy plot
# legible when multiple models occupy a similar cost bucket.
MODEL_MARKER = {
    "claude-haiku-4-5":  "o",
    "claude-sonnet-4-6": "D",
    "claude-opus-4-7":   "s",
}
# Models whose runs were captured under the current (post-PR16) triage prompt;
# everything not in this set was captured under an earlier prompt and gets a
# footnote-style caveat on plots that mix them.
PROMPT_FRESH_MODELS: frozenset[str] = frozenset({"claude-opus-4-7"})


def _load_ground_truth() -> dict[str, dict[str, str]]:
    with SUBBENCH_TSV.open() as f:
        return {r["gene_symbol"]: r for r in csv.DictReader(f, delimiter="\t")}


def _load_runs() -> list[dict]:
    """Collect every persisted per-cell record.

    Path layout: data/eval/triage_subbench_v1/<model_slug>/<variant>/<gene>_run<N>.json
    Falls back to the flat <variant>/<gene>_run<N>.json layout for legacy
    records — those carry the model name in-record.
    """
    out = []
    for entry in sorted(RUNS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        # Model-isolated layout (new).
        for variant_dir in sorted(entry.iterdir()):
            if not variant_dir.is_dir() or variant_dir.name not in VARIANT_ORDER:
                continue
            for path in sorted(variant_dir.glob("*_run*.json")):
                try:
                    out.append(json.loads(path.read_text()))
                except json.JSONDecodeError:
                    continue
        # Legacy flat layout (variants directly under RUNS_DIR).
        if entry.name in VARIANT_ORDER:
            for path in sorted(entry.glob("*_run*.json")):
                try:
                    out.append(json.loads(path.read_text()))
                except json.JSONDecodeError:
                    continue
    return out


def _build_dataframe() -> pd.DataFrame:
    """One row per per-cell run.

    Always re-derives ``truth_verdict`` + ``correct`` from the current
    subbench TSV rather than trusting the snapshot stored in each per-run
    JSON. This keeps the plots in sync after a truth-table relabel without
    requiring every (model × variant × replicate) cell to be rerun.
    """
    truth = _load_ground_truth()
    runs = _load_runs()
    rows = []
    for r in runs:
        gene = r["gene_symbol"]
        current_truth = (truth.get(gene) or {}).get("ground_truth_verdict") or r["truth_verdict"]
        rows.append({
            "variant": r["variant"],
            "model": r["model"],
            "gene_symbol": gene,
            "replicate": r["replicate"],
            "truth_verdict": current_truth,
            "predicted_verdict": r["predicted_verdict"] or "MISSING",
            "predicted_reason": r["predicted_reason"] or "",
            "correct": (r["predicted_verdict"] or "") == current_truth,
            "cost_usd": r["cost_usd"],
            "latency_s": r["latency_s"],
            "n_web_searches": r["n_web_searches"],
        })
    return pd.DataFrame(rows)


def _accuracy_by_variant(df: pd.DataFrame) -> pd.DataFrame:
    """(model, variant) → accuracy + total cost."""
    agg = (
        df.groupby(["model", "variant"], as_index=False)
        .agg(n=("correct", "size"), n_correct=("correct", "sum"),
             total_cost=("cost_usd", "sum"),
             mean_latency=("latency_s", "mean"),
             mean_web=("n_web_searches", "mean"))
    )
    agg["accuracy"] = agg.n_correct / agg.n
    return agg


def plot_accuracy_by_variant(df: pd.DataFrame, out_dir: Path) -> None:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    agg = _accuracy_by_variant(df)
    fig, ax = plt.subplots(figsize=(11, 5.5))

    palette = [CLAUDE_ORANGE_SHADES[v] for v in VARIANT_ORDER]
    models = [m for m in MODEL_ORDER if m in agg.model.unique()]

    sns.barplot(
        data=agg,
        x="model", y="accuracy", hue="variant",
        order=models, hue_order=VARIANT_ORDER,
        palette=palette, edgecolor="none", saturation=1.0, ax=ax,
    )

    # Per-replicate accuracy points overlaid on each bar, so cells with
    # multiple reps show the spread alongside the aggregate.
    per_rep = (
        df.groupby(["model", "variant", "replicate"], as_index=False)
        .agg(n=("correct", "size"), n_correct=("correct", "sum"))
    )
    per_rep["accuracy"] = per_rep.n_correct / per_rep.n

    # `ax.containers` is one BarContainer per hue (variant), each holding
    # one Rectangle per model in x-axis order. This is the reliable way to
    # recover the actual bar geometry seaborn placed — manual indexing
    # via `ax.patches` is fragile when seaborn skips zero-data combinations.
    for variant_idx, variant in enumerate(VARIANT_ORDER):
        if variant_idx >= len(ax.containers):
            continue
        container = ax.containers[variant_idx]
        for model_idx, model in enumerate(models):
            if model_idx >= len(container.patches):
                continue
            bar = container.patches[model_idx]
            bar_x = bar.get_x() + bar.get_width() / 2

            # Per-rep dots
            cell_reps = per_rep[(per_rep.variant == variant) & (per_rep.model == model)]
            if not cell_reps.empty:
                n_pts = len(cell_reps)
                if n_pts == 1:
                    jitter = [0.0]
                else:
                    spread = bar.get_width() * 0.32
                    jitter = [spread * (i / (n_pts - 1) - 0.5) for i in range(n_pts)]
                ax.scatter(
                    [bar_x + j for j in jitter],
                    cell_reps.accuracy.tolist(),
                    s=42, color="white", edgecolor=COLORS["dark"],
                    linewidth=1.1, zorder=5,
                )

            # n_correct/n + $cost annotation
            row = agg[(agg.variant == variant) & (agg.model == model)]
            if row.empty:
                continue
            r = row.iloc[0]
            ax.text(
                bar_x,
                bar.get_height() + 0.018,
                f"{int(r.n_correct)}/{int(r.n)}\n${r.total_cost:.2f}",
                ha="center", va="bottom",
                fontsize=8.5, color=COLORS["dark"],
                linespacing=1.2,
            )

    ax.set_xlabel("")
    ax.set_ylabel("Verdict accuracy on 17-protein sub-benchmark")
    ax.set_title("Triage sub-benchmark: variant × model accuracy (dots = per replicate)")
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels([MODEL_LABEL[m] for m in models])
    ax.set_ylim(0, 1.18)
    # Build the legend from coloured Patch swatches so each variant's shade
    # is visible in the legend (the default barplot legend renders as
    # outline-only lines when we override the labels).
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    legend_handles = [
        Patch(facecolor=CLAUDE_ORANGE_SHADES[v], edgecolor="none", label=VARIANT_LABEL[v])
        for v in VARIANT_ORDER
    ] + [
        Line2D(
            [], [], marker="o", color="w", markerfacecolor="white",
            markeredgecolor=COLORS["dark"], markeredgewidth=1.1,
            markersize=8, label="One replicate",
        )
    ]
    ax.legend(
        handles=legend_handles,
        title="Prompt variant",
        loc="upper left", bbox_to_anchor=(1.02, 1.0),
        frameon=False, borderaxespad=0.0,
    )
    sns.despine(ax=ax, top=True, right=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    save_figure(
        fig, filename="subbench_accuracy_by_variant",
        output_dir=str(out_dir), formats=["pdf", "png"],
    )
    plt.close(fig)


def plot_per_protein(df: pd.DataFrame, out_dir: Path) -> None:
    """Per-protein × variant grid, one column per model.

    Each cell shows the prediction (yes/contextual/no) with a filled
    background when correct and a striped/light background when wrong.
    """
    setup_plotting_style(style="white", context="notebook", font_scale=0.85)

    truth = _load_ground_truth()
    genes = list(truth.keys())  # preserve TSV order
    n_genes = len(genes)
    models = [m for m in MODEL_ORDER if m in df.model.unique()]

    # Use a representative replicate per (gene, variant, model): pick the
    # majority prediction across replicates, breaking ties toward the
    # truth-correct one.
    cell_view: dict[tuple[str, str, str], dict] = {}
    for (gene, variant, model), group in df.groupby(["gene_symbol", "variant", "model"]):
        preds = group.predicted_verdict.value_counts()
        # Majority pred; in tie, prefer one matching truth.
        truth_v = truth.get(gene, {}).get("ground_truth_verdict", "?")
        if truth_v in preds.index and preds.get(truth_v, 0) == preds.max():
            pred = truth_v
        else:
            pred = preds.index[0]
        # Did at least one replicate get it right?
        any_correct = bool(group["correct"].any())
        cell_view[(gene, variant, model)] = {
            "pred": pred, "any_correct": any_correct, "truth": truth_v,
        }

    fig, axes = plt.subplots(
        1, len(models), figsize=(2 + 2.5 * len(models), 0.32 * n_genes + 1.6),
        sharey=True,
    )
    if len(models) == 1:
        axes = [axes]
    for ax, model in zip(axes, models):
        for var_idx, variant in enumerate(VARIANT_ORDER):
            color = CLAUDE_ORANGE_SHADES[variant]
            for gene_idx, gene in enumerate(genes):
                cell = cell_view.get((gene, variant, model))
                if cell is None:
                    continue
                # Cell background: filled with the variant's shade when
                # correct in ANY replicate; light-grey wash when always wrong.
                if cell["any_correct"]:
                    ax.add_patch(plt.Rectangle(
                        (var_idx - 0.45, gene_idx - 0.45), 0.9, 0.9,
                        color=color, alpha=0.85,
                    ))
                else:
                    ax.add_patch(plt.Rectangle(
                        (var_idx - 0.45, gene_idx - 0.45), 0.9, 0.9,
                        color="#e4dcd5", alpha=0.6,
                    ))
                # Print the prediction abbreviation.
                pred_abbrev = {"yes": "Y", "contextual": "C", "no": "N",
                               "MISSING": "—"}.get(cell["pred"], cell["pred"][:1])
                ax.text(
                    var_idx, gene_idx, pred_abbrev,
                    ha="center", va="center",
                    fontsize=10, fontweight="bold",
                    color="white" if cell["any_correct"] else COLORS["neutral"],
                )
        ax.set_xlim(-0.6, len(VARIANT_ORDER) - 0.4)
        ax.set_ylim(n_genes - 0.5, -0.5)
        ax.set_xticks(range(len(VARIANT_ORDER)))
        ax.set_xticklabels(
            [VARIANT_LABEL[v].replace("\n", "\n") for v in VARIANT_ORDER],
            rotation=30, ha="right", fontsize=9,
        )
        ax.set_yticks(range(n_genes))
        truth_labels = [
            f"{g} ({truth[g]['ground_truth_verdict'][:3]})" for g in genes
        ]
        ax.set_yticklabels(truth_labels, fontsize=9)
        ax.set_title(MODEL_LABEL[model], fontsize=12)
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)

    fig.suptitle(
        "Sub-benchmark per-protein correctness  ·  Y=yes / C=contextual / N=no  ·  "
        "colored cell = correct in ≥1 replicate, grey = always wrong",
        y=1.02, fontsize=10,
    )
    fig.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    save_figure(
        fig, filename="subbench_per_protein",
        output_dir=str(out_dir), formats=["pdf", "png"],
    )
    plt.close(fig)


def plot_cost_vs_accuracy(df: pd.DataFrame, out_dir: Path) -> None:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    # One point per (model, variant, replicate) — so Haiku 4.5 / Sonnet 4.6
    # contribute two points per variant and Opus 4.7 contributes one.
    per_rep = (
        df.groupby(["model", "variant", "replicate"], as_index=False)
        .agg(
            n=("correct", "size"),
            n_correct=("correct", "sum"),
            total_cost=("cost_usd", "sum"),
        )
    )
    per_rep["accuracy"] = per_rep.n_correct / per_rep.n

    fig, ax = plt.subplots(figsize=(8.5, 5.8))
    mixed_prompts = (
        bool(per_rep.model.isin(PROMPT_FRESH_MODELS).any())
        and bool((~per_rep.model.isin(PROMPT_FRESH_MODELS)).any())
    )

    for model in MODEL_ORDER:
        sub = per_rep[per_rep.model == model]
        if sub.empty:
            continue
        marker = MODEL_MARKER.get(model, "o")
        is_fresh = model in PROMPT_FRESH_MODELS
        # Label each variant once per model (on its lowest-replicate point) so
        # the figure doesn't get cluttered when reps are stacked.
        first_labeled: set[tuple[str, str]] = set()
        for _, row in sub.iterrows():
            ax.scatter(
                row.total_cost, row.accuracy,
                s=200, color=CLAUDE_ORANGE_SHADES[row.variant],
                marker=marker, edgecolor=COLORS["dark"], linewidth=1.0,
                zorder=3,
            )
            key = (row.model, row.variant)
            if key not in first_labeled:
                label = row.variant + ("*" if mixed_prompts and is_fresh else "")
                ax.annotate(
                    label, (row.total_cost, row.accuracy),
                    xytext=(8, 4), textcoords="offset points", fontsize=9,
                    color=COLORS["neutral"],
                )
                first_labeled.add(key)

    ax.set_xlabel("Cost per replicate on 17-protein sub-benchmark (USD)")
    ax.set_ylabel("Verdict accuracy per replicate")
    n_points = int(per_rep.shape[0])
    n_cells = int(per_rep.groupby(["model", "variant"]).ngroups)
    ax.set_title(
        f"Cost vs accuracy: {n_points} replicates across {n_cells} (model × variant) cells"
    )
    ax.set_ylim(0, 1.05)
    # Legend: shade-by-variant, marker-by-model.
    from matplotlib.lines import Line2D
    models_present = [m for m in MODEL_ORDER if m in per_rep.model.unique()]
    handles = [
        Line2D([], [], marker="o", color="w", markerfacecolor=CLAUDE_ORANGE_SHADES[v],
               markersize=11, markeredgecolor=COLORS["dark"], label=VARIANT_LABEL[v].replace("\n", " "))
        for v in VARIANT_ORDER
    ] + [
        Line2D(
            [], [], marker=MODEL_MARKER[m], color="w",
            markerfacecolor=COLORS["neutral"], markersize=10,
            markeredgecolor=COLORS["dark"],
            label=MODEL_LABEL[m] + ("*" if mixed_prompts and m in PROMPT_FRESH_MODELS else ""),
        )
        for m in models_present
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1.0),
              frameon=False, borderaxespad=0.0)
    sns.despine(ax=ax, top=True, right=True)

    if mixed_prompts:
        fresh_label = ", ".join(MODEL_LABEL[m] for m in models_present if m in PROMPT_FRESH_MODELS)
        fig.text(
            0.5, 0.01,
            f"*{fresh_label} runs use the current triage system prompt; "
            "Haiku 4.5 / Sonnet 4.6 cells were captured against an earlier revision. "
            "Each marker is one replicate (17 genes); cells with multiple reps appear as multiple markers.",
            ha="center", va="bottom", fontsize=8.5,
            color=COLORS["neutral"], style="italic",
        )
        fig.subplots_adjust(bottom=0.16)

    out_dir.mkdir(parents=True, exist_ok=True)
    save_figure(
        fig, filename="subbench_cost_vs_accuracy",
        output_dir=str(out_dir), formats=["pdf", "png"],
    )
    plt.close(fig)


def main() -> None:
    df = _build_dataframe()
    if df.empty:
        raise SystemExit(
            f"No sub-bench run records found under {RUNS_DIR}. "
            f"Run scripts/triage_subbench_runner.py first."
        )
    print(f"Loaded {len(df)} run records")
    print(df.groupby(["model", "variant"]).size().to_string())
    plot_accuracy_by_variant(df, OUT_DIR)
    plot_per_protein(df, OUT_DIR)
    plot_cost_vs_accuracy(df, OUT_DIR)
    print(f"\nWrote 3 plots to {OUT_DIR}")


if __name__ == "__main__":
    main()
