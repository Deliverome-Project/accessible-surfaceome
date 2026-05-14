# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "pandas>=2.2",
#   "seaborn>=0.13",
#   "httpx>=0.27",
# ]
# ///
"""Reproduce ``benchmark_cost_vs_accuracy.{pdf,png}`` from the public repo.

Fetches the canonical main-bench export (D1 → flat TSV) +
benchmark-truth TSV via ``raw.githubusercontent.com``, then renders the
8-cell cost/accuracy frontier in the Claude-orange palette.

Visual styling matches the in-repo `_plotting_config` (Deliverome
categorical palette + Manrope-when-available). Inlined so the gist
runs standalone.

Standalone — ``uv run make_benchmark_cost_vs_accuracy.py`` is all
you need.
"""
from __future__ import annotations

import io
from pathlib import Path

import httpx
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"

BENCH_TSV   = f"{BASE}/data/eval/triage_benchmark_v1.tsv"
PREDS_TSV   = f"{BASE}/data/processed/triage_bench/mainbench_canonical_v1.tsv"

# ──── Inline brand styling — sentinel: brand-style-v1 ────
# Mirrors src/accessible_surfaceome/audit/_plotting_config.py so the gist
# stays self-contained. Kept in sync via tests/test_figure_gists_styling.py.
BRAND_PALETTE = [
    "#BC3C4C",  # maroon-light
    "#3D6B60",  # teal-mid
    "#F4AA28",  # amber-bright
    "#8878C8",  # lavender-bright
    "#6E1428",  # maroon-dark
    "#7AAB9F",  # teal-light
]
BRAND_SEQUENTIAL = {
    "maroon":   ["#3E0A18", "#6E1428", "#922038", "#BC3C4C", "#F0A098", "#FDE8E6"],
    "teal":     ["#152E28", "#244840", "#3D6B60", "#4D8A80", "#7AAB9F", "#CCE8E4"],
    "amber":    ["#5A2608", "#8C4210", "#C07830", "#F4AA28", "#F4C070", "#FAECD4"],
    "lavender": ["#1E1450", "#3A2888", "#5848A8", "#8878C8", "#A090D4", "#E4E0F8"],
}
BRAND_CLAUDE_ORANGE = "#d87851"
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
            for ttf in sorted(fonts_dir.glob("*.ttf")):
                try:
                    fm.fontManager.addfont(str(ttf))
                except Exception:  # noqa: BLE001
                    continue
            return


def _apply_brand_style() -> None:
    """Inline equivalent of `setup_plotting_style`. Sentinel: brand-style-v1."""
    _register_brand_fonts()
    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=1.0)
    plt.rcParams.update({
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "figure.facecolor": "none",
        "savefig.facecolor": "none",
        "font.family": "sans-serif",
        "font.sans-serif": ["Manrope", "Outfit", "DejaVu Sans", "Liberation Sans", "Arial"],
        "font.size": 12,
        "axes.labelsize": 13,
        "axes.titlesize": 0,
        "axes.titlepad": 0,
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
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "xtick.color": BRAND_INK,
        "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "legend.fontsize": 11,
        "patch.edgecolor": "none",
        "patch.linewidth": 0.0,
    })


# Anthropic published prices ($/M tokens, 2026-05).
_PRICE = {
    "claude-haiku-4-5":  {"in": 1.00, "out": 5.00,  "cr": 0.10, "cw": 1.25},
    "claude-sonnet-4-6": {"in": 3.00, "out": 15.00, "cr": 0.30, "cw": 3.75},
    "claude-opus-4-7":   {"in": 15.0, "out": 75.0,  "cr": 1.50, "cw": 18.75},
}
WEB_SEARCH_USD_PER_QUERY = 0.01
WHOLE_GENOME_N = 19_324  # protein-coding human genes with a valid HGNC + UniProt mapping

# Per-cell label + Claude-orange sequential walk (light → dark = more-context cells).
CELL_LABEL = {
    ("claude-haiku-4-5",  "naive"):       "Haiku (naive)",
    ("claude-haiku-4-5",  "ncbi"):        "Haiku (+ NCBI)",
    ("claude-haiku-4-5",  "pubmed_ncbi"): "Haiku (+ NCBI + PubMed)",
    ("claude-haiku-4-5",  "web_ncbi"):    "Haiku (+ NCBI + web)",
    ("claude-sonnet-4-6", "naive"):       "Sonnet (naive)",
    ("claude-sonnet-4-6", "ncbi"):        "Sonnet (+ NCBI)",
    ("claude-sonnet-4-6", "pubmed_ncbi"): "Sonnet (+ NCBI + PubMed)",
    ("claude-sonnet-4-6", "web_ncbi"):    "Sonnet (+ NCBI + web)",
    ("claude-opus-4-7",   "naive"):       "Opus (naive)",
    ("claude-opus-4-7",   "ncbi"):        "Opus (+ NCBI)",
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
    ("claude-opus-4-7",   "naive"):       "#b66547",
    ("claude-opus-4-7",   "ncbi"):        "#a85b3f",
}

