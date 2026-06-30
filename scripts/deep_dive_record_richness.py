"""Deep-dive record richness across five axes, split by surface verdict (MOCK).

Five-panel violin showing the per-record distribution along the axes that
characterise *how much information* a single deep dive captures for a gene.
Panels are split by surface verdict so the reader can see which dimensions
genuinely separate calls vs. which look similar across the cohort. The aim
is to communicate *richness* — a reader clicking any gene should expect
roughly this much per axis.

The five axes
-------------
a. **Papers found** — the discovery-corpus size (EuropePMC + PubTator NER +
   gene2pubmed union, dedup by pmid). **Two violins** (no vs
   surface-yes-even-weak). Fully mocked because ``n_papers_found`` landed in
   schema 2.14.0 *after* the published records were annotated; pending a
   discover-only backfill. Each bucket's fan is drawn from a lognormal
   anchored on the methods-section stats (median 234.5, range ~50–400) with
   a bucket-specific offset so the two shapes are visually distinguishable.

b. **Papers selected** — unique papers in the evidence list
   (``len({span.source.source_id for ev in evidence})``). **Two violins**
   (no vs surface-yes-even-weak). Real per-gene values; each bucket's violin
   fan is synthesised around its own real mean / std.

c. **Papers with extracellular-evidence** — subset of (b) where the agent
   extracted *primary*-tier evidence with an experimental surface-method tag
   (flow cytometry, immunofluorescence, immunohistochemistry, mass-spec
   surfaceome, live-cell surface labeling). **Single violin, surface-yes
   only** — non-surface proteins have no extracellular evidence by
   definition, so the "no" bucket is filtered out.

d. **Filters carrying evidence** — count of populated catalog filter fields
   out of 24 (14 enums + 10 booleans the catalog UI surfaces). **Single
   violin, surface-yes only.** Near-saturated (~22 of 24) because most filter
   values are mandatory in the schema.

e. **Deterministic features populated** — count of non-null
   deterministic-features sub-blocks out of 7 (canonical_topology,
   isoform_topologies, structure, orthologs, paralogs, surface_bind,
   homo_oligomerization). **Single violin, surface-yes only.**

Real values from the published records render as dark dots overlaid on each
violin. The violin itself is a *synthesised* 5000-draw fan intended to
communicate the *shape* a full-cohort distribution would have — clearly
marked MOCK so a reviewer never confuses the synthesis with measured data.
Panel-b/c/d/e violins synthesise around the real per-bucket mean ± std;
panel-a (papers_found) synthesises around the methods-section stats.

"surface-yes-even-weak" = any deep-dive ``surface_accessibility`` value
except ``"no"`` (i.e. high / moderate / low / uncertain), bucketed in the
TSV as ``surface_verdict_bucket`` so panels a/b split and panels c/d/e
filter on it.

Why violin?
-----------
Each axis has a very different scale (papers in the hundreds vs
boolean-counts ≤ 24) so a shared Y axis would compress the small axes into
the baseline. Five small per-panel violins (one Y axis each) lets each
distribution speak for itself.

Data source
-----------
Reads the bundled per-figure TSV at
``data/processed/figures/deep_dive_record_richness.tsv`` (one row per
published deep-dive record: the 4 real per-gene axes + a
``surface_verdict_bucket`` label). ``papers_found`` is not in the TSV — it
is null on every record pending the discover-only backfill — so panel (a)
is synthesised entirely from the methods-section stats.

Run::

    uv run python scripts/deep_dive_record_richness.py

# Reproduction: https://gist.github.com/beccajcarlson/35119ea2bca9585c7245d247334b8c01
"""
from __future__ import annotations

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
# In-repo per-figure TSV: one row per published deep-dive record, with the
# 4 real per-gene axes + a `surface_verdict_bucket` label ('no' vs
# 'surface_yes') derived from `executive_summary.surface_accessibility`.
# papers_found is excluded — null on every record pending the discover-only
# backfill; panel (a) is synthesised from the methods-section stats.
DATA_TSV = ROOT / "data/processed/figures/deep_dive_record_richness.tsv"

# Published reproduction gist (embedded into output PNG Source / PDF Subject
# metadata via save_figure(gist_url=...)).
GIST_URL = "https://gist.github.com/beccajcarlson/35119ea2bca9585c7245d247334b8c01"

