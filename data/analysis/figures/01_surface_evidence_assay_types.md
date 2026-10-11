# `surface_evidence_assay_types` — reproduction

Which experiments showed the surface proteins in the catalog are actually on the
surface, and how often each one was the only direct evidence behind a call.

The catalog's `evidence_grade` says how many direct methods a gene has (multi vs
single). It never names them, so a gene graded "direct, single method" could rest
on live-cell flow cytometry or on one functional assay, and a reader cannot tell
which. This figure names them.

## Source: the methods block, not the evidence ledger

Each deep-dive record carries a `surface_evidence.methods` block: one row per
experiment, written by the methods builder from the cited quotes. Every row gets a
judgment of what the experiment shows:

- **Direct** (solid bars): an antibody or probe reached the protein from outside an
  intact cell. Live or non-permeabilized staining of an extracellular epitope or
  tag, membrane-impermeable labeling, or a functional readout that needs surface
  access.
- **Supporting only** (light bars): places the protein at the plasma membrane
  without showing the outside is reachable. Membrane-rim staining, fluorescent-
  protein fusions, membranous IHC. IHC is never direct, because sectioning
  exposes intracellular epitopes.

Rows judged membrane association only (fractionation), expression only or weak
are left out. The evidence grade is graded from this same block: 2,166 of the
2,266 genes with a direct row here carry a `direct_*` grade; the other 100 are
graded supportive (58), conflicting (32) or weak (10).

We use this block rather than the evidence ledger's `evidence_type` because the
ledger only names the technique mentioned in a quote. It labels permeabilized
immunofluorescence and whole-cell proteomics as surface assays, so it overcounts
immunofluorescence (2,272 genes vs 337 with direct IF) and surfaceome mass spec
(866 vs 321).

## Panels

- **a** — genes with direct evidence from each method (solid), plus genes where
  that method only reached the supporting level (light).
- **b** — the share of direct-evidence genes for which the method was the **only**
  direct method: remove it and the gene has no direct surface evidence left.
  Immunohistochemistry has 2 direct genes, too few for a share.

Color is assay family:

| Family | Methods |
|---|---|
| Imaging and cytometry | flow cytometry, immunofluorescence, immunohistochemistry |
| Surface labeling or capture | surface biotin pulldown, proximity labeling, cell-surface capture MS |
| Functional surface assay | something outside the cell acted on the protein: toxin, blocking or therapeutic antibody, ADC or CAR-T killing; radioligand binding on live cells; ectodomain shedding; transport of an extracellular substrate |
| Other | e.g. cell-surface ELISA / on-cell western, CITE-seq antibody tags, immuno-EM on intact cells, membrane-impermeable crosslinkers |

Surface labeling is not all mass spec. Surface biotin pulldowns are read out by
western blot more often than by MS; proximity labeling is mostly MS; cell-surface
capture is MS by definition.

## Category rules

The record's `method_family` and `method_subclass` overlap (a cell-surface capture
experiment can be filed under the biotinylation, glycoproteomics or mass-spec
family), so the subclass decides where it does:

1. `proximity_labeling` family → proximity labeling
2. `surface_biotinylation` subclass → surface biotin pulldown
3. `cell_surface_capture` / `N_glycoproteomics` subclass, or `glycoproteomics` family → cell-surface capture MS
4. flow subclasses or family → flow cytometry
5. IF subclasses or family → immunofluorescence
6. IHC subclasses or family → immunohistochemistry
7. `functional_surface_assay` family → functional surface assay
8. everything else → other

Genes are restricted to surface-positive deep-dive tiers (canonical / likely / low):
4,049 genes, of which 2,266 have at least one direct method.

## Run

```sh
uv run make_surface_evidence_assay_types.py
```

`uv` reads the [PyPA inline script metadata](https://packaging.python.org/en/latest/specifications/inline-script-metadata/)
header, installs matplotlib / seaborn / pandas in a one-shot env, and emits
`surface_evidence_assay_types.{pdf,png}` in the current directory.

## Data + canonical generator

- **Bundled TSV** — `surface_evidence_assay_types.tsv`, one row per method with
  `family`, `genes_direct`, `genes_supporting_only`, `genes_sole_direct`,
  `pct_sole_direct`, plus the cohort totals `n_surface_genes` and
  `n_genes_any_direct`.
- **TSV builder** — [`scripts/build_figure_tsvs.py:build_surface_evidence_assay_types`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/build_figure_tsvs.py)
  (holds the category rules above)
- **Upstream D1 export** — [`scripts/figures/export_deep_dive_figure_source.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/figures/export_deep_dive_figure_source.py)
  (`_surface_methods_sql`), which walks `surface_annotation.annotation_json` →
  `$.surface_evidence.methods` with `json_each`.
- **Canonical generator** — [`scripts/figures/surface_evidence_assay_types.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/figures/surface_evidence_assay_types.py)
- **Method vocabulary** — the closed `MethodFamily`, `MethodSubclass` and
  `AccessibilityRelevance` enums in
  [`src/accessible_surfaceome/tools/_shared/models.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/src/accessible_surfaceome/tools/_shared/models.py)
