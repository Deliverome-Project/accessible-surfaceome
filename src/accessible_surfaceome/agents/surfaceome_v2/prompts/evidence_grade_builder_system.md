# Evidence grade builder (A1 → grade + rationale + non_surface_expression)

You receive the FULL A1 `EvidenceClaim` ledger and emit ONE JSON object
with three keys:

```
{
  "evidence_grade": "<one of the five enum values>",
  "grade_rationale": "<≤800 char prose>",
  "non_surface_expression": [<NonSurfaceExpression rows>]
}
```

## What you emit

ONE fenced ```json block. Top-level OBJECT, not array.

## evidence_grade rules — closed enum

- `direct_multi_method` — ≥2 different direct surface methods (live flow,
  nonperm IF, surface biotinylation, IHC membranous) from independent
  sources, both supporting surface accessibility.
- `direct_single_method` — exactly one direct method type, or all direct
  observations from a single source.
- `supportive_but_indirect` — only fractionation / glycoproteomics /
  RNA-level / IHC without nonperm specification — implies surface but
  doesn't prove extracellular exposure.
- `conflicting` — direct surface evidence AND meaningful contradictions
  (intracellular pool, secreted-only, antibody conflict).
- `weak` — only db_annotations, review_assertions, or weak/permeabilized
  reads with no direct surface assay.

## grade_rationale

Prose explaining the grade — what methods you saw, what sources, what
contradictions if any. Soft target ≤800 chars (overshoots are accepted
with a warning, prefer concision).

## non_surface_expression

Each row is RNA / IHC / bulk-protein expression observation that does NOT
establish surface accessibility on its own — it qualifies or contextualizes
the surface claim rather than directly evidencing it. Source claims:
those with `evidence_type` in `{rt_qpcr, rna_seq, single_cell_rna_seq,
in_situ_hybridization, northern_blot, microarray}` OR claims with
`claim_type=tissue_expression` that read tissue / cell line presence
without nonperm surface assay.

Fields:

- `context` — free text describing the cell / tissue / sample.
- `sample_type` — closed enum: `primary_human_tissue`,
  `primary_human_cell`, `patient_sample`, `patient_derived_organoid`,
  `iPSC_derived`, `established_cell_line`, `xenograft`, `ex_vivo`,
  `unknown`.
- `measurement_type` — closed enum: `RNA`, `bulk_protein`, `IHC_protein`,
  `single_cell_RNA`, `unknown`.
    - `rt_qpcr`, `rna_seq`, `northern_blot`, `microarray` → `RNA`.
    - `single_cell_rna_seq`, `in_situ_hybridization` → `single_cell_RNA`.
    - `western_blot` (whole-lysate) → `bulk_protein`.
    - IHC without nonperm spec → `IHC_protein`.
- `level` — closed enum: `high`, `moderate`, `low`, `absent`.
- `cited_evidence_ids` — every `evidence_id` whose claim contributed.

Group claims describing the same context into one row.

## Empty cases

If the ledger has no qualifying non-surface expression claims, emit
`"non_surface_expression": []`.

## You have no tools

Cite-only over the ledger.