# Catalog facets we count "carrying evidence" against. Sourced from
# viewer/lib/deep-dive-fields.ts DD_ENUM_FIELDS + DD_BOOL_FIELDS.
# Kept for documentation of the denominator; the per-gene counts are
# precomputed in the TSV (n_filters_evidence column).
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

# Deterministic-features sub-blocks. From models.py DeterministicFeatures.
N_DET = 7

# Panel colors picked from the centralized SEQUENTIAL_PALETTES.
PANEL_TEAL = SEQUENTIAL_PALETTES["teal"][2]      # rich teal  -> #3D6B60
PANEL_AMBER = SEQUENTIAL_PALETTES["amber"][3]    # bright amber -> #F4AA28
PANEL_MAROON = SEQUENTIAL_PALETTES["maroon"][3]  # -> #BC3C4C
PANEL_LAVENDER = SEQUENTIAL_PALETTES["lavender"][3]  # -> #8878C8
PANEL_TEAL_DEEP = SEQUENTIAL_PALETTES["teal"][1]  # -> #244840

# Bucket hue for the "no" arm of the split panels (a, b). Muted warm-grey
# so the eye reads it as "absence of surface signal"; surface_yes gets the
# panel's accent color.
BUCKET_NO_COLOR = "#9C8C88"
BUCKET_ORDER = ["no", "surface_yes"]
BUCKET_LABEL = {
    "no":          "no",
    "surface_yes": "surface yes\n(even weak)",
}

# Five-panel specs: (tsv_key, display label, denom or None, accent_color,
#                    is_mocked, split_by_bucket)
# Panels a/b split by bucket (two side-by-side violins). Panels c/d/e
# filter to surface_yes only (single violin).
PANELS = [
    ("papers_found",       "Papers found\n(discovery corpus)",       None,           PANEL_AMBER,     True,  True),   # mocked
    ("papers_selected",    "Papers selected\n(into evidence list)",  None,           PANEL_TEAL,      False, True),
    ("papers_with_ec",     "Papers with\nextracellular evidence",    None,           PANEL_MAROON,    False, False),
    ("n_filters_evidence", "Filters carrying\nevidence (of 24)",     TOTAL_FILTERS,  PANEL_LAVENDER,  False, False),
    ("n_det_features",     "Deterministic\nfeatures (of 7)",         N_DET,          PANEL_TEAL_DEEP, False, False),
]

# Synth size for the violin fan ("what would 5000 deep dives look like?").
N_SYNTH = 5_000

# Methods-section documented stats for papers_found (only mocked axis):
# median 234.5, range ~50 (orphan genes) to ~400 (well-studied receptors).
# Panel (a) is split by bucket — we offset the "no" bucket to a smaller
# median (non-surface proteins are less-studied as surfaceome candidates,
# but still studied as their actual compartment proteins) so the two
# violins are visually distinguishable.
PAPERS_FOUND_MEDIAN_YES = 234.5
PAPERS_FOUND_MEDIAN_NO = 140.0
PAPERS_FOUND_LO = 50
PAPERS_FOUND_HI = 400


def _load_real_values() -> pd.DataFrame:
    """Read the bundled per-figure TSV (one row per published deep-dive
    record). Carries the 4 real per-gene axes + the
    ``surface_verdict_bucket`` label; ``papers_found`` is absent (null on
    every record pending backfill) and synthesised in panel (a)."""
    return pd.read_csv(DATA_TSV, sep="\t")


def _synth_papers_found(bucket: str, rng: np.random.Generator) -> np.ndarray:
    """Lognormal fan around the methods-section stats — separate medians
    per bucket so the two violins are visually distinguishable. Clipped so
    neither violin grows a long unphysical upper tail."""
    median = PAPERS_FOUND_MEDIAN_YES if bucket == "surface_yes" else PAPERS_FOUND_MEDIAN_NO
    mu = np.log(median)
    # Pick sigma so the 5th-95th lies near [LO, HI].
    sigma = (np.log(PAPERS_FOUND_HI) - np.log(PAPERS_FOUND_LO)) / 3.3
    return np.clip(rng.lognormal(mu, sigma, N_SYNTH), 20, 700)


