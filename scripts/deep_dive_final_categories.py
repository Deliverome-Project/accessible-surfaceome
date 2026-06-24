"""Deep-dive final categorization — distribution of the ~5k surface candidates
across canonical / likely / cell-state-induced / cell-type-restricted /
below-threshold buckets after the v2 deep-dive sweep.

**MOCK — counts are placeholder estimates** pending the full sweep
(``scripts/surfaceome_v2_annotate.py`` over the ~5k Sonnet-triage YES
cohort). Bucket boundaries follow the closed-enum families in
``src/accessible_surfaceome/tools/_shared/models.py``:

  • canonical = ``filters.surface_call_reason`` ∈ ``_YES_REASONS``
    (classical_surface_receptor / multipass_with_exposed_loops / gpi_anchored /
    extracellular_face_protein / stable_complex_partner)
  • likely    = soft-contextual ``_CONTEXTUAL_REASONS``
    (stable_surface_attachment / lysosomal_exocytosis / dual_localization)
  • cell_state = ``surface_call_reason == 'cell_state_induced'``, BROKEN OUT
    by ``filters.induction_trigger`` ∈ ``InductionTrigger``
    (oncogenic / immune / stress_hypoxia / cell_death / infection / other)
  • cell_type_restricted = ``surface_call_reason == 'tissue_restricted_surface'``
  • below_threshold = ``_NO_REASONS``
    (cytoplasmic / nuclear / mitochondrial_internal / endomembrane_resident /
    secreted_only / nuclear_envelope / pmhc_only_intracellular)

When the sweep lands, swap ``_PLACEHOLDER_COUNTS`` for a public-D1
``surface_annotation`` SELECT over ``annotation_json`` (or read directly
from ``viewer/public/data/surfaceome/*.json``).

# Reproduction:
#   Public gist (reader-side standalone, PyPA inline-script-metadata deps):
#   https://gist.github.com/beccajcarlson/c2441f8d0314c5524463bc85a3e86612
#   Reader-side mirror script:
#   data/analysis/figures/make_deep_dive_final_categories.py.

Run:
    uv run python scripts/deep_dive_final_categories.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import (
    COLORS,
    save_figure,
    setup_plotting_style,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data/analysis/figures"
SLUG = "deep_dive_final_categories"
GIST_URL = "https://gist.github.com/beccajcarlson/c2441f8d0314c5524463bc85a3e86612"

# ── MOCK placeholder counts (sum ≈ 5,000) ────────────────────────────────
# Proportions are eyeballed from the 14 committed deep-dive records under
# viewer/public/data/surfaceome/ + typical surfaceome literature. SWAP for
# real D1 counts when the v2 sweep completes.
_PLACEHOLDER_CANONICAL = 2_900       # _YES_REASONS bucket
_PLACEHOLDER_LIKELY = 700            # _CONTEXTUAL_REASONS (soft YES) bucket
_PLACEHOLDER_CELL_STATE_BY_TRIGGER = {
    "oncogenic":      230,
    "immune":         140,
    "stress_hypoxia":  80,
    "cell_death":      60,
    "infection":       30,
    "other":           10,
}
_PLACEHOLDER_CELL_TYPE_RESTRICTED = 450
_PLACEHOLDER_BELOW_THRESHOLD = 400   # _NO_REASONS bucket

# Brand palette — follow the existing convention from
# scripts/zero_db_rescues_by_triage.py:
#   YES bucket  → green/teal family ("definite surface")
#   CONTEXTUAL  → amber family       ("state/lineage dependent")
# Cell-type-restricted gets maroon (the brand primary) so it pops off the
# cell-state amber stack. Below-threshold is muted neutral.
_COLOR_CANONICAL = "#2E7A55"   # success green
_COLOR_LIKELY = "#3D6B60"      # teal-mid
_COLOR_CELL_TYPE = "#BC3C4C"   # maroon-light
_COLOR_BELOW = "#9C8C88"       # lifted neutral (more readable than ink-grey)
# Amber sequential ramp for the cell-state stack — dark → light = most → least
# common trigger. Matches the SEQUENTIAL_PALETTES["amber"] family.
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
    "below_threshold":      "below\nthreshold",
}


def _make_counts() -> dict[str, int | dict[str, int]]:
    return {
        "canonical":            _PLACEHOLDER_CANONICAL,
        "likely":               _PLACEHOLDER_LIKELY,
        "cell_state":           dict(_PLACEHOLDER_CELL_STATE_BY_TRIGGER),
        "cell_type_restricted": _PLACEHOLDER_CELL_TYPE_RESTRICTED,
        "below_threshold":      _PLACEHOLDER_BELOW_THRESHOLD,
    }


def _bar_total(counts: dict, key: str) -> int:
    v = counts[key]
    if isinstance(v, dict):
        return sum(v.values())
    return int(v)


def make_plot() -> tuple[plt.Figure, plt.Axes]:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    # Brand-style-v3 font sizes (mirror parity). The gist mirror at
    # data/analysis/figures/make_deep_dive_final_categories.py sets these
    # inline; this canonical script applies them via rcParams so its
    # render matches the published gist. See CLAUDE.md "Canonical
    # generator vs gist mirror" + tests/test_figure_canonical_mirror_sync.py.
    plt.rcParams.update({
        "font.size": 20, "axes.labelsize": 20, "axes.titlesize": 0,
        "xtick.labelsize": 20, "ytick.labelsize": 20, "legend.fontsize": 20,
    })
    counts = _make_counts()
    categories = list(_CATEGORY_LABELS.keys())
    totals = [_bar_total(counts, c) for c in categories]
    cohort_n = sum(totals)

    fig, ax = plt.subplots(figsize=(13, 8))

    x = list(range(len(categories)))
    bar_width = 0.72

    # 1) Solid bars for canonical / likely / cell-type-restricted / below-threshold
    solid_color = {
        "canonical":            _COLOR_CANONICAL,
        "likely":               _COLOR_LIKELY,
        "cell_type_restricted": _COLOR_CELL_TYPE,
        "below_threshold":      _COLOR_BELOW,
    }
    for i, key in enumerate(categories):
        if key == "cell_state":
            continue
        ax.bar(
            i,
            totals[i],
            width=bar_width,
            color=solid_color[key],
            edgecolor="none",
        )

    # 2) Stacked bar for cell-state, bottom-to-top in _CELL_STATE_STACK_ORDER
    i_cs = categories.index("cell_state")
    bottom = 0.0
    cs_dict = counts["cell_state"]
    assert isinstance(cs_dict, dict)
    legend_handles = []
    legend_labels = []
    for trigger in _CELL_STATE_STACK_ORDER:
        n = cs_dict.get(trigger, 0)
        if n <= 0:
            continue
        color = _CELL_STATE_PALETTE[trigger]
        rect = ax.bar(
            i_cs,
            n,
            width=bar_width,
            bottom=bottom,
            color=color,
            edgecolor="none",
        )
        bottom += n
        legend_handles.append(rect[0])
        legend_labels.append(f"{trigger.replace('_', ' ')}  ({n})")

    # 3) Count above each bar
    y_max = max(totals)
    label_pad = y_max * 0.025
    for i, key in enumerate(categories):
        n = totals[i]
        ax.text(
            i,
            n + label_pad,
            f"{n:,}",
            ha="center",
            va="bottom",
            fontsize=18,
            fontweight="bold",
            color=COLORS["dark"],
        )

    # 4) X-axis
    ax.set_xticks(x)
    ax.set_xticklabels([_CATEGORY_LABELS[c] for c in categories])

    # 5) Y-axis — wrap per figure_ylabel_wrap memory (single-line >22 chars too tight at labelsize 16)
    ax.set_ylabel("Proteins in\ndeep-dive cohort")
    ax.set_ylim(0, y_max * 1.16)

    # 6) Cell-state legend, anchored under the cell-state bar
    ax.legend(
        legend_handles,
        legend_labels,
        title="cell-state trigger",
        loc="upper center",
        bbox_to_anchor=(0.52, -0.16),
        ncols=3,
        frameon=False,
        fontsize=12,
        title_fontsize=13,
    )

    # 7) Footer annotation — MOCK callout + cohort n, attached to the figure
    #    so it sits below the legend without being clipped.
    fig.text(
        0.5,
        -0.05,
        f"MOCK — placeholder counts pending the v2 deep-dive sweep "
        f"(cohort n = {cohort_n:,})",
        ha="center",
        va="top",
        fontsize=13,
        style="italic",
        color=COLORS["neutral"],
    )

    sns.despine(ax=ax, top=True, right=True)
    fig.tight_layout()
    return fig, ax


def main() -> None:
    fig, _ = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"), gist_url=GIST_URL)


if __name__ == "__main__":
    main()
