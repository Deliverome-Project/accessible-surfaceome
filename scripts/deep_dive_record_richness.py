"""Deep-dive record richness across four axes, split by surface verdict.

Four-panel violin showing the per-record distribution along the axes that
characterise *how much information* a single deep dive captures for a gene.
Panels a/b are split by surface verdict (non-surface vs surface-yes-even-weak)
so the reader can see which dimensions separate calls; panels c/d show the
surface-yes subset only. The aim is to communicate *richness* — a reader
clicking any gene should expect roughly this much per axis.

The four axes
-------------
a. **Papers found** — the discovery-corpus size (EuropePMC + PubTator NER +
   gene2pubmed union). **Two violins** (no vs surface-yes-even-weak). Now a
   REAL per-gene value (``n_papers_found``, median ~240); each bucket's violin
   fan is synthesised around its own real mean / std.

b. **Papers selected** — unique papers read full-text into the evidence list
   (``n_papers_selected``). **Two violins** (no vs surface-yes-even-weak).
   Real per-gene values.

c. **Papers with extracellular evidence** — the primary-tier evidence with an
   experimental surface-method tag (``primary_evidence_count``). **Single
   violin, surface-yes only** — non-surface proteins have little extracellular
   evidence by definition.

d. **Evidence records** — the total number of extracted evidence records on the
   deep-dive (``evidence_count``). **Single violin, surface-yes only.**

Real values from the published records render as dots overlaid on each violin
(panels a–d). The violin itself is a *synthesised* 5000-draw fan intended to
communicate the *shape* a full-cohort distribution would have — clearly labelled
so a reviewer never confuses the synthesis with measured data. Every panel
synthesises around the real per-bucket mean ± std.

"surface-yes-even-weak" = any deep-dive ``surface_accessibility`` value except
``"no"`` (i.e. high / moderate / low / uncertain), bucketed in the TSV as
``surface_verdict_bucket`` so panels a/b split and panels c/d filter on it.

Why violin?
-----------
Each axis has a very different scale (papers in the hundreds vs evidence
counts in the tens) so a shared Y axis would compress the small axes into the
baseline. Four small per-panel violins (one Y axis each) lets each distribution
speak for itself.

Data source
-----------
Reads the bundled per-figure TSV at
``data/processed/figures/deep_dive_record_richness.tsv`` (one row per published
deep-dive record: the 4 real per-gene axes + a ``surface_verdict_bucket`` label
+ the finer ``tier``).

PRELIMINARY — ~1,197 of ~5,128 swept, pre-QA-fix.

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
# 'surface_yes') derived from `surface_accessibility` + the finer `tier`.
DATA_TSV = ROOT / "data/processed/figures/deep_dive_record_richness.tsv"

# Published reproduction gist (embedded into output PNG Source / PDF Subject
# metadata via save_figure(gist_url=...)).
GIST_URL = "https://gist.github.com/beccajcarlson/35119ea2bca9585c7245d247334b8c01"

# Panel colors picked from the centralized SEQUENTIAL_PALETTES.
PANEL_TEAL = SEQUENTIAL_PALETTES["teal"][2]      # rich teal  -> #3D6B60
PANEL_AMBER = SEQUENTIAL_PALETTES["amber"][3]    # bright amber -> #F4AA28
PANEL_MAROON = SEQUENTIAL_PALETTES["maroon"][3]  # -> #BC3C4C
PANEL_LAVENDER = SEQUENTIAL_PALETTES["lavender"][3]  # -> #8878C8

# Bucket hue for the "no" arm of the split panels (a, b). Muted warm-grey
# so the eye reads it as "absence of surface signal"; surface_yes gets the
# panel's accent color.
BUCKET_NO_COLOR = "#9C8C88"
BUCKET_ORDER = ["no", "surface_yes"]
BUCKET_LABEL = {
    "no":          "no",
    "surface_yes": "surface yes\n(even weak)",
}

# Four-panel specs: (tsv_key, display label, denom or None, accent_color,
#                    split_by_bucket)
# Panels a/b split by bucket (two side-by-side violins). Panels c/d
# filter to surface_yes only (single violin). Every panel is real.
PANELS = [
    ("papers_found",       "Papers found\n(discovery corpus)",       None,     PANEL_AMBER,     True),
    ("papers_selected",    "Papers selected\n(into evidence list)",  None,     PANEL_TEAL,      True),
    ("papers_with_ec",     "Papers with\nextracellular evidence",    None,     PANEL_MAROON,    False),
    ("n_filters_evidence", "Evidence records\nextracted",            None,     PANEL_LAVENDER,  False),
]

# Synth size for the violin fan ("what would 5000 deep dives look like?").
N_SYNTH = 5_000


def _load_real_values() -> pd.DataFrame:
    """Read the bundled per-figure TSV (one row per published deep-dive
    record). Carries the 4 real per-gene axes + the ``surface_verdict_bucket``
    label."""
    return pd.read_csv(DATA_TSV, sep="\t")


def _synth_around_real(real: np.ndarray, *, lo: float, hi: float,
                       rng: np.random.Generator) -> np.ndarray:
    """Synthesise an N_SYNTH-sized fan around the real values: keep the
    real mean/std, add Gaussian noise + clip to [lo, hi]. With n small the
    empirical std is noisy, so we floor it at 15% of the mean so the violin
    doesn't collapse to a flat line on near-constant axes."""
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


