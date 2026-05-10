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

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np

from accessible_surfaceome.audit._plotting_config import (
    CATEGORICAL_PALETTE,
    COLORS,
    save_figure,
    setup_plotting_style,
)


def register_bundled_fonts() -> None:
    """Add `./assets/fonts/*.ttf` to matplotlib's font manager.

    The project's plotting config asks for Manrope, but matplotlib only
    finds it if it's been added to the font manager. This walks the
    bundled assets/fonts dir and registers each TTF before any axes
    are constructed.
    """

    fonts_dir = Path("assets/fonts")
    if not fonts_dir.is_dir():
        return
    for ttf in sorted(fonts_dir.glob("*.ttf")):
        try:
            fm.fontManager.addfont(str(ttf))
        except Exception:
            continue


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


def overall_accuracy() -> dict[str, float]:
    """Total fraction correct per DB across every benchmark protein (all classes pooled).

    A DB is correct on a protein when its vote aligns with the surface-side
    reading of the ground truth — same convention used per-class.
    """

    bench = load_benchmark_with_votes()
    by_db_correct: dict[str, int] = defaultdict(int)
    for p in bench:
        for flag, label in DB_FLAGS_5:
            vote = p["votes"][flag]
            if p["verdict"] in ("yes", "maybe"):
                if vote:
                    by_db_correct[label] += 1
            else:  # no
                if not vote:
                    by_db_correct[label] += 1
    n = len(bench)
    return {label: by_db_correct[label] / n for _, label in DB_FLAGS_5}


def make_plot(out_dir: Path) -> None:
    register_bundled_fonts()
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    fractions, totals, correct_counts = compute_correctness()
    overall = overall_accuracy()

    # Sort DB labels by overall accuracy (descending) so the most-accurate
    # database appears leftmost in each cluster.
    db_labels_sorted = sorted(
        (label for _, label in DB_FLAGS_5),
        key=lambda lbl: -overall[lbl],
    )

    fig, ax = plt.subplots(figsize=(10, 5.5))

    n_groups = len(VERDICT_ORDER)
    n_bars = len(db_labels_sorted)
    bar_width = 0.16
    x_centers = np.arange(n_groups)

    # Map sorted labels back to colors from the categorical palette
    palette_lookup = dict(
        zip(
            (label for _, label in DB_FLAGS_5),
            CATEGORICAL_PALETTE[: len(DB_FLAGS_5)],
        )
    )

    for i, db_label in enumerate(db_labels_sorted):
        offsets = bar_width * (i - (n_bars - 1) / 2)
        heights = [fractions[v][db_label] for v in VERDICT_ORDER]
        legend_label = f"{db_label} ({overall[db_label]:.0%})"
        bars = ax.bar(
            x_centers + offsets,
            heights,
            width=bar_width,
            label=legend_label,
            color=palette_lookup[db_label],
            edgecolor="none",
        )
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

    # Legend outside the plotting area on the right; sorted-by-overall-accuracy.
    ax.legend(
        title="Database (overall acc.)",
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        frameon=True,
        framealpha=0.95,
        borderaxespad=0.0,
    )

    # Add overall-n subtitle so the totals are immediately visible
    subtitle = "  ·  ".join(
        f"n({v}) = {totals[v]}" for v in VERDICT_ORDER
    )
    ax.text(
        0.5, -0.18, subtitle,
        transform=ax.transAxes,
        ha="center", va="top",
        fontsize=10,
        color=COLORS.get("muted", COLORS["neutral"]),
    )

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
