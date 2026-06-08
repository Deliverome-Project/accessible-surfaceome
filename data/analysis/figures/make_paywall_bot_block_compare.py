# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "seaborn>=0.13",
#   "httpx>=0.27",
# ]
# ///
"""Reproduce paywall_bot_block_compare.{pdf,png} from the public repo.

Two-bar comparison of body-fetch reachability under two literature-recall
strategies applied to the same 100 random genes × 10 random papers each:

* **Production**: the v2 deep-dive's full 21-axis A1 kickoff
  (EuropePMC search + PubTator NER + NCBI gene2pubmed + topic_search +
  6 standing axes — byte-identical to ``build_a1_kickoff()`` in
  ``src/accessible_surfaceome/agents/plan_trim_select/kickoff_templates.py``).
* **OpenAlex**: a broader retrieval surface — 10 axes via OpenAlex's
  REST API (one broad gene-name search + 9 method-keyword
  conjunctions). Catches preprints (bioRxiv/medRxiv) + non-PubMed
  journals + grey literature that EuropePMC doesn't index.

Each paper is classified into one of four reachability buckets by
running the **production fetch chain** (``_fetch_body_drafts`` →
PMC JATS → Unpaywall PDF → fallback abstract). When the prod fetch
fails, the secondary Unpaywall lookup distinguishes bot-blocked
(only OA path is a 403'ing host like Wiley/bioRxiv/Elsevier/MDPI/
ASH/OUP/Cell) from no-OA (Unpaywall says is_oa=false or no record).

Headline result: production's 21-axis search has high precision
(~88% reachable) on a tighter corpus; OpenAlex finds 2.4× more papers
per gene but only 43% are reachable — the additional pool is mostly
paywalled non-PMC literature and bot-blocked preprint servers.

Standalone — ``uv run make_paywall_bot_block_compare.py``.
"""
from __future__ import annotations

import csv
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

TSV_URL = f"{BASE}/data/processed/paywall_bot_block/paywall_bot_block_compare.tsv"

# Published reproduction gist (embedded into output PNG Source / PDF Subject)
GIST_URL = "https://gist.github.com/beccajcarlson/cbc950dad1c3a6595fd5018cdb6b030d"

# ──── Inline brand styling — sentinel: brand-style-v2 ────
BRAND_PALETTE = [
    "#BC3C4C", "#3D6B60", "#F4AA28", "#8878C8",
    "#6E1428", "#7AAB9F",
]
BRAND_INK = "#1F1718"
BRAND_GRID = "#E6DAD4"


def _register_brand_fonts() -> None:
    candidates = [
        Path(__file__).resolve().parents[3] / "assets" / "fonts",
        Path.cwd() / "assets" / "fonts",
    ]
    for fonts_dir in candidates:
        if fonts_dir.is_dir():
            for f in list(fonts_dir.glob("*.otf")) + list(fonts_dir.glob("*.ttf")):
                try:
                    fm.fontManager.addfont(str(f))
                except Exception:  # noqa: BLE001
                    continue
            return


def _apply_brand_style() -> None:
    _register_brand_fonts()
    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=1.0)
    plt.rcParams.update({
        "savefig.dpi": 300, "savefig.bbox": "tight",
        "figure.facecolor": "none", "savefig.facecolor": "none",
        "font.family": "sans-serif",
        "font.sans-serif": ["Manrope", "Outfit", "DejaVu Sans", "Liberation Sans", "Arial"],
        # Match _plotting_config: no light defaults. Manrope at weight 400
        # reads as light against the variable range (300-800); default to
        # 500 so figures don't render with thin defaults.
        "font.weight": "medium",
        "font.size": 14, "axes.labelsize": 16, "axes.titlesize": 0, "axes.titlepad": 0,
        "axes.labelweight": "medium", "axes.titleweight": "semibold",
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "axes.axisbelow": True,
        "axes.edgecolor": BRAND_GRID, "axes.labelcolor": BRAND_INK,
        "axes.facecolor": "none", "text.color": BRAND_INK,
        "grid.alpha": 0.35, "grid.linestyle": "-", "grid.linewidth": 0.7, "grid.color": BRAND_GRID,
        "xtick.labelsize": 16, "ytick.labelsize": 12,
        "xtick.color": BRAND_INK, "ytick.color": BRAND_INK,
        "legend.frameon": False, "legend.fontsize": 12,
        "patch.edgecolor": "none", "patch.linewidth": 0.0,
    })


