#!/usr/bin/env python3
"""Regenerate the CellxGene cell-count cache from CZI Census.

Builds three TSVs the v2.1 enrichment pipeline reads at /tmp/:

* ``czi_cell_tissue_counts.tsv`` — ``(cl_id, uberon_id, n_cells)``,
  the per-(CL, UBERON) primary-cell count from
  ``cellxgene_census.obs``. Each cell counted once at its
  direct ``cell_type_ontology_term_id`` (no ancestor expansion).

  **Note on cache vs WMG nnz mismatch.** For some (CL, UBERON)
  pairs, WMG nnz can exceed the cache n_total (e.g. cardiac
  fibroblast in heart: cache=466, WMG=127,804 for EGFR). This is
  NOT staleness — both the cache and WMG come from Census
  2025-11-08. WMG's construction aggregates cells at a different
  granularity than the public obs API exposes (likely via
  on-build-time annotation rollup not visible in
  ``cell_type_ontology_term_id``). Re-running this script will
  give the same cache; the mismatch is intrinsic. The v2.1
  build script's clean-only-pair filter drops the mismatched
  pairs from per-UBERON aggregation.
* ``cl_id_to_label.tsv`` — ``(cl_id, label)`` for every CL that
  appears in the cohort, with the Census-published label string.
* ``uberon_to_label.tsv`` — same for tissues.

Pulls only ``is_primary_data == True`` cells so the counts match
WMG construction.

Usage:

    uv run python scripts/regen_cellxgene_cache.py

Targets Census ``2025-11-08`` by default (matches the WMG snapshot
the build reads). Pass ``--census-version 2024-07-01`` etc. to pin
a different release.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cellxgene_census

DEFAULT_CENSUS_VERSION = "2025-11-08"

OUT_DIR = Path("/tmp")
PAIR_COUNTS_TSV = OUT_DIR / "czi_cell_tissue_counts.tsv"
CL_LABELS_TSV = OUT_DIR / "cl_id_to_label.tsv"
UBERON_LABELS_TSV = OUT_DIR / "uberon_to_label.tsv"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--census-version",
        default=DEFAULT_CENSUS_VERSION,
        help=f"Census version tag (default: {DEFAULT_CENSUS_VERSION}).",
    )
    args = ap.parse_args()

    print(f"opening Census {args.census_version}...", file=sys.stderr)
    with cellxgene_census.open_soma(census_version=args.census_version) as census:
        obs_query = census["census_data"]["homo_sapiens"].obs.read(
            column_names=[
                "cell_type",
                "cell_type_ontology_term_id",
                "tissue",
                "tissue_ontology_term_id",
                "is_primary_data",
            ],
        )
        obs = obs_query.concat().to_pandas()

    n_total = len(obs)
    obs = obs[obs["is_primary_data"]]
    print(
        f"  total rows: {n_total:,}; primary: {len(obs):,}",
        file=sys.stderr,
    )

    # Direct (cl, ub) → cell count from obs.value_counts. Each cell
    # contributes to exactly one (cl, ub) pair via its primary
    # `cell_type_ontology_term_id`. We DON'T do ancestor expansion
    # here: WMG nnz can exceed obs counts for parent CL terms because
    # WMG aggregates at a different granularity than obs primary
    # annotation (WMG construction details not exposed via the public
    # Census obs API). The build script's clean-only-pair filter
    # handles the resulting (cl, ub) where WMG > obs by dropping
    # them from the per-UBERON aggregation — better than synthesizing
    # an expansion that doesn't match WMG either.
    pair_counts = (
        obs.groupby(
            ["cell_type_ontology_term_id", "tissue_ontology_term_id"],
            observed=True,
        )
        .size()
        .reset_index(name="n_cells")
        .sort_values("n_cells", ascending=False)
    )
    print(f"  (cl, ub) pairs: {len(pair_counts):,}", file=sys.stderr)

    # Labels for each CL / UBERON. obs.cell_type is the human-readable
    # label CZI ships; take a representative row per ontology id.
    cl_labels = (
        obs[["cell_type_ontology_term_id", "cell_type"]]
        .drop_duplicates(subset=["cell_type_ontology_term_id"])
        .rename(columns={"cell_type_ontology_term_id": "cl_id", "cell_type": "label"})
        .sort_values("cl_id")
    )
    ub_labels = (
        obs[["tissue_ontology_term_id", "tissue"]]
        .drop_duplicates(subset=["tissue_ontology_term_id"])
        .rename(columns={"tissue_ontology_term_id": "uberon_id", "tissue": "label"})
        .sort_values("uberon_id")
    )
    print(
        f"  distinct CL: {len(cl_labels):,}; distinct UBERON: {len(ub_labels):,}",
        file=sys.stderr,
    )

    pair_counts.to_csv(PAIR_COUNTS_TSV, sep="\t", index=False)
    print(f"wrote {PAIR_COUNTS_TSV} ({PAIR_COUNTS_TSV.stat().st_size:,} bytes)", file=sys.stderr)
    cl_labels.to_csv(CL_LABELS_TSV, sep="\t", index=False)
    print(f"wrote {CL_LABELS_TSV} ({CL_LABELS_TSV.stat().st_size:,} bytes)", file=sys.stderr)
    ub_labels.to_csv(UBERON_LABELS_TSV, sep="\t", index=False)
    print(f"wrote {UBERON_LABELS_TSV} ({UBERON_LABELS_TSV.stat().st_size:,} bytes)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
