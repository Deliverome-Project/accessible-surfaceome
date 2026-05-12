"""5-way Venn diagram of the M1 surface databases.

For each of the 5 retained surface DBs (UniProt subcellular query,
GO cellular component, HPA, SURFY, CSPA), build the set of UniProt
accessions in the M1 candidate universe that the DB votes ``true``.
Render an elliptical 5-way Venn showing how those sets overlap.

5-way Venns are intrinsically busy — 31 non-empty regions are
possible — but they make the structure of DB agreement immediately
visible: large central area = consensus surface proteins, lobes =
DB-specific calls, narrow slivers = pairwise quirks.

Outputs (PDF + PNG):
  data/analysis/triage_bench/db_overlap_venn.{pdf,png}
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import matplotlib.pyplot as plt
from venn import venn

from accessible_surfaceome.audit._plotting_config import (
    CATEGORICAL_PALETTE,
    save_figure,
    setup_plotting_style,
)


DB_FLAGS_5 = [
    ("uniprot_surface_flag", "UniProt"),
    ("go_surface_flag", "GO CC"),
    ("hpa_surface_flag", "HPA"),
    ("surfy_surface_flag", "SURFY"),
    ("cspa_surface_flag", "CSPA"),
]


def build_sets(path: Path) -> dict[str, set[str]]:
    sets: dict[str, set[str]] = {label: set() for _, label in DB_FLAGS_5}
    with path.open() as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            acc = row["uniprot_accession"]
            for flag, label in DB_FLAGS_5:
                if row.get(flag, "0") == "1":
                    sets[label].add(acc)
    return sets


def make_plot(out_dir: Path) -> None:
    setup_plotting_style(style="white", context="notebook", font_scale=1.0)
    sets = build_sets(Path("data/processed/candidate_universe/candidate_universe.tsv"))

    # Sort by set size descending so the largest set ends up under the
    # most-readable ellipse slot in the `venn` package layout.
    sorted_keys = sorted(sets, key=lambda k: -len(sets[k]))
    sorted_sets = {k: sets[k] for k in sorted_keys}

    fig, ax = plt.subplots(figsize=(9, 9))
    venn(
        sorted_sets,
        ax=ax,
        cmap=CATEGORICAL_PALETTE[: len(sorted_sets)],
        fontsize=10,
        legend_loc=None,  # custom legend below so it doesn't overlap the ellipses
    )

    total_union = len(set().union(*sets.values()))
    total_intersection = len(set.intersection(*sets.values()))
    ax.set_title(
        "Surface-database overlap across the M1 candidate universe\n"
        f"n = {total_union:,} proteins flagged by ≥1 of 5 DBs · "
        f"{total_intersection:,} in 5-way intersection",
        fontsize=12,
        pad=14,
    )
    ax.set_xticks([])
    ax.set_yticks([])

    # Legend with per-DB set size, anchored below the diagram
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=CATEGORICAL_PALETTE[i], alpha=0.6)
        for i in range(len(sorted_keys))
    ]
    labels = [f"{k}  (n = {len(sets[k]):,})" for k in sorted_keys]
    ax.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.02),
        ncols=len(sorted_keys),
        frameon=False,
        fontsize=10,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    save_figure(
        fig,
        filename="db_overlap_venn",
        output_dir=str(out_dir),
        formats=("pdf", "png"),
    )
    plt.close(fig)


def main() -> None:
    # Default output dir tracks the "final" rendering folder so a venn
    # regenerate doesn't drift back into the staging dir. Override via
    # the VENN_OUT_DIR env var.
    out_dir = Path(os.environ.get(
        "VENN_OUT_DIR", "data/analysis/triage_bench_final"
    ))
    make_plot(out_dir)


if __name__ == "__main__":
    main()
