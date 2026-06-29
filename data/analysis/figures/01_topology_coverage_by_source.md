# `topology_coverage_by_source` — reproduction

What each of the 6 surface-call sources (5 M1 databases + Sonnet 4.6 triage)
preferentially captures by protein topology, across the 6,588-protein
cohort-tightened candidate-surfaceome universe.

For every (source × topology class) pair, the bar height is the share
of the universe that the source includes AND that has the topology
feature — so the y-axis is `% of any-yes-vote universe`, denominator
6,588. Sonnet sits leftmost as the implicit reference; the 5 DBs
follow in the same color order as `make_db_correctness_by_class.py`.

The 9 panels are 7 hand-picked architecture classes (GPI, 7TM GPCR,
multi-pass TM, single-pass TM, likely-secreted, inner-leaflet
lipidated, no-TM-no-signal) plus glycosylation and the
`deeptm_TM_NO_SP` (DeepTMHMM TM-without-signal-peptide) class.

## Run

```sh
uv run https://gist.githubusercontent.com/beccajcarlson/95b0f4cdcaf6a6b91f57539cd1515a25/raw/make_topology_coverage_by_source.py
```

Or after cloning the gist:

```sh
uv run make_topology_coverage_by_source.py
```

`uv` reads the [PyPA inline script metadata](https://packaging.python.org/en/latest/specifications/inline-script-metadata/)
header (`# /// script ... # ///`), installs matplotlib / pandas /
seaborn / httpx in a one-shot env, and emits
`topology_coverage_by_source.{pdf,png}` in the current directory.

## Data + canonical generator

- **Per-protein feature table** (~2.8 MB, plain TSV):
  [`data/analysis/db_vs_sonnet_inclusion/per_protein_features.tsv`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/data/analysis/db_vs_sonnet_inclusion/per_protein_features.tsv).
  One row per universe protein with the 6 source-inclusion flags,
  topology-class one-hots, UniProt feature counts, DeepTMHMM
  classification, and HGNC family flags.
- **Canonical generator** (uses the in-repo `_plotting_config` and
  builds the feature table from D1 + bundled raw sources):
  [`scripts/audit/audit_db_vs_sonnet_inclusion.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/audit/audit_db_vs_sonnet_inclusion.py).
  The standalone script in this gist is a thin reproduction that
  fetches the pre-computed feature table and renders the figure
  without depending on the project's plotting module.

## Method (brief)

For each (source, topology feature) pair, the script counts proteins
satisfying `(source-included) AND (feature-positive == 1)` and
divides by the size of the universe (6,588 — every member of the
universe has ≥1 yes vote across the 6 sources by construction, so the
denominator equals the any-yes-vote count).

Topology features are derived from UniProt keywords + features as
follows:
- `topo_gpi_anchored`: UniProt keyword `GPI-anchor`.
- `topo_gpcr_7tm`: UniProt keyword `G-protein coupled receptor`
  AND `feature_transmembrane_count ≥ 5`.
- `topo_multi_pass_tm`: `tm_count ≥ 2` (after the GPCR bucket claims).
- `topo_single_pass_tm`: `tm_count == 1`.
- `topo_signal_only_secreted`: `signal_count ≥ 1 AND tm_count == 0
  AND (Secreted keyword OR no lipidation)`.
- `topo_inner_leaflet_lipidated`: `(Prenylation OR Myristate keyword)
  AND tm_count == 0 AND signal_count == 0` — captures Ras-family
  GTPases (KRAS, RhoA), Src-family kinases (SRC, LCK).
- `topo_no_tm_no_signal`: everything else with `tm_count == 0 AND
  signal_count == 0`.
- `up_has_glyc`: UniProt `feature_glycosylation_count ≥ 1`.
- `deeptm_TM_NO_SP`: DeepTMHMM predicted-topology class `TM` (TM
  helix present, signal peptide absent).

See `scripts/audit/audit_db_vs_sonnet_inclusion.py` for the full topology-
class derivation rules and the feature-build pipeline.