def _synth_around_real(real: np.ndarray, *, lo: float, hi: float,
                       rng: np.random.Generator) -> np.ndarray:
    """Synthesise an N_SYNTH-sized fan around the real values: keep the
    real mean/std, add Gaussian noise + clip to [lo, hi]. With n small the
    empirical std is noisy, so we floor it at 15% of the mean so the violin
    doesn't collapse to a flat line on near-saturated axes
    (filters_with_evidence varies only ~21–23 of 24)."""
    if len(real) == 0:
        return np.zeros(N_SYNTH)
    m = float(np.nanmean(real))
    s = max(float(np.nanstd(real, ddof=1)), m * 0.15)
    fan = rng.normal(m, s, N_SYNTH)
    return np.clip(fan, lo, hi)


def _draw_violin(ax: plt.Axes, synth: np.ndarray, position: float,
                 width: float, color: str) -> None:
    """Single violin + median tick + IQR box, all in the panel accent color."""
    parts = ax.violinplot(
        [synth], positions=[position], widths=[width], showextrema=False,
        showmedians=False, showmeans=False,
    )
    for body in parts["bodies"]:
        body.set_facecolor(color)
        body.set_alpha(0.32)
        body.set_edgecolor(color)
        body.set_linewidth(1.4)
    q25, q50, q75 = np.percentile(synth, [25, 50, 75])
    half = width * 0.36
    ax.hlines(q50, position - half, position + half, colors=color, lw=2.0, zorder=4)
    ax.add_patch(mpatches.Rectangle(
        (position - half * 0.30, q25), half * 0.60, q75 - q25,
        facecolor=color, alpha=0.5, edgecolor=color, lw=0,
        zorder=3,
    ))


