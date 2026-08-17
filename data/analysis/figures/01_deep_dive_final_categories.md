# `deep_dive_final_categories` — reproduction (Figure 5)

Two-panel summary of how the deep-dive agent sorts the surface cohort, and
the cross-cutting cell-type and cell-state facets that overlay the surface
tiers. Computed over the full deep-dive cohort (**5,130 genes**).

## Panel a — five-tier confidence spectrum

Each deep-dived gene is placed on a confidence spectrum:

- **canonical** (1,782) — the strict gold-standard surface tier
- **likely** (1,243) — the broader passes-likely surface set
- **low** (973) — low/moderate accessibility but weak evidence (maybe surface)
- **no** (1,078) — leaned not-surface
- **uncertain** (54) — ambiguous

`canonical` and `likely` are exactly the frontend catalog-preset predicates
(`passesCanonical` / `passesLikely`); the low/no/uncertain split of the
negatives is a figure-only refinement (the presets don't cover the negatives).

## Panel b — cross-cutting surface facets, by reason

The two cross-cutting surface facets — cell-type restricted and cell-state
induced — counted by the deep dive's `surface_call_reason` and broken out
across the three surface-bearing tiers (canonical / likely / low). Counting by
reason rather than the evidence-gated facet keeps the weak-evidence surface
calls that land in `low`. Each tier bar stacks three categories:

- **Cell-type restricted** — `surface_call_reason == 'tissue_restricted_surface'`
- **Induced — oncogenic** — `surface_call_reason ∈ {cell_state_induced,
  lysosomal_exocytosis}` with `induction_trigger == 'oncogenic'`
- **Induced — other** — the same induced reasons with any other trigger

Totals across the three tiers: **1,314 cell-type restricted** and **600
cell-state induced** (416 oncogenic, 184 other). Canonical carries no cell-type
restricted by construction (the canonical gate excludes
`tissue_restricted_surface`).

## Run

```sh
uv run make_deep_dive_final_categories.py
```

`uv` reads the [PyPA inline script metadata](https://packaging.python.org/en/latest/specifications/inline-script-metadata/)
header, installs matplotlib / seaborn / pandas in a one-shot env, and emits
`deep_dive_final_categories.{pdf,png}` in the current directory.

## Data + canonical generator

- **Bundled single TSV** (`deep_dive_final_categories.tsv`): one row per
  deep-dived gene with its `category` (tier), `surface_call_reason`,
  `induction_trigger`, and `facet`. Pre-joined by
  [`scripts/build_figure_tsvs.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/build_figure_tsvs.py).
- **Canonical generator** (uses the in-repo `_plotting_config`):
  [`scripts/deep_dive_final_categories.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/deep_dive_final_categories.py).
  The standalone script in this gist reads the bundled TSV and renders without
  depending on the project's plotting module.
- Bucket boundaries are pinned by the closed enums in
  [`src/accessible_surfaceome/tools/_shared/models.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/src/accessible_surfaceome/tools/_shared/models.py)
  (`TriageReason`, `InductionTrigger`).

The mirror's `_fetch_tsv` is sibling-first: it reads the bundled TSV next to the
script (the gist case), falling back to the in-repo path otherwise.