BUCKET_ORDER = ["pmc", "unpaywall", "bot_blocked", "no_oa"]
BUCKET_LABEL = {
    "pmc": "Full body via PMC",
    "unpaywall": "Full body via Unpaywall",
    "bot_blocked": "Bot-blocked publisher",
    "no_oa": "No open access",
}
BUCKET_COLOR = {
    "pmc": BRAND_PALETTE[1],
    "unpaywall": BRAND_PALETTE[2],
    "bot_blocked": BRAND_PALETTE[0],
    "no_oa": BRAND_PALETTE[4],
}

SOURCE_LABEL = {
    "production": "Production strategy\n(EuropePMC + PubTator\n+ gene2pubmed,\n21 axes/gene)",
    "openalex":   "OpenAlex strategy\n(broad gene + method-\nkeyword search,\n21 axes/gene)",
}


def fetch_tsv() -> list[dict]:
    """Read the TSV — from the public repo over HTTP, or from a local checkout."""
    local = (
        Path(__file__).resolve().parents[3]
        / "data/processed/paywall_bot_block/paywall_bot_block_compare.tsv"
    )
    if local.is_file():
        text = local.read_text()
    else:
        r = httpx.get(TSV_URL, timeout=30)
        r.raise_for_status()
        text = r.text
    return list(csv.DictReader(io.StringIO(text), delimiter="\t"))


def main() -> None:
    _apply_brand_style()
    rows = fetch_tsv()
    print(f"loaded {len(rows)} rows")

    by_source: dict[str, list[dict]] = {"production": [], "openalex": []}
    for r in rows:
        by_source.setdefault(r["source"], []).append(r)

    # Narrower aspect: labels wrap aggressively so the figure stays compact.
    fig, ax = plt.subplots(figsize=(10, 6))
    bar_h = 0.55
    # openalex at y=0 (bottom), production at y=1 (top) — matplotlib's
    # default y-axis orientation puts smaller indices below.
    sources = ["openalex", "production"]
    y_positions = list(range(len(sources)))

    for ypos, src in zip(y_positions, sources):
        papers = by_source.get(src, [])
        c = Counter(p["bucket"] for p in papers)
        total = sum(c.values()) or 1
        genes = {p["gene"] for p in papers}
        cum = 0.0
        for bucket in BUCKET_ORDER:
            n = c.get(bucket, 0)
            if n == 0:
                continue
            pct = 100 * n / total
            ax.barh([ypos], [pct], left=cum, height=bar_h,
                    color=BUCKET_COLOR[bucket],
                    edgecolor="white", linewidth=2.0)
            if pct >= 6:
                ax.text(cum + pct / 2, ypos, f"{pct:.0f}%",
                        ha="center", va="center",
                        color="white", fontweight="bold", fontsize=16)
            cum += pct
        ax.text(
            104, ypos,
            f"{total} papers /\n{len(genes)} genes",
            ha="left", va="center", fontsize=11, fontweight="medium",
            color=BRAND_INK,
        )

    ax.set_xlim(0, 100)
    ax.set_ylim(-0.7, len(sources) - 0.3)
    ax.set_yticks(y_positions)
    ax.set_yticklabels([SOURCE_LABEL[s] for s in sources], fontweight="medium")
    ax.set_xlabel("% of sampled papers")
    # No baked-in title — figure gets captioned in the gist README.
    handles = [
        Patch(facecolor=BUCKET_COLOR[b], edgecolor="white", linewidth=1.5, label=BUCKET_LABEL[b])
        for b in BUCKET_ORDER
    ]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.45, -0.18),
              ncol=4, frameon=False)
    sns.despine(ax=ax, top=True, right=True, left=True, bottom=False)
    fig.tight_layout()
    out_pdf = Path.cwd() / "paywall_bot_block_compare.pdf"
    out_png = Path.cwd() / "paywall_bot_block_compare.png"
    fig.savefig(out_pdf, format="pdf", dpi=300, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, format="png", dpi=300, bbox_inches="tight", metadata={"Source": GIST_URL})
    plt.close(fig)
    print(f"wrote {out_pdf}, {out_png}")


if __name__ == "__main__":
    main()