# Per-cell label offsets (pixels) to deconflict dense clusters — mirrors
# scripts/triage_bench_db_barplot.py::make_cost_vs_accuracy_plot. Without
# these, Opus(naive) and Sonnet(+NCBI+web) land at similar (cost, acc.) and
# their labels stack. When abs(dy) >= 16 a short leader line is drawn so
# the label → point mapping stays unambiguous. Re-tune if cells move.
CELL_LABEL_OFFSET = {
    ("claude-haiku-4-5",  "naive"):       (7,   6),
    ("claude-haiku-4-5",  "ncbi"):        (7,  10),
    ("claude-haiku-4-5",  "pubmed_ncbi"): (7, -18),
    ("claude-haiku-4-5",  "web_ncbi"):    (7,   6),
    ("claude-sonnet-4-6", "naive"):       (7, -18),
    ("claude-sonnet-4-6", "ncbi"):        (7,  10),
    ("claude-sonnet-4-6", "pubmed_ncbi"): (7, -20),
    ("claude-sonnet-4-6", "web_ncbi"):    (7,   6),
    ("claude-opus-4-7",   "naive"):       (7, -18),
    ("claude-opus-4-7",   "ncbi"):        (7,  10),
}


def _fetch_tsv(url: str) -> pd.DataFrame:
    local = Path(__file__).resolve().parents[3] / url[len(BASE) + 1:]
    if local.is_file():
        return pd.read_csv(local, sep="\t")
    r = httpx.get(url, timeout=30)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text), sep="\t")


def _verdict_match(pred: str | None, truth: str | None) -> bool:
    """yes ≡ contextual collapse — same rule the runner applies."""
    if pred is None or truth is None:
        return False
    if pred == truth:
        return True
    return pred in ("yes", "contextual") and truth in ("yes", "contextual")


def _whole_genome_cost(group: pd.DataFrame) -> float:
    """Per-cell cost extrapolated to one pass over the 19,324-gene catalog."""
    model = group["model"].iloc[0]
    pricing = _PRICE[model]
    n = len(group)
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
    out_per_cell  = ot       * pricing["out"] / 1_000_000
    web_per_cell  = ws       * WEB_SEARCH_USD_PER_QUERY
    return (sys_per_cell + user_per_cell + out_per_cell + web_per_cell) * WHOLE_GENOME_N


def main() -> None:
    _apply_brand_style()
    preds = _fetch_tsv(PREDS_TSV)
    truth = _fetch_tsv(BENCH_TSV).set_index("gene_symbol")["ground_truth_verdict"]
    preds["truth_verdict"] = preds["gene_symbol"].map(truth)
    preds = preds.dropna(subset=["truth_verdict"])
    preds["correct"] = [
        _verdict_match(p, t)
        for p, t in zip(preds["predicted_verdict"], preds["truth_verdict"], strict=True)
    ]

    cells = []
    for (model, variant), grp in preds.groupby(["model", "prompt_variant"], sort=False):
        if (model, variant) not in CELL_LABEL:
            continue
        cells.append({
            "model": model,
            "variant": variant,
            "label": CELL_LABEL[(model, variant)],
            "color": CELL_COLOR[(model, variant)],
            "accuracy": grp["correct"].mean(),
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
            fontsize=9.5, color=BRAND_INK,
            arrowprops=arrowprops,
        )
    ax.set_xscale("log")
    ax.set_xlabel("$ / whole-genome triage pass (19,324 genes, 1 replicate)")
    ax.set_ylabel("Verdict accuracy on 147-gene bench (%)")
    ymin = min(c["accuracy"] for c in cells) * 100
    ax.set_ylim(max(78, ymin - 2), 100)
    sns.despine(ax=ax, top=True, right=True)

    out_pdf = Path("benchmark_cost_vs_accuracy.pdf")
    out_png = Path("benchmark_cost_vs_accuracy.png")
    fig.savefig(out_pdf, bbox_inches="tight")
    fig.savefig(out_png, bbox_inches="tight", dpi=300)
    print(f"Wrote {out_pdf} + {out_png} ({len(df)} cells)")


if __name__ == "__main__":
    main()
