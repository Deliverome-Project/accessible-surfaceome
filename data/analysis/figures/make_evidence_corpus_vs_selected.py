# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``evidence_corpus_vs_selected.{pdf,png}`` — per-gene papers
found (discovery corpus) vs papers selected as evidence, colored by the
agent's ``evidence_grade`` verdict (panel a), plus deep-dive surface tier
composition by papers-found bin (panel b).

**Real data.** Every point is a published deep-dive record with a real gene
symbol and real counts:

  * ``papers_found``     — discovery-corpus size (EuropePMC + PubTator +
    gene2pubmed union; ``n_papers_found``, median 220, range 1–395). Panel
    a's log axis starts at 25, so the 120 genes with fewer than 25 papers
    found are not drawn.
  * ``papers_selected``  — papers the agent read full-text and kept as
    evidence (``n_papers_selected``, median 10). The median selection rate
    rises from ~2% of the corpus for small corpora to ~8% at 200–300 papers
    found, then falls again for larger corpora.
  * ``evidence_grade``   ∈ {direct_multi_method, direct_single_method,
    supportive_but_indirect, conflicting, weak} — the agent's grade of the
    retained evidence base; tracks selection depth.

The bundled sibling TSV is produced by ``scripts/build_figure_tsvs.py``
(``build_evidence_corpus_vs_selected``) from the deep-dive export, so this
mirror renders the same dataset as the in-repo canonical.

One row per deep-dive record (5,332 genes; median 220 found, 10
selected); every record carries both counts.

Standalone — ``uv run make_evidence_corpus_vs_selected.py``.
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
BRANCH = "main"  # pin to a commit SHA at publication for immutable citation
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
# Single per-figure TSV: one row per published deep-dive record with
# (gene_symbol, uniprot_acc, papers_found, papers_selected, evidence_grade,
# tier). Real counts, produced by ``scripts/build_figure_tsvs.py``. Gist
# bundles this TSV next to the script; the figure reads ONLY from the
# sibling — no other URLs.
DATA_TSV = f"{BASE}/data/processed/figures/evidence_corpus_vs_selected.tsv"

# Published reproduction gist (embedded into output PNG Source / PDF
# Subject metadata — mirrors save_figure in _plotting_config.py).
GIST_URL = "https://gist.github.com/beccajcarlson/cb550702344d7626ee80804bc7f6c549"

# ──── Inline brand styling — sentinel: brand-style-v3 ────
# Mirrors src/accessible_surfaceome/audit/_plotting_config.py so the gist
# stays self-contained (no in-repo imports — Substack readers run it
# standalone). Kept in sync via tests/test_figure_canonical_mirror_sync.py.
BRAND_INK = "#1F1718"
BRAND_PALETTE = [
    "#BC3C4C",  # maroon-light
    "#3D6B60",  # teal-mid
    "#F4AA28",  # amber-bright
    "#8878C8",  # lavender-bright
    "#6E1428",  # maroon-dark
    "#7AAB9F",  # teal-light
]
BRAND_NEUTRAL = "#6F5D5A"
BRAND_GRID = "#E6DAD4"

# Verdict ordering = best → worst evidence quality (drives legend order
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
    """Inline equivalent of ``setup_plotting_style``. Sentinel: brand-style-v3."""
    _register_brand_fonts()
    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=1.0)
    plt.rcParams.update({
        "savefig.dpi": 600,
        "savefig.bbox": "tight",
        "figure.facecolor": "none",
        "savefig.facecolor": "none",
        "font.family": ["Manrope", "DejaVu Sans"],
        "font.sans-serif": ["Manrope", "Outfit", "DejaVu Sans", "Liberation Sans", "Arial"],
        "font.weight": "semibold",
        "font.size": 18,
        "axes.labelsize": 16,
        "axes.labelweight": "semibold",
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
        "xtick.labelsize": 14.5,
        "ytick.labelsize": 14.5,
        "xtick.color": BRAND_INK,
        "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "legend.fontsize": 14.5,
        "patch.edgecolor": "none",
        "patch.linewidth": 0.0,
    })


