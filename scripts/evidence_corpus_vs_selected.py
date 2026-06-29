"""Papers found vs papers selected as evidence per gene, colored by
agent ``evidence_grade`` verdict (MOCK supplementary).

For each gene in the deep-dive cohort, the literature pipeline returns:

  * **Papers found** — the size of the per-gene candidate corpus from
    discovery (EuropePMC + PubTator NER + gene2pubmed; median 234.5
    papers per gene on the 100-gene audit, range ~50 for orphan genes
    to ~400 for well-studied receptors).
  * **Papers selected as evidence** — the subset the deep-dive's
    `plan_trim_select` step ranks high-enough to feed into the block
    builders for full-text claim extraction. The selection ratio
    decreases with corpus size — more candidate papers means more
    noise, not proportionally more relevant evidence.

The agent then assigns each gene's evidence base an ``evidence_grade``
verdict from the closed enum:

  * ``direct_multi_method``     — multiple independent assay types
  * ``direct_single_method``    — direct surface evidence from one assay
  * ``supportive_but_indirect`` — circumstantial / topology-based
  * ``weak``                    — sparse or low-quality evidence

This figure shows how the verdict tracks the two corpus axes — well-
evidenced surface targets pile up in the upper-right (rich corpus +
rich selection → multi-method verdict), while weak-evidence calls
cluster in the lower-left.

**MOCK** — counts are synthesized from the production-pipeline
distributional shape pending the full v2 deep-dive sweep. Replace
``_synthesize_mock_data()`` with a public-D1 SELECT once
``deep_dive_run.evidence_grade`` is populated genome-wide:

    SELECT gene_symbol,
           json_extract(annotation_json, '$.evidence_count')         AS papers_found,
           json_extract(annotation_json, '$.primary_evidence_count') AS papers_selected,
           json_extract(annotation_json, '$.filters.evidence_grade') AS verdict
    FROM surface_annotation;

Run:
    uv run python scripts/evidence_corpus_vs_selected.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import (
    COLORS,
    save_figure,
    setup_plotting_style,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data/analysis/figures"
SLUG = "evidence_corpus_vs_selected"

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

# Mock target ~ deep-dive cohort scale; reproducible via fixed seed
# so the placeholder figure doesn't drift between renders.
_N_MOCK_GENES = 220
_RANDOM_SEED = 42


def _synthesize_mock_data() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate per-gene (papers_found, papers_selected, verdict) tuples
    with a plausible joint shape:

      • papers_found ~ Lognormal(μ=ln 234, σ=0.6), clipped to [25, 550]
        — anchored on the 234.5 median + ~50–400 range from the
        methods-text 100-gene audit.
      • selection rate decreases with log(found) — agents extract fewer
        papers per gene as the corpus grows (more noise to filter).
      • verdict assigned probabilistically as a function of
        log(selected) so higher-evidence genes tilt toward
        direct_multi_method; lower-evidence genes tilt toward weak.

    Returns three same-length arrays."""
    rng = np.random.default_rng(_RANDOM_SEED)
    n = _N_MOCK_GENES

    # Papers found: lognormal centred at 234 (audit median)
    papers_found = np.clip(
        rng.lognormal(mean=np.log(234), sigma=0.6, size=n),
        25, 550,
    )

    # Selection rate: shrinks with corpus size; baseline 12% scaled by
    # ln(75)/ln(found) so a 75-paper gene keeps ~12%, a 400-paper gene
    # selects ~6%. Add gaussian noise on top.
    base_rate = 0.12 * np.log(75) / np.log(papers_found)
    noise = rng.normal(0.0, 0.025, size=n)
    selection_rate = np.clip(base_rate + noise, 0.01, 0.30)
    papers_selected = np.clip(np.round(papers_found * selection_rate), 2, 50).astype(int)
    papers_found = np.round(papers_found).astype(int)

    # Verdict: cumulative thresholds on a latent quality score that
    # is mostly papers_selected with a small contribution from
    # selection rate (so high-selection-rate small-corpus genes can
    # also reach a high verdict).
    quality = np.log1p(papers_selected) + 1.5 * selection_rate
    # Empirical thresholds chosen so each bucket gets a reasonable
    # share of the 220 mock genes (~45% direct_multi/single, ~35%
    # supportive, ~20% weak) — mirrors the v1 sample shape.
    verdicts = np.empty(n, dtype=object)
    q_noise = rng.normal(0.0, 0.22, size=n)
    q = quality + q_noise
    # Thresholds chosen to land target shares ~ 30/25/25/20 across
    # direct_multi / direct_single / supportive / weak. The previous
    # cutoffs (3.2/2.6/2.0) pushed too many genes into the top two
    # buckets and left weak nearly empty.
    verdicts[q >= 3.45] = "direct_multi_method"
    verdicts[(q >= 3.10) & (q < 3.45)] = "direct_single_method"
    verdicts[(q >= 2.75) & (q < 3.10)] = "supportive_but_indirect"
    verdicts[q < 2.75] = "weak"

    return papers_found, papers_selected, verdicts


def make_plot() -> tuple[plt.Figure, plt.Axes]:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    plt.rcParams.update({
        "font.size": 18, "axes.labelsize": 20, "axes.titlesize": 0,
        "xtick.labelsize": 16, "ytick.labelsize": 16, "legend.fontsize": 14,
    })
    found, selected, verdicts = _synthesize_mock_data()

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
        f"MOCK — synthesized from the 100-gene audit shape "
        f"(median {int(np.median(found))} papers/gene, "
        f"median {int(np.median(selected))} selected); n={_N_MOCK_GENES} genes",
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
