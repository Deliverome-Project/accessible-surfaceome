# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "seaborn>=0.13",
#   "httpx>=0.27",
# ]
# ///
"""Reproduce ``paywall_bot_block_overview.{pdf,png}`` from the public repo.

Single-panel horizontal stacked bar showing how 150 random genes from the
6,521-gene v2 deep-dive cohort (candidate_universe_v2.tsv) distribute
across four operationally-relevant body-fetch outcomes. For each gene,
the top-5 most-recent PubMed papers were classified (n = 680 total) by
which path through the production fetch chain would succeed:

* **PMC** — paper has a PMC ID → native PMC OA fetches the full body
  (the happy path; the pipeline's first-choice fallback).
* **Unpaywall** — no PMC, but Unpaywall finds an OA copy via a publisher
  or repository whose host is *not* on the bot-block list. The pipeline's
  second-choice fallback recovers the body.
* **Bot-blocked** — Unpaywall's only OA path is a publisher that 403s
  our polite User-Agent (Wiley, ASH/Blood, Elsevier in some flows).
  The pipeline falls back to abstract.
* **No OA** — Unpaywall returns ``is_oa=false`` (truly paywalled) OR has
  no record. The pipeline falls back to abstract.

Operational success rate (PMC + Unpaywall together) is ~76% of papers,
~24% fall back to abstract-only.

Standalone — ``uv run make_paywall_bot_block_overview.py``.
"""
from __future__ import annotations

import io
import json
from collections import Counter
from pathlib import Path

import httpx
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.patches import Patch

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"

SAMPLE_JSON = f"{BASE}/data/analysis/paywall_bot_block/cohort_150_4bucket.json"

# Published reproduction gist (embedded into output PNG Source / PDF
# Subject metadata — mirrors save_figure(gist_url=...) in
# src/accessible_surfaceome/audit/_plotting_config.py).
GIST_URL = "https://gist.github.com/beccajcarlson/76242a980c18d98ee3a2fc759a756422"

# ──── Inline brand styling — sentinel: brand-style-v2 ────
# Mirrors src/accessible_surfaceome/audit/_plotting_config.py so the gist
# stays self-contained. Kept in sync via tests/test_figure_gists_styling.py.
BRAND_PALETTE = [
    "#BC3C4C",  # maroon-light — fetch fails / bot-blocked
    "#3D6B60",  # teal-mid     — happy path (PMC)
    "#F4AA28",  # amber-bright — fallback that works (Unpaywall)
    "#8878C8",  # lavender-bright
    "#6E1428",  # maroon-dark  — no OA at all
    "#7AAB9F",  # teal-light
]
BRAND_INK = "#1F1718"
BRAND_NEUTRAL = "#6F5D5A"
BRAND_GRID = "#E6DAD4"


def _register_brand_fonts() -> None:
    candidates = [
        Path(__file__).resolve().parents[3] / "assets" / "fonts",
        Path.cwd() / "assets" / "fonts",
    ]
    for fonts_dir in candidates:
        if fonts_dir.is_dir():
            for otf in sorted(fonts_dir.glob("*.otf")):
                try:
                    fm.fontManager.addfont(str(otf))
                except Exception:  # noqa: BLE001
                    continue
            for ttf in sorted(fonts_dir.glob("*.ttf")):
                try:
                    fm.fontManager.addfont(str(ttf))
                except Exception:  # noqa: BLE001
                    continue
            return


def _apply_brand_style() -> None:
    """Inline equivalent of `setup_plotting_style`. Sentinel: brand-style-v2."""
    _register_brand_fonts()
    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=1.0)
    plt.rcParams.update(
        {
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "figure.facecolor": "none",
            "savefig.facecolor": "none",
            "font.family": "sans-serif",
            "font.sans-serif": [
                "Manrope", "Outfit", "DejaVu Sans", "Liberation Sans", "Arial",
            ],
            "font.weight": "medium",
            "font.size": 14,
            "axes.labelsize": 16,
            "axes.titlesize": 14,
            "axes.titlepad": 12,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.axisbelow": True,
            "axes.edgecolor": BRAND_GRID,
            "axes.labelcolor": BRAND_INK,
            "axes.facecolor": "none",
            "text.color": BRAND_INK,
            "grid.alpha": 0.35,
            "grid.linestyle": "-",
            "grid.linewidth": 0.7,
            "grid.color": BRAND_GRID,
            "xtick.labelsize": 14,
            "ytick.labelsize": 14,
            "xtick.color": BRAND_INK,
            "ytick.color": BRAND_INK,
            "legend.frameon": False,
            "legend.fontsize": 12,
            "patch.edgecolor": "none",
            "patch.linewidth": 0.0,
        }
    )


PMC_COLOR = BRAND_PALETTE[1]        # teal-mid
UNPAYWALL_COLOR = BRAND_PALETTE[2]  # amber
BOTBLOCK_COLOR = BRAND_PALETTE[0]   # maroon-light
NOOA_COLOR = BRAND_PALETTE[4]       # maroon-dark

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


def _fetch_json(url: str):
    local = Path(__file__).resolve().parents[3] / url[len(BASE) + 1 :]
    if local.is_file():
        return json.loads(local.read_text())
    r = httpx.get(url, timeout=30)
    r.raise_for_status()
    return json.loads(r.text)


def main() -> None:
    _apply_brand_style()

    raw = _fetch_json(SAMPLE_JSON)
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
        if pct >= 7:
            ax.text(
                cum + pct / 2, 0, f"{pct:.0f}%",
                ha="center", va="center",
                color="white", fontweight="bold", fontsize=12,
            )
        handles.append(
            Patch(
                facecolor=color, edgecolor="white", linewidth=1.5,
                label=f"{BUCKET_LABEL[key]}  ({n}/{n_papers})",
            )
        )
        cum += pct

    # Annotate the operational success-rate cutpoint (PMC + Unpaywall).
    success = counts.get("pmc", 0) + counts.get("unpaywall", 0)
    success_pct = 100 * success / n_papers
    ax.axvline(success_pct, 0.10, 0.90, color=BRAND_INK, linewidth=1.2, alpha=0.6)
    ax.text(
        success_pct, 0.7,
        f"  ← {success_pct:.0f}% full-body success rate",
        ha="left", va="center", fontsize=9, color=BRAND_INK,
        style="italic",
    )

    ax.set_xlim(0, 100)
    ax.set_ylim(-0.7, 0.9)
    ax.set_yticks([])
    ax.set_xlabel(
        f"% of papers (n = {n_papers} papers from {n_genes} random cohort genes × top-5 most-recent)"
    )
    ax.set_title(
        "Body-fetch outcome buckets for the v2 surfaceome deep-dive cohort\n"
        "(150 random genes from candidate_universe_v2; 4-bucket classification per the operational fetch chain)",
        fontsize=11,
    )
    ax.legend(
        handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.45),
        ncol=4, frameon=False, fontsize=9,
    )
    sns.despine(ax=ax, top=True, right=True, left=True)

    fig.tight_layout()
    out_dir = Path.cwd()
    out_pdf = out_dir / "paywall_bot_block_overview.pdf"
    out_png = out_dir / "paywall_bot_block_overview.png"
    fig.savefig(out_pdf, format="pdf", dpi=300, bbox_inches="tight",
                metadata={"Subject": GIST_URL})
    fig.savefig(out_png, format="png", dpi=300, bbox_inches="tight",
                metadata={"Source": GIST_URL})
    plt.close(fig)
    print(f"wrote {out_pdf}")
    print(f"wrote {out_png}")


if __name__ == "__main__":
    main()
