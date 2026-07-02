# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``deep_dive_final_categories.{pdf,png}`` from the public repo.

Two panels:

**a.** The deep-dive cohort placed on a five-tier confidence spectrum —
``canonical`` (strict gold-standard surface), ``likely`` (broader
passes-likely surface), then the below-likely genes split by the
deep-dive's tentative surface call: ``low`` (low/moderate accessibility but
weak evidence — maybe surface), ``uncertain``, and ``no`` (leaned
not-surface).

**b.** The composition of the ``likely`` tier: WHY those calls are only
likely, as a sorted horizontal bar chart over the cell-type + cell-state
reasons.

**PRELIMINARY** — ~1,175 of ~5,128 swept, pre-QA-fix. Nearly all
below-likely genes (low/uncertain/no) carry weak/conflicting evidence —
partly the pretrim-cap recall bug that deletes foundational literature — so
those three tiers are tentative leans on thin evidence, and the cell-state
``oncogenic`` share is inflated by tumour-associated over-flagging;
re-render after the full sweep + QA fixes.

Visual styling matches the in-repo `_plotting_config` (Deliverome
categorical palette + Manrope-when-available). Inlined so the gist runs
standalone — ``uv run make_deep_dive_final_categories.py``.
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
# Single per-figure TSV: (category, subcategory, n_genes) — the
# distribution that drives Panel-a tier heights + the Panel-b `likely`
# composition. Produced by ``scripts/build_figure_tsvs.py``. Gist bundles
# this TSV next to the script; the figure reads ONLY from the sibling —
# no other URLs.
DATA_TSV = f"{BASE}/data/processed/figures/deep_dive_final_categories.tsv"


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

# Published reproduction gist (embedded into output PNG Source / PDF
# Subject metadata — mirrors save_figure in _plotting_config.py).
GIST_URL = "https://gist.github.com/beccajcarlson/c2441f8d0314c5524463bc85a3e86612"

# ──── Inline brand styling — sentinel: brand-style-v3 ────
# Mirrors src/accessible_surfaceome/audit/_plotting_config.py so the gist
# stays self-contained (no in-repo imports — Substack readers run it
# standalone). Kept in sync via tests/test_figure_canonical_mirror_sync.py.
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
        "font.size": 20,
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
        "xtick.labelsize": 20,
        "ytick.labelsize": 20,
        "xtick.color": BRAND_INK,
        "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "legend.fontsize": 20,
        "patch.edgecolor": "none",
        "patch.linewidth": 0.0,
    })


# Panel-a tier colours — a confidence spectrum from surface (green) to
# not-surface (neutral).
_COLOR_CANONICAL = "#2E7A55"   # brand success green — strict tier
_COLOR_LIKELY = "#3D6B60"      # teal-mid — broader tier
_COLOR_LOW = "#C99A5B"         # amber-tan — low/moderate access, weak evidence
_COLOR_UNCERTAIN = "#C7BDB6"   # light warm grey — ambiguous
_COLOR_NO = "#9C8C88"          # lifted neutral — leaned not-surface

# Per-reason colour + label for the Panel-b breakdown of `likely`.
_LIKELY_COLORS: dict[str, str] = {
    "cell_type_restricted":      "#BC3C4C",
    "cell_state_oncogenic":      "#5A2608",
    "cell_state_immune":         "#8C4210",
    "cell_state_stress_hypoxia": "#C07830",
    "cell_state_cell_death":     "#E0952F",
    "cell_state_infection":      "#EFC178",
    "cell_state_other":          "#D8A24A",
    "likely_other":              "#3D6B60",
}
_LIKELY_LABELS: dict[str, str] = {
    "cell_type_restricted":      "cell-type restricted",
    "cell_state_oncogenic":      "cell-state · oncogenic",
    "cell_state_immune":         "cell-state · immune",
    "cell_state_stress_hypoxia": "cell-state · stress/hypoxia",
    "cell_state_cell_death":     "cell-state · cell death",
    "cell_state_infection":      "cell-state · infection",
    "cell_state_other":          "cell-state · other",
    "likely_other":              "other",
}


def _read(data: pd.DataFrame) -> dict[str, dict[str, int]]:
    """Aggregate the PER-GENE table (one row per deep-dived gene, browsable)
    into {category: {subcategory: n_genes}} — count rows."""
    out: dict[str, dict[str, int]] = {}
    for _, row in data.iterrows():
        sub = out.setdefault(str(row["category"]), {})
        key = str(row["subcategory"])
        sub[key] = sub.get(key, 0) + 1
    return out