def make_plot() -> tuple[plt.Figure, list[plt.Axes]]:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    plt.rcParams.update({
        # Each subplot uses a TITLE (axes.titlesize) instead of an x-axis
        # label so the per-panel description renders at a readable size;
        # the bucket names occupy the x-tick labels.
        "font.size": 18, "axes.labelsize": 20, "axes.titlesize": 16,
        "axes.titleweight": "semibold", "axes.titlepad": 12,
        "xtick.labelsize": 12, "ytick.labelsize": 18, "legend.fontsize": 14,
    })

    data = _load_real_values()
    n_real_total = len(data)
    n_real_yes = int((data["surface_verdict_bucket"] == "surface_yes").sum())
    n_real_no = int((data["surface_verdict_bucket"] == "no").sum())
    rng = np.random.default_rng(seed=42)  # deterministic mock

    fig, axes = plt.subplots(1, 5, figsize=(20, 6.5))
    panel_letters = ["a", "b", "c", "d", "e"]

    for idx, (ax, (key, label, denom, accent_color, is_mocked, split_by_bucket)) in enumerate(
        zip(axes, PANELS, strict=True)
    ):
        # ── Split panels (a, b): two side-by-side violins, no vs surface_yes ──
        if split_by_bucket:
            positions = {"no": -0.35, "surface_yes": 0.35}
            bucket_colors = {"no": BUCKET_NO_COLOR, "surface_yes": accent_color}
            width = 0.55
            if key in data.columns:
                real_vals_all = data[key].to_numpy(dtype=float)
                real_clean_all = real_vals_all[~np.isnan(real_vals_all)]
                panel_max = float(real_clean_all.max()) if len(real_clean_all) else 0.0
            else:
                panel_max = 0.0
            for bucket in BUCKET_ORDER:
                sub = data[data["surface_verdict_bucket"] == bucket]
                if key in sub.columns:
                    real_vals = sub[key].to_numpy(dtype=float)
                    real_clean = real_vals[~np.isnan(real_vals)]
                else:
                    real_clean = np.array([], dtype=float)
                # Build the synth fan for THIS bucket
                if key == "papers_found":
                    synth = _synth_papers_found(bucket, rng)
                else:
                    cap = denom if denom is not None else max(panel_max * 1.5, 1)
                    synth = _synth_around_real(real_clean, lo=0, hi=cap, rng=rng)
                _draw_violin(ax, synth, positions[bucket], width, bucket_colors[bucket])
                # Real dots overlay for this bucket
                if len(real_clean):
                    jx = rng.uniform(-width * 0.30, width * 0.30, size=len(real_clean))
                    ax.scatter(
                        positions[bucket] + jx, real_clean, s=24, color=COLORS["dark"],
                        edgecolor="white", linewidth=0.6, zorder=6,
                    )
            ax.set_xticks(list(positions.values()))
            ax.set_xticklabels([BUCKET_LABEL[b] for b in BUCKET_ORDER])
            ax.set_xlim(-0.95, 0.95)
            # y-limits cover both buckets' synth fans
            if key == "papers_found":
                lo, hi = 0, 750
            else:
                cap = denom if denom is not None else max(panel_max * 1.5, 1)
                lo, hi = 0, cap * 1.10
        # ── Filtered panels (c, d, e): surface_yes only, single violin ──
        else:
            sub = data[data["surface_verdict_bucket"] == "surface_yes"]
            real_vals = sub[key].to_numpy(dtype=float)
            real_clean = real_vals[~np.isnan(real_vals)]
            cap = denom if denom is not None else max(real_clean.max() * 1.5, 1)
            synth = _synth_around_real(real_clean, lo=0, hi=cap, rng=rng)
            _draw_violin(ax, synth, 0.0, 0.7, accent_color)
            if len(real_clean):
                jx = rng.uniform(-0.22, 0.22, size=len(real_clean))
                ax.scatter(
                    jx, real_clean, s=24, color=COLORS["dark"],
                    edgecolor="white", linewidth=0.6, zorder=6,
                )
            ax.set_xticks([0])
            ax.set_xticklabels([BUCKET_LABEL["surface_yes"]])
            ax.set_xlim(-0.6, 0.6)
            lo, hi = 0, max(cap * 1.08, synth.max() * 1.08)

        # Per-panel label renders as a TITLE (larger, easier to read in
        # print). NOTE: ``setup_plotting_style`` monkey-patches
        # ``Axes.set_title`` only when it is fed a benchmark-style title;
        # here we set a plain descriptive title which is unaffected.
        ax.set_title(label, fontsize=16, fontweight="semibold",
                     pad=14, linespacing=1.2)
        ax.set_ylim(lo, hi)

        # Mark the denominator line where applicable
        if denom is not None:
            ax.axhline(denom, color=COLORS["neutral"], lw=0.8,
                       ls="--", alpha=0.6, zorder=1)
            x_anno = 0.92 if split_by_bucket else 0.55
            ax.text(x_anno, denom, f" max = {denom}", va="center",
                    fontsize=10, color=COLORS["neutral"], ha="left")

        # MOCK badge + "no real records yet" callout on the mocked panel (a)
        if is_mocked:
            ax.text(
                0.97, 0.97, "MOCK",
                transform=ax.transAxes, ha="right", va="top",
                fontsize=10, color=PANEL_AMBER, fontweight="bold",
                bbox={"boxstyle": "round,pad=0.3", "facecolor": "white",
                      "edgecolor": PANEL_AMBER, "lw": 1.0},
            )
            ax.text(
                0.5, 0.02,
                "no real records yet —\nn_papers_found pending backfill",
                transform=ax.transAxes, ha="center", va="bottom",
                fontsize=9, color=COLORS["neutral"], style="italic",
            )

        # Subpanel letter (lowercase, ExtraBold) at upper-left — paper
        # convention from figure_subpanel_labels memory.
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
        f"Dark dots = real values from the {n_real_total} published deep dives "
        f"({n_real_no} surface_accessibility='no'; {n_real_yes} surface-yes-even-weak). "
        f"Panels a/b split by verdict bucket; panels c/d/e restricted to surface-yes since "
        f"non-surface proteins lack extracellular evidence by definition. "
        f"Violin shape + IQR box = synthesised {N_SYNTH:,}-draw fan extrapolating to a full cohort "
        f"(lognormal for papers_found around the methods-documented median 234.5 / range 50–400, "
        f"offset down for the 'no' bucket; Gaussian around the per-bucket empirical mean ± std "
        f"(or 15%% mean, whichever larger) for the other axes). "
        f"MOCK pending the discover-only backfill for papers_found and the full cohort sweep.",
        ha="center", va="bottom", fontsize=10, style="italic",
        color=COLORS["neutral"], wrap=True,
    )

    fig.tight_layout(rect=(0, 0.05, 1, 0.96))
    return fig, list(axes)


def main() -> None:
    fig, _ = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"),
                gist_url=GIST_URL)


if __name__ == "__main__":
    main()
