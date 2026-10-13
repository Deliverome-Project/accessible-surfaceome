"""Supp Fig 2 — LLM-only overall accuracy on the 147-gene benchmark.

Grouped bars by model (Haiku 4.5 / Haiku 5.5 / Sonnet 4.6 / Sonnet 5 /
Sonnet 5.5 / Opus 4.8 / Opus 5 / Opus 5.5) with hatched bars for the
within-model prompt variants (naive / + IDs / + IDs + web / + IDs + PubMed /
+ IDs at low reasoning effort). Haiku 4.5 and Sonnet 4.6 have all four context
variants, Haiku 5.5, Sonnet 5.5 and Opus 4.8 naive and + IDs, Sonnet 5 and
Opus 5 + IDs only, and Opus 5.5 + IDs at its default and at low effort. Groups
are packed: a model gets only as many bar slots as it has variants. Bar
height = mean of the three per-replicate accuracies, with each replicate's
accuracy overlaid as a point and a run-to-run SEM error bar.

Color encodes model generation (orange Claude 4.x, blue Claude 5, teal
Claude 5.5; darker = larger model), and the two Sonnet 4.6 configurations the
production pipeline uses are lavender. Refused calls (``refused`` = 1, a
safety-classifier stop; only Opus 5.5 refuses here) are excluded from
accuracy, and the refusal rate is printed on the bar.

DATA SOURCE — reads ``data/processed/figures/db_correctness_overall.tsv``
(built by ``scripts/build_figure_tsvs.py``), the SAME single source of truth the
gist mirror ``data/analysis/figures/make_db_correctness_overall.py`` reads. This
is the canonical generator that replaced the ``triage_bench_db_barplot.py``
``make_overall_plot`` path, whose hardcoded ``opus-4-7`` model ID shipped empty
bars when the data moved to Opus 4.8. ``MODEL_ORDER`` below is still a fixed
list (it sets display order, labels and colors), so a new model ID in the TSV
must be added there or it is silently skipped.

Run: ``uv run python scripts/figures/db_correctness_overall.py``
# Reproduction: https://gist.github.com/beccajcarlson/9c765ed9673d7bd845c3ac091ad2204d
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.patches import Patch

from accessible_surfaceome.audit._plotting_config import save_figure, setup_plotting_style

REPO = Path(__file__).resolve().parents[2]
DATA_TSV = REPO / "data/processed/figures/db_correctness_overall.tsv"
OUT_DIR = REPO / "data/analysis/figures"
GIST_URL = "https://gist.github.com/beccajcarlson/9c765ed9673d7bd845c3ac091ad2204d"

INK = "#1F1718"
# Model display order + color: hue = generation (orange 4.x, blue 5, teal
# 5.5), light → dark = larger model.
MODEL_ORDER = [
    ("claude-haiku-4-5",  "Haiku 4.5",  "#f1c4ab"),
    ("claude-haiku-5-5",  "Haiku 5.5",  "#9fd3cf"),
    ("claude-sonnet-4-6", "Sonnet 4.6", "#d87851"),
    ("claude-sonnet-5",   "Sonnet 5",   "#6b9cc4"),
    ("claude-sonnet-5-5", "Sonnet 5.5", "#3f9c96"),
    ("claude-opus-4-8",   "Opus 4.8",   "#a85b3f"),
    ("claude-opus-5",     "Opus 5",     "#2e5d7a"),
    ("claude-opus-5-5",   "Opus 5.5",   "#1f5f5b"),
]
# The configurations the production pipeline runs, recolored so they stand
# out from their generation.
PRODUCTION_COLOR = {
    ("claude-sonnet-4-6", "ncbi"):        "#7B6BB0",
    ("claude-sonnet-4-6", "pubmed_ncbi"): "#B3A6DA",
}
# Variant display order + matplotlib hatch pattern.
VARIANT_ORDER = [
    ("naive",           "naive",                 ""),
    ("ncbi",            "+ IDs",                 "//"),
    ("web_ncbi",        "+ IDs + web",           "xx"),
    ("pubmed_ncbi",     "+ IDs + PubMed",        ".."),
    ("ncbi_effort_low", "+ IDs, low effort",     "\\\\"),
]
COLOR_LEGEND = [
    ("Claude 4.x", "#d87851"),
    ("Claude 5", "#2e5d7a"),
    ("Claude 5.5", "#3f9c96"),
    ("Production triage", "#7B6BB0"),
]
BAR_W = 0.22      # one bar slot, in axis units
GROUP_GAP = 0.30  # space between model groups


def _per_rep_accuracy(reps_df: pd.DataFrame) -> dict[tuple[str, str], list[float]]:
    """{(model, variant): [acc_rep1, …]} — mean ``is_match`` per
    (model, variant, replicate) group over answered calls, as a percentage."""
    reps_df = reps_df.copy()
    reps_df["is_match"] = reps_df["is_match"].astype(int)
    if "refused" in reps_df:
        reps_df = reps_df[reps_df["refused"].fillna(0).astype(int) == 0]
    grouped = (
        reps_df.groupby(["model", "prompt_variant", "replicate"])["is_match"]
        .mean()
        .reset_index()
    )
    out: dict[tuple[str, str], list[float]] = {}
    for (model, variant), g in grouped.groupby(["model", "prompt_variant"]):
        out[(model, variant)] = [v * 100 for v in g["is_match"].tolist()]
    return out


def _refusal_pct(reps_df: pd.DataFrame) -> dict[tuple[str, str], float]:
    if "refused" not in reps_df:
        return {}
    refused = reps_df["refused"].fillna(0).astype(int)
    return (refused.groupby([reps_df["model"], reps_df["prompt_variant"]]).mean() * 100).to_dict()


def main() -> None:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    # Match the gist mirror's layout fingerprint (tests/test_figure_canonical_mirror_sync).
    plt.rcParams.update({
        "axes.labelsize": 18, "xtick.labelsize": 16, "ytick.labelsize": 16,
        "legend.fontsize": 16, "axes.titlesize": 0, "font.size": 16,
    })
    reps_df = pd.read_csv(DATA_TSV, sep="\t")
    rep_acc = _per_rep_accuracy(reps_df)
    refusal_pct = _refusal_pct(reps_df)

    fig, ax = plt.subplots(figsize=(18, 5.5))
    x, centers, labels = 0.0, [], []
    for model, m_label, color in MODEL_ORDER:
        present = [(v, h) for v, _, h in VARIANT_ORDER if rep_acc.get((model, v))]
        if not present:
            continue  # model not in the data
        xs = [x + i * BAR_W for i in range(len(present))]
        for xi, (variant, hatch) in zip(xs, present):
            reps = rep_acc[(model, variant)]
            mean_rep = sum(reps) / len(reps)
            ax.bar(xi, mean_rep, width=BAR_W, color=PRODUCTION_COLOR.get((model, variant), color),
                   hatch=hatch, edgecolor=INK, linewidth=0.8, zorder=3)
            sem = 0.0
            if len(reps) >= 2:
                sd = (sum((v - mean_rep) ** 2 for v in reps) / (len(reps) - 1)) ** 0.5
                sem = sd / (len(reps) ** 0.5)
                ax.errorbar(xi, mean_rep, yerr=sem, fmt="none", ecolor=INK,
                            elinewidth=1.1, capsize=3, capthick=1.1, zorder=4)
            for j, rv in enumerate(reps):
                jitter = (j - (len(reps) - 1) / 2) * (BAR_W * 0.18)
                ax.scatter(xi + jitter, rv, s=20, color=INK, edgecolor="white",
                           linewidth=0.5, zorder=5, alpha=0.85)
            # Clear the highest replicate dot / SEM cap, not just the bar.
            ax.annotate(f"{mean_rep:.1f}%", xy=(xi, max([*reps, mean_rep + sem])),
                        xytext=(0, 5), textcoords="offset points", ha="center",
                        va="bottom", fontsize=13.5, color=INK)
            pct = refusal_pct.get((model, variant), 0.0)
            if pct:
                ax.annotate(f"{pct:.1f}% of calls refused", xy=(xi, mean_rep / 2),
                            ha="center", va="center", rotation=90, fontsize=13,
                            color="white", fontweight="bold", zorder=6)
        centers.append(sum(xs) / len(xs))
        labels.append(m_label)
        x = xs[-1] + BAR_W + GROUP_GAP

    ax.set_xticks(centers)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Overall accuracy on\n147-gene benchmark")
    ax.set_ylim(0, 106)
    ax.set_xlim(-BAR_W / 2 - 0.12, x - GROUP_GAP - BAR_W / 2 + 0.12)
    hatch_handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor="white", edgecolor=INK,
                      hatch=hatch, linewidth=0.8, label=variant_label)
        for _, variant_label, hatch in VARIANT_ORDER
    ]
    # Two legends above the axes: context (hatch) on the left, color on the
    # right, so the bars get the full width.
    hatch_legend = ax.legend(
        handles=hatch_handles, title="Context (hatch)", loc="lower left",
        bbox_to_anchor=(0.0, 1.04), ncol=len(hatch_handles), frameon=False,
        title_fontsize=16, fontsize=14, columnspacing=1.2, handlelength=2.0,
        alignment="left",
    )
    ax.add_artist(hatch_legend)
    ax.legend(
        handles=[Patch(facecolor=c, edgecolor=INK, label=lab) for lab, c in COLOR_LEGEND],
        title="Color (darker = larger model)", loc="lower right",
        bbox_to_anchor=(1.0, 1.04), ncol=len(COLOR_LEGEND), frameon=False,
        title_fontsize=16, fontsize=14, columnspacing=1.2, handlelength=1.6,
        alignment="left",
    )
    sns.despine(ax=ax, top=True, right=True)

    fig.tight_layout()
    save_figure(fig, "db_correctness_overall", OUT_DIR, gist_url=GIST_URL)


if __name__ == "__main__":
    main()
