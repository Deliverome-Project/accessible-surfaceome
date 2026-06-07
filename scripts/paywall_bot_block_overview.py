"""Paywall + bot-block landscape for the v2 deep-dive cohort.

Two-panel figure:

* **Top**: de-facto body-fetch outcomes from the 5 anchor deep-dive runs
  (TACSTD2 / HMGB1 / SRC / GPR75 / TGOLN2). Stacked bar shows what fraction
  of each gene's contributing-paper set arrived as PMC full text vs.
  PMID-only abstract. This is the OPERATIONAL truth — what the pipeline
  actually retrieved through its full fallback chain (PMC native →
  PMID→PMCID eLink → Unpaywall PDF), with the gap explained downstream as
  bot-blocked / paywalled / parse-failed.

* **Bottom**: forward-looking OA mix for 28 random cohort genes × top-5
  most-recent PubMed papers each (140 papers checked via Unpaywall). Shows
  the distribution of OA states *before* the fetch chain runs — informs
  what the bottom-up expected paywall rate looks like across the cohort.

The gap between the two panels — the anchor genes' PMC% is consistently
HIGHER than the Unpaywall sample's "OA via PMC" rate — comes from the
fact that the deep-dive's selector preferentially picks PMC-OA papers
when both PMC and non-PMC options are available (PMC body is cheaper to
parse and richer than PDF). The bottom panel is the worst case; the top
panel is what actually happens.

# Reproduction:
#   Public gist (reader-side standalone, PEP 723 deps):
#   https://gist.github.com/beccajcarlson/76242a980c18d98ee3a2fc759a756422
#   Reader-side mirror script:
#   data/analysis/paywall_bot_block/make_paywall_bot_block_overview.py.

Run:
    uv run python scripts/paywall_bot_block_overview.py
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import (
    CATEGORICAL_PALETTE,
    save_figure,
    setup_plotting_style,
)

ROOT = Path(__file__).resolve().parents[1]
ANCHOR_JSON = ROOT / "data/analysis/paywall_bot_block/anchor_genes_body_fetch_rates.json"
SAMPLE_JSON = ROOT / "data/analysis/paywall_bot_block/oa_status_sample_28genes.json"
OUT_DIR = ROOT / "data/analysis/paywall_bot_block"

# Anchor colors from the brand palette
PMC_COLOR = CATEGORICAL_PALETTE[1]      # teal — "happy path, full body retrieved"
PMID_COLOR = CATEGORICAL_PALETTE[0]     # maroon — "fell back to abstract"
PUBLISHER_OA = CATEGORICAL_PALETTE[3]   # lavender — Unpaywall OA via publisher
REPO_OA = CATEGORICAL_PALETTE[2]        # amber — OA via repository
UNKNOWN = "#9CA3AF"                      # neutral grey — Unpaywall has no record


# Gist mirror gets a public URL after `gh gist create`; embedded in saved
# artifacts via save_figure(gist_url=...).
GIST_URL = "https://gist.github.com/beccajcarlson/76242a980c18d98ee3a2fc759a756422"


def _load_anchors() -> pd.DataFrame:
    rows = json.loads(ANCHOR_JSON.read_text())
    df = pd.DataFrame(rows)
    # Order anchors by descending PMC rate so the visual ramp is clear
    return df.sort_values("pct_pmc", ascending=False).reset_index(drop=True)


def _summarize_sample() -> pd.DataFrame:
    """Collapse the 140-paper sample into a per-OA-status count + share."""
    raw = json.loads(SAMPLE_JSON.read_text())
    counts = Counter(r["oa_status"] for r in raw)
    total = sum(counts.values())
    label_order = ["oa_pmc", "oa_repo", "oa_publisher", "oa_unknown", "unknown", "closed"]
    label_pretty = {
        "oa_pmc": "OA via PMC\n(works reliably)",
        "oa_repo": "OA via repository\n(Unpaywall recovers)",
        "oa_publisher": "OA via publisher\n(some bot-blocked)",
        "oa_unknown": "OA via other",
        "unknown": "Unknown\n(no Unpaywall record)",
        "closed": "Closed access\n(paywalled)",
    }
    label_color = {
        "oa_pmc": PMC_COLOR,
        "oa_repo": REPO_OA,
        "oa_publisher": PUBLISHER_OA,
        "oa_unknown": UNKNOWN,
        "unknown": UNKNOWN,
        "closed": PMID_COLOR,
    }
    rows = []
    for key in label_order:
        n = counts.get(key, 0)
        if n == 0:
            continue
        rows.append(
            {
                "status_key": key,
                "label": label_pretty[key],
                "color": label_color[key],
                "n": n,
                "pct": 100 * n / total,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    setup_plotting_style()

    anchors = _load_anchors()
    sample = _summarize_sample()

    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(11, 9), gridspec_kw={"height_ratios": [1, 1.05]}
    )

    # ---- Top panel: per-anchor stacked bar -----------------------------
    x = list(range(len(anchors)))
    pmc_vals = anchors["pct_pmc"].tolist()
    pmid_vals = anchors["pct_pmid_only"].tolist()
    ax_top.bar(
        x, pmc_vals, color=PMC_COLOR, label="Full body via PMC",
        edgecolor="white", linewidth=1.0,
    )
    ax_top.bar(
        x, pmid_vals, bottom=pmc_vals, color=PMID_COLOR,
        label="Abstract-only fallback", edgecolor="white", linewidth=1.0,
    )
    # Annotate each bar with the absolute paper count
    for i, row in anchors.iterrows():
        ax_top.text(
            i, 102,
            f"n={row['n_unique_papers']}",
            ha="center", va="bottom", fontsize=10, color="#374151",
        )
    ax_top.set_xticks(x)
    ax_top.set_xticklabels(anchors["gene"].tolist())
    ax_top.set_ylabel("% of contributing papers")
    ax_top.set_ylim(0, 112)
    ax_top.set_yticks([0, 25, 50, 75, 100])
    ax_top.set_title(
        "Operational: body-fetch outcomes in 5 deep-dive runs\n"
        "(after full fallback chain: PMC native → eLink → Unpaywall PDF)",
        fontsize=13,
    )
    ax_top.legend(loc="lower right", framealpha=0.95, fontsize=10)
    sns.despine(ax=ax_top, top=True, right=True)

    # ---- Bottom panel: cohort-wide Unpaywall mix -----------------------
    # Horizontal stacked bar so the legend labels stay readable.
    cum = 0
    handles = []
    for _, row in sample.iterrows():
        ax_bot.barh(
            [0], [row["pct"]], left=cum,
            color=row["color"], edgecolor="white", linewidth=1.5,
        )
        # In-bar label when wide enough
        if row["pct"] >= 8:
            ax_bot.text(
                cum + row["pct"] / 2, 0,
                f"{row['pct']:.0f}%",
                ha="center", va="center",
                color="white", fontweight="bold", fontsize=11,
            )
        from matplotlib.patches import Patch
        handles.append(
            Patch(facecolor=row["color"], edgecolor="white", linewidth=1.5,
                  label=f"{row['label']}  ({row['n']}/{sample['n'].sum()})")
        )
        cum += row["pct"]
    ax_bot.set_xlim(0, 100)
    ax_bot.set_ylim(-0.7, 0.7)
    ax_bot.set_yticks([])
    ax_bot.set_xlabel("% of papers (n = 140 random papers from 28 cohort genes × top-5 most-recent)")
    ax_bot.set_title(
        "Cohort-wide OA mix for the 6,521-gene candidate-universe sample (Unpaywall lookup)",
        fontsize=13,
    )
    ax_bot.legend(
        handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.55),
        ncol=3, frameon=False, fontsize=10,
    )
    sns.despine(ax=ax_bot, top=True, right=True, left=True)

    fig.suptitle(
        "Paywall & bot-block landscape for the v2 surfaceome deep-dive cohort",
        fontsize=15, y=1.0,
    )
    fig.tight_layout()

    save_figure(
        fig, "paywall_bot_block_overview", OUT_DIR,
        formats=("pdf", "png"), gist_url=GIST_URL,
    )
    plt.close(fig)
    print(f"wrote {OUT_DIR}/paywall_bot_block_overview.{{pdf,png}}")


if __name__ == "__main__":
    main()
