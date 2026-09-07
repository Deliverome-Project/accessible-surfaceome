"""Figure 1 — 5-DB surface-proteome overlap Venn (native / initial cutoffs).

Reads ``data/processed/figures/db_overlap_venn.tsv`` (the per-figure committed
TSV, built by ``scripts/build_figure_tsvs.py``) and renders a topologically-
correct ellipse Venn of the five surface-prediction databases, using each DB's
INITIAL (pre-recalibration) surface flags.  This is a databases-overlap figure,
so it ships its own minimal input — free of the catalog's triage / optimised /
universe-version columns.

Columns consumed from the TSV:
  uniprot_acc                — unique protein key
  uniprot_surface_flag       — UniProt KW/CC surface annotation (0/1)
  go_surface_flag            — GO CC:0009986 / plasma-membrane terms (0/1)
  hpa_surface_flag           — HPA single-cell surface localisation (0/1)
  surfy_surface_flag         — SURFY membrane proteomics panel (0/1)
  cspa_surface_flag          — CSPA mass-spec surface atlas (0/1)

Run: ``uv run python scripts/db_overlap_venn.py``
# Reproduction: https://gist.github.com/beccajcarlson/d655abfc9c7deeaff1cfbe584de96ffa
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from venn import venn

from accessible_surfaceome.audit._plotting_config import save_figure, setup_plotting_style

REPO = Path(__file__).resolve().parents[1]
DATA_TSV = REPO / "data/processed/figures/db_overlap_venn.tsv"
OUT_DIR = REPO / "data/analysis/figures"
GIST_URL = "https://gist.github.com/beccajcarlson/d655abfc9c7deeaff1cfbe584de96ffa"

# Brand categorical palette (same order as CATEGORICAL_PALETTE in _plotting_config).
_BRAND_PALETTE = [
    "#BC3C4C",  # maroon-light
    "#3D6B60",  # teal-mid
    "#F4AA28",  # amber-bright
    "#8878C8",  # lavender-bright
    "#6E1428",  # maroon-dark
    "#7AAB9F",  # teal-light
]

DB_FLAGS = [
    ("uniprot_surface_flag", "UniProt"),
    ("go_surface_flag",      "GO CC"),
    ("hpa_surface_flag",     "HPA"),
    ("surfy_surface_flag",   "SURFY"),
    ("cspa_surface_flag",    "CSPA"),
]
PALETTE_BY_LABEL = {label: _BRAND_PALETTE[i] for i, (_, label) in enumerate(DB_FLAGS)}


def main() -> None:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    # Match the gist mirror's layout fingerprint (tests/test_figure_canonical_mirror_sync).
    plt.rcParams.update({
        "font.size": 21,
        "axes.labelsize": 25,
        "axes.titlesize": 0,
        "xtick.labelsize": 20,
        "ytick.labelsize": 20,
        "legend.fontsize": 20,
    })

    df = pd.read_csv(DATA_TSV, sep="\t", dtype=str)

    sets: dict[str, set[str]] = {label: set() for _, label in DB_FLAGS}
    for _, row in df.iterrows():
        acc = str(row["uniprot_acc"])
        for flag, label in DB_FLAGS:
            if row.get(flag, "0") == "1":
                sets[label].add(acc)

    sorted_keys = sorted(sets, key=lambda k: -len(sets[k]))
    sorted_sets = {k: sets[k] for k in sorted_keys}
    cmap = [PALETTE_BY_LABEL[k] for k in sorted_keys]

    fig, ax = plt.subplots(figsize=(11, 10))
    venn(sorted_sets, ax=ax, cmap=cmap, fontsize=22, legend_loc=None)
    ax.set_xticks([])
    ax.set_yticks([])
    sns.despine(ax=ax, top=True, right=True, bottom=True, left=True)

    # Suppress small intersection counts — the 32 regions of a 5-set Venn
    # include many sliver intersections (3-DB / 4-DB / 5-DB cells with
    # double-digit counts) whose labels collide and read as noise.
    MIN_DISPLAY = 100
    for t in ax.texts:
        raw = t.get_text().strip().replace(",", "")
        try:
            if int(raw) < MIN_DISPLAY:
                t.set_text("")
        except ValueError:
            continue

    handles = [
        plt.Rectangle((0, 0), 1, 1, color=PALETTE_BY_LABEL[k], alpha=0.6)
        for k in sorted_keys
    ]
    labels = [f"{k}  (n = {len(sets[k]):,})" for k in sorted_keys]
    # Two-row legend (ceil(N/2)) — 5 DB chips at v3 fontsize without
    # overflowing the figure width.
    ax.legend(
        handles, labels,
        loc="upper center", bbox_to_anchor=(0.5, -0.02),
        ncols=(len(sorted_keys) + 1) // 2, frameon=False, fontsize=21,
    )

    save_figure(fig, "db_overlap_venn", OUT_DIR, gist_url=GIST_URL)
    print(
        f"  Per-DB votes: {sum(len(s) for s in sets.values()):,} "
        f"across {len(set().union(*sets.values())):,} unique proteins"
    )


if __name__ == "__main__":
    main()
