"""Plot agreement across the seven M1 sources for surface-exposed proteins.

Reads ``data/processed/candidate_universe/candidate_universe.tsv`` (written
by ``src/surface_proteome/candidates/merge.py``) and produces:

1. **Agreement bar**: number of proteins supported by k/N sources (k = 1..N,
   N = len(SOURCE_FLAGS) = 7) — restricted to ``n_sources_surface >= 1``.
2. **UpSet plot**: all non-empty intersections across the source flags,
   showing which combinations of sources co-occur and how many proteins
   fall into each combination.
3. **Pairwise Jaccard heatmap**: agreement between every pair of sources
   on the set of accessions each flags as surface.

Figures are written under ``data/analysis/candidate_universe_agreement/``
in PDF + JPEG per the repo plotting contract.

Sources in the figure legend:

- ``uniprot``       — UniProt human surface-candidate query
- ``go``            — GO gene products under configured surface roots
  (non-IEA evidence required)
- ``surfy``         — SURFY label == "surface" (Bausch-Fluck 2018)
- ``cspa``          — Cell Surface Protein Atlas human detections (BF 2015)
  (high-confidence OR putative only)
- ``deeptmhmm``     — DeepTMHMM predicted membrane topology
  (label ∈ {TM, SP+TM, BETA})
- ``hpa``           — Human Protein Atlas subcellular_location v25 IF
  (PM accessible OR junctional at per-tier Enhanced/Supported/Approved;
  secreted-only rows excluded)
- ``compartments``  — JensenLab COMPARTMENTS stars ≥ 3 on
  max(experiments ∖ HPA, textmining) across surface GO terms AND
  corroborated by at least one other source's surface flag
  (knowledge + predictions channels are provenance-only)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from upsetplot import UpSet, from_indicators

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from surface_proteome.plotting_config import (  # noqa: E402
    COLORS,
    create_figure,
    save_figure,
    setup_plotting_style,
)

DEFAULT_INPUT = (
    ROOT / "data" / "processed" / "candidate_universe" / "candidate_universe.tsv"
)
DEFAULT_OUTPUT_DIR = ROOT / "data" / "analysis" / "candidate_universe_agreement"

SOURCE_FLAGS = [
    "uniprot_surface_flag",
    "go_surface_flag",
    "surfy_surface_flag",
    "cspa_surface_flag",
    "deeptmhmm_surface_flag",
    "hpa_surface_flag",
    "compartments_surface_flag",
]
SOURCE_NAMES = {
    "uniprot_surface_flag": "uniprot",
    "go_surface_flag": "go",
    "surfy_surface_flag": "surfy",
    "cspa_surface_flag": "cspa",
    "deeptmhmm_surface_flag": "deeptmhmm",
    "hpa_surface_flag": "hpa",
    "compartments_surface_flag": "compartments",
}
N_SOURCES = len(SOURCE_FLAGS)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-tsv", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return p.parse_args()


def _bar_palette(n: int) -> list[str]:
    palette = [
        COLORS["light"],
        COLORS["accent_gold"],
        COLORS["accent_green"],
        COLORS["secondary"],
        COLORS["primary"],
        COLORS["dark"],
        COLORS["neutral"],
    ]
    if n <= len(palette):
        return palette[:n]
    # Cycle if we ever grow past the palette length (not expected at N=7).
    return [palette[i % len(palette)] for i in range(n)]


def _plot_agreement_bar(df: pd.DataFrame, out_dir: Path) -> None:
    counts = (
        df[df["n_sources_surface"] >= 1]["n_sources_surface"]
        .value_counts()
        .reindex(range(1, N_SOURCES + 1), fill_value=0)
        .sort_index()
    )
    fig, ax = create_figure(figsize=(10, 6))
    bars = ax.bar(
        counts.index,
        counts.values,
        color=_bar_palette(N_SOURCES),
        edgecolor=COLORS["dark"],
        linewidth=1.2,
    )
    for bar, val in zip(bars, counts.values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{val:,}",
            ha="center",
            va="bottom",
            fontsize=14,
            color=COLORS["dark"],
        )
    ax.set_xlabel("# sources flagging protein as surface-exposed")
    ax.set_ylabel("# proteins (unique UniProt accessions)")
    ax.set_title(
        f"Cross-source agreement on surface-exposed proteins (N = {N_SOURCES})"
    )
    ax.set_xticks(list(range(1, N_SOURCES + 1)))
    ax.set_ylim(0, counts.values.max() * 1.12)
    ax.grid(axis="y", alpha=0.3)

    total = int(counts.sum())
    # "High agreement" = top three buckets (all-or-near-all-sources),
    # matching the semantic of the previous 4-5/5 annotation at N=5.
    high_buckets = list(range(max(1, N_SOURCES - 2), N_SOURCES + 1))
    high_label = f"{high_buckets[0]}-{high_buckets[-1]}"
    high_agreement = int(counts.loc[high_buckets].sum())
    ax.text(
        0.98,
        0.96,
        f"total flagged: {total:,}\n"
        f"{high_label} source agreement: {high_agreement:,} "
        f"({100*high_agreement/total:.1f}%)",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=12,
        color=COLORS["dark"],
        bbox={"facecolor": "white", "edgecolor": COLORS["neutral"], "alpha": 0.9},
    )
    save_figure(fig, "candidate_source_agreement_bar", output_dir=out_dir)
    plt.close(fig)


def _plot_upset(df: pd.DataFrame, out_dir: Path) -> None:
    sub = df[df["n_sources_surface"] >= 1].copy()
    ind = sub[SOURCE_FLAGS].astype(bool)
    ind.columns = [SOURCE_NAMES[c] for c in ind.columns]
    data = from_indicators(list(ind.columns), data=ind)

    fig = plt.figure(figsize=(13, 8))
    upset = UpSet(
        data,
        subset_size="count",
        show_counts=True,
        sort_by="cardinality",
        min_subset_size=20,
        facecolor=COLORS["secondary"],
        element_size=None,
    )
    upset.plot(fig=fig)
    fig.suptitle(
        "Source-intersection sizes for surface-exposed proteins "
        "(min subset size = 20)",
        fontsize=14,
        color=COLORS["dark"],
    )
    save_figure(fig, "candidate_source_agreement_upset", output_dir=out_dir)
    plt.close(fig)


def _plot_pairwise_jaccard(df: pd.DataFrame, out_dir: Path) -> None:
    sources = [SOURCE_NAMES[c] for c in SOURCE_FLAGS]
    sets = {
        SOURCE_NAMES[c]: set(df.loc[df[c] == 1, "uniprot_accession"])
        for c in SOURCE_FLAGS
    }
    n = len(sources)
    jac = np.zeros((n, n))
    inter = np.zeros((n, n), dtype=int)
    for i, a in enumerate(sources):
        for j, b in enumerate(sources):
            s_a, s_b = sets[a], sets[b]
            union = s_a | s_b
            interset = s_a & s_b
            jac[i, j] = (len(interset) / len(union)) if union else 0.0
            inter[i, j] = len(interset)

    fig, ax = create_figure(figsize=(8, 7))
    im = ax.imshow(jac, cmap="viridis", vmin=0, vmax=1)
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(sources, rotation=30, ha="right")
    ax.set_yticklabels(sources)
    for i in range(n):
        for j in range(n):
            text_color = "white" if jac[i, j] < 0.55 else "black"
            ax.text(
                j,
                i,
                f"{jac[i, j]:.2f}\n({inter[i, j]:,})",
                ha="center",
                va="center",
                fontsize=11,
                color=text_color,
            )
    ax.set_title(
        "Pairwise Jaccard across surface-flag sources\n"
        "(cell: Jaccard / intersection size)"
    )
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Jaccard similarity")
    save_figure(fig, "candidate_source_pairwise_jaccard", output_dir=out_dir)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    setup_plotting_style(context="notebook", font_scale=1.1)

    df = pd.read_csv(args.input_tsv, sep="\t", low_memory=False)
    for col in SOURCE_FLAGS:
        df[col] = df[col].fillna(0).astype(int)
    df["n_sources_surface"] = df["n_sources_surface"].fillna(0).astype(int)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"input rows: {len(df):,}")
    print(f"flagged (n_sources>=1): {(df['n_sources_surface'] >= 1).sum():,}")

    _plot_agreement_bar(df, args.output_dir)
    _plot_upset(df, args.output_dir)
    _plot_pairwise_jaccard(df, args.output_dir)

    # Write a small TSV of the agreement counts for easy reference
    counts = (
        df[df["n_sources_surface"] >= 1]["n_sources_surface"]
        .value_counts()
        .reindex(range(1, N_SOURCES + 1), fill_value=0)
        .sort_index()
    )
    counts_df = counts.rename_axis("n_sources").reset_index(name="n_proteins")
    counts_df.to_csv(
        args.output_dir / "agreement_level_counts.tsv", sep="\t", index=False
    )

    print(f"figures written to {args.output_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
