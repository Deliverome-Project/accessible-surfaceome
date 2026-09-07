"""Cost vs. accuracy scatter — LLM-only cells on the 147-gene benchmark.

Each point is one (model × prompt_variant) cell; x-axis is the extrapolated
dollar cost for one whole-genome triage pass (19,324 genes, 1 replicate),
y-axis is mean-of-replicate verdict accuracy on the benchmark.  The Claude-
orange colour walk (light → dark = more-context / larger-model) connects
the cells visually without a legend.

DATA SOURCE — reads ``data/processed/figures/benchmark_cost_vs_accuracy.tsv``
(built by ``scripts/build_figure_tsvs.py``), the SAME single source of truth
the gist mirror ``data/analysis/figures/make_benchmark_cost_vs_accuracy.py``
reads from ``raw.githubusercontent.com``.  The model list comes from the data,
never a hardcode — this is the canonical generator for the cost/accuracy
frontier figure, replacing the ``triage_bench_db_barplot.py``
``make_cost_vs_accuracy_plot`` path whose hardcoded model list caused empty
cells when the data moved to Opus 4.8.

Run: ``uv run python scripts/benchmark_cost_vs_accuracy.py``
# Reproduction: https://gist.github.com/beccajcarlson/d7f764d2de288ae31cf44173bc396d41
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import save_figure, setup_plotting_style

REPO = Path(__file__).resolve().parents[1]
DATA_TSV = REPO / "data/processed/figures/benchmark_cost_vs_accuracy.tsv"
OUT_DIR = REPO / "data/analysis/figures"
GIST_URL = "https://gist.github.com/beccajcarlson/d7f764d2de288ae31cf44173bc396d41"

BRAND_INK = "#1F1718"
BRAND_NEUTRAL = "#6F5D5A"
BRAND_GRID = "#E6DAD4"
BRAND_CLAUDE_ORANGE = "#d87851"

# Anthropic published prices ($/M tokens, 2026-05).
_PRICE = {
    "claude-haiku-4-5":  {"in": 1.00, "out": 5.00,  "cr": 0.10, "cw": 1.25},
    "claude-sonnet-4-6": {"in": 3.00, "out": 15.00, "cr": 0.30, "cw": 3.75},
    "claude-sonnet-5":   {"in": 3.00, "out": 15.00, "cr": 0.30, "cw": 3.75},
    "claude-opus-4-8":   {"in": 15.0, "out": 75.0,  "cr": 1.50, "cw": 18.75},
}
WEB_SEARCH_USD_PER_QUERY = 0.01
WHOLE_GENOME_N = 19_324  # protein-coding human genes with a valid HGNC + UniProt mapping

# Per-cell label + Claude-orange sequential walk (light → dark = more-context cells).
CELL_LABEL = {
    ("claude-haiku-4-5",  "naive"):       "Haiku (naive)",
    ("claude-haiku-4-5",  "ncbi"):        "Haiku (+ IDs)",
    ("claude-haiku-4-5",  "pubmed_ncbi"): "Haiku (+ IDs + PubMed)",
    ("claude-haiku-4-5",  "web_ncbi"):    "Haiku (+ IDs + web)",
    ("claude-sonnet-4-6", "naive"):       "Sonnet 4.6 (naive)",
    ("claude-sonnet-4-6", "ncbi"):        "Sonnet 4.6 (+ IDs)",
    ("claude-sonnet-4-6", "pubmed_ncbi"): "Sonnet 4.6 (+ IDs + PubMed)",
    ("claude-sonnet-4-6", "web_ncbi"):    "Sonnet 4.6 (+ IDs + web)",
    ("claude-sonnet-5",   "ncbi"):        "Sonnet 5 (+ IDs)",
    ("claude-opus-4-8",   "naive"):       "Opus (naive)",
    ("claude-opus-4-8",   "ncbi"):        "Opus (+ IDs)",
}
CELL_COLOR = {
    ("claude-haiku-4-5",  "naive"):       "#f7d8c4",
    ("claude-haiku-4-5",  "ncbi"):        "#f1c4ab",
    ("claude-haiku-4-5",  "pubmed_ncbi"): "#eab695",
    ("claude-haiku-4-5",  "web_ncbi"):    "#ec9e7d",
    ("claude-sonnet-4-6", "naive"):       "#e3a07d",
    ("claude-sonnet-4-6", "ncbi"):        BRAND_CLAUDE_ORANGE,
    ("claude-sonnet-4-6", "pubmed_ncbi"): "#cb6f4a",
    ("claude-sonnet-4-6", "web_ncbi"):    "#c46139",
    ("claude-sonnet-5",   "ncbi"):        "#b35238",
    ("claude-opus-4-8",   "naive"):       "#b66547",
    ("claude-opus-4-8",   "ncbi"):        "#a85b3f",
}

# Per-cell label offsets (pixels) to deconflict dense clusters.
# When abs(dy) >= 16 a short leader line is drawn so the label → point
# mapping stays unambiguous.  Re-tune if cells move.
CELL_LABEL_OFFSET = {
    ("claude-haiku-4-5",  "naive"):       (7,   6),
    ("claude-haiku-4-5",  "ncbi"):        (7,  10),
    ("claude-haiku-4-5",  "pubmed_ncbi"): (7, -18),
    ("claude-haiku-4-5",  "web_ncbi"):    (7,   6),
    # Sonnet 4.6 (naive) sits just above Sonnet 5 (+ IDs) at a near-identical
    # cost — send its label LEFT (into the empty gap toward Haiku) so it
    # doesn't collide with the Sonnet 5 point/label below it.
    ("claude-sonnet-4-6", "naive"):       (-128,  2),
    ("claude-sonnet-4-6", "ncbi"):        (7,   12),
    # + IDs + web and + IDs + PubMed nearly overlap (same cost, 0.5pp apart):
    # push PubMed's label HIGH (clear above the +IDs row) with a leader, and
    # keep web's label just up-right on its point — so neither lands on the
    # other's point or on Opus (naive) to their right.
    ("claude-sonnet-4-6", "pubmed_ncbi"): (7,  34),
    ("claude-sonnet-4-6", "web_ncbi"):    (7,   6),
    # Sonnet 5 (+ IDs) sits ~1pp below Sonnet 4.6 (naive) at a very similar
    # cost; push its label well down with a leader line.
    ("claude-sonnet-5",   "ncbi"):        (16, -44),
    ("claude-opus-4-8",   "naive"):       (7, -18),
    ("claude-opus-4-8",   "ncbi"):        (7,  10),
}


def _whole_genome_cost(group: pd.DataFrame) -> float:
    """Per-cell cost extrapolated to one pass over the 19,324-gene catalog.

    Per-rep TSV: each row IS one replicate (gene × model × variant × rep),
    so token columns already carry per-replicate counts.  Cost is per single
    triage pass — average the per-rep counts across the cell's
    (gene, replicate) rows.  ``n`` here is gene-count (rows ÷ reps per gene
    ≈ unique genes), used only in the system-prompt amortisation.
    """
    model = group["model"].iloc[0]
    pricing = _PRICE[model]
    n = group["gene_symbol"].nunique()
    pt = group["prompt_tokens"].mean()
    cr = group["cache_read_tokens"].mean()
    cw = group["cache_creation_tokens"].mean()
    ot = group["completion_tokens"].mean()
    ws = group["n_web_searches"].mean()

    if cr > 0 or cw > 0:
        sys_size = max(cr, cw)
        user_size = pt
    else:
        sys_size = min(2000.0, pt)
        user_size = max(0.0, pt - sys_size)

    sys_per_cell = (
        sys_size * pricing["cw"] + (n - 1) * sys_size * pricing["cr"]
    ) / n / 1_000_000
    user_per_cell = user_size * pricing["in"] / 1_000_000
    out_per_cell  = ot        * pricing["out"] / 1_000_000
    web_per_cell  = ws        * WEB_SEARCH_USD_PER_QUERY
    return (sys_per_cell + user_per_cell + out_per_cell + web_per_cell) * WHOLE_GENOME_N


def main() -> None:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    # Match the gist mirror's layout fingerprint (tests/test_figure_canonical_mirror_sync).
    plt.rcParams.update({
        "savefig.dpi": 600,
        "savefig.bbox": "tight",
        "figure.facecolor": "none",
        "savefig.facecolor": "none",
        "font.size": 14,
        "axes.labelsize": 14,
        "axes.labelweight": "medium",
        "axes.titlesize": 0,
        "axes.titlepad": 0,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": BRAND_GRID,
        "axes.labelcolor": BRAND_INK,
        "xtick.labelsize": 13,
        "ytick.labelsize": 13,
        "xtick.color": BRAND_INK,
        "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "legend.fontsize": 13,
    })

    reps_df = pd.read_csv(DATA_TSV, sep="\t")
    reps_df["is_match"] = reps_df["is_match"].astype(int)

    # Mean-of-replicate accuracy per (model, variant) — matches the 3 bar
    # figures.  Equivalent to mean-of-cells-of-mean-of-reps.
    rep_mean_acc = (
        reps_df.groupby(["model", "prompt_variant", "replicate"])["is_match"]
        .mean().reset_index()
        .groupby(["model", "prompt_variant"])["is_match"].mean().to_dict()
    )

    cells = []
    for (model, variant), grp in reps_df.groupby(["model", "prompt_variant"], sort=False):
        if (model, variant) not in CELL_LABEL:
            continue
        cells.append({
            "model": model,
            "variant": variant,
            "label": CELL_LABEL[(model, variant)],
            "color": CELL_COLOR[(model, variant)],
            "accuracy": rep_mean_acc.get((model, variant), grp["is_match"].mean()),
            "cost_whole_genome_usd": _whole_genome_cost(grp),
        })
    df = pd.DataFrame(cells).sort_values("cost_whole_genome_usd").reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(9.5, 6))
    for _, row in df.iterrows():
        x = row["cost_whole_genome_usd"]
        y = row["accuracy"] * 100
        ax.scatter(
            x, y,
            s=180, c=row["color"], edgecolor=BRAND_INK, linewidth=0.8, zorder=3,
        )
        dx, dy = CELL_LABEL_OFFSET.get((row["model"], row["variant"]), (8, -3))
        arrowprops = (
            dict(arrowstyle="-", color=BRAND_NEUTRAL,
                 linewidth=0.6, alpha=0.7, shrinkA=0, shrinkB=4)
            if abs(dy) >= 16 else None
        )
        ax.annotate(
            row["label"], (x, y),
            xytext=(dx, dy), textcoords="offset points",
            fontsize=14, color=BRAND_INK,
            arrowprops=arrowprops,
        )
    ax.set_xscale("log")
    ax.set_xlabel("$ / whole-genome triage pass (19,324 genes, 1 replicate)")
    ax.set_ylabel("Verdict accuracy on\n147-gene bench (%)")
    ymin = min(c["accuracy"] for c in cells) * 100
    ax.set_ylim(max(78, ymin - 2), 100)
    sns.despine(ax=ax, top=True, right=True)

    save_figure(fig, "benchmark_cost_vs_accuracy", OUT_DIR, gist_url=GIST_URL)


if __name__ == "__main__":
    main()
