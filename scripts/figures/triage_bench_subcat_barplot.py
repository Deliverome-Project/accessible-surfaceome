"""Per-subcategory correctness barplot for the triage benchmark.

Extends the per-class plot by drilling into the ``class`` column from
``triage_benchmark_v1.tsv`` — e.g. within ``yes`` we see
``disagreement_rich_positive`` vs ``gpcr_extracellular_pocket`` vs
``gpi_anchored_positive`` etc. Lets the reader spot error patterns by
mechanism (which callers miss pMHC, which miss GPI, which call
GPCRs surface vs not).

Same binary-vote convention as the per-class plot:
* truth = yes / contextual → caller correct iff vote = True
* truth = no               → caller correct iff vote = False

Callers: 5 surface DBs + Haiku (yes-or-contextual = surface vote).

Output: data/analysis/triage_bench/caller_correctness_by_subcategory.{pdf,png}
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
HAIKU_COLOR = "#d87851"  # Claude orange
HAIKU_RUN_TSV = "data/eval/triage_haiku_live_run.tsv"
VERDICT_ORDER = ["yes", "contextual", "no"]


def _all_callers() -> list[tuple[str, str]]:
    return [*DB_FLAGS_5, ("_haiku", HAIKU_LABEL)]


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

    haiku_vote_by_gene: dict[str, bool] = {}
    with open(HAIKU_RUN_TSV) as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            pred = (r.get("predicted_verdict") or "").strip()
            haiku_vote_by_gene[r["gene_symbol"]] = pred in {"yes", "contextual"}

    out = []
    for r in bench:
        acc = r["uniprot_acc"]
        votes = votes_by_acc.get(acc, {flag: False for flag, _ in DB_FLAGS_5}).copy()
        votes["_haiku"] = haiku_vote_by_gene.get(r["gene_symbol"], False)
        out.append({
            "gene": r["gene_symbol"],
            "uniprot_acc": acc,
            "verdict": r["ground_truth_verdict"],
            "klass": r["class"],
            "votes": votes,
        })
    return out


def _pretty_class(klass: str) -> str:
    """Drop the trailing _positive/_negative/_borderline tag for tighter axis labels."""
    suffixes = ("_positive", "_negative", "_borderline")
    for s in suffixes:
        if klass.endswith(s):
            return klass[: -len(s)].replace("_", " ")
    return klass.replace("_", " ")


def _compute_dataframe() -> pd.DataFrame:
    """One row per (verdict, class, caller) with fraction + n_correct + n_total."""
    bench = load_benchmark_with_votes()
    by_class: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for p in bench:
        by_class[(p["verdict"], p["klass"])].append(p)

    rows = []
    for (verdict, klass), proteins in by_class.items():
        n = len(proteins)
        for flag, caller_label in _all_callers():
            n_correct = 0
            for p in proteins:
                vote = p["votes"][flag]
                if verdict in ("yes", "contextual"):
                    is_correct = vote
                else:
                    is_correct = not vote
                if is_correct:
                    n_correct += 1
            rows.append({
                "verdict": verdict,
                "klass": klass,
                "klass_pretty": _pretty_class(klass),
                "caller": caller_label,
                "fraction": n_correct / n,
                "n_correct": n_correct,
                "n_total": n,
            })
    return pd.DataFrame(rows)


def _overall_accuracy(df: pd.DataFrame) -> dict[str, float]:
    """Sum n_correct / sum n_total across the whole benchmark, per caller."""
    out: dict[str, float] = {}
    for caller in df.caller.unique():
        sub = df[df.caller == caller]
        # n_total per (verdict, class) is fixed; total = sum of unique class sizes.
        # Easiest: walk one caller's rows, sum n_correct and n_total directly.
        n_correct = sub.n_correct.sum()
        n_total = sub.n_total.sum()
        out[caller] = n_correct / n_total if n_total else 0.0
    return out


def make_plot(out_dir: Path) -> None:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    df = _compute_dataframe()
    overall = _overall_accuracy(df)

    all_callers = [label for _, label in _all_callers()]
    callers_sorted = sorted(all_callers, key=lambda lbl: -overall[lbl])
    palette_lookup = {
        label: CATEGORICAL_PALETTE[i] for i, (_, label) in enumerate(DB_FLAGS_5)
    }
    palette_lookup[HAIKU_LABEL] = HAIKU_COLOR
    palette_sorted = [palette_lookup[lbl] for lbl in callers_sorted]

    # Three subplots stacked vertically — each verdict gets a full-width row
    # so the subcategory labels have horizontal room to breathe.
    subcats_per_verdict = {v: sorted(df[df.verdict == v].klass.unique()) for v in VERDICT_ORDER}
    heights = [len(subcats_per_verdict[v]) for v in VERDICT_ORDER]
    fig, axes = plt.subplots(
        3, 1,
        figsize=(15, 16),
        gridspec_kw={"height_ratios": heights, "hspace": 0.62},
    )

    for ax, verdict in zip(axes, VERDICT_ORDER):
        sub_df = df[df.verdict == verdict].copy()
        # Order subcategories by their n_total (descending) so the most
        # well-populated subcategory sits leftmost.
        sizes = (
            sub_df.groupby("klass_pretty")["n_total"].first().sort_values(ascending=False)
        )
        order = list(sizes.index)
        sns.barplot(
            data=sub_df,
            x="klass_pretty",
            y="fraction",
            hue="caller",
            order=order,
            hue_order=callers_sorted,
            palette=palette_sorted,
            edgecolor="none",
            saturation=1.0,
            ax=ax,
        )
        # Annotate each bar with n_correct/n_total. Only show numerator + slash
        # form when the class is meaningfully populated (n_total >= 3); for
        # smaller classes the count is in the x-tick label instead.
        for patch_idx, patch in enumerate(ax.patches):
            caller_idx = patch_idx // len(order)
            klass_idx = patch_idx % len(order)
            if caller_idx >= len(callers_sorted) or klass_idx >= len(order):
                continue
            caller_label = callers_sorted[caller_idx]
            klass_pretty = order[klass_idx]
            row = sub_df[(sub_df.caller == caller_label) & (sub_df.klass_pretty == klass_pretty)]
            if row.empty:
                continue
            r = row.iloc[0]
            label_text = f"{r.n_correct}/{r.n_total}"
            ax.text(
                patch.get_x() + patch.get_width() / 2,
                patch.get_height() + 0.018,
                label_text,
                ha="center",
                va="bottom",
                fontsize=8,
                color=COLORS["dark"],
            )

        # Embed the per-class n in the tick label so the reader sees sample
        # size without needing the small annotations.
        tick_labels = [f"{k}\n(n={int(sizes[k])})" for k in order]
        ax.set_xticks(range(len(order)))
        ax.set_xticklabels(tick_labels)

        ax.set_xlabel("")
        ax.set_ylabel("Fraction correct")
        n_total = sub_df.n_total.sum() // len(callers_sorted)
        ax.set_title(
            f"truth = {verdict}   (n = {n_total} proteins, {len(order)} subcategories)",
            fontsize=13,
            loc="left",
        )
        ax.set_ylim(0, 1.18)
        ax.tick_params(axis="x", labelrotation=18, labelsize=10)
        for label in ax.get_xticklabels():
            label.set_horizontalalignment("right")
        ax.get_legend().remove()
        sns.despine(ax=ax, top=True, right=True)

    # Master legend at the top, above all subplots.
    legend_labels = [f"{lbl} ({overall[lbl]:.0%})" for lbl in callers_sorted]
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=palette_lookup[lbl]) for lbl in callers_sorted
    ]
    fig.legend(
        handles,
        legend_labels,
        title="Caller (overall accuracy on 130-protein benchmark)",
        loc="upper center",
        bbox_to_anchor=(0.5, 1.005),
        ncol=len(callers_sorted),
        frameon=False,
    )

    fig.suptitle(
        "Surface caller performance per ground-truth subcategory",
        fontsize=15,
        y=1.025,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    save_figure(
        fig,
        filename="caller_correctness_by_subcategory",
        output_dir=str(out_dir),
        formats=["pdf", "png"],
    )
    plt.close(fig)


def main() -> None:
    make_plot(Path("data/analysis/triage_bench"))


if __name__ == "__main__":
    main()
