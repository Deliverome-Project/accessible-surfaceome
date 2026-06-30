# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``evidence_corpus_vs_selected.{pdf,png}`` from the public repo.

**MOCK supplementary figure.** Papers found vs papers selected as evidence
per gene, colored by agent ``evidence_grade`` verdict. For each gene in
the deep-dive cohort, the literature pipeline returns:

  * **Papers found** — the size of the per-gene candidate corpus from
    discovery (EuropePMC + PubTator NER + gene2pubmed; median ~234
    papers per gene on the 100-gene audit).
  * **Papers selected as evidence** — the subset the deep-dive's
    `plan_trim_select` step ranks high-enough to feed into the block
    builders for full-text claim extraction.

The agent then assigns each gene's evidence base an ``evidence_grade``
verdict from the closed enum: direct_multi_method / direct_single_method
/ supportive_but_indirect / weak.

Counts are synthesized from the production-pipeline distributional shape
pending the full v2 deep-dive sweep. Replace ``_synthesize_mock_data()``
with a public-D1 SELECT once ``deep_dive_run.evidence_grade`` is
populated genome-wide.

Visual styling matches the in-repo `_plotting_config` (Deliverome
categorical palette + Manrope-when-available). Inlined so the gist
runs standalone — ``uv run make_evidence_corpus_vs_selected.py``.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"

# Published reproduction gist — embedded into output PNG Source / PDF
# Subject metadata (mirrors save_figure in _plotting_config.py).
GIST_URL = "https://gist.github.com/beccajcarlson/27acf83e5e0175fd0887777adf49497b"

# Single bundled per-figure TSV — synthesized per-gene (papers_found,
# papers_selected, verdict) tuples. The mirror reads this rather than
# regenerating the mock at render time so the gist stays single-source.
DATA_TSV = f"{BASE}/data/processed/figures/evidence_corpus_vs_selected.tsv"

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
        "font.size": 18,
        "axes.labelsize": 20,
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
        "xtick.labelsize": 16,
        "ytick.labelsize": 16,
        "xtick.color": BRAND_INK,
        "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "legend.fontsize": 14,
        "patch.edgecolor": "none",
        "patch.linewidth": 0.0,
    })


# Verdict ordering = best → worst evidence quality (used for legend
# + plot z-order so weak dots don't occlude direct_multi dots).
VERDICT_ORDER = [
    "direct_multi_method",
    "direct_single_method",
    "supportive_but_indirect",
    "weak",
]
VERDICT_COLOR = {
    "direct_multi_method":     "#2E7A55",  # success green
    "direct_single_method":    "#3D6B60",  # teal-mid
    "supportive_but_indirect": "#C07830",  # amber-dark
    "weak":                    "#9C8C88",  # neutral grey
}
VERDICT_LABEL = {
    "direct_multi_method":     "direct, multi-method",
    "direct_single_method":    "direct, single method",
    "supportive_but_indirect": "supportive but indirect",
    "weak":                    "weak / sparse",
}

def _fetch_tsv(url: str) -> pd.DataFrame:
    """Read the bundled sibling TSV next to this script.

    Per the PR #86 single-TSV invariant: each gist is a self-contained
    reproduction unit (script + bundled TSV) cited as ``swh:1:rev:<sha>``
    of the gist HEAD commit. Sibling-first; falls back to in-repo dev
    tree path so canonical-mirror parity tests pass without re-bundling.
    """
    sibling = Path(__file__).parent / Path(url).name
    if sibling.is_file():
        return pd.read_csv(sibling, sep="\t")
    if url.startswith(BASE + "/"):
        local = Path(__file__).resolve().parents[3] / url[len(BASE) + 1:]
        if local.is_file():
            return pd.read_csv(local, sep="\t")
    raise FileNotFoundError(
        f"Bundled TSV not found next to script: {sibling}. "
        f"This script reads only the bundled sibling — clone the gist "
        f"or run the canonical generator from the repo's in-repo dev tree."
    )


def _load_mock_data() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load the bundled per-gene (papers_found, papers_selected,
    verdict) tuples. Synthesized into the TSV at build time
    (``scripts/build_figure_tsvs.py::build_evidence_corpus_vs_selected``)
    so the figure stays reproducible from a single bundled source."""
    df = _fetch_tsv(DATA_TSV)
    return (
        df["papers_found"].to_numpy(dtype=int),
        df["papers_selected"].to_numpy(dtype=int),
        df["verdict"].to_numpy(dtype=object),
    )


def main() -> None:
    _apply_brand_style()
    found, selected, verdicts = _load_mock_data()

    fig, ax = plt.subplots(figsize=(12, 8))

    # Plot in worst → best verdict order so the strong verdicts land on
    # top of the weak ones and aren't occluded.
    counts = Counter(verdicts.tolist())
    for verdict in reversed(VERDICT_ORDER):
        mask = verdicts == verdict
        ax.scatter(
            found[mask], selected[mask],
            s=70, alpha=0.75, edgecolor="white", linewidth=0.6,
            color=VERDICT_COLOR[verdict],
            label=f"{VERDICT_LABEL[verdict]}  (n={counts.get(verdict, 0)})",
            zorder=3 + VERDICT_ORDER.index(verdict),
        )

    # Reference lines at canonical selection rates (5%, 10%).
    x_ref = np.geomspace(25, 600, 200)
    for rate, label in [(0.05, "5%"), (0.10, "10%")]:
        ax.plot(x_ref, rate * x_ref, ls=":", lw=1.0, color=BRAND_NEUTRAL, alpha=0.5, zorder=2)
        y_at_right = rate * 540
        ax.text(540, y_at_right - 1.5, label, color=BRAND_NEUTRAL,
                fontsize=11, ha="right", va="top", alpha=0.75)

    ax.set_xscale("log")
    ax.set_xlim(25, 600)
    ax.set_ylim(0, 55)
    ax.set_xlabel("Papers found per gene  (discovery corpus)")
    ax.set_ylabel("Papers selected\nas evidence")
    ax.set_xticks([30, 50, 100, 200, 400])
    ax.set_xticklabels(["30", "50", "100", "200", "400"])

    handles, labels = ax.get_legend_handles_labels()
    # Re-order legend to best → worst.
    handle_by_label = dict(zip(labels, handles))
    ordered_labels = [
        f"{VERDICT_LABEL[v]}  (n={counts.get(v, 0)})" for v in VERDICT_ORDER
    ]
    ax.legend(
        [handle_by_label[lbl] for lbl in ordered_labels if lbl in handle_by_label],
        [lbl for lbl in ordered_labels if lbl in handle_by_label],
        title="agent evidence_grade verdict",
        loc="upper left", bbox_to_anchor=(0.01, 0.99),
        frameon=False, fontsize=13, title_fontsize=14,
    )

    fig.text(
        0.5, -0.04,
        f"MOCK — synthesized from the 100-gene audit shape "
        f"(median {int(np.median(found))} papers/gene, "
        f"median {int(np.median(selected))} selected); n={len(found)} genes",
        ha="center", va="top", fontsize=12, style="italic", color=BRAND_NEUTRAL,
    )

    sns.despine(ax=ax, top=True, right=True)
    fig.tight_layout()

    out_pdf = Path("evidence_corpus_vs_selected.pdf")
    out_png = Path("evidence_corpus_vs_selected.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=600, metadata={"Source": GIST_URL})
    print(f"Wrote {out_pdf} + {out_png}  (n = {len(found)} genes)")


if __name__ == "__main__":
    main()
