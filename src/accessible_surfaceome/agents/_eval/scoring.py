"""Aggregate per-run records into summary.tsv + per_protein.tsv + scatter.png.

Walks ``data/eval/triage_bench_v1/<cell_label>/<gene>.json`` for every
cell directory present, computes per-cell totals and per-protein
correctness, and emits three artifacts in ``EVAL_ROOT``.

Plot is matplotlib + saved as both PNG and PDF for paper-friendly use.
"""

from __future__ import annotations

import csv
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .runner import EVAL_ROOT


@dataclass
class CellSummary:
    cell_label: str
    variant: str
    model: str | None
    n_runs: int
    n_correct_verdict: int
    n_correct_signal: int
    verdict_accuracy: float
    signal_accuracy: float
    # Binary classification (accessible = yes|contextual; skip = no). For
    # triage we weight recall higher than precision: a false negative
    # silently drops a real candidate forever, while a false positive
    # just adds one item to the deep-dive queue.
    binary_accuracy: float
    accessible_recall: float  # TP / (TP + FN)
    inaccessible_specificity: float  # TN / (TN + FP)
    f2_score: float  # F-beta with beta=2 — weights recall 2x precision
    total_cost_usd: float
    mean_latency_s: float


def write_report(eval_root: Path = EVAL_ROOT) -> dict[str, Path]:
    """Aggregate every cell directory under ``eval_root`` and emit the report.

    Returns a dict of artifact name → path written.
    """

    from .database_baselines import compute_database_baselines

    eval_root.mkdir(parents=True, exist_ok=True)
    cells = _discover_cells(eval_root)
    if not cells:
        raise RuntimeError(f"no cell directories found under {eval_root}")

    summaries: list[CellSummary] = []
    per_protein: dict[str, dict[str, Any]] = {}  # gene -> {cell_label: correctness, ...}
    for cell_dir in cells:
        records = _load_records(cell_dir)
        if not records:
            continue
        summary = _summarize(cell_dir, records)
        summaries.append(summary)
        for r in records:
            gene = r["gene_symbol"]
            per_protein.setdefault(gene, {"gene_symbol": gene, "ground_truth_verdict": r["ground_truth_verdict"]})
            per_protein[gene][f"{summary.cell_label}_verdict"] = r.get("emitted_verdict") or "MISSING"
            per_protein[gene][f"{summary.cell_label}_correct"] = "Y" if r.get("correct_verdict") else "N"

    # Append per-database baselines so the summary table shows the full
    # cost/accuracy/recall frontier in one place.
    summaries.extend(compute_database_baselines())

    summary_path = eval_root / "summary.tsv"
    _write_summary_tsv(summaries, summary_path)

    per_protein_path = eval_root / "per_protein.tsv"
    _write_per_protein_tsv(summaries, per_protein, per_protein_path)

    scatter_paths = _write_scatter(summaries, eval_root)

    return {
        "summary_tsv": summary_path,
        "per_protein_tsv": per_protein_path,
        **scatter_paths,
    }


def _discover_cells(eval_root: Path) -> list[Path]:
    return sorted(p for p in eval_root.iterdir() if p.is_dir())


