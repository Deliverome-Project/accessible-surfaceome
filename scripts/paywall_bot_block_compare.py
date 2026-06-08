"""Render the production-vs-OpenAlex paywall+bot-block comparison.

**Data sources** (asymmetric — OpenAlex's daily free API budget was
exhausted before we could finish a 21-axis rerun, so it stays at the
10-axis sample from the earlier run):

* **production** — live JSONL from
  ``probe_results/cohort100x10_production.jsonl`` (~21-axis, mirrors
  ``build_a1_kickoff()``). Re-render at any time to pick up additional
  genes as the probe progresses.
* **openalex** — TSV snapshot at
  ``probe_results/cohort100x10_openalex_10axis.tsv`` (10-axis run from
  pre-rate-limit). Frozen at 86 genes / 849 papers.

Emits a side-by-side stacked-bar PDF/PNG showing the 4-bucket
distribution under each retrieval strategy, plus a refreshed
``paywall_bot_block_compare.tsv`` (union of the live production rows
and the salvaged openalex snapshot).

# Reproduction:
#   Public gist (reader-side standalone, PEP 723 deps):
#   https://gist.github.com/beccajcarlson/cbc950dad1c3a6595fd5018cdb6b030d
#   Reader-side mirror script:
#   data/analysis/paywall_bot_block/make_paywall_bot_block_compare.py.

Run:
    uv run python scripts/paywall_bot_block_compare.py
"""
from __future__ import annotations

import csv
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
PROBE_DIR = ROOT / "data/analysis/paywall_bot_block/probe_results"
# Figure assets live in the canonical figures folder (next to the rest
# of the published figures). Per-paper probe inputs stay in the
# paywall_bot_block/probe_results subfolder.
OUT_DIR = ROOT / "data/analysis/figures"

PROD_JSONL = PROBE_DIR / "cohort100x10_production.jsonl"
# Live OpenAlex JSONL (preferred — has correct n_avail per gene). Falls back
# to the salvaged 10-axis TSV snapshot only if the JSONL is missing/empty,
# so a fresh worktree without local probe data can still re-render.
OAX_JSONL = PROBE_DIR / "cohort100x10_openalex.jsonl"
OAX_TSV_SNAPSHOT = PROBE_DIR / "cohort100x10_openalex_10axis.tsv"

GIST_URL = "https://gist.github.com/beccajcarlson/cbc950dad1c3a6595fd5018cdb6b030d"

BUCKET_ORDER = ["pmc", "unpaywall", "bot_blocked", "no_oa"]
BUCKET_LABEL = {
    "pmc": "Full body via PMC",
    "unpaywall": "Full body via Unpaywall",
    "bot_blocked": "Bot-blocked publisher",
    "no_oa": "No open access",
}
BUCKET_COLOR = {
    "pmc": CATEGORICAL_PALETTE[1],          # teal
    "unpaywall": CATEGORICAL_PALETTE[2],    # amber
    "bot_blocked": CATEGORICAL_PALETTE[0],  # maroon-light
    "no_oa": CATEGORICAL_PALETTE[4],        # maroon-dark
}

# Production = 21 axes (mirrors build_a1_kickoff exactly). OpenAlex =
# 10 axes (was the original sample before the rate limit blocked a
# 21-axis rerun). Labels reflect what the data actually is.
SOURCE_LABEL = {
    "production": "Production strategy\n(EuropePMC + PubTator\n+ gene2pubmed,\n21 axes/gene)",
    "openalex":   "OpenAlex strategy\n(broad gene + method-\nkeyword search,\n21 axes/gene)",
}


def load_production_jsonl(path: Path) -> tuple[list[dict], list[dict]]:
    """Read live production probe JSONL. Returns (gene_rows, paper_rows).

    Each paper_row gets a ``gene`` field merged in for downstream tidy-form
    consumption. Empty genes (no harvested papers) are still included in
    gene_rows so the avg-papers-per-gene denominator is honest.
    """
    genes, papers = [], []
    if not path.exists():
        return genes, papers
    with path.open() as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            genes.append(row)
            for p in row.get("papers", []):
                papers.append({**p, "gene": row["gene"]})
    return genes, papers


def load_openalex_tsv_snapshot(path: Path) -> tuple[list[dict], list[dict]]:
    """Read the salvaged OpenAlex TSV snapshot — same shape as JSONL.

    Reconstructs gene_rows + paper_rows from the TSV. n_avail is not
    preserved in the TSV (it lives only in the original JSONL, which we
    lost when the rate limit hit). We synthesize ``n_avail = paper_count``
    as a lower bound — the actual per-gene pre-sample harvest size is
    unknown for OpenAlex.
    """
    genes_map: dict[str, list[dict]] = {}
    if not path.exists():
        return [], []
    with path.open() as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r.get("source") != "openalex":
                continue
            sym = r["gene"]
            paper = {
                "pmid": int(r["pmid"]) if r.get("pmid") else 0,
                "pmc_id": r.get("pmc_id") or None,
                "doi": r.get("doi") or None,
                "year": int(r["year"]) if r.get("year") else None,
                "title": r.get("title") or "",
                "bucket": r["bucket"],
                "gene": sym,
            }
            genes_map.setdefault(sym, []).append(paper)
    gene_rows = []
    paper_rows = []
    for sym, papers in genes_map.items():
        gene_rows.append({
            "gene": sym,
            "n_avail": len(papers),  # NB: lower bound — see docstring
            "papers": papers,
        })
        paper_rows.extend(papers)
    return gene_rows, paper_rows


