# `surface_evidence_assay_types` — reproduction

Which experiments actually established the surface calls in the catalog, and
how often each one was the only thing holding a call up.

The catalog already exposes `evidence_grade` — how direct the evidence is and
whether more than one method contributed — but it never names the assay. So a
gene marked "direct, single method" could rest on flow cytometry or on a single
surfaceome mass-spec hit, and a reader cannot tell which. This figure names them.

## Panel a — prevalence

Genes with at least one **supporting** surface-expression claim from each assay.
Teal bars are assays that put a probe on an intact cell (flow cytometry, surface
biotinylation, surfaceome MS, immunofluorescence, IHC); grey bars are everything
else — review assertions, functional readouts, structures, transcript measurements.

## Panel b — how often it stood alone

The share of those genes for which the assay was the **only primary-tier assay**
supporting the call. Remove it and the call has no direct experimental support left.

Panel b is the one worth reading. Prevalence mostly tracks how common a technique
is in the literature. Standing alone tracks how much weight the catalog is placing
on it:

- **Surfaceome mass spec** is 7th by prevalence (866 genes) but the highest of any
  intact-cell assay at standing alone (7.0%). For those genes a surfaceome hit is
  often the only published experiment that put a probe on the outside of the protein.
- **Surface biotinylation** is the mirror image — 495 genes, but alone only 0.8% of
  the time. It travels with corroborating evidence.
- **Review assertion** is prevalent (2,033 genes) and almost never load-bearing
  (0.3%), which is the expected shape: reviews are secondary-tier by construction.

## Scope

Every filter below changes the answer, so all of them are stated:

- `claim_type = 'surface_expression'` only. Tissue-expression and topology rows
  reuse the same assay vocabulary but say nothing about whether the protein
  reaches the surface; counting them inflates every assay uniformly.
- `direction = 'supports'` only. An assay arguing *against* surface localization
  is not evidence the call rests on.
- Genes in a surface-positive deep-dive tier (canonical / likely / low), so
  "only assay" means only assay behind a real surface call.
- Assays under **50 genes** are omitted. A sole-rate computed over 26 genes is
  noise and invites a comparison against a rate over 2,796 that the data cannot
  support. The dropped assays are in the bundled TSV if you want them.

## Run

```sh
uv run make_surface_evidence_assay_types.py
```

`uv` reads the [PyPA inline script metadata](https://packaging.python.org/en/latest/specifications/inline-script-metadata/)
header, installs matplotlib / seaborn / pandas in a one-shot env, and emits
`surface_evidence_assay_types.{pdf,png}` in the current directory.

## Data + canonical generator

- **Bundled TSV** — `surface_evidence_assay_types.tsv`, one row per
  `evidence_type` with `genes_used`, `genes_sole`, `genes_sole_primary`,
  `pct_sole`, `pct_sole_primary`, `n_rows`. Note the TSV carries **two**
  sole-measures: `genes_sole` (only assay of any tier) and `genes_sole_primary`
  (only primary-tier assay, what panel b plots). They differ because an assay can
  be the lone primary source while secondary rows corroborate it.
- **TSV builder** — [`scripts/build_figure_tsvs.py:build_surface_evidence_assay_types`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/build_figure_tsvs.py)
- **Upstream D1 export** — [`scripts/figures/export_deep_dive_figure_source.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/figures/export_deep_dive_figure_source.py)
  (`_evidence_types_sql`), which walks `surface_annotation.annotation_json` →
  `$.evidence` with `json_each`.
- **Canonical generator** — [`scripts/figures/surface_evidence_assay_types.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/figures/surface_evidence_assay_types.py)
- **Assay vocabulary** — the closed `EvidenceType` enum in
  [`src/accessible_surfaceome/tools/_shared/models.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/src/accessible_surfaceome/tools/_shared/models.py)
