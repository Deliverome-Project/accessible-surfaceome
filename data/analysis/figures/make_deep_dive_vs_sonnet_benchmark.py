# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=1.26",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``deep_dive_vs_sonnet_benchmark.{pdf,png}``.

**Supplementary Fig 12.** Deep-dive vs Sonnet+NCBI accuracy on the
SurfaceBench genes deep-dived so far (the intersection, n = 27 of 147).
Each protein's evidence-anchored deep-dive surface call and the
Sonnet+NCBI triage call are scored against the curated ground-truth
verdict under the soft-credit rule — a contextually-surface protein
counts correct when called surface.

  * **a.** Overall soft-credit accuracy — deep dive vs Sonnet+NCBI.
  * **b.** Accuracy split by ground-truth bucket (yes / contextual / no).

The deep-dive bar is STACKED by the tier it assigned to the
correctly-classified genes — canonical / likely / low (green shades)
and uncertain / no (grey), the same five-tier palette as Figure 5a — so
its confidence composition is visible. Sonnet+NCBI accuracy is the mean
of three mainbench replicates (one dot per replicate; the error bar is
the SEM across replicates); the deep dive runs once per gene, so its bar
carries no replicate spread. Deep dive and Sonnet are near-identical
overall (96% vs 96%).

PRELIMINARY — n = 27 is small (the 'no' bucket is only 2 genes); read
these as an early signal that firms up as the sweep covers more
benchmark genes.

The single bundled TSV (one row per deep-dived bench gene with both
predictors' soft-credit correctness, the deep-dive tier, and the three
Sonnet replicate flags) is produced by ``scripts/build_figure_tsvs.py``
so the gist is a one-TSV reproduction unit.

Visual styling matches the in-repo ``_plotting_config`` (Deliverome
categorical palette + Manrope-when-available). Inlined so the gist runs
standalone — ``uv run make_deep_dive_vs_sonnet_benchmark.py``.
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"

# Published reproduction gist — embedded into output PNG Source / PDF
# Subject metadata (mirrors save_figure in _plotting_config.py).
GIST_URL = "https://gist.github.com/beccajcarlson/d88f7c7a135bf222ccc5883b9c1a2eb4"

# Single bundled per-figure TSV — one tidy row per deep-dived bench gene.
DATA_TSV = f"{BASE}/data/processed/figures/deep_dive_vs_sonnet_benchmark.tsv"

_SONNET_COLOR = "#E5946A"   # Sonnet — lighter orange
_BUCKET_ORDER = ["yes", "contextual", "no"]
_BUCKET_LABEL = {"yes": "yes\n(surface)", "contextual": "contextual",
                 "no": "no\n(not surface)"}

# The deep-dive accuracy bar is stacked by the tier it assigned to the
# correctly classified genes. Tier colours are EXACTLY Figure 5a's
# (deep_dive_final_categories) five-tier spectrum, so the two figures
# read as one palette.
_TIER_ORDER = ["canonical", "likely", "low", "uncertain", "no"]
_TIER_COLOR = {
    "canonical": "#2E7A55",  # success green — strict tier
    "likely":    "#3D6B60",  # teal-mid — broader tier
    "low":       "#C99A5B",  # amber-tan — low/moderate, weak evidence
    "uncertain": "#C7BDB6",  # light warm-grey — ambiguous
    "no":        "#9C8C88",  # lifted neutral — leaned not-surface
}
_TIER_LABEL = {"canonical": "canonical", "likely": "likely", "low": "low",
               "uncertain": "uncertain", "no": "no"}

