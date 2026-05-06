# accessible-surfaceome

A `uv` project that builds an annotated catalogue of human cell-surface
proteins **accessible to therapeutic targeting, agnostic to therapeutic
modality.** Full design notes:
[docs/plans/2026-04-16-surface-proteome-annotation.md](docs/plans/2026-04-16-surface-proteome-annotation.md).

The headline call per protein is *accessibility* — physical surface
localization, extracellular-face exposure, and any conditional/induced
surface presentation (cell-state induced, tissue subset, trafficking
cycling). Therapeutic context (approved drugs, clinical trials, patent
disclosures, preclinical characterizations) accompanies each call.

The current checked-in implementation covers the M1 candidate-universe work:
source downloads, source normalization, accession reconciliation, and the
seven-source candidate-universe merge.

## Layout

- `src/accessible_surfaceome/sources/` - one module per data source (`uniprot.py`, `go.py`, `surfy.py`, `cspa.py`, `deeptmhmm.py`, `hpa.py`, `compartments.py`); each exposes `download` / `build` subcommands. Shared helpers (UniProt accession history, ENSG/ENSP mapping, traceability) live under `sources/_support/`.
- `src/accessible_surfaceome/merge/` - candidate-universe orchestration; loaders, normalization, and gene-symbol resolution split into named neighbors.
- `src/accessible_surfaceome/audit/` - audit scripts (accession-collapse audit, cross-source UniProt audit) and blog figures.
- `src/accessible_surfaceome/controls.py` - control-panel builder (ADC/Lycia/LYTAC positives + negatives).
- `src/accessible_surfaceome/tools/` - per-machine install plumbing (DeepTMHMM academic install).
- `data/raw/` - raw source workbooks used by the M1 builders.
- `data/external/` - downloaded external snapshots and traceability manifests.
- `data/processed/` - normalized M1 source tables and candidate-universe outputs.
- `docs/` - project plans, reports, and onepagers.

## Commands

From this directory:

```bash
uv sync
uv run accessible-surfaceome build
uv run python -m accessible_surfaceome.merge
uv run python -m accessible_surfaceome.sources.surfy build
uv run python -m accessible_surfaceome.sources.cspa build
uv run python -m accessible_surfaceome.sources.deeptmhmm build
uv run python -m accessible_surfaceome.controls build \
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
