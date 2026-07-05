# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``deep_dive_record_richness.{pdf,png}`` — a 5-panel violin of
per-record richness across the deep-dive cohort, faceted by deep-dive tier.

**Real data.** Each panel renders the real per-gene distribution along one
"richness" axis a reader would care about after opening a gene page. Every panel
is faceted by the deep-dive **tier** (canonical / likely / low / no):

  a. Papers found        — discovery-corpus size. Tiers: canonical, likely,
                           low, no.
  b. Papers selected     — unique papers read full-text into the evidence list.
                           Tiers: canonical, likely, low, no.
  c. Papers with EC      — selected papers carrying an extracellular /
                           surface-method tag. Tiers: canonical, likely, low.
  d. LLM filters w/ evid — how many of the ~20 LLM filter facets carry a
                           positive/non-default (evidence-backed) call; the LLM
                           analogue of e. Tiers: canonical, likely, low.
  e. Deterministic feats — how many of the seven deterministic features are
                           populated (0–7). Tiers: canonical, likely, low.

Each violin is the real distribution of that tier's genes (median line inside;
faint real-value point strip overlaid). Panels c–e drop the "no" tier since
non-surface proteins carry little extracellular evidence by definition; the
``uncertain`` tier (n=9) is dropped everywhere as too small to plot.

PRELIMINARY — 1,175 of ~5,128 swept, pre-QA-fix.

Standalone — ``uv run make_deep_dive_record_richness.py``.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"  # pin to a commit SHA at publication for immutable citation
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
# Single per-figure TSV: one row per deep-dived gene, carrying the five real
# per-gene axes + the deep-dive `tier`. Produced by
# ``scripts/build_figure_tsvs.py``. Gist bundles this TSV next to the script;
# the figure reads ONLY from the sibling — no other URLs.
DATA_TSV = f"{BASE}/data/processed/figures/deep_dive_record_richness.tsv"

# Published reproduction gist (embedded into output PNG Source / PDF
# Subject metadata — mirrors save_figure in _plotting_config.py).
GIST_URL = "https://gist.github.com/beccajcarlson/35119ea2bca9585c7245d247334b8c01"

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

# Tier colors — MUST match Fig 5. canonical=green, likely=teal, low=amber,
# no=muted warm-grey. `uncertain` is dropped everywhere (n=9, too small).
TIER_COLORS = {
    "canonical": "#2E7A55",
    "likely":    "#3D6B60",
    "low":       "#C99A5B",
    "no":        "#9C8C88",
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
        # Per-panel description renders as a TITLE (axes.titlesize)
        # rather than the x-axis label slot, mirroring the canonical.
        "font.size": 18, "axes.labelsize": 20, "axes.titlesize": 16,
        "axes.titleweight": "semibold", "axes.titlepad": 12,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": BRAND_GRID, "axes.labelcolor": BRAND_INK,
        "axes.facecolor": "none",
        "text.color": BRAND_INK,
        "grid.alpha": 0.35, "grid.linestyle": "-", "grid.linewidth": 0.7,
        "grid.color": BRAND_GRID,
        "xtick.labelsize": 14, "ytick.labelsize": 18, "legend.fontsize": 14,
        "xtick.color": BRAND_INK, "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "patch.edgecolor": "none", "patch.linewidth": 0.0,
    })


# Five-panel specs: (tsv_key, subtitle, tiers-to-show).
# Panels a/b keep the "no" tier; c/d/e drop it (non-surface genes carry
# little extracellular evidence by definition).
_FOUR = ["canonical", "likely", "low", "no"]
_THREE = ["canonical", "likely", "low"]
PANELS = [
    ("papers_found",       "Papers found (discovery corpus)",          _FOUR),
    ("papers_selected",    "Papers selected (into evidence list)",     _FOUR),
    ("papers_with_ec",     "Papers with extracellular evidence",       _THREE),
    ("n_filters_evidence", "LLM filters with evidence",                _THREE),
    ("n_det_features",     "Deterministic features populated (0-7)",   _THREE),
]