def _fetch_tsv(url: str) -> pd.DataFrame:
    """Bundled-only: the gist HEAD commit SHA is the SWHID for the
    whole reproduction unit (script + data + README), so we must
    never read a *different* TSV than what's bundled. Sibling-first
    (gist case); fall back to the in-repo TSV path (dev case). No
    network fetch — a missing sibling in a gist is a hard error."""
    sibling = Path(__file__).parent / Path(url).name
    if sibling.is_file():
        return pd.read_csv(sibling, sep="\t")
    local = Path(__file__).resolve().parents[3] / url[len(BASE) + 1:]
    if local.is_file():
        return pd.read_csv(local, sep="\t")
    raise FileNotFoundError(
        f"TSV not found at sibling ({sibling.name}) or local ({local}). "
        f"In a gist, the bundled TSV must sit next to this script."
    )


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
                        fontsize=13, color="white")
        bottom = [b + v for b, v in zip(bottom, vals, strict=True)]

    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{lab}\n(n={int(n_per[lab]):,})" for lab in _STRATA_LABELS])
    ax.set_xlabel("Papers found per gene  (discovery corpus)")
    ax.set_ylabel("Share of genes\nin stratum (%)")
    ax.set_ylim(0, 100)
    ax.grid(axis="x", visible=False)
    ax.legend(title="deep-dive surface tier", loc="upper center",
              bbox_to_anchor=(0.5, -0.23), ncol=5, frameon=False,
              title_fontsize=16)


def _panel_letter(ax, letter: str) -> None:
    ax.text(-0.02, 1.04, letter, transform=ax.transAxes, fontsize=21.5,
            fontweight=800, va="bottom", ha="right", color=BRAND_INK)


def main() -> None:
    _apply_brand_style()

    data = _fetch_tsv(DATA_TSV)
    found = data["papers_found"].to_numpy()
    selected = data["papers_selected"].to_numpy()
    verdicts = data["evidence_grade"].to_numpy()

    # Stacked (a over b): side by side, panel a's legend could not fit the
    # empty low-literature corner without covering points at print size.
    fig, (ax, ax_b) = plt.subplots(
        2, 1, figsize=(15, 13.5),
        gridspec_kw={"height_ratios": [1.15, 1.0], "hspace": 0.4},
    )

    # Plot in worst → best verdict order so the strong verdicts land on
    # top of the weak ones and aren't occluded.
    counts = Counter(verdicts.tolist())
    for verdict in reversed(VERDICT_ORDER):
        mask = verdicts == verdict
        ax.scatter(
            found[mask], selected[mask],
            s=55, alpha=0.32, edgecolor="white", linewidth=0.6,
            color=VERDICT_COLOR[verdict],
            label=f"{VERDICT_LABEL[verdict]}  (n={counts.get(verdict, 0)})",
            zorder=3 + VERDICT_ORDER.index(verdict),
        )


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
    leg_a = ax.legend(
        [handle_by_label[lbl] for lbl in ordered_labels if lbl in handle_by_label],
        [lbl for lbl in ordered_labels if lbl in handle_by_label],
        title="agent evidence_grade verdict",
        loc="upper left", bbox_to_anchor=(0.01, 0.99),
        frameon=False, title_fontsize=16,
    )
    for _h in leg_a.legend_handles:  # solid swatches despite translucent points
        _h.set_alpha(1.0)

    # Footer sits under panel a (which it describes), below its x-axis label.
    ax.text(
        0.5, -0.155,
        f"Real deep-dive records with a papers-found count: n={len(data):,} genes "
        f"(median {np.median(found):.0f} papers found, {np.median(selected):.0f} selected; "
        f"x-axis starts at 25).",
        ha="center", va="top", transform=ax.transAxes, fontsize=13, style="italic", color=BRAND_NEUTRAL,
    )

    _draw_tier_composition(ax_b, data)
    _panel_letter(ax, "a")
    _panel_letter(ax_b, "b")
    for _a in (ax, ax_b):
        sns.despine(ax=_a, top=True, right=True)
    fig.tight_layout()

    out_pdf = Path("evidence_corpus_vs_selected.pdf")
    out_png = Path("evidence_corpus_vs_selected.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=600, metadata={"Source": GIST_URL})
    print(f"Wrote {out_pdf} + {out_png}  (n = {len(data):,} genes)")


if __name__ == "__main__":
    main()
