"""Per-database correctness barplot for the triage benchmark.

For each ground-truth class (`yes`, `maybe`, `no`), shows the fraction of
benchmark proteins each of the 5 retained M1 surface databases correctly
classifies. The user's convention: a database is *correct* when its vote
aligns with the surface-side reading of the truth label, i.e.:

* truth = `yes`   → DB correct iff vote = True
* truth = `maybe` → DB correct iff vote = True (the "yes is correct" convention;
                    DBs that flag a borderline protein as surface are doing the
                    right thing for triage)
* truth = `no`    → DB correct iff vote = False

The chart shows one cluster per verdict class with 5 colored bars per
cluster (one per database). The total n in each class is annotated above
each bar.

Outputs (PDF + JPEG):
  data/analysis/triage_bench/db_correctness_by_class.{pdf,jpeg}
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from accessible_surfaceome.audit._plotting_config import (
    CATEGORICAL_PALETTE,
    COLORS,
    save_figure,
    setup_plotting_style,
)


DB_FLAGS_5 = [
    ("uniprot_surface_flag", "UniProt"),
    ("go_surface_flag", "GO CC"),
    ("hpa_surface_flag", "HPA"),
    ("surfy_surface_flag", "SURFY"),
    ("cspa_surface_flag", "CSPA"),
]
VERDICT_ORDER = ["yes", "maybe", "no"]
VERDICT_LABEL = {
    "yes": "yes",
    "maybe": "maybe\n(yes-vote = correct)",
    "no": "no",
}


def load_benchmark_with_votes() -> list[dict[str, object]]:
    bench = []
    with open("data/eval/triage_benchmark_v1.tsv") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            bench.append(r)

    votes_by_acc = {}
    with open("data/processed/candidate_universe/candidate_universe.tsv") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            acc = r["uniprot_accession"]
            votes_by_acc[acc] = {flag: (r.get(flag, "0") == "1") for flag, _ in DB_FLAGS_5}

    out = []
    for r in bench:
        acc = r["uniprot_acc"]
        votes = votes_by_acc.get(acc, {flag: False for flag, _ in DB_FLAGS_5})
        out.append({
            "gene": r["gene_symbol"],
            "uniprot_acc": acc,
            "verdict": r["ground_truth_verdict"],
            "votes": votes,
            "in_m1": acc in votes_by_acc,
        })
    return out


def compute_correctness() -> tuple[
    dict[str, dict[str, float]],
    dict[str, int],
    dict[str, dict[str, int]],
]:
    """Compute per-(verdict, DB) correctness fraction + per-verdict n + per-(verdict, DB) correct counts."""
    bench = load_benchmark_with_votes()
    by_verdict = defaultdict(list)
    for entry in bench:
        by_verdict[entry["verdict"]].append(entry)

    fractions: dict[str, dict[str, float]] = {}
    counts_correct: dict[str, dict[str, int]] = {}
    counts_total: dict[str, int] = {}
    for verdict in VERDICT_ORDER:
        proteins = by_verdict.get(verdict, [])
        counts_total[verdict] = len(proteins)
        fractions[verdict] = {}
        counts_correct[verdict] = {}
        for flag, label in DB_FLAGS_5:
            if not proteins:
                fractions[verdict][label] = 0.0
                counts_correct[verdict][label] = 0
                continue
            n_correct = 0
            for p in proteins:
                vote = p["votes"][flag]
                if verdict in ("yes", "maybe"):
                    is_correct = vote  # surface-positive DB call is "correct"
                else:
                    is_correct = not vote  # surface-negative DB call is "correct"
                if is_correct:
                    n_correct += 1
            fractions[verdict][label] = n_correct / len(proteins)
            counts_correct[verdict][label] = n_correct
    return fractions, counts_total, counts_correct


def make_plot(out_dir: Path) -> None:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    fractions, totals, correct_counts = compute_correctness()

    fig, ax = plt.subplots(figsize=(10, 5.5))

    db_labels = [label for _, label in DB_FLAGS_5]
    n_groups = len(VERDICT_ORDER)
    n_bars = len(db_labels)
    bar_width = 0.16
    x_centers = np.arange(n_groups)

    palette = CATEGORICAL_PALETTE[: len(db_labels)]

    for i, db_label in enumerate(db_labels):
        offsets = bar_width * (i - (n_bars - 1) / 2)
        heights = [fractions[v][db_label] for v in VERDICT_ORDER]
        bars = ax.bar(
            x_centers + offsets,
            heights,
            width=bar_width,
            label=db_label,
            color=palette[i],
            edgecolor="none",
        )
        # Annotate each bar with the correct/total count
        for j, bar in enumerate(bars):
            v = VERDICT_ORDER[j]
            n_correct = correct_counts[v][db_label]
            n_total = totals[v]
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.02,
                f"{n_correct}/{n_total}",
                ha="center",
                va="bottom",
                fontsize=8.5,
                color=COLORS["dark"],
            )

    ax.set_xticks(x_centers)
    ax.set_xticklabels([VERDICT_LABEL[v] for v in VERDICT_ORDER])
    ax.set_ylabel("Fraction of class correctly classified by DB")
    ax.set_title("Surface-database performance per ground-truth class")
    ax.set_ylim(0, 1.12)
    ax.yaxis.set_major_locator(plt.MaxNLocator(6))
    ax.legend(title="Database", loc="upper right", ncols=1, frameon=True, framealpha=0.95)

    # Add overall-n subtitle so the totals are immediately visible
    subtitle = "  ·  ".join(
        f"n({v}) = {totals[v]}" for v in VERDICT_ORDER
    )
    ax.text(
        0.5, -0.18, subtitle,
        transform=ax.transAxes,
        ha="center", va="top",
        fontsize=10,
        color=COLORS["muted"] if "muted" in COLORS else COLORS["neutral"],
    )

    fig.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    save_figure(
        fig,
        filename="db_correctness_by_class",
        output_dir=str(out_dir),
        formats=["pdf", "jpeg"],
    )
    plt.close(fig)


def main() -> None:
    make_plot(Path("data/analysis/triage_bench"))


if __name__ == "__main__":
    main()
