# `surfaceome_deterministic_features_placeholder` — reproduction (Supp Fig 13)

Distribution of **twelve deterministic per-gene features** across the
surfaceome, faceted by the real deep-dive surface-accessibility tier (collapsed
to four groups) plus a fifth facet — the **full Sonnet dual-triage surface
pool**. A 4×3 panel grid compares each feature across the five facets: the
three continuous features (TM-helix count, protein length, ECD length) are
violins; the nine boolean features (signal peptide, N/C-terminus extracellular,
mouse + cyno 1:1 ortholog, Schweke-2024 homo-oligomer, alt-isoform topology
change, concerning paralog, extracellular surface-bind site) are per-facet
fraction bars.

## The five facets

| Facet | Definition | Feature source |
|---|---|---|
| `canonical` / `likely` / `low` / `uncertain·no` | Deep-dive tier (`_dd_assign_bucket`), pooling the two weakest tiers | Deep-dive **records** (full coverage per deep-dived gene) |
| `Sonnet dual triage` | Every gene the genome-wide Sonnet triage (`genome_full_sonnet_ncbi_v2`) called `yes`/`contextual` (~4,236 with topology) | Genome-wide **D1 tables** (`topology_public`, `compara_*`, `schweke_homomer_public`, `surface_bind_*`) |

The Sonnet facet is a broader, *different* category from the tiers — its det
features come from the genome-wide tables (the same DeepTMHMM / Compara /
Schweke computation, ~100% topology coverage) because most of those genes
aren't deep-dived. It lets the reader compare the curated deep-dive tiers
against everything the triage flags surface. Boolean-feature absence in a table
is a real negative (no 1:1 ortholog / not a homomer / no concerning paralog / no
extracellular surface-bind site), matching how the records encode it. `pending`
(not-yet-deep-dived) genes are excluded from the deep-dive tiers.

**PRELIMINARY** — the deep-dive tiers are a partial sweep of the ~5,128
candidate genes, so those per-tier rates are provisional; the Sonnet pool is the
complete triage-flagged set.

## Run

```sh
uv run make_surfaceome_deterministic_features_placeholder.py
```

`uv` reads the [PyPA inline script metadata](https://packaging.python.org/en/latest/specifications/inline-script-metadata/)
header, installs matplotlib / numpy / pandas / seaborn in a one-shot env, and
emits `surfaceome_deterministic_features_placeholder.{pdf,png}` in the current
directory.

## Data + canonical generator

- **Bundled single TSV** (`surfaceome_deterministic_features_placeholder.tsv`):
  one row per gene with its `group` (a deep-dive tier or `sonnet_dual_triage`)
  + the twelve deterministic feature columns. Pre-joined by
  [`scripts/build_figure_tsvs.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/build_figure_tsvs.py)
  from the deep-dive export (`deep_dive_records.tsv`, for the tiers) unioned
  with the Sonnet-universe export (`sonnet_universe_det_features.tsv`, for the
  Sonnet pool).
- **Magnitude behind the boolean flags** (for reader analysis; not plotted).
  The boolean feature columns say *whether* a gene has a feature; six extra
  columns — joined from
  [`scripts/export_det_feature_detail.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/export_det_feature_detail.py)
  (the same genome-wide D1 tables, uniform across both facets) — give the
  magnitude, so you can filter/sort on it rather than just the yes/no:

  | Column | Magnitude behind the flag |
  |---|---|
  | `mouse_ortholog_pct_id` / `cyno_ortholog_pct_id` | `mouse/cyno_has_one2one` — the 1:1 ortholog % identity |
  | `homomer_stoichiometry` | `schweke_homomer` — Schweke stoichiometry (2 / 3 / 4 …) |
  | `top_paralog_symbol` / `top_paralog_ecd_pct` | `has_concerning_paralog` — the closest paralog + its ECD % identity |
  | `n_ec_surface_bind_sites` | `has_ec_surface_bind_site` — # extracellular surface-bind sites |

  Empty where the feature is absent (no paralog, not a homomer, …).
- **Canonical generator** (uses the in-repo `_plotting_config`):
  [`scripts/surfaceome_deterministic_features_placeholder.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/surfaceome_deterministic_features_placeholder.py).
  The standalone script in this gist reads the bundled TSV and renders without
  depending on the project's plotting module.
- **Sonnet det-feature export** (genome-wide D1 tables →
  `sonnet_universe_det_features.tsv`):
  [`scripts/export_sonnet_universe_det_features.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/export_sonnet_universe_det_features.py).

The mirror's `_fetch_tsv` is sibling-first: it reads the bundled TSV next to the
script (the gist case), falling back to the in-repo path otherwise.
