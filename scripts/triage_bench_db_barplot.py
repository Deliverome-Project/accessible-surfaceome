"""Per-database + Haiku-agent correctness barplot for the triage benchmark.

For each ground-truth class (`yes`, `contextual`, `no`), shows the fraction of
benchmark proteins each of the 5 retained M1 surface databases — plus the
live Haiku surface_triage agent (with HGNC + NCBI gene-resolver context
injected by the orchestrator) — correctly classifies.

Correctness convention (binary: surface vs not-surface):

* truth = `yes`        → caller correct iff vote = True
* truth = `contextual` → caller correct iff vote = True (the "yes is correct"
                         convention; callers that flag a borderline protein as
                         surface are doing the right thing for triage)
* truth = `no`         → caller correct iff vote = False

For the surface DBs the vote is the boolean flag column from
``candidate_universe.tsv``. For the Haiku agent the vote is True iff the
emitted verdict is ``yes`` or ``contextual`` — matching the scoring.py
convention that contextual = accessible.

Outputs (PDF + PNG):
  data/analysis/triage_bench/db_correctness_by_class.{pdf,png}
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
HAIKU_LABEL = "Haiku+NCBI gene"
HAIKU_COLOR = "#d87851"  # Claude orange — distinct from the brand DB palette
HAIKU_RUN_TSV = "data/eval/triage_haiku_live_run.tsv"
VERDICT_ORDER = ["yes", "contextual", "no"]
VERDICT_LABEL = {
    "yes": "yes",
    "contextual": "contextual\n(yes-vote = correct)",
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

    # Haiku-agent predictions from the live run TSV — vote = True iff the
    # agent emitted yes or contextual (the surface-side reading; matches the
    # scoring.py convention that contextual counts as accessible).
    haiku_vote_by_gene: dict[str, bool] = {}
    with open(HAIKU_RUN_TSV) as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            pred = (r.get("predicted_verdict") or "").strip()
            haiku_vote_by_gene[r["gene_symbol"]] = pred in {"yes", "contextual"}

    out = []
    for r in bench:
        acc = r["uniprot_acc"]
        votes = votes_by_acc.get(acc, {flag: False for flag, _ in DB_FLAGS_5}).copy()
        # Per-DB vote columns are merged with the Haiku vote under a shared
        # dict so the existing per-class correctness logic works unchanged.
        votes["_haiku"] = haiku_vote_by_gene.get(r["gene_symbol"], False)
        out.append({
            "gene": r["gene_symbol"],
            "uniprot_acc": acc,
            "verdict": r["ground_truth_verdict"],
            "votes": votes,
            "in_m1": acc in votes_by_acc,
            "haiku_predicted": r["gene_symbol"] in haiku_vote_by_gene,
        })
    return out


def _all_callers() -> list[tuple[str, str]]:
    """Return the (vote-key, display-label) list of every caller column.

    Surface DBs come from DB_FLAGS_5; Haiku is appended last so it sits to
    the right of the DBs visually (then re-sorted by overall accuracy).
    """
    return [*DB_FLAGS_5, ("_haiku", HAIKU_LABEL)]


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
    callers = _all_callers()
    for verdict in VERDICT_ORDER:
        proteins = by_verdict.get(verdict, [])
        counts_total[verdict] = len(proteins)
        fractions[verdict] = {}
        counts_correct[verdict] = {}
        for flag, label in callers:
            if not proteins:
                fractions[verdict][label] = 0.0
                counts_correct[verdict][label] = 0
                continue
            n_correct = 0
            for p in proteins:
                vote = p["votes"][flag]
                if verdict in ("yes", "contextual"):
                    is_correct = vote  # surface-positive call is "correct"
                else:
                    is_correct = not vote  # surface-negative call is "correct"
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
    callers = _all_callers()
    for p in bench:
        for flag, label in callers:
            vote = p["votes"][flag]
            if p["verdict"] in ("yes", "contextual"):
                if vote:
                    by_db_correct[label] += 1
            else:  # no
                if not vote:
                    by_db_correct[label] += 1
    n = len(bench)
    return {label: by_db_correct[label] / n for _, label in callers}


def _long_dataframe() -> pd.DataFrame:
    """Tidy long-format DataFrame: one row per (verdict, caller) with fraction + n_correct + n_total."""
    fractions, totals, correct_counts = compute_correctness()
    rows = []
    for verdict in VERDICT_ORDER:
        for _, caller_label in _all_callers():
            rows.append({
                "verdict": verdict,
                "verdict_label": VERDICT_LABEL[verdict],
                "database": caller_label,
                "fraction": fractions[verdict][caller_label],
                "n_correct": correct_counts[verdict][caller_label],
                "n_total": totals[verdict],
            })
    return pd.DataFrame(rows)


def make_plot(out_dir: Path) -> None:
    # setup_plotting_style registers bundled fonts (Manrope) automatically.
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    overall = overall_accuracy()
    df = _long_dataframe()

    # Sort callers by overall accuracy (descending) so the most-accurate
    # appears leftmost in each cluster.
    all_labels = [label for _, label in _all_callers()]
    db_labels_sorted = sorted(all_labels, key=lambda lbl: -overall[lbl])
    # Color identity per caller: surface DBs use brand-palette colors;
    # Haiku gets Claude orange. Lookup is by label so order doesn't matter.
    palette_lookup = {
        label: CATEGORICAL_PALETTE[i] for i, (_, label) in enumerate(DB_FLAGS_5)
    }
    palette_lookup[HAIKU_LABEL] = HAIKU_COLOR
    palette_sorted = [palette_lookup[lbl] for lbl in db_labels_sorted]

    fig, ax = plt.subplots(figsize=(11.5, 5.5))

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
    for i, caller_label in enumerate(db_labels_sorted):
        for j, verdict in enumerate(VERDICT_ORDER):
            bar = ax.patches[i * len(VERDICT_ORDER) + j]
            row = df[(df.database == caller_label) & (df.verdict == verdict)].iloc[0]
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
    ax.set_ylabel("Fraction of class correctly classified")
    ax.set_title("Surface caller performance per ground-truth class")
    ax.set_ylim(0, 1.12)
    ax.yaxis.set_major_locator(plt.MaxNLocator(6))

    # Replace seaborn's default legend with sorted-by-overall-accuracy version
    # placed outside the plotting area on the right.
    handles, _ = ax.get_legend_handles_labels()
    legend_labels = [f"{lbl} ({overall[lbl]:.0%})" for lbl in db_labels_sorted]
    ax.legend(
        handles,
        legend_labels,
        title="Caller (overall acc.)",
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        frameon=False,
        borderaxespad=0.0,
    )

    # Overall-n subtitle
    totals = {v: df[df.verdict == v].iloc[0].n_total for v in VERDICT_ORDER}
    _n_label = {"yes": "yes", "contextual": "contextual", "no": "no"}
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
