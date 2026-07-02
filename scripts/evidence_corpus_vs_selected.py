"""Papers found vs papers selected as evidence per gene, colored by the
agent's ``evidence_grade`` verdict (Supplementary S11).

For each gene in the deep-dive cohort, the literature pipeline records two
corpus sizes:

  * **Papers found** — the size of the per-gene candidate corpus from
    discovery (EuropePMC + PubTator NER + gene2pubmed union), i.e.
    ``n_papers_found`` (methods-section median 234.5, range ~50–400).
  * **Papers selected as evidence** — the subset the deep-dive's
    ``plan_trim_select`` step ranks high enough to read full-text and feed
    into the block builders (``n_papers_selected``). The selection count
    grows sub-linearly with corpus size — more candidate papers means more
    noise, not proportionally more relevant evidence.

Each gene's evidence base is graded ``evidence_grade`` from the closed enum:

  * ``direct_multi_method``     — multiple independent assay types
  * ``direct_single_method``    — direct surface evidence from one assay
  * ``supportive_but_indirect`` — circumstantial / topology-based
  * ``weak``                    — sparse or low-quality evidence
  * ``conflicting``             — evidence points both ways

The verdict tracks the two corpus axes — well-evidenced surface targets pile
up toward the upper-right (rich corpus + rich selection → multi-method
verdict), while weak / conflicting calls cluster low.

**Real data.** Every point is a published deep-dive record with real gene
symbols and real counts, read from the bundled per-figure TSV at
``data/processed/figures/evidence_corpus_vs_selected.tsv`` (columns:
``gene_symbol, uniprot_acc, papers_found, papers_selected, evidence_grade,
tier``). The single source of that TSV is ``scripts/build_figure_tsvs.py``
(``build_evidence_corpus_vs_selected``), which reads the deep-dive export;
this canonical generator reads the TSV so it renders the **same** dataset as
the gist mirror (``data/analysis/figures/make_evidence_corpus_vs_selected.py``).

PRELIMINARY — ~1,197 of ~5,128 swept, pre-QA-fix; ``papers_found`` is null on
a handful of legacy records so those genes are absent (both axes must be
present to plot). The ``weak`` pile is partly the pretrim-cap recall bug
deleting foundational literature; re-render after the full sweep + QA fixes.

Run:
    uv run python scripts/evidence_corpus_vs_selected.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import (
    COLORS,
    save_figure,
    setup_plotting_style,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data/analysis/figures"
SLUG = "evidence_corpus_vs_selected"

# Bundled per-figure TSV — one row per published deep-dive record, produced by
# ``scripts/build_figure_tsvs.py`` (``build_evidence_corpus_vs_selected``).
# Reading it here keeps canonical == gist mirror == bundled TSV.
DATA_TSV = ROOT / "data/processed/figures/evidence_corpus_vs_selected.tsv"

# Verdict ordering = best → worst evidence quality (used for legend
# + plot z-order so weak dots don't occlude direct_multi dots).
VERDICT_ORDER = [
    "direct_multi_method",
    "direct_single_method",
    "supportive_but_indirect",
    "conflicting",
    "weak",
]
VERDICT_COLOR = {
    "direct_multi_method":     "#2E7A55",  # success green
    "direct_single_method":    "#3D6B60",  # teal-mid
    "supportive_but_indirect": "#C07830",  # amber-dark
    "conflicting":             "#8878C8",  # lavender — points both ways
    "weak":                    "#9C8C88",  # neutral grey
}
VERDICT_LABEL = {
    "direct_multi_method":     "direct, multi-method",
    "direct_single_method":    "direct, single method",
    "supportive_but_indirect": "supportive but indirect",
    "conflicting":             "conflicting",
    "weak":                    "weak / sparse",
}


def _load_data() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Read the bundled per-figure TSV and return three same-length arrays
    ``(papers_found, papers_selected, verdicts)``.

    The TSV is the single source of the data, produced by
    ``scripts/build_figure_tsvs.py`` (``build_evidence_corpus_vs_selected``),
    so this canonical generator and the gist mirror render the identical
    dataset. Enforced by tests/test_canonical_mock_reads_bundled_tsv.py."""
    data = pd.read_csv(DATA_TSV, sep="\t")
    found = data["papers_found"].to_numpy()
    selected = data["papers_selected"].to_numpy()
    verdicts = data["evidence_grade"].to_numpy()
    return found, selected, verdicts


def make_plot() -> tuple[plt.Figure, plt.Axes]:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    plt.rcParams.update({
        "font.size": 18, "axes.labelsize": 20, "axes.titlesize": 0,
        "xtick.labelsize": 16, "ytick.labelsize": 16, "legend.fontsize": 14,
    })
    found, selected, verdicts = _load_data()

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

    # Reference lines at canonical selection rates (5%, 10%) — higher
    # rates would exit the visible window at x≪600 and either need
    # their labels clipped or stretch the canvas vertically. Keep only
    # the two rates the bulk of the data actually crosses.
    x_ref = np.geomspace(25, 600, 200)
    for rate, label in [(0.05, "5%"), (0.10, "10%")]:
        ax.plot(x_ref, rate * x_ref, ls=":", lw=1.0, color=COLORS["neutral"], alpha=0.5, zorder=2)
        y_at_right = rate * 540
        ax.text(540, y_at_right - 1.5, label, color=COLORS["neutral"],
                fontsize=11, ha="right", va="top", alpha=0.75)

    ax.set_xscale("log")
    ax.set_xlim(25, 600)
    ax.set_ylim(0, 55)
    ax.set_xlabel("Papers found per gene  (discovery corpus)")
    ax.set_ylabel("Papers selected\nas evidence")
    ax.set_xticks([30, 50, 100, 200, 400])
    ax.set_xticklabels(["30", "50", "100", "200", "400"])

    handles, labels = ax.get_legend_handles_labels()
    # Re-order legend to best → worst so the reader's eye moves
    # natural reading direction (top label = best verdict).
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
        f"Real deep-dive records (median {int(np.median(found))} papers found/gene, "
        f"median {int(np.median(selected))} selected); n={len(found)} genes. "
        f"PRELIMINARY — ~1,197 of ~5,128 swept, pre-QA-fix.",
        ha="center", va="top", fontsize=12, style="italic", color=COLORS["neutral"],
    )

    sns.despine(ax=ax, top=True, right=True)
    fig.tight_layout()
    return fig, ax


def main() -> None:
    fig, _ = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"))


if __name__ == "__main__":
    main()
