"""Paywall + bot-block landscape across 150 random cohort genes.

Single-panel horizontal stacked bar showing how the 6,521-gene v2 deep-
dive cohort distributes across the four operationally-relevant body-fetch
outcomes. For each of 150 random genes, we sampled the top-5 most-recent
PubMed papers (n = 750 total) and classified each by:

* **PMC** — paper has a PMC ID → native PMC OA fetches the full body
  reliably (the happy path; the pipeline's first-choice fallback step).
* **Unpaywall** — no PMC, but Unpaywall finds an OA copy via a publisher
  or repository whose host is *not* on the known-bot-blocked list. The
  pipeline's second-choice fallback recovers the body.
* **Bot-blocked** — Unpaywall's only OA path is a publisher that 403s
  our polite User-Agent (Wiley, ASH/*Blood*, sometimes Elsevier per the
  in-repo operational notes). The pipeline falls back to abstract.
* **No OA** — Unpaywall returns ``is_oa=false`` (truly paywalled) OR
  has no record at all. The pipeline falls back to abstract.

The figure is the bottom-up worst-case estimate for the cohort: PMC + Unpaywall
buckets succeed in body-fetch; Bot-blocked + No OA degrade to
abstract-only. Production runs typically do better because the selector
preferentially picks PMC papers when both PMC and non-PMC options
exist — the figure shows what we'd face on a random walk.

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
import seaborn as sns
from matplotlib.patches import Patch

from accessible_surfaceome.audit._plotting_config import (
    CATEGORICAL_PALETTE,
    save_figure,
    setup_plotting_style,
)

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_JSON = ROOT / "data/analysis/paywall_bot_block/cohort_150_4bucket.json"
OUT_DIR = ROOT / "data/analysis/paywall_bot_block"

# Bucket → palette mapping. Teal+amber for the two successful paths;
# maroon dark+light for the two failure paths. The ordering left→right
# tells the story: pipeline tries PMC first, then Unpaywall, then falls
# back when both succeed or both fail.
PMC_COLOR = CATEGORICAL_PALETTE[1]          # teal-mid — happy path
UNPAYWALL_COLOR = CATEGORICAL_PALETTE[2]    # amber — fallback that works
BOTBLOCK_COLOR = CATEGORICAL_PALETTE[0]     # maroon-light — fetch fails, falls back to abstract
NOOA_COLOR = CATEGORICAL_PALETTE[4]         # maroon-dark — truly paywalled, no fetch possible

BUCKET_ORDER = ["pmc", "unpaywall", "bot_blocked", "no_oa"]
BUCKET_LABEL = {
    "pmc": "Full body via PMC",
    "unpaywall": "Full body via Unpaywall",
    "bot_blocked": "Bot-blocked publisher\n(falls back to abstract)",
    "no_oa": "No open access\n(falls back to abstract)",
}
BUCKET_COLOR = {
    "pmc": PMC_COLOR,
    "unpaywall": UNPAYWALL_COLOR,
    "bot_blocked": BOTBLOCK_COLOR,
    "no_oa": NOOA_COLOR,
}

GIST_URL = "https://gist.github.com/beccajcarlson/76242a980c18d98ee3a2fc759a756422"


def main() -> None:
    setup_plotting_style()

    raw = json.loads(SAMPLE_JSON.read_text())
    n_papers = len(raw)
    n_genes = len({r["gene"] for r in raw})
    counts = Counter(r["bucket"] for r in raw)

    fig, ax = plt.subplots(figsize=(12, 5))

    cum = 0
    handles = []
    for key in BUCKET_ORDER:
        n = counts.get(key, 0)
        if n == 0:
            continue
        pct = 100 * n / n_papers
        color = BUCKET_COLOR[key]
        ax.barh(
            [0], [pct], left=cum, color=color,
            edgecolor="white", linewidth=2.0,
        )
        # In-bar label when wide enough
        if pct >= 7:
            ax.text(
                cum + pct / 2, 0,
                f"{pct:.0f}%",
                ha="center", va="center",
                color="white", fontweight="bold", fontsize=14,
            )
        handles.append(
            Patch(
                facecolor=color, edgecolor="white", linewidth=1.5,
                label=f"{BUCKET_LABEL[key]}  ({n}/{n_papers})",
            )
        )
        cum += pct

    # Annotate the operational success-rate cutpoint (PMC + Unpaywall together)
    success = counts.get("pmc", 0) + counts.get("unpaywall", 0)
    success_pct = 100 * success / n_papers
    ax.axvline(success_pct, 0.10, 0.90, color="#1F1718", linewidth=1.2, alpha=0.6)
    ax.text(
        success_pct, 0.7,
        f"  ← {success_pct:.0f}% full-body success rate",
        ha="left", va="center", fontsize=11, color="#1F1718",
        style="italic",
    )

    ax.set_xlim(0, 100)
    ax.set_ylim(-0.7, 0.9)
    ax.set_yticks([])
    ax.set_xlabel(f"% of papers (n = {n_papers} papers from {n_genes} random cohort genes × top-5 most-recent)")
    ax.set_title(
        "Body-fetch outcome buckets for the v2 surfaceome deep-dive cohort\n"
        "(150 random genes from candidate_universe_v2; 4-bucket classification per the operational fetch chain)",
        fontsize=13,
    )
    ax.legend(
        handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.45),
        ncol=4, frameon=False, fontsize=11,
    )
    sns.despine(ax=ax, top=True, right=True, left=True)

    fig.tight_layout()
    save_figure(
        fig, "paywall_bot_block_overview", OUT_DIR,
        formats=("pdf", "png"), gist_url=GIST_URL,
    )
    plt.close(fig)
    print(f"wrote {OUT_DIR}/paywall_bot_block_overview.{{pdf,png}}")


if __name__ == "__main__":
    main()
