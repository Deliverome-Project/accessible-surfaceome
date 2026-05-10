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
import pandas as pd
import seaborn as sns

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
# Display labels. The underlying schema still uses "maybe" — we rename to
# "contextual" only at the figure level (more descriptive: pMHC, induced,
# cycling, etc. are all context-dependent surface forms).
VERDICT_LABEL = {
    "yes": "yes",
    "maybe": "contextual\n(yes-vote = correct)",
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


def _long_dataframe() -> pd.DataFrame:
    """Tidy long-format DataFrame: one row per (verdict, db) with fraction + n_correct + n_total."""
    fractions, totals, correct_counts = compute_correctness()
    rows = []
    for verdict in VERDICT_ORDER:
        for _, db_label in DB_FLAGS_5:
            rows.append({
                "verdict": verdict,
                "verdict_label": VERDICT_LABEL[verdict],
                "database": db_label,
                "fraction": fractions[verdict][db_label],
                "n_correct": correct_counts[verdict][db_label],
                "n_total": totals[verdict],
            })
    return pd.DataFrame(rows)


def make_plot(out_dir: Path) -> None:
    # setup_plotting_style registers bundled fonts (Manrope) automatically.
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    overall = overall_accuracy()
    df = _long_dataframe()

    # Sort DBs by overall accuracy (descending) so the most-accurate
    # database appears leftmost in each cluster.
    db_labels_sorted = sorted(
        (label for _, label in DB_FLAGS_5),
        key=lambda lbl: -overall[lbl],
    )
    # Map sorted labels back to brand-palette colors (preserve color identity
    # per DB regardless of sort order).
    palette_lookup = dict(
        zip(
            (label for _, label in DB_FLAGS_5),
            CATEGORICAL_PALETTE[: len(DB_FLAGS_5)],
        )
    )
    palette_sorted = [palette_lookup[lbl] for lbl in db_labels_sorted]

    fig, ax = plt.subplots(figsize=(10, 5.5))

    sns.barplot(
        data=df,
        x="verdict_label",
        y="fraction",
        hue="database",
        order=[VERDICT_LABEL[v] for v in VERDICT_ORDER],
        hue_order=db_labels_sorted,
        palette=palette_sorted,
        edgecolor="none",
        saturation=1.0,
        ax=ax,
    )

    # Annotate each bar with n_correct / n_total. Walk the patches in
    # legend-order; seaborn lays them out hue-major then x-major.
    for i, db_label in enumerate(db_labels_sorted):
        for j, verdict in enumerate(VERDICT_ORDER):
            bar = ax.patches[i * len(VERDICT_ORDER) + j]
            row = df[(df.database == db_label) & (df.verdict == verdict)].iloc[0]
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.02,
                f"{row.n_correct}/{row.n_total}",
                ha="center",
                va="bottom",
                fontsize=8.5,
                color=COLORS["dark"],
            )

    ax.set_xlabel("")
    ax.set_ylabel("Fraction of class correctly classified by DB")
    ax.set_title("Surface-database performance per ground-truth class")
    ax.set_ylim(0, 1.12)
    ax.yaxis.set_major_locator(plt.MaxNLocator(6))

    # Replace seaborn's default legend with sorted-by-overall-accuracy version
    # placed outside the plotting area on the right.
    handles, _ = ax.get_legend_handles_labels()
    legend_labels = [f"{lbl} ({overall[lbl]:.0%})" for lbl in db_labels_sorted]
    ax.legend(
        handles,
        legend_labels,
        title="Database (overall acc.)",
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        frameon=False,
        borderaxespad=0.0,
    )

    # Overall-n subtitle
    totals = {v: df[df.verdict == v].iloc[0].n_total for v in VERDICT_ORDER}
    _n_label = {"yes": "yes", "maybe": "contextual", "no": "no"}
    subtitle = "  ·  ".join(f"n({_n_label[v]}) = {totals[v]}" for v in VERDICT_ORDER)
    ax.text(
        0.5, -0.16, subtitle,
        transform=ax.transAxes,
        ha="center", va="top",
        fontsize=10,
        color=COLORS["neutral"],
    )

    # Despine after axes creation (config calls it before, which is too early).
    sns.despine(ax=ax, top=True, right=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    save_figure(
        fig,
        filename="db_correctness_by_class",
        output_dir=str(out_dir),
        # PNG preserves the transparent figure/axes background that the
        # config sets; JPEG cannot carry alpha so it ends up white.
        formats=["pdf", "png"],
    )
    plt.close(fig)


def main() -> None:
    make_plot(Path("data/analysis/triage_bench"))


if __name__ == "__main__":
    main()
