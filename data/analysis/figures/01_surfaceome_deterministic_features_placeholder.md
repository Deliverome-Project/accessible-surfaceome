# `surfaceome_deterministic_features_placeholder` — reproduction (Supp Fig 13)

Distribution of seven deterministic per-gene features across the
Sonnet-positive surfaceome (n = 4,249), faceted into three buckets. A
3×3 panel grid compares each feature across the buckets: TM-helix
count, protein length, signal peptide, N/C-terminus extracellular,
mouse + cyno 1:1 high-confidence ortholog presence, Schweke-2024
homo-oligomer state, and alt-isoform topology change.

**MOCK figure.** The deep-dive hues are placeholders derived from
Sonnet verdicts for now; they will be replaced once the deep-dive runs
over the full surfaceome:

| Bucket | Placeholder definition |
|---|---|
| `triage_yes` | Sonnet verdict `yes` (non-high confidence) |
| `deep_dive_high_conf` | Sonnet `yes` + high confidence |
| `deep_dive_likely_surface` | Sonnet verdict `contextual` |

## Run

```sh
uv run https://gist.githubusercontent.com/beccajcarlson/57cf3cc3db903ab39bc0ba315ce5e4d5/raw/make_surfaceome_deterministic_features_placeholder.py
```

Or after cloning the gist:

```sh
uv run make_surfaceome_deterministic_features_placeholder.py
```

`uv` reads the [PyPA inline script metadata](https://packaging.python.org/en/latest/specifications/inline-script-metadata/)
header, installs matplotlib / numpy / pandas / seaborn / httpx in a
one-shot env, and emits
`surfaceome_deterministic_features_placeholder.{pdf,png}` in the current
directory.

## Data + canonical generator

- **Bundled single TSV** (`surfaceome_deterministic_features_placeholder.tsv`):
  one tidy row per gene with the bucket assignment + the seven
  deterministic feature columns. Pre-joined by
  [`scripts/build_figure_tsvs.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/build_figure_tsvs.py)
  from `per_protein_features.tsv` × DeepTMHMM canonical + isoforms ×
  Schweke 2024 × Ensembl Compara.
- **Canonical generator** (uses the in-repo `_plotting_config`):
  [`scripts/surfaceome_deterministic_features_placeholder.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/surfaceome_deterministic_features_placeholder.py).
  The standalone script in this gist is a thin reproduction that reads
  the bundled TSV and renders the figure without depending on the
  project's plotting module.

The mirror's `_fetch_tsv` is sibling-first: it reads the bundled TSV
next to the script (the gist case), falling back to the raw GitHub URL
otherwise.