FIGSIZE = (25, 6.5)


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


def _draw_panel(ax: plt.Axes, data: pd.DataFrame, key: str,
                tiers: list[str]) -> None:
    """Real violins, one per tier, in tier colors. Median line inside each
    violin + a faint real-value point strip so the reader sees the actual n."""
    sub = data[data["tier"].isin(tiers)].copy()
    sub = sub[["tier", key]].dropna()
    sub[key] = sub[key].astype(float)

    palette = {t: TIER_COLORS[t] for t in tiers}
    sns.violinplot(
        data=sub, x="tier", y=key, order=tiers, hue="tier",
        hue_order=tiers, palette=palette, legend=False,
        inner="quartile", cut=0, density_norm="width",
        linewidth=1.2, saturation=1.0, ax=ax,
    )
    # Soften the violin bodies + recolor the inner quartile lines so the
    # median (middle line) reads as a solid tick and the quartiles as faint.
    for coll in ax.collections:
        coll.set_alpha(0.35)
    for line in ax.lines:
        line.set_color(BRAND_INK)
        line.set_alpha(0.9)
        line.set_linewidth(1.4)

    # Faint real-value point strip on top so the actual per-tier n is visible.
    sns.stripplot(
        data=sub, x="tier", y=key, order=tiers, hue="tier",
        hue_order=tiers, palette=palette, legend=False,
        size=2.2, alpha=0.28, jitter=0.18, ax=ax,
    )

    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.margins(y=0.04)


def main() -> None:
    _apply_brand_style()
    data = _fetch_tsv(DATA_TSV)
    n_real_total = len(data)

    fig, axes = plt.subplots(1, 5, figsize=FIGSIZE)
    panel_letters = ["a", "b", "c", "d", "e"]

    for idx, (ax, (key, subtitle, tiers)) in enumerate(
        zip(axes, PANELS, strict=True)
    ):
        _draw_panel(ax, data, key, tiers)

        # setup_plotting_style monkey-patches set_title/suptitle to NO-OPS, so
        # render the per-panel subtitle as centered text above each panel.
        ax.text(
            0.5, 1.03, subtitle, transform=ax.transAxes,
            ha="center", va="bottom", fontsize=15, fontweight="semibold",
            color=BRAND_INK,
        )

        # Subpanel letter (lowercase, ExtraBold) at upper-left, baseline-aligned
        ax.text(
            -0.14, 1.03, panel_letters[idx],
            transform=ax.transAxes, ha="left", va="bottom",
            fontsize=22, fontweight=800, color=BRAND_INK,
        )

        sns.despine(ax=ax, top=True, right=True)

    # suptitle is monkey-patched to a no-op; use fig.text for the figure title.
    fig.text(
        0.5, 0.995, "Deep-dive record richness scales with confidence tier",
        ha="center", va="top", fontsize=18, fontweight="semibold",
        color=BRAND_INK,
    )

    fig.text(
        0.5, 0.02,
        f"Real per-gene distributions from the {n_real_total} deep dives, faceted "
        f"by deep-dive tier (median line inside each violin; faint dots = the real "
        f"per-tier values). Panels a/b keep the 'no' tier; panels c-e drop it since "
        f"non-surface proteins carry little extracellular evidence by definition. "
        f"The 'uncertain' tier (n=9) is dropped everywhere as too small to plot. "
        f"PRELIMINARY - {n_real_total} of ~5,128 swept, pre-QA-fix.",
        ha="center", va="bottom", fontsize=10, style="italic",
        color=BRAND_NEUTRAL, wrap=True,
    )

    fig.tight_layout(rect=(0, 0.05, 1, 0.96))

    out_pdf = Path("deep_dive_record_richness.pdf")
    out_png = Path("deep_dive_record_richness.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=600, metadata={"Source": GIST_URL})
    print(f"Wrote {out_pdf} + {out_png}  (n_real total = {n_real_total})")


if __name__ == "__main__":
    main()
