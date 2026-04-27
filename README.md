# accessible-surfaceome

Standalone `uv` project for the surface-proteome annotation pipeline (sourced from
`Deliverome-Project/deliverome-internal/analyses/surface-proteome`) described in
`docs/plans/2026-04-16-surface-proteome-annotation.md`.

The current checked-in implementation covers the M1 candidate-universe work:
source downloads, source normalization, accession reconciliation, and the
seven-source candidate-universe merge.

## Layout

- `src/surface_proteome/candidates/` - M1 candidate-universe builders.
- `src/surface_proteome/retrieval/` - planned literature/source retrieval code.
- `src/surface_proteome/agents/` - planned extraction/synthesis agents and prompts.
- `src/surface_proteome/pipeline/` - planned per-gene and batch orchestration.
- `src/surface_proteome/reports/` - planned analysis/report generation code.
- `data/raw/` - raw source workbooks used by the M1 builders.
- `data/external/` - downloaded external snapshots and traceability manifests.
- `data/processed/` - normalized M1 source tables and candidate-universe outputs.
- `docs/` - project plans, reports, and onepagers moved from the repo-level docs tree.

## Commands

From this directory:

```bash
uv sync
uv run accessible-surfaceome build
uv run python -m surface_proteome.candidates.merge
uv run python -m surface_proteome.candidates.build_surfy
uv run python -m surface_proteome.candidates.build_cspa
uv run python -m surface_proteome.candidates.build_ml_predictions
uv run python -m surface_proteome.candidates.build_controls \
  --controls-json /path/to/canonical_delivery_positive_controls/controls.json \
  --surfaceome-csv /path/to/surfaceome_expressed.csv \
  --mygene-symbol-universe-tsv /path/to/candidate_universe.tsv
```

The candidate-universe merge currently writes TSV outputs under
`data/processed/candidate_universe/`; a parquet export can be added when the
downstream annotation pipeline starts consuming `data/candidates.parquet`.

The control builder writes a consolidated panel under
`data/processed/controls/surfaceome_control_panel.tsv`.
It consolidates ADC benchmark positives, strict Lycia/LYTAC benchmark positives,
the broader patent delivery-handle positives, and negative controls.
The panel includes both parent-2,379 and M1-candidate-universe membership
annotations (`in_parent_surfaceome_2379`, `in_m1_candidate_universe`) and marks
explicitly pinned user negatives (`is_pinned_specified_negative`).
