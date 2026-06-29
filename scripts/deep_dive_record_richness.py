"""Deep-dive record richness across five axes (MOCK PLACEHOLDER).

Five-panel faceted violin showing the per-record distribution along
the axes that characterise *how much information* a single deep dive
captures for a gene. The aim is to communicate *richness* — a reader
clicking any gene should expect roughly this much per axis.

The five axes
-------------
1. **Papers found** — the discovery-corpus size (EuropePMC + PubTator
   NER + gene2pubmed union, dedup by pmid). On the 14 already-published
   records this defaults to 0 because ``n_papers_found`` landed in
   schema 2.14.0 *after* those records were annotated — we mock the
   distribution from the methods section's documented stats (median
   234.5, range ~50–400) pending a discover-only rerun.

2. **Papers selected** — unique papers in the evidence list
   (``len({span.source.source_id for ev in evidence})``). Real values
   for all 14 records (backfilled in PR #90).

3. **Papers with extracellular-evidence** — subset of (2) where the
   agent extracted *primary*-tier evidence with an experimental
   surface-method tag (flow cytometry, immunofluorescence,
   immunohistochemistry, mass-spec surfaceome, live-cell surface
   labeling). Real values from the existing 14 records.

4. **Filters carrying evidence** — count of populated catalog filter
   fields out of 24 (14 enums + 10 booleans the catalog UI surfaces).
   Real, near-saturated (~22 of 24 today) because most filter values
   are mandatory in the schema; the under-24 cases are genes where
   an optional facet (e.g., ``primary_compartment``) wasn't
   confidently set.

5. **Deterministic features populated** — count of non-null
   deterministic-features sub-blocks out of 7 (canonical_topology,
   isoform_topologies, structure, orthologs, paralogs, surface_bind,
   homo_oligomerization). Real values; missing entries fall out of
   genes outside SURFACE-Bind coverage or without a Schweke homomer
   prediction.

Real values from the 14 existing records render as gray dots overlaid
on each violin. The violin itself is a *synthesised* 5000-draw fan
intended to communicate the *shape* a full-cohort distribution would
have — clearly marked MOCK so a reviewer never confuses the synthesis
with measured data. Panel-2/3/4/5 violins synthesise around the real
14-record mean ± std; panel-1 (papers_found) synthesises around the
methods-section stats.

Why violin?
-----------
Each axis has a very different scale (papers in the hundreds vs
boolean-counts ≤ 24) so a shared Y axis would compress the small
axes into the baseline. Five small per-panel violins (one Y axis
each) lets each distribution speak for itself.

Alternatives considered (kept available for future iteration):

  • **Sankey funnel** — papers_found → papers_selected → papers with
    EC evidence. Shows the agent's *filtering pipeline* visually but
    drops axes 4 and 5 (filters / deterministic features aren't on
    the funnel chain).
  • **Per-record richness table** — 14 rows × 5 columns, each cell a
    horizontal fill bar. Less aggregate, more "show me the actual
    records"; nice for an appendix companion view.

Run::

    uv run python scripts/deep_dive_record_richness.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import (
    COLORS,
    SEQUENTIAL_PALETTES,
    save_figure,
    setup_plotting_style,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data/analysis/figures"
SLUG = "deep_dive_record_richness"
SNAPSHOTS = ROOT / "viewer/public/data/surfaceome"

# Catalog facets we count "carrying evidence" against. Sourced from
# viewer/lib/deep-dive-fields.ts DD_ENUM_FIELDS + DD_BOOL_FIELDS.
DD_ENUM_FIELDS = {
    "surface_accessibility", "confidence", "state_dependence",
    "surface_call_reason", "subcategory", "llm_family",
    "evidence_grade", "evidence_density", "ecd_accessibility_class",
    "expression_level", "expression_breadth", "surface_specificity",
    "co_receptor_dependency", "primary_compartment",
}
DD_BOOL_FIELDS = {
    "has_known_ligand", "low_endogenous_expression",
    "overexpression_surface_localization_observed",
    "has_shed_form", "has_secreted_form", "has_epitope_masking",
    "has_restricted_subdomain", "n_term_extracellular",
    "c_term_extracellular", "tumor_associated",
}
TOTAL_FILTERS = len(DD_ENUM_FIELDS) + len(DD_BOOL_FIELDS)  # 24

# Experimental surface-evidence types (Evidence.evidence_type enum,
# primary tier only). Counted toward axis 3.
EC_EVIDENCE_TYPES = {
    "flow_cytometry", "immunofluorescence", "immunohistochemistry",
    "mass_spec_surfaceome", "live_cell_surface_labeling",
}

# Deterministic-features sub-blocks. From models.py DeterministicFeatures.
DET_FIELDS = [
    "canonical_topology", "isoform_topologies", "structure",
    "orthologs", "paralogs", "surface_bind", "homo_oligomerization",
]
N_DET = len(DET_FIELDS)

# Five panel specs: (axis_key, display label, denom or None, color)
PANEL_TEAL = SEQUENTIAL_PALETTES["teal"][2]    # rich teal
PANEL_AMBER = SEQUENTIAL_PALETTES["amber"][3]  # bright amber
PANEL_MAROON = SEQUENTIAL_PALETTES["maroon"][3]
PANEL_LAVENDER = SEQUENTIAL_PALETTES["lavender"][3]
PANEL_TEAL_DEEP = SEQUENTIAL_PALETTES["teal"][1]

PANELS = [
    ("papers_found",       "Papers found\n(discovery corpus)",       None,           PANEL_AMBER,   True),   # mocked
    ("papers_selected",    "Papers selected\n(into evidence list)",  None,           PANEL_TEAL,    False),
    ("papers_with_ec",     "Papers with\nextracellular evidence",    None,           PANEL_MAROON,  False),
    ("n_filters_evidence", "Filters carrying\nevidence (of 24)",     TOTAL_FILTERS,  PANEL_LAVENDER, False),
    ("n_det_features",     "Deterministic\nfeatures (of 7)",         N_DET,           PANEL_TEAL_DEEP, False),
]

# Synth size for the violin fan ("what would 5000 deep dives look like?").
N_SYNTH = 5_000

# Methods-section documented stats for papers_found (only mocked axis).
# Reference: median 234.5, range ~50 (orphan genes) to ~400
# (well-studied receptors), from the literature-retrieval methods.
PAPERS_FOUND_MEDIAN = 234.5
PAPERS_FOUND_LO = 50
PAPERS_FOUND_HI = 400


def _load_real_values() -> pd.DataFrame:
    """Walk the 14 published snapshots and compute the 5 axes per gene.
    ``papers_found`` is left as NaN — the field exists in schema 2.14.0
    but the records pre-date it. Axes 2-5 are computed from the
    existing evidence + filters + deterministic_features blocks."""
    rows = []
    for path in sorted(SNAPSHOTS.glob("*.json")):
        rec = json.loads(path.read_text())
        sym = rec.get("gene_symbol") or path.stem
        filters = rec.get("filters") or {}
        det = rec.get("deterministic_features") or {}
        evidence = rec.get("evidence") or []
        # Skip records without an evidence list (stubs / draft snapshots)
        if not evidence:
            continue
        n_selected = filters.get("n_papers_selected") or 0
        ec_ids: set[str] = set()
        for ev in evidence:
            if ev.get("evidence_tier") != "primary":
                continue
            if ev.get("evidence_type") not in EC_EVIDENCE_TYPES:
                continue
            for span in ev.get("spans") or []:
                sid = (span.get("source") or {}).get("source_id")
                if sid:
                    ec_ids.add(sid)
        n_filt_with_data = sum(
            1 for k in DD_ENUM_FIELDS
            if filters.get(k) not in (None, "", "unknown", "none")
        ) + sum(
            1 for k in DD_BOOL_FIELDS
            if isinstance(filters.get(k), bool)
        )
        n_det = sum(
            1 for k in DET_FIELDS
            if det.get(k) not in (None, {}, [])
        )
        rows.append({
            "gene_symbol": sym,
            "papers_found": np.nan,  # backfill follow-up
            "papers_selected": n_selected,
            "papers_with_ec": len(ec_ids),
            "n_filters_evidence": n_filt_with_data,
            "n_det_features": n_det,
        })
    return pd.DataFrame(rows)


def _synth_papers_found(rng: np.random.Generator) -> np.ndarray:
    """Lognormal fan around the methods-section stats (median 234.5,
    range ~50–400). Clipped so the violin doesn't grow a long unphysical
    upper tail."""
    mu = np.log(PAPERS_FOUND_MEDIAN)
    # Pick sigma so the 5th-95th lies near [LO, HI]: ln(LO)-ln(MEDIAN) ≈
    # -1.6σ for a 5th-percentile-at-LO model.
    sigma = (np.log(PAPERS_FOUND_HI) - np.log(PAPERS_FOUND_LO)) / 3.3
    return np.clip(rng.lognormal(mu, sigma, N_SYNTH), 20, 700)


def _synth_around_real(real: np.ndarray, *, lo: float, hi: float,
                       rng: np.random.Generator) -> np.ndarray:
    """Synthesise an N_SYNTH-sized fan around the real values: keep
    the real mean/std, add Gaussian noise + clip to [lo, hi]. With
    n=14 the empirical std is noisy, so we floor it at 15% of the mean
    so the violin doesn't collapse to a flat line on near-saturated
    axes (filters_with_evidence varies only 21–23 of 24)."""
    if len(real) == 0:
        return np.zeros(N_SYNTH)
    m = float(np.nanmean(real))
    s = max(float(np.nanstd(real, ddof=1)), m * 0.15)
    fan = rng.normal(m, s, N_SYNTH)
    return np.clip(fan, lo, hi)


def make_plot() -> tuple[plt.Figure, list[plt.Axes]]:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    plt.rcParams.update({
        "font.size": 14, "axes.labelsize": 14, "axes.titlesize": 0,
        "xtick.labelsize": 12, "ytick.labelsize": 13, "legend.fontsize": 12,
    })

    real_df = _load_real_values()
    n_real = len(real_df)
    rng = np.random.default_rng(seed=42)  # deterministic mock

    fig, axes = plt.subplots(1, 5, figsize=(20, 6.5))

    panel_letters = ["a", "b", "c", "d", "e"]
    for idx, (ax, (key, label, denom, color, is_mocked)) in enumerate(
        zip(axes, PANELS, strict=True)
    ):
        real_vals = real_df[key].to_numpy()
        real_clean = real_vals[~np.isnan(real_vals)]

        # Build the synth fan
        if key == "papers_found":
            synth = _synth_papers_found(rng)
            lo, hi = 0, max(700, synth.max() * 1.05)
        else:
            cap = denom if denom is not None else max(real_clean.max() * 1.5, 1)
            synth = _synth_around_real(real_clean, lo=0, hi=cap, rng=rng)
            lo = 0
            hi = max(cap * 1.08, synth.max() * 1.08)

        # Violin (synth) — outline only, hint that it's the fan
        parts = ax.violinplot(
            [synth], positions=[0], widths=[0.7], showextrema=False,
            showmedians=False, showmeans=False,
        )
        for body in parts["bodies"]:
            body.set_facecolor(color)
            body.set_alpha(0.32)
            body.set_edgecolor(color)
            body.set_linewidth(1.4)

        # Median + IQR overlay on the synth
        q25, q50, q75 = np.percentile(synth, [25, 50, 75])
        ax.hlines(q50, -0.25, 0.25, colors=color, lw=2.0, zorder=4)
        ax.add_patch(mpatches.Rectangle(
            (-0.07, q25), 0.14, q75 - q25,
            facecolor=color, alpha=0.5, edgecolor=color, lw=0,
            zorder=3,
        ))

        # Real values overlay — jittered dots in dark ink so eye locks
        # onto measured rather than synthesised
        if len(real_clean):
            jx = rng.uniform(-0.22, 0.22, size=len(real_clean))
            ax.scatter(
                jx, real_clean, s=24, color=COLORS["dark"],
                edgecolor="white", linewidth=0.6, zorder=6,
                label=f"real records (n={len(real_clean)})",
            )

        ax.set_xticks([0])
        ax.set_xticklabels([label], fontsize=11, linespacing=1.3)
        ax.set_ylim(lo, hi)
        ax.set_xlim(-0.6, 0.6)

        # Mark the denominator line where applicable
        if denom is not None:
            ax.axhline(denom, color=COLORS["neutral"], lw=0.8,
                       ls="--", alpha=0.6, zorder=1)
            ax.text(0.55, denom, f" max = {denom}", va="center",
                    fontsize=10, color=COLORS["neutral"], ha="left")

        # Top-right marker for mocked axes; explicit "no real records
        # yet" callout when there's nothing to overlay (field landed in
        # schema 2.14.0 after the 14 records were annotated).
        if is_mocked:
            badge_text = "MOCK" if len(real_clean) else "MOCK"
            ax.text(
                0.97, 0.97, badge_text,
                transform=ax.transAxes, ha="right", va="top",
                fontsize=10, color=PANEL_AMBER, fontweight="bold",
                bbox={"boxstyle": "round,pad=0.3", "facecolor": "white",
                      "edgecolor": PANEL_AMBER, "lw": 1.0},
            )
            if not len(real_clean):
                ax.text(
                    0.5, 0.02,
                    "no real records yet —\nn_papers_found pending backfill",
                    transform=ax.transAxes, ha="center", va="bottom",
                    fontsize=9, color=COLORS["neutral"], style="italic",
                )

        # Subpanel letter (lowercase, ExtraBold) at upper-left — paper
        # convention from figure_subpanel_labels memory. Offset is
        # axes-transform; -0.30 / 1.08 clears the top y-tick label
        # comfortably on panel b (the 2-digit "50" tick previously
        # collided with "b" at the earlier -0.18 / 1.05 position).
        ax.text(
            -0.30, 1.08, panel_letters[idx],
            transform=ax.transAxes, ha="left", va="top",
            fontsize=22, fontweight=800, color=COLORS["dark"],
        )

        sns.despine(ax=ax, top=True, right=True)

    fig.suptitle(
        "Deep-dive records are dense across every axis",
        fontsize=18, fontweight="semibold",
        y=0.99, x=0.5, ha="center",
    )

    fig.text(
        0.5, 0.02,
        f"Each panel: per-gene distribution on one richness axis. "
        f"Dark dots = real values from the {n_real} published deep dives. "
        f"Violin shape + IQR box = synthesised {N_SYNTH:,}-draw fan extrapolating to a full cohort "
        f"(lognormal for papers_found around the methods-documented median 234.5 / range 50–400; "
        f"Gaussian around the empirical mean ± std (or 15%% mean, whichever larger) for the other axes). "
        f"MOCK pending the discover-only backfill for papers_found and the full cohort sweep.",
        ha="center", va="bottom", fontsize=10, style="italic",
        color=COLORS["neutral"], wrap=True,
    )

    fig.tight_layout(rect=(0, 0.05, 1, 0.96))
    return fig, list(axes)


def main() -> None:
    fig, _ = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"))


if __name__ == "__main__":
    main()