def _panel_label(ax, letter: str) -> None:
    ax.text(-0.02, 1.06, letter, transform=ax.transAxes, fontsize=26,
            fontweight=800, va="bottom", ha="right", color=BRAND_INK)


def main() -> None:
    _apply_brand_style()

    # Single bundled TSV with (category, subcategory, n_genes) rows.
    # Panel a reads the per-tier totals; Panel b reads the `likely`
    # sub-buckets (one row per cell-type / cell-state reason).
    data = _read(_fetch_tsv(DATA_TSV))
    canon = sum(data.get("canonical", {}).values())
    likely = data.get("likely", {})
    likely_total = sum(likely.values())
    low_total = sum(data.get("low", {}).values())
    unc_total = sum(data.get("uncertain", {}).values())
    no_total = sum(data.get("no", {}).values())
    cohort_n = canon + likely_total + low_total + unc_total + no_total

    fig, (axA, axB) = plt.subplots(
        1, 2, figsize=(18, 7),
        gridspec_kw={"width_ratios": [1.25, 1.4], "wspace": 0.60},
    )

    # ── Panel a: the five-tier confidence spectrum ──────────────────────────
    tiers = [
        ("canonical\n(strict)", canon, _COLOR_CANONICAL),
        ("likely", likely_total, _COLOR_LIKELY),
        ("low", low_total, _COLOR_LOW),
        ("no", no_total, _COLOR_NO),
        ("uncertain", unc_total, _COLOR_UNCERTAIN),
    ]
    tier_max = max(t[1] for t in tiers)
    for i, (label, n, color) in enumerate(tiers):
        axA.bar(i, n, width=0.74, color=color, edgecolor="none")
        axA.text(i, n + tier_max * 0.02, f"{n:,}", ha="center", va="bottom",
                 fontsize=17, fontweight="bold", color=BRAND_INK)
    axA.set_xticks(range(len(tiers)))
    axA.set_xticklabels([t[0] for t in tiers], fontsize=15)
    axA.set_ylabel("Proteins in\ndeep-dive cohort")
    axA.set_ylim(0, tier_max * 1.16)
    axA.set_xlim(-0.6, len(tiers) - 0.4)
    sns.despine(ax=axA, top=True, right=True)
    _panel_label(axA, "a")

    # ── Panel b: composition of `likely`, sorted horizontal ─────────────────
    items = sorted(likely.items(), key=lambda kv: kv[1])  # ascending → biggest on top
    ys = list(range(len(items)))
    b_max = max((n for _, n in items), default=1)
    for y, (key, n) in zip(ys, items):
        axB.barh(y, n, color=_LIKELY_COLORS.get(key, "#999999"),
                 edgecolor="#1F1718", linewidth=0.4)
        axB.text(n + b_max * 0.012, y, f"{n:,}", va="center", ha="left",
                 fontsize=15, color=BRAND_INK)
    axB.set_yticks(ys)
    axB.set_yticklabels([_LIKELY_LABELS.get(k, k) for k, _ in items], fontsize=15)
    axB.set_xlabel("Proteins")
    axB.set_xlim(0, b_max * 1.14)
    axB.set_ylim(-0.6, len(items) - 0.4)
    axB.text(0.0, 1.06,
             f"Composition of the {likely_total:,} 'likely' calls — "
             f"by cell-type / cell-state reason",
             transform=axB.transAxes, fontsize=15, style="italic",
             color=BRAND_NEUTRAL, va="bottom", ha="left")
    sns.despine(ax=axB, top=True, right=True)
    _panel_label(axB, "b")

    fig.text(
        0.5, -0.02,
        f"PRELIMINARY — {cohort_n:,} of ~5,128 swept, pre-QA-fix "
        f"(low/uncertain/no are weak-evidence tentative leans, inflated by the "
        f"pretrim-cap bug; cell-state 'oncogenic' by tumour-associated over-flagging).",
        ha="center", va="top", fontsize=12, style="italic", color=BRAND_NEUTRAL,
    )

    fig.tight_layout()

    out_pdf = Path("deep_dive_final_categories.pdf")
    out_png = Path("deep_dive_final_categories.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=600, metadata={"Source": GIST_URL})
    print(f"Wrote {out_pdf} + {out_png}  (cohort n = {cohort_n:,})")


if __name__ == "__main__":
    main()
