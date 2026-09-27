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

Computed over the completed deep-dive sweep; ``papers_found`` is null on
a handful of legacy records so those genes are absent (both axes must be
present to plot). The ``weak`` pile is partly the pretrim-cap recall bug
deleting foundational literature; re-render after the full sweep + QA fixes.

Run:
    uv run python scripts/figures/evidence_corpus_vs_selected.py
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

ROOT = Path(__file__).resolve().parents[2]
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
    return found, selected, verdicts, data



# ── Panel b: tier composition within literature-size strata ────────────────
# A reviewer asked to separate "well studied" from "strong evidence": the
# low-literature flag says which genes are sparse, but not what the pipeline
# concluded about them. The manuscript reports the canonical rate per stratum
# in prose; showing the full composition makes the other tiers visible, and
# the clearest signal is `low` collapsing from ~60% to ~11% across strata —
# sparse literature produces weak calls, not negative ones.
#
# Tier colours MUST match Figure 5a and Supp S13; a tier name carrying a
# different colour across figures is exactly the inconsistency a reviewer
# caught on S11.
_STRATA_EDGES = [0, 75, 100, 150, 200, 10**9]
_STRATA_LABELS = ["<75", "75-100", "100-150", "150-200", ">200"]
_TIER_ORDER_B = ["canonical", "likely", "low", "no", "uncertain"]
_TIER_COLOR_B = {
    "canonical": "#2E7A55",   # success green — strict tier
    "likely":    "#3D6B60",   # teal-mid — broader tier
    "low":       "#C99A5B",   # amber-tan — weak evidence
    "no":        "#9C8C88",   # lifted neutral — leaned not-surface
    "uncertain": "#C7BDB6",   # light warm grey — undetermined
}


def _draw_tier_composition(ax, data) -> None:
    import pandas as _pd

    strata = _pd.cut(data["papers_found"], bins=_STRATA_EDGES,
                     labels=_STRATA_LABELS, right=False)
    ct = _pd.crosstab(strata, data["tier"], normalize="index") * 100
    n_per = strata.value_counts().reindex(_STRATA_LABELS)

    bottom = [0.0] * len(_STRATA_LABELS)
    x = range(len(_STRATA_LABELS))
    for tier in _TIER_ORDER_B:
        if tier not in ct.columns:
            continue
        vals = ct.reindex(_STRATA_LABELS)[tier].fillna(0).to_numpy()
        ax.bar(x, vals, bottom=bottom, width=0.72,
               color=_TIER_COLOR_B[tier], edgecolor="white", linewidth=0.8,
               label=tier, zorder=2)
        for xi, (v, b) in enumerate(zip(vals, bottom, strict=True)):
            if v >= 6:  # only label a segment tall enough to hold the text
                ax.text(xi, b + v / 2, f"{v:.0f}%", ha="center", va="center",
                        fontsize=12, color="white", fontweight="semibold")
        bottom = [b + v for b, v in zip(bottom, vals, strict=True)]

    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{lab}\n(n={int(n_per[lab]):,})" for lab in _STRATA_LABELS],
                       fontsize=14)
    ax.set_xlabel("Papers found per gene  (discovery corpus)")
    ax.set_ylabel("Share of genes\nin stratum (%)")
    ax.set_ylim(0, 100)
    ax.grid(axis="x", visible=False)
    ax.legend(title="deep-dive surface tier", loc="upper center",
              bbox_to_anchor=(0.5, -0.20), ncol=5, frameon=False,
              fontsize=13, title_fontsize=14)


def _panel_letter(ax, letter: str) -> None:
    ax.text(-0.02, 1.04, letter, transform=ax.transAxes, fontsize=24,
            fontweight=800, va="bottom", ha="right", color=COLORS["dark"])


def make_plot() -> tuple[plt.Figure, tuple[plt.Axes, plt.Axes]]:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    plt.rcParams.update({
        "font.size": 18, "axes.labelsize": 20, "axes.titlesize": 0,
        "xtick.labelsize": 16, "ytick.labelsize": 16, "legend.fontsize": 14,
    })
    found, selected, verdicts, data = _load_data()

    fig, (ax, ax_b) = plt.subplots(
        1, 2, figsize=(22, 8),
        gridspec_kw={"width_ratios": [1.15, 1.0], "wspace": 0.22},
    )

    # Plot in worst → best verdict order so the strong verdicts land on
    # top of the weak ones and aren't occluded.
    counts = Counter(verdicts.tolist())
    for verdict in reversed(VERDICT_ORDER):
        mask = verdicts == verdict
        ax.scatter(
            found[mask], selected[mask],
            s=70, alpha=0.5, edgecolor="white", linewidth=0.6,
            color=VERDICT_COLOR[verdict],
            label=f"{VERDICT_LABEL[verdict]}  (n={counts.get(verdict, 0)})",
            zorder=3 + VERDICT_ORDER.index(verdict),
        )

    # Reference lines at canonical selection rates (5%, 10%) — higher
    # rates would exit the visible window at x≪600 and either need
    # their labels clipped or stretch the canvas vertically. Keep only
    # the two rates the bulk of the data actually crosses.
    x_ref = np.geomspace(25, 600, 200)
    # Label each iso-line with what the percentage MEANS, not a bare "5%".
    # A reviewer asked "specify what the curves indicated with percentages
    # are" — they are constant selection rates (selected / found), so a
    # gene sitting on the 10% line had one paper in ten promoted from the
    # discovery corpus to the evidence ledger. The bare percentage read as
    # an unexplained third variable.
    for rate, label in [(0.05, "5% selected"), (0.10, "10% selected")]:
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
        f"Dotted lines mark a constant selection rate (papers selected \u00f7 papers found). "
        f"Real deep-dive records (median {int(np.median(found))} papers found/gene, "
        f"median {int(np.median(selected))} selected); n={len(found)} genes "
        f"(full deep-dive cohort).",
        ha="center", va="top", fontsize=12, style="italic", color=COLORS["neutral"],
    )

    _draw_tier_composition(ax_b, data)
    _panel_letter(ax, "a")
    _panel_letter(ax_b, "b")
    for _a in (ax, ax_b):
        sns.despine(ax=_a, top=True, right=True)
    fig.tight_layout()
    return fig, (ax, ax_b)


def main() -> None:
    fig, _ = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"))


if __name__ == "__main__":
    main()
