"""Cost vs accuracy + per-class accuracy plots for the v2 18-gene subbench.

Reads runs from ``data/eval/triage_subbench_v1/<model>/<variant>/``
(now containing the v2 18-gene set) and produces:

* ``subbench_v2_cost_vs_accuracy.{png,pdf}`` — 9 cells in
  ($/subbench-pass, accuracy) space; LLM cells in the brand
  Claude-orange progression (lightest=naive → darkest=web+NCBI).
* ``subbench_v2_accuracy_by_verdict.{png,pdf}`` — grouped bars per cell
  showing overall + per-verdict (yes/contextual/no) accuracy.

Accuracy uses the same soft-credit rule as the main runner: a
``yes`` prediction is correct against ``contextual`` truth and vice
versa; ``no`` is only correct against ``no``.
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


ROOT = Path(__file__).resolve().parents[1]
SUBBENCH_TSV = ROOT / "data/eval/triage_subbench_v1.tsv"
RUNS_DIR = ROOT / "data/eval/triage_subbench_v1"
OUT_DIR = ROOT / "data/analysis/triage_bench"

# (vote_key, model, variant, label, palette_idx_in_orange_scale)
# Claude-orange light→dark progression: 0=lightest tint, 5=deepest shade
CELLS = [
    ("haiku-4-5",  "naive",       "Haiku (naive)",          "#f7d8c4"),
    ("haiku-4-5",  "ncbi",        "Haiku (+ NCBI)",         "#f1c4ab"),
    ("haiku-4-5",  "web_ncbi",    "Haiku (web + NCBI)",     "#e3a07d"),
    ("sonnet-4-6", "naive",       "Sonnet (naive)",         "#d87851"),
    ("sonnet-4-6", "ncbi",        "Sonnet (+ NCBI)",        "#c46838"),
    ("sonnet-4-6", "pubmed_ncbi", "Sonnet (pubmed + NCBI)", "#b6633f"),
    ("sonnet-4-6", "web_ncbi",    "Sonnet (web + NCBI)",    "#a85b3f"),
    ("opus-4-7",   "naive",       "Opus (naive)",           "#8c4a30"),
    ("opus-4-7",   "ncbi",        "Opus (+ NCBI)",          "#7a3b25"),
    ("opus-4-7",   "web_ncbi",    "Opus (web + NCBI)",      "#5a2608"),
]

VERDICT_ORDER = ["yes", "contextual", "no"]
WHOLE_GENOME_N = 19_464


def _ok(pred, tv):
    if pred is None:
        return False
    return pred == tv or (pred in {"yes", "contextual"} and tv in {"yes", "contextual"})


def _load_truth() -> dict[str, str]:
    with SUBBENCH_TSV.open() as fh:
        return {r["gene_symbol"]: r["ground_truth_verdict"]
                for r in csv.DictReader(fh, delimiter="\t")}


def _load_cell(model: str, variant: str) -> tuple[dict[str, str], dict[str, float]]:
    """Return (gene → predicted_verdict, gene → cost_usd)."""
    preds: dict[str, str] = {}
    costs: dict[str, float] = {}
    d = RUNS_DIR / model / variant
    if not d.exists():
        return preds, costs
    for p in d.glob("*_run1.json"):
        try:
            rec = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        g = rec.get("gene_symbol") or p.stem.split("_run")[0]
        preds[g] = rec.get("predicted_verdict")
        costs[g] = float(rec.get("cost_usd") or 0.0)
    return preds, costs


def _score_cell(truth, preds) -> dict:
    """Return overall and per-verdict accuracy."""
    by_v: dict[str, list[bool]] = {v: [] for v in VERDICT_ORDER}
    overall: list[bool] = []
    for g, tv in truth.items():
        ok = _ok(preds.get(g), tv)
        by_v[tv].append(ok)
        overall.append(ok)
    out = {
        "overall": sum(overall) / len(overall) if overall else 0.0,
        "n": len(overall),
    }
    for v in VERDICT_ORDER:
        ns = by_v[v]
        out[v] = sum(ns) / len(ns) if ns else float("nan")
        out[f"{v}_n"] = len(ns)
    return out


def make_plots(out_dir: Path) -> None:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    truth = _load_truth()
    n_total = len(truth)

    cell_data = []
    for model, variant, label, color in CELLS:
        preds, costs = _load_cell(model, variant)
        scores = _score_cell(truth, preds)
        total_cost = sum(costs.values())
        cell_data.append({
            "label": label, "color": color, "model": model, "variant": variant,
            "overall": scores["overall"],
            "yes": scores["yes"], "contextual": scores["contextual"], "no": scores["no"],
            "yes_n": scores["yes_n"], "contextual_n": scores["contextual_n"], "no_n": scores["no_n"],
            "cost_total": total_cost,
            "cost_per_call": (total_cost / scores["n"]) if scores["n"] else 0.0,
        })

    out_dir.mkdir(parents=True, exist_ok=True)

    # --- Cost vs accuracy ---
    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    for d in cell_data:
        x = d["cost_per_call"] * WHOLE_GENOME_N
        y = d["overall"] * 100
        ax.scatter(x, y, s=200, c=d["color"], edgecolor=COLORS["dark"],
                   linewidth=0.8, zorder=5)
        ax.annotate(d["label"], (x, y), xytext=(8, 6),
                    textcoords="offset points", fontsize=10, color=COLORS["dark"])
    ax.set_xscale("log")
    ax.set_xlabel(f"Cost per whole-genome pass at 1 rep  ($, log scale; ×{WHOLE_GENOME_N:,} genes)")
    ax.set_ylabel(f"Overall accuracy on {n_total}-gene subbench (%)")
    ax.set_title("v2 subbench — Cost vs accuracy (9 Claude cells)")
    ymin = min(d["overall"] for d in cell_data) * 100
    ax.set_ylim(max(20, ymin - 8), 100)
    sns.despine(ax=ax, top=True, right=True)
    save_figure(fig, "subbench_v2_cost_vs_accuracy", output_dir=str(out_dir), formats=["pdf","png"])
    plt.close(fig)

    # --- Per-verdict grouped bars — verdict groups on x-axis, cells within ---
    cell_order = [d["label"] for d in cell_data]
    label_to_color = {d["label"]: d["color"] for d in cell_data}

    rows = []
    for d in cell_data:
        for v in VERDICT_ORDER:
            rows.append({
                "verdict": v,
                "cell": d["label"],
                "accuracy": d[v] * 100,
                "n": d[f"{v}_n"],
            })
    df = pd.DataFrame(rows)
    palette = [label_to_color[c] for c in cell_order]

    fig, ax = plt.subplots(figsize=(13, 5.8))
    sns.barplot(
        data=df,
        x="verdict", y="accuracy",
        hue="cell",
        order=VERDICT_ORDER,
        hue_order=cell_order,
        palette=palette,
        edgecolor="none", saturation=1.0,
        ax=ax,
    )

    # Annotate each bar with its accuracy. seaborn lays patches hue-major
    # then x-major: patches[i*n_v + j] = cell i, verdict j.
    n_v = len(VERDICT_ORDER)
    for i, cell_label in enumerate(cell_order):
        for j, verdict in enumerate(VERDICT_ORDER):
            bar = ax.patches[i * n_v + j]
            row = df[(df.cell == cell_label) & (df.verdict == verdict)].iloc[0]
            if row.accuracy != row.accuracy:  # NaN
                continue
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1,
                f"{row.accuracy:.0f}",
                ha="center", va="bottom",
                fontsize=7.5, color=COLORS["dark"],
            )

    ax.set_xlabel("")
    ax.set_ylabel("Accuracy (%)")
    ax.set_ylim(0, 115)
    ax.set_title(f"v2 subbench ({n_total} genes) — accuracy by ground-truth verdict, grouped by Claude cell")
    cd = cell_data[0]
    subtitle = f"n(yes) = {cd['yes_n']}  ·  n(contextual) = {cd['contextual_n']}  ·  n(no) = {cd['no_n']}"
    ax.text(0.5, -0.10, subtitle, transform=ax.transAxes, ha="center", va="top",
            fontsize=10, color=COLORS["neutral"])

    handles, _ = ax.get_legend_handles_labels()
    legend_labels = [
        f"{c}  ({df[(df.cell == c)].accuracy.mean():.0f}%)"
        for c in cell_order
    ]
    ax.legend(
        handles, legend_labels,
        title="Cell (mean across verdicts)",
        loc="upper left", bbox_to_anchor=(1.02, 1.0),
        frameon=False, borderaxespad=0.0,
    )
    sns.despine(ax=ax, top=True, right=True)
    save_figure(fig, "subbench_v2_accuracy_by_verdict", output_dir=str(out_dir), formats=["pdf","png"])
    plt.close(fig)

    # --- Print summary table ---
    print(f"{'cell':24s} {'overall':>7s} {'yes':>7s} {'contextual':>11s} {'no':>7s} {'cost':>7s}")
    for d in cell_data:
        print(f"{d['label']:24s} {d['overall']:>6.1%} {d['yes']:>6.1%}  {d['contextual']:>10.1%} {d['no']:>6.1%}  ${d['cost_total']:>5.3f}")


if __name__ == "__main__":
    make_plots(OUT_DIR)
