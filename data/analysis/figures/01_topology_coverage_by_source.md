# `topology_coverage_by_source` — reproduction

A single **bubble matrix** of the 7 surface-call sources (rows) × 9 topology
features (columns), across the FULL any-yes-vote candidate-surfaceome universe
(6,586 genes — Sonnet yes/contextual incl. the PubMed rescue, OR any
optimized-DB vote). Each cell's dot encodes both metrics that differ only by
denominator:

- **dot area ∝ within-source enrichment** — % of that source's OWN calls carrying the feature (`|source ∩ feature| / |source|`)
- **dot color = coverage** — % of the whole surface universe those proteins represent (`|source ∩ feature| / |universe|`)

CSPA × glycosylation is a large, pale dot (~75% of its own calls but ~11% of the
universe — its N-glycocapture chemistry); SURFY/UniProt show the same glyco
enrichment at larger scale (dark, high-coverage); the **zero-DB Sonnet rescues
(960 genes) are dominated by likely-secreted (~51%) + glycosylated (~40%)
contextual-surface proteins** the classical-topology DBs miss — no GPCR / GPI.

## Run

```sh
uv run https://gist.githubusercontent.com/beccajcarlson/95b0f4cdcaf6a6b91f57539cd1515a25/raw/make_topology_coverage_by_source.py
```

Or after cloning the gist:

```sh
uv run make_topology_coverage_by_source.py
```

`uv` reads the [PyPA inline script metadata](https://packaging.python.org/en/latest/specifications/inline-script-metadata/)
header, installs matplotlib / pandas / seaborn in a one-shot env, and emits
`topology_coverage_by_source.{pdf,png}` in the current directory.

## Data + canonical generator

- **Bundled figure TSV** (`topology_coverage_by_source.tsv`): one row per
  universe GENE with the `src_*` source-inclusion flags, the optimized cutoff
  columns (`uniprot_optimized` / `cspa_optimized` / `n_sources_optimized`), and
  the 9 topology binary features on FULL genome-wide coverage. Built offline by
  [`scripts/build_figure_tsvs.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/build_figure_tsvs.py)
  from the full-universe source `per_protein_features_topology_full.tsv`, which
  is produced by
  [`scripts/export_s9_full_universe_features.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/export_s9_full_universe_features.py)
  — that export carries the UniProt REST + D1 (`topology_public`) pulls that give
  every gene, including the ~900 zero-DB Sonnet rescues the M1 feature table
  never scored, its real topology. (The earlier M1-limited source under-counted
  the zero-DB rescues, 794 vs 960, and left their topology unscored — so the
  Sonnet-only row read as misleadingly empty.)
- **Canonical generator** (uses the in-repo `_plotting_config`):
  [`scripts/topology_coverage_by_source.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/topology_coverage_by_source.py).
  The standalone script in this gist is a brand-styled mirror that reads the
  bundled TSV and renders without the project's plotting module.

## Method (brief)

The universe is the any-yes-vote union; `sonnet_only` = Sonnet-positive AND
`n_sources_optimized == 0` (960 genes). For each (source, feature): enrichment =
`|source ∩ feature| / |source|` (dot area), coverage = `|source ∩ feature| /
|universe|` (dot color). Topology features are derived from UniProt keywords +
features (and DeepTMHMM for the last), following
`scripts/audit_db_vs_sonnet_inclusion.py`:

- `topo_gpi_anchored`: UniProt keyword `GPI-anchor`.
- `topo_gpcr_7tm`: keyword `G-protein coupled receptor` AND `tm_count ≥ 5`.
- `topo_multi_pass_tm`: `tm_count ≥ 2` (after the GPCR bucket claims).
- `topo_single_pass_tm`: `tm_count == 1`.
- `topo_signal_only_secreted`: `signal_count ≥ 1 AND tm_count == 0 AND (Secreted keyword OR no lipidation)`.
- `topo_inner_leaflet_lipidated`: `(Prenylation OR Myristate keyword) AND tm_count == 0 AND signal_count == 0` (Ras/Src-family — cytoplasmic-facing).
- `topo_no_tm_no_signal`: keyword present, `tm_count == 0 AND signal_count == 0`.
- `up_has_glyc`: UniProt `feature_glycosylation_count ≥ 1`.
- `deeptm_TM_NO_SP`: DeepTMHMM class `TM` (TM helix, no signal peptide) — from `topology_public`, genome-wide.