def _load_records(cell_dir: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in sorted(cell_dir.glob("*.json")):
        try:
            out.append(json.loads(path.read_text()))
        except json.JSONDecodeError:
            continue
    return out


def _summarize(cell_dir: Path, records: list[dict[str, Any]]) -> CellSummary:
    n = len(records)
    n_correct_verdict = sum(1 for r in records if r.get("correct_verdict"))
    n_correct_signal = sum(1 for r in records if r.get("correct_signal"))
    total_cost = sum(float(r.get("cost_usd") or 0.0) for r in records)
    latencies = [float(r.get("latency_s") or 0.0) for r in records if r.get("latency_s") is not None]

    # Binary classification: accessible = yes|contextual, skip = no.
    tp = tn = fp = fn = 0
    for r in records:
        truth = 1 if r.get("ground_truth_verdict") in ("yes", "contextual") else 0
        emit = r.get("emitted_verdict")
        pred = 1 if emit in ("yes", "contextual") else 0
        if pred == 1 and truth == 1:
            tp += 1
        elif pred == 0 and truth == 0:
            tn += 1
        elif pred == 1 and truth == 0:
            fp += 1
        else:
            fn += 1
    binary_acc = (tp + tn) / n if n else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    spec = tn / (tn + fp) if (tn + fp) else 0.0
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    beta = 2
    if prec + recall > 0:
        f2 = (1 + beta**2) * prec * recall / ((beta**2 * prec) + recall)
    else:
        f2 = 0.0

    return CellSummary(
        cell_label=cell_dir.name,
        variant=records[0].get("variant") or "?",
        model=records[0].get("model"),
        n_runs=n,
        n_correct_verdict=n_correct_verdict,
        n_correct_signal=n_correct_signal,
        verdict_accuracy=n_correct_verdict / n if n else 0.0,
        signal_accuracy=n_correct_signal / n if n else 0.0,
        binary_accuracy=binary_acc,
        accessible_recall=recall,
        inaccessible_specificity=spec,
        f2_score=f2,
        total_cost_usd=total_cost,
        mean_latency_s=statistics.fmean(latencies) if latencies else 0.0,
    )


def _write_summary_tsv(summaries: list[CellSummary], path: Path) -> None:
    summaries = sorted(summaries, key=lambda s: (s.variant, s.cell_label))
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(
            [
                "cell_label",
                "variant",
                "model",
                "n_runs",
                "verdict_acc",
                "signal_acc",
                "binary_acc",
                "accessible_recall",
                "inaccessible_specificity",
                "f2_score",
                "total_cost_usd",
                "mean_latency_s",
            ]
        )
        for s in summaries:
            writer.writerow(
                [
                    s.cell_label,
                    s.variant,
                    s.model or "",
                    s.n_runs,
                    f"{s.verdict_accuracy:.3f}",
                    f"{s.signal_accuracy:.3f}",
                    f"{s.binary_accuracy:.3f}",
                    f"{s.accessible_recall:.3f}",
                    f"{s.inaccessible_specificity:.3f}",
                    f"{s.f2_score:.3f}",
                    f"{s.total_cost_usd:.4f}",
                    f"{s.mean_latency_s:.2f}",
                ]
            )


def _write_per_protein_tsv(
    summaries: list[CellSummary],
    per_protein: dict[str, dict[str, Any]],
    path: Path,
) -> None:
    cell_labels = sorted({s.cell_label for s in summaries})
    fieldnames = ["gene_symbol", "ground_truth_verdict"]
    for label in cell_labels:
        fieldnames.append(f"{label}_verdict")
        fieldnames.append(f"{label}_correct")

    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for gene in sorted(per_protein):
            row = {k: per_protein[gene].get(k, "") for k in fieldnames}
            writer.writerow(row)


def _write_scatter(summaries: list[CellSummary], eval_root: Path) -> dict[str, Path]:
    """Cost (x) vs verdict accuracy (y) scatter; one point per cell."""

    try:
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except ModuleNotFoundError:  # pragma: no cover - matplotlib is in deps
        return {}

    fig, ax = plt.subplots(figsize=(8, 5.5))
    for s in summaries:
        x = max(s.total_cost_usd, 1e-4)  # log-friendly: bump 0 to small positive
        y = s.verdict_accuracy
        size = 80 + max(s.mean_latency_s, 0.0) * 8
        color = {"A": "#1f77b4", "B": "#2ca02c", "C": "#ff7f0e", "D": "#d62728"}.get(
            s.variant, "#7f7f7f"
        )
        ax.scatter([x], [y], s=size, color=color, alpha=0.75, edgecolors="black", linewidths=0.5)
        ax.annotate(
            s.cell_label, (x, y), xytext=(6, 4), textcoords="offset points", fontsize=8
        )
    ax.set_xscale("log")
    ax.set_xlabel("Total cost across benchmark (USD, log scale)")
    ax.set_ylabel("Verdict accuracy")
    ax.set_ylim(-0.05, 1.05)
    ax.grid(True, which="both", linestyle=":", alpha=0.4)
    ax.set_title("Triage variant comparison: verdict accuracy vs cost")

    legend_entries = [
        ("Variant A: pure model", "#1f77b4"),
        ("Variant B: deterministic", "#2ca02c"),
        ("Variant C: PubMed tool", "#ff7f0e"),
        ("Variant D: full triage", "#d62728"),
    ]
    handles = [
        plt.scatter([], [], s=80, color=c, edgecolors="black", linewidths=0.5, label=label)
        for label, c in legend_entries
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=8)

    fig.tight_layout()
    png_path = eval_root / "scatter.png"
    pdf_path = eval_root / "scatter.pdf"
    fig.savefig(png_path, dpi=150)
    fig.savefig(pdf_path)
    plt.close(fig)
    return {"scatter_png": png_path, "scatter_pdf": pdf_path}


__all__ = ["write_report", "CellSummary"]
