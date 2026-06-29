# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``deep_dive_final_categories.{pdf,png}`` from the public repo.

**MOCK figure** — distribution of the ~5k surface candidates across
canonical / likely / cell-state-induced / cell-type-restricted / no
buckets after the v2 deep-dive sweep. Counts are
placeholder estimates pending the full sweep
(``scripts/surfaceome_v2_annotate.py`` over the ~5k Sonnet-triage YES
cohort). Bucket boundaries follow the closed-enum families in
``src/accessible_surfaceome/tools/_shared/models.py``; the cell-state
bar is broken out by ``InductionTrigger`` (oncogenic / immune /
stress_hypoxia / cell_death / infection / other).

Visual styling matches the in-repo `_plotting_config` (Deliverome
categorical palette + Manrope-when-available). Inlined so the gist
runs standalone — ``uv run make_deep_dive_final_categories.py``.
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
# distribution that drives the bar heights + the cell-state stack.
# Hand-authored MOCK pending the v2 deep-dive sweep. Produced by
# ``scripts/build_figure_tsvs.py``. Gist bundles this TSV next to
# the script; the figure reads ONLY from the sibling — no other URLs.
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


_COLOR_CANONICAL = "#2E7A55"
_COLOR_LIKELY = "#3D6B60"
_COLOR_CELL_TYPE = "#BC3C4C"
_COLOR_NO = "#9C8C88"
_CELL_STATE_STACK_ORDER = [
    "oncogenic",
    "immune",
    "stress_hypoxia",
    "cell_death",
    "infection",
    "other",
]
_CELL_STATE_PALETTE = {
    "oncogenic":      "#5A2608",
    "immune":         "#8C4210",
    "stress_hypoxia": "#C07830",
    "cell_death":     "#F4AA28",
    "infection":      "#F4C070",
    "other":          "#FAECD4",
}

_CATEGORY_LABELS = {
    "canonical":            "canonical\nsurface",
    "likely":               "likely\nsurface",
    "cell_state":           "cell-state\ninduced",
    "cell_type_restricted": "cell-type\nrestricted",
    "no":                   "no",
}


def main() -> None:
    _apply_brand_style()

    # Single bundled TSV with (category, subcategory, n_genes) rows.
    # cell_state gets multiple rows (one per induction trigger); the
    # other categories use subcategory='all' as their single row.
    data = _fetch_tsv(DATA_TSV)
    cs_rows = data[data["category"] == "cell_state"]
    cs_dict = dict(zip(cs_rows["subcategory"], cs_rows["n_genes"].astype(int)))

    def _scalar(cat: str) -> int:
        rows = data[data["category"] == cat]
        return int(rows["n_genes"].sum())

    counts: dict[str, int | dict[str, int]] = {
        "canonical":            _scalar("canonical"),
        "likely":               _scalar("likely"),
        "cell_state":           cs_dict,
        "cell_type_restricted": _scalar("cell_type_restricted"),
        "no":                   _scalar("no"),
    }
    categories = list(_CATEGORY_LABELS.keys())

    def _bar_total(key: str) -> int:
        v = counts[key]
        return sum(v.values()) if isinstance(v, dict) else int(v)

    totals = [_bar_total(c) for c in categories]
    cohort_n = sum(totals)

    fig, ax = plt.subplots(figsize=(13, 8))
    x = list(range(len(categories)))
    bar_width = 0.72

    solid_color = {
        "canonical":            _COLOR_CANONICAL,
        "likely":               _COLOR_LIKELY,
        "cell_type_restricted": _COLOR_CELL_TYPE,
        "no":      _COLOR_NO,
    }
    for i, key in enumerate(categories):
        if key == "cell_state":
            continue
        ax.bar(i, totals[i], width=bar_width, color=solid_color[key], edgecolor="none")

    i_cs = categories.index("cell_state")
    bottom = 0.0
    cs_dict = counts["cell_state"]
    assert isinstance(cs_dict, dict)
    legend_handles, legend_labels = [], []
    for trigger in _CELL_STATE_STACK_ORDER:
        n = cs_dict.get(trigger, 0)
        if n <= 0:
            continue
        color = _CELL_STATE_PALETTE[trigger]
        rect = ax.bar(i_cs, n, width=bar_width, bottom=bottom, color=color, edgecolor="none")
        bottom += n
        legend_handles.append(rect[0])
        legend_labels.append(f"{trigger.replace('_', ' ')}  ({n})")

    y_max = max(totals)
    label_pad = y_max * 0.025
    for i, _key in enumerate(categories):
        ax.text(
            i, totals[i] + label_pad, f"{totals[i]:,}",
            ha="center", va="bottom", fontsize=18, fontweight="bold", color=BRAND_INK,
        )

    ax.set_xticks(x)
    ax.set_xticklabels([_CATEGORY_LABELS[c] for c in categories])
    ax.set_ylabel("Proteins in\ndeep-dive cohort")
    ax.set_ylim(0, y_max * 1.16)

    ax.legend(
        legend_handles, legend_labels,
        title="cell-state trigger",
        loc="upper center", bbox_to_anchor=(0.52, -0.16),
        ncols=3, frameon=False, fontsize=12, title_fontsize=13,
    )

    fig.text(
        0.5, -0.05,
        f"MOCK — placeholder counts pending the v2 deep-dive sweep "
        f"(cohort n = {cohort_n:,})",
        ha="center", va="top", fontsize=13, style="italic", color=BRAND_NEUTRAL,
    )

    sns.despine(ax=ax, top=True, right=True)
    fig.tight_layout()

    out_pdf = Path("deep_dive_final_categories.pdf")
    out_png = Path("deep_dive_final_categories.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=600, metadata={"Source": GIST_URL})
    print(f"Wrote {out_pdf} + {out_png}  (cohort n = {cohort_n:,})")


if __name__ == "__main__":
    main()