# Real values render as dots; with ~1,000 genes per panel we use small,
# semi-transparent points so the violin stays legible underneath.
_DOT_KW = dict(s=6, alpha=0.35, color=COLORS["dark"], edgecolor="none", zorder=6)


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
    rng = np.random.default_rng(seed=42)  # deterministic synth

    fig, axes = plt.subplots(1, 4, figsize=(20, 6.5))
    panel_letters = ["a", "b", "c", "d"]

    for idx, (ax, (key, label, denom, accent_color, split_by_bucket)) in enumerate(
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
                cap = denom if denom is not None else max(panel_max * 1.5, 1)
                synth = _synth_around_real(real_clean, lo=0, hi=cap, rng=rng)
                _draw_violin(ax, synth, positions[bucket], width, bucket_colors[bucket])
                # Real dots overlay for this bucket
                if len(real_clean):
                    jx = rng.uniform(-width * 0.30, width * 0.30, size=len(real_clean))
                    ax.scatter(positions[bucket] + jx, real_clean, **_DOT_KW)
            ax.set_xticks(list(positions.values()))
            ax.set_xticklabels([BUCKET_LABEL[b] for b in BUCKET_ORDER])
            ax.set_xlim(-0.95, 0.95)
            # y-limits cover both buckets' synth fans
            cap = denom if denom is not None else max(panel_max * 1.5, 1)
            lo, hi = 0, cap * 1.10
        # ── Filtered panels (c, d): surface_yes only, single violin ──
        else:
            sub = data[data["surface_verdict_bucket"] == "surface_yes"]
            real_vals = sub[key].to_numpy(dtype=float) if key in sub.columns else np.array([])
            real_clean = real_vals[~np.isnan(real_vals)]
            cap = denom if denom is not None else max(real_clean.max() * 1.5, 1) if len(real_clean) else 1
            synth = _synth_around_real(real_clean, lo=0, hi=cap, rng=rng)
            _draw_violin(ax, synth, 0.0, 0.7, accent_color)
            if len(real_clean):
                jx = rng.uniform(-0.22, 0.22, size=len(real_clean))
                ax.scatter(jx, real_clean, **_DOT_KW)
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
        f"Dots = real values from the {n_real_total} published deep dives "
        f"({n_real_no} surface_accessibility='no'; {n_real_yes} surface-yes-even-weak). "
        f"Panels a/b split by verdict bucket; panels c/d restricted to surface-yes since "
        f"non-surface proteins carry little extracellular evidence by definition. "
        f"Violin shape + IQR box = synthesised {N_SYNTH:,}-draw fan (Gaussian around the "
        f"per-bucket empirical mean ± std, or 15%% mean, whichever larger) extrapolating to a "
        f"full cohort. PRELIMINARY — ~1,197 of ~5,128 swept, pre-QA-fix.",
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
