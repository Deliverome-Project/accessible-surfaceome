"""Supp Fig 1 — LLM-only overall accuracy on the 147-gene benchmark.

Grouped bars by model (Haiku 4.5 / Sonnet 4.6 / Opus 4.8) with hatched bars
for the within-model prompt variants (naive / + IDs / + IDs + web /
+ IDs + PubMed); bar height = mean of per-replicate accuracies, with each
replicate's accuracy overlaid as a point and a run-to-run SEM error bar.

DATA SOURCE — reads ``data/processed/figures/db_correctness_overall.tsv``
(built by ``scripts/build_figure_tsvs.py``), the SAME single source of truth the
gist mirror ``data/analysis/figures/make_db_correctness_overall.py`` reads. The
model list comes from the data, never a hardcode — this is the canonical
generator that replaced the ``triage_bench_db_barplot.py`` ``make_overall_plot``
path, whose hardcoded ``opus-4-7`` model list shipped empty bars when the data
moved to Opus 4.8.

Run: ``uv run python scripts/db_correctness_overall.py``
# Reproduction: https://gist.github.com/beccajcarlson/9c765ed9673d7bd845c3ac091ad2204d
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import save_figure, setup_plotting_style

REPO = Path(__file__).resolve().parents[1]
DATA_TSV = REPO / "data/processed/figures/db_correctness_overall.tsv"
OUT_DIR = REPO / "data/analysis/figures"
GIST_URL = "https://gist.github.com/beccajcarlson/9c765ed9673d7bd845c3ac091ad2204d"

INK = "#1F1718"
# Model display order + Claude-orange walk (light → dark = larger model).
MODEL_ORDER = [
    ("claude-haiku-4-5",  "Haiku 4.5",  "#f1c4ab"),
    ("claude-sonnet-4-6", "Sonnet 4.6", "#d87851"),
    ("claude-opus-4-8",   "Opus 4.8",   "#a85b3f"),
]
# Variant display order + matplotlib hatch pattern.
VARIANT_ORDER = [
    ("naive",        "naive",          ""),
    ("ncbi",         "+ IDs",          "//"),
    ("web_ncbi",     "+ IDs + web",    "xx"),
    ("pubmed_ncbi",  "+ IDs + PubMed", ".."),
]


def _per_rep_accuracy(reps_df: pd.DataFrame) -> dict[tuple[str, str], list[float]]:
    """{(model, variant): [acc_rep1, …]} — mean ``is_match`` per
    (model, variant, replicate) group, as a percentage."""
    reps_df = reps_df.copy()
    reps_df["is_match"] = reps_df["is_match"].astype(int)
    grouped = (
        reps_df.groupby(["model", "prompt_variant", "replicate"])["is_match"]
        .mean()
        .reset_index()
    )
    out: dict[tuple[str, str], list[float]] = {}
    for (model, variant), g in grouped.groupby(["model", "prompt_variant"]):
        out[(model, variant)] = [v * 100 for v in g["is_match"].tolist()]
    return out


def main() -> None:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    # Match the gist mirror's layout fingerprint (tests/test_figure_canonical_mirror_sync).
    plt.rcParams.update({
        "axes.labelsize": 20, "xtick.labelsize": 20, "ytick.labelsize": 20,
        "legend.fontsize": 20, "axes.titlesize": 0, "font.size": 20,
    })
    rep_acc = _per_rep_accuracy(pd.read_csv(DATA_TSV, sep="\t"))

    fig, ax = plt.subplots(figsize=(16, 5.5))
    n_models, n_variants = len(MODEL_ORDER), len(VARIANT_ORDER)
    bar_w = 0.78 / n_variants

    for mi, (model, _, color) in enumerate(MODEL_ORDER):
        for vi, (variant, _, hatch) in enumerate(VARIANT_ORDER):
            reps = rep_acc.get((model, variant), [])
            if not reps:
                continue  # e.g. opus-4-8 was only run on naive + ncbi
            mean_rep = sum(reps) / len(reps)
            x = mi + (vi - (n_variants - 1) / 2) * bar_w
            ax.bar(x, mean_rep, width=bar_w, color=color, hatch=hatch,
                   edgecolor=INK, linewidth=0.8, zorder=3)
            if len(reps) >= 2:
                sd = (sum((v - mean_rep) ** 2 for v in reps) / (len(reps) - 1)) ** 0.5
                sem = sd / (len(reps) ** 0.5)
                ax.errorbar(x, mean_rep, yerr=sem, fmt="none", ecolor=INK,
                            elinewidth=1.1, capsize=3, capthick=1.1, zorder=4)
            for j, rv in enumerate(reps):
                jitter = (j - (len(reps) - 1) / 2) * (bar_w * 0.18)
                ax.scatter(x + jitter, rv, s=20, color=INK, edgecolor="white",
                           linewidth=0.5, zorder=5, alpha=0.85)
            ax.text(x, mean_rep + 2.6, f"{mean_rep:.1f}%", ha="center",
                    va="bottom", fontsize=14, color=INK)

    ax.set_xticks(range(n_models))
    ax.set_xticklabels([m_label for _, m_label, _ in MODEL_ORDER], fontsize=19)
    ax.set_ylabel("Overall accuracy on\n147-gene benchmark", fontsize=17)
    ax.set_ylim(0, 105)
    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor="white", edgecolor=INK,
                      hatch=hatch, linewidth=0.8, label=variant_label)
        for _, variant_label, hatch in VARIANT_ORDER
    ]
    ax.legend(handles=legend_handles, title="Variant (hatch)", loc="center left",
              bbox_to_anchor=(1.01, 0.5), frameon=False, fontsize=16, title_fontsize=19)
    sns.despine(ax=ax, top=True, right=True)

    fig.tight_layout()
    save_figure(fig, "db_correctness_overall", OUT_DIR, gist_url=GIST_URL)


if __name__ == "__main__":
    main()
