# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``deep_dive_record_richness.{pdf,png}`` — a 4-panel violin of
per-record richness across the deep-dive cohort, split by surface verdict.

**Real data.** Each panel renders the per-gene distribution along one
"richness" axis a reader would care about after opening a gene page. Panels
a/b are split by surface verdict; panels c/d show the surface-yes subset:

  a. Papers found        — discovery-corpus size (``n_papers_found``, median
                           ~240), **two violins** (no vs surface-yes-even-weak).
                           Real per-gene value; each bucket's fan is synthesised
                           around its own real mean / std.
  b. Papers selected     — unique papers read full-text (``n_papers_selected``),
                           **two violins**. Real per-gene values.
  c. Papers with EC      — primary-tier, surface-method-tagged evidence
                           (``primary_evidence_count``). **Single violin,
                           surface-yes only.**
  d. Evidence records    — total extracted evidence records (``evidence_count``).
                           **Single violin, surface-yes only.**

Real values render as dots overlaid on each violin (panels a–d). The violin
itself is a synthesised 5000-draw fan that communicates the *shape* a
full-cohort distribution would have.

"surface-yes-even-weak" = any deep-dive ``surface_accessibility`` value except
``"no"`` (i.e. high / moderate / low / uncertain), bucketed in the TSV as
``surface_verdict_bucket`` so the mirror can split panels a/b and filter panels
c/d on it.

PRELIMINARY — ~1,197 of ~5,128 swept, pre-QA-fix.

Standalone — ``uv run make_deep_dive_record_richness.py``.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"  # pin to a commit SHA at publication for immutable citation
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
# Single per-figure TSV: one row per published deep-dive record, with
# the 4 real per-gene axes + a `surface_verdict_bucket` label
# ('no' vs 'surface_yes') derived from `surface_accessibility` + the finer
# `tier`. Produced by ``scripts/build_figure_tsvs.py``. Gist bundles this TSV
# next to the script; the figure reads ONLY from the sibling — no other URLs.
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

# Panel colors mirror SEQUENTIAL_PALETTES picks from the canonical
# generator: teal[2], amber[3], maroon[3], lavender[3].
PANEL_TEAL = "#3D6B60"        # teal[2]
PANEL_AMBER = "#F4AA28"       # amber[3]
PANEL_MAROON = "#BC3C4C"      # maroon[3]
PANEL_LAVENDER = "#8878C8"    # lavender[3]

# Bucket hues for the split panels (a, b). "no" gets the muted neutral
# so the eye reads it as "absence of surface signal"; surface_yes gets
# the panel's accent color (assigned per panel below).
BUCKET_NO_COLOR = "#9C8C88"   # muted warm-grey
BUCKET_ORDER = ["no", "surface_yes"]
BUCKET_LABEL = {
    "no":          "no",
    "surface_yes": "surface yes\n(even weak)",
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
        "xtick.labelsize": 12, "ytick.labelsize": 18, "legend.fontsize": 14,
        "xtick.color": BRAND_INK, "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "patch.edgecolor": "none", "patch.linewidth": 0.0,
    })


# Four-panel specs: (tsv_key, display label, denom or None, accent_color,
#                    split_by_bucket)
# Panels a/b split by bucket (two side-by-side violins). Panels c/d
# filter to surface_yes only (single violin). Every panel is real.
PANELS = [
    ("papers_found",       "Papers found\n(discovery corpus)",       None,   PANEL_AMBER,     True),
    ("papers_selected",    "Papers selected\n(into evidence list)",  None,   PANEL_TEAL,      True),
    ("papers_with_ec",     "Papers with\nextracellular evidence",    None,   PANEL_MAROON,    False),
    ("n_filters_evidence", "Evidence records\nextracted",            None,   PANEL_LAVENDER,  False),
]

# Synth size for the violin fan ("what would 5000 deep dives look like?").
N_SYNTH = 5_000


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


def _synth_around_real(real: np.ndarray, *, lo: float, hi: float,
                        rng: np.random.Generator) -> np.ndarray:
    """Synthesise an N_SYNTH-sized fan around the real values: keep
    the real mean/std, add Gaussian noise + clip to [lo, hi]. With
    n small the empirical std is noisy, so we floor it at 15% of the
    mean so the violin doesn't collapse to a flat line."""
    if len(real) == 0:
        return np.zeros(N_SYNTH)
    m = float(np.nanmean(real))
    s = max(float(np.nanstd(real, ddof=1)), m * 0.15)
    fan = rng.normal(m, s, N_SYNTH)
    return np.clip(fan, lo, hi)


def _draw_violin(ax: plt.Axes, synth: np.ndarray, position: float, width: float,
                  color: str) -> None:
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
_DOT_KW = dict(s=6, alpha=0.35, color=BRAND_INK, edgecolor="none", zorder=6)


def main() -> None:
    _apply_brand_style()
    data = _fetch_tsv(DATA_TSV)
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

        # Per-panel label renders as a TITLE (larger, easier to read in print).
        ax.set_title(label, fontsize=16, fontweight="semibold",
                      pad=14, linespacing=1.2)
        ax.set_ylim(lo, hi)

        # Mark the denominator line where applicable
        if denom is not None:
            ax.axhline(denom, color=BRAND_NEUTRAL, lw=0.8,
                        ls="--", alpha=0.6, zorder=1)
            x_anno = 0.92 if split_by_bucket else 0.55
            ax.text(x_anno, denom, f" max = {denom}", va="center",
                     fontsize=10, color=BRAND_NEUTRAL, ha="left")

        # Subpanel letter (lowercase, ExtraBold) at upper-left
        ax.text(
            -0.30, 1.08, panel_letters[idx],
            transform=ax.transAxes, ha="left", va="top",
            fontsize=22, fontweight=800, color=BRAND_INK,
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
        f"per-bucket empirical mean +/- std, or 15% mean, whichever larger) extrapolating to a "
        f"full cohort. PRELIMINARY - ~1,197 of ~5,128 swept, pre-QA-fix.",
        ha="center", va="bottom", fontsize=10, style="italic",
        color=BRAND_NEUTRAL, wrap=True,
    )

    fig.tight_layout(rect=(0, 0.05, 1, 0.96))

    out_pdf = Path("deep_dive_record_richness.pdf")
    out_png = Path("deep_dive_record_richness.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=600, metadata={"Source": GIST_URL})
    print(f"Wrote {out_pdf} + {out_png}  "
          f"(n_real total = {n_real_total}; no = {n_real_no}; surface_yes = {n_real_yes})")


if __name__ == "__main__":
    main()