def write_tsv(prod_papers, oax_papers, out_path: Path) -> None:
    """Tidy long-form: one row per (source, gene, paper).

    Refresh the canonical TSV — prod rows are live from JSONL, openalex
    rows are passed through from the snapshot. Idempotent on repeat runs.
    """
    rows = []
    for src, papers in [("production", prod_papers), ("openalex", oax_papers)]:
        for p in papers:
            rows.append({
                "source": src,
                "gene": p["gene"],
                "pmid": p.get("pmid") or "",
                "pmc_id": p.get("pmc_id") or "",
                "doi": p.get("doi") or "",
                "year": p.get("year") or "",
                "bucket": p["bucket"],
                "title": (p.get("title") or "").replace("\t", " ").replace("\n", " ")[:200],
            })
    cols = ["source", "gene", "pmid", "pmc_id", "doi", "year", "bucket", "title"]
    with out_path.open("w") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"  wrote {out_path} ({len(rows)} rows)")


def make_figure(prod_genes, prod_papers, oax_genes, oax_papers, out_dir: Path) -> None:
    setup_plotting_style()

    sources = [
        ("openalex",   oax_genes,  oax_papers),
        ("production", prod_genes, prod_papers),
    ]

    # One horizontal stacked bar per source. Bars run along y; values along x.
    # Tighter aspect: labels wrap aggressively so the figure stays narrow.
    fig, ax = plt.subplots(figsize=(10, 6))
    bar_h = 0.55
    y_positions = list(range(len(sources)))

    for ypos, (src, genes, papers) in zip(y_positions, sources):
        c = Counter(p["bucket"] for p in papers)
        total = sum(c.values()) or 1
        cum = 0.0
        for bucket in BUCKET_ORDER:
            n = c.get(bucket, 0)
            if n == 0:
                continue
            pct = 100 * n / total
            ax.barh(
                [ypos], [pct], left=cum, height=bar_h,
                color=BUCKET_COLOR[bucket],
                edgecolor="white", linewidth=2.0,
            )
            if pct >= 6:
                ax.text(
                    cum + pct / 2, ypos,
                    f"{pct:.0f}%",
                    ha="center", va="center",
                    color="white", fontweight="bold", fontsize=16,
                )
            cum += pct

        # Right-side annotation: sample size + avg pre-sample papers/gene.
        # Wrapped to 4 short lines so the rightmost column stays narrow.
        valid = [g for g in genes if g.get("n_avail", 0) > 0]
        avg_avail = sum(g["n_avail"] for g in valid) / max(len(valid), 1)
        ax.text(
            104, ypos,
            f"{total} papers /\n{len(genes)} genes\navg {avg_avail:.0f} papers/\ngene pre-sample",
            ha="left", va="center", fontsize=11, fontweight="medium",
            color="#1F1718",
        )

    ax.set_xlim(0, 100)
    ax.set_ylim(-0.7, len(sources) - 0.3)
    ax.set_yticks(y_positions)
    ax.set_yticklabels([SOURCE_LABEL[s[0]] for s in sources], fontweight="medium")
    ax.set_xlabel("% of sampled papers")
    # No baked-in title — figure gets captioned in the gist README + paper
    # (per _plotting_config convention: axes.titlesize=0 suppresses anyway).

    # Legend below
    handles = [
        Patch(facecolor=BUCKET_COLOR[b], edgecolor="white", linewidth=1.5,
              label=BUCKET_LABEL[b])
        for b in BUCKET_ORDER
    ]
    ax.legend(
        handles=handles, loc="upper center", bbox_to_anchor=(0.45, -0.18),
        ncol=4, frameon=False,
    )
    sns.despine(ax=ax, top=True, right=True, left=True, bottom=False)

    fig.tight_layout()
    save_figure(
        fig, "paywall_bot_block_compare", out_dir,
        formats=("pdf", "png"), gist_url=GIST_URL,
    )
    plt.close(fig)


def main() -> None:
    prod_genes, prod_papers = load_production_jsonl(PROD_JSONL)
    # Prefer the live 21-axis JSONL; fall back to the 10-axis snapshot if
    # the JSONL is missing or empty (so a fresh worktree without local probe
    # data still renders the figure from the committed TSV).
    oax_genes, oax_papers = load_production_jsonl(OAX_JSONL)
    if not oax_genes:
        oax_genes, oax_papers = load_openalex_tsv_snapshot(OAX_TSV_SNAPSHOT)
        oax_note = "10-axis TSV snapshot (live 21-axis JSONL absent)"
    else:
        oax_note = "live 21-axis JSONL"
    print(f"production: {len(prod_genes)} genes / {len(prod_papers)} papers (live JSONL)")
    print(f"openalex:   {len(oax_genes)} genes / {len(oax_papers)} papers ({oax_note})")

    write_tsv(prod_papers, oax_papers, OUT_DIR / "paywall_bot_block_compare.tsv")
    make_figure(prod_genes, prod_papers, oax_genes, oax_papers, OUT_DIR)
    print(f"  wrote {OUT_DIR}/paywall_bot_block_compare.{{pdf,png}}")


if __name__ == "__main__":
    main()