# ──── Inline brand styling — sentinel: brand-style-v3 ────
# Mirrors src/accessible_surfaceome/audit/_plotting_config.py so the gist
# stays self-contained (no in-repo imports — Substack readers run it
# standalone). Kept in sync via tests/test_figure_gists_styling.py.
BRAND_PALETTE = [
    "#BC3C4C",  # maroon-light
    "#3D6B60",  # teal-mid
    "#F4AA28",  # amber-bright
    "#8878C8",  # lavender-bright
    "#6E1428",  # maroon-dark
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
            for path in sorted(list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf"))):
                try:
                    fm.fontManager.addfont(str(path))
                except Exception:  # noqa: BLE001
                    continue
            return


def _apply_brand_style() -> None:
    """Inline equivalent of `setup_plotting_style`. Sentinel: brand-style-v3."""
    _register_brand_fonts()
    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=1.0)
    plt.rcParams.update({
        "savefig.dpi": 600,
        "savefig.bbox": "tight",
        "figure.facecolor": "none",
        "savefig.facecolor": "none",
        "font.family": "sans-serif",
        "font.sans-serif": ["Manrope", "Outfit", "DejaVu Sans", "Liberation Sans", "Arial"],
        "font.weight": "medium",
        "font.size": 13,
        "axes.labelsize": 13,
        "axes.labelweight": "medium",
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
        "xtick.labelsize": 13,
        "ytick.labelsize": 13,
        "xtick.color": BRAND_INK,
        "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "legend.fontsize": 13,
        "patch.edgecolor": "none",
        "patch.linewidth": 0.0,
    })


def _load() -> list[dict]:
    """Sibling-first: the bundled TSV must sit next to this script (gist).
    Falls back to the in-repo canonical path for a local checkout run."""
    sibling = Path(__file__).parent / Path(DATA_TSV).name
    if sibling.is_file():
        path = sibling
    else:
        path = Path(__file__).resolve().parents[3] / DATA_TSV[len(BASE) + 1:]
    with open(path) as f:
        return list(csv.DictReader(f, delimiter="\t"))


_RNG = np.random.default_rng(0)  # deterministic jitter


def _stats(rows: list[dict], key: str) -> tuple[float, float, list[float]]:
    """Soft-credit accuracy (%), its binomial SEM (%), and the per-gene
    0/100 correctness values."""
    vals = [int(r[key]) for r in rows]
    n = len(vals)
    if n == 0:
        return 0.0, 0.0, []
    p = sum(vals) / n
    sem = 100.0 * ((p * (1 - p)) ** 0.5) / (n ** 0.5)
    return 100.0 * p, sem, [100.0 * v for v in vals]


def _sonnet_replicate_accs(rows: list[dict]) -> list[float]:
    """Per-replicate soft-credit accuracy (%) — one value per replicate
    with data (the mainbench Sonnet+NCBI triage ran 3 replicates)."""
    accs = []
    for col in ("sonnet_correct_r1", "sonnet_correct_r2", "sonnet_correct_r3"):
        vals = [int(row[col]) for row in rows if str(row.get(col, "")) != ""]
        if vals:
            accs.append(100.0 * sum(vals) / len(vals))
    return accs


def _panel_label(ax: plt.Axes, letter: str) -> None:
    ax.text(-0.02, 1.06, letter, transform=ax.transAxes, fontsize=26,
            fontweight=800, va="bottom", ha="right", color=BRAND_INK)


def _draw_sonnet(ax: plt.Axes, rows: list[dict], x: float, width: float) -> None:
    """Sonnet+NCBI bar = MEAN of the per-replicate accuracies; one dot per
    replicate + SEM ACROSS replicates."""
    accs = _sonnet_replicate_accs(rows)
    if not accs:
        return
    mean = sum(accs) / len(accs)
    sem = float(np.std(accs, ddof=1)) / (len(accs) ** 0.5) if len(accs) > 1 else 0.0
    ax.bar(x, mean, width=width, color=_SONNET_COLOR, zorder=2)
    ax.errorbar(x, mean, yerr=sem, fmt="none", ecolor=BRAND_INK,
                elinewidth=1.4, capsize=5, zorder=4)
    jx = _RNG.uniform(-width * 0.20, width * 0.20, size=len(accs))
    ax.scatter(x + jx, accs, s=26, color=BRAND_INK, alpha=0.75,
               edgecolor="white", linewidth=0.5, zorder=5)
    ax.text(x, mean + sem + 2, f"{mean:.0f}", ha="center", va="bottom",
            fontsize=14, color=_SONNET_COLOR, fontweight="bold")


def _draw_deep_dive(ax: plt.Axes, rows: list[dict], x: float, width: float) -> None:
    """Deep-dive accuracy bar, STACKED by the tier of the correctly-classified
    genes. Stack height == accuracy."""
    n = len(rows)
    dd, _, _ = _stats(rows, "deep_dive_correct")
    counts = Counter(r["deep_dive_tier"] for r in rows
                     if int(r["deep_dive_correct"]) == 1)
    bottom = 0.0
    for t in _TIER_ORDER:
        h = 100.0 * counts.get(t, 0) / n if n else 0.0
        if h <= 0:
            continue
        ax.bar(x, h, bottom=bottom, width=width, color=_TIER_COLOR[t], zorder=2)
        bottom += h
    ax.text(x, dd + 2, f"{dd:.0f}", ha="center", va="bottom", fontsize=14,
            color=BRAND_INK, fontweight="bold")


def _embed_source_in_metadata(out_path: Path, url: str) -> None:
    """Write the gist URL into the PNG's Source tEXt chunk so the URL
    travels with the file."""
    if out_path.suffix == ".png":
        try:
            from PIL import Image, PngImagePlugin
            img = Image.open(out_path)
            meta = PngImagePlugin.PngInfo()
            for k, v in img.info.items():
                if isinstance(v, (str, bytes)):
                    meta.add_text(k, v if isinstance(v, str) else v.decode("latin-1", "ignore"))
            meta.add_text("Source", url)
            img.save(out_path, "PNG", pnginfo=meta)
        except Exception:  # noqa: BLE001 — best-effort
            pass


def make_plot() -> plt.Figure:
    _apply_brand_style()
    plt.rcParams.update({
        "font.size": 18, "axes.labelsize": 18, "axes.titlesize": 0,
        "xtick.labelsize": 15, "ytick.labelsize": 15, "legend.fontsize": 15,
    })
    rows = _load()

    fig, (axA, axB) = plt.subplots(
        1, 2, figsize=(13, 6),
        gridspec_kw={"width_ratios": [0.8, 1.5], "wspace": 0.28},
    )

    # ── Panel a: overall ────────────────────────────────────────────────────
    width = 0.6
    _draw_deep_dive(axA, rows, -width / 2, width)
    _draw_sonnet(axA, rows, width / 2, width)
    axA.set_xticks([-width / 2, width / 2])
    axA.set_xticklabels(["deep\ndive", "Sonnet\n+NCBI"])
    axA.set_ylabel("Soft-credit accuracy (%)")
    axA.set_ylim(0, 112)
    axA.set_xlim(-0.7, 0.7)
    axA.text(0.5, 1.02, f"n = {len(rows)} genes", transform=axA.transAxes,
             ha="center", va="bottom", fontsize=13, color=BRAND_NEUTRAL)
    sns.despine(ax=axA, top=True, right=True)
    _panel_label(axA, "a")

    # ── Panel b: by ground-truth bucket ─────────────────────────────────────
    bwidth = 0.38
    bucket_n = {bk: sum(1 for r in rows if r["ground_truth_verdict"] == bk)
                for bk in _BUCKET_ORDER}
    for bi, bk in enumerate(_BUCKET_ORDER):
        sub = [r for r in rows if r["ground_truth_verdict"] == bk]
        _draw_deep_dive(axB, sub, bi - bwidth / 2, bwidth)
        _draw_sonnet(axB, sub, bi + bwidth / 2, bwidth)
    axB.set_xticks(range(len(_BUCKET_ORDER)))
    axB.set_xticklabels([f"{_BUCKET_LABEL[b]}\nn={bucket_n[b]}"
                         for b in _BUCKET_ORDER])
    axB.set_ylabel("Soft-credit accuracy (%)")
    axB.set_ylim(0, 112)
    axB.set_xlim(-0.6, len(_BUCKET_ORDER) - 0.4)
    handles = [mpatches.Patch(color=_TIER_COLOR[t], label=_TIER_LABEL[t])
               for t in _TIER_ORDER]
    handles.append(mpatches.Patch(color=_SONNET_COLOR, label="Sonnet+NCBI"))
    axB.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1.0),
               frameon=False, fontsize=11, title="deep-dive tier / Sonnet",
               title_fontsize=11, labelspacing=0.35, handlelength=1.2)
    sns.despine(ax=axB, top=True, right=True)
    _panel_label(axB, "b")

    fig.tight_layout(rect=(0, 0, 0.84, 1))
    return fig


def main() -> None:
    fig = make_plot()
    out_dir = Path(__file__).parent
    pdf = out_dir / "deep_dive_vs_sonnet_benchmark.pdf"
    png = out_dir / "deep_dive_vs_sonnet_benchmark.png"
    fig.savefig(pdf, metadata={"Subject": GIST_URL})
    fig.savefig(png, dpi=600, metadata={"Source": GIST_URL})
    _embed_source_in_metadata(png, GIST_URL)
    plt.close(fig)
    print(f"Wrote {pdf}")


if __name__ == "__main__":
    main()
