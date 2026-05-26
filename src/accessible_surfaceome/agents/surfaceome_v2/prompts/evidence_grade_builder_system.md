# Evidence grade builder (A1 → grade + claim_stances + rationale + non_surface_expression)

You receive the FULL A1 `EvidenceClaim` ledger and emit ONE JSON object
with four keys, **in this order** (so the structured per-claim call
comes first; the rationale then summarizes the stances rather than the
reverse):

```
{
  "evidence_grade": "<one of the five enum values>",
  "claim_stances": [<ClaimStanceRow entries — one per claim that informed the grade>],
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

## claim_stances — emit BEFORE grade_rationale

One row per `EvidenceClaim` in the input ledger that informed your
grade verdict. Skip claims that are truly tangential / not load-bearing
on the grade (don't pad). Field shape:

```
{
  "claim_id": "<one of the input ledger's evidence_ids — must resolve>",
  "stance": "<supports_surface | contradicts_surface | tangential | expression_only>",
  "weight": "<high | moderate | low>",
  "note": "<optional ≤120-char qualifier or null>"
}
```

**stance — closed enum:**

* `supports_surface` — the claim positively backs surface accessibility
  (direct surface methodology AND/OR functional engagement at the
  extracellular face).
* `contradicts_surface` — the claim refutes surface accessibility
  (canonical intracellular topology, secreted-only assertion, negative
  surface-staining result).
* `tangential` — the claim informs the picture but doesn't commit to
  either pole (cell-type expression context, mechanistic biology
  unrelated to the surface call).
* `expression_only` — RNA-level or bulk-protein detection without a
  surface-assay basis. These don't establish surface accessibility on
  their own. Also goes into the `non_surface_expression` rollup below.

**weight — closed enum (apply these criteria, not vibes):**

* `high` — direct surface methodology (live flow, nonperm IF, surface
  biotin, IHC membranous-nonperm) WITH knockout/siRNA control OR
  corroboration across multiple independent sources. Also: review
  articles that aggregate ≥3 primary sources count as `high` when
  there's no contradicting evidence.
* `moderate` — direct methodology, single source, weak antibody
  validation (vendor-only datasheet, no KO control). OR a strong
  indirect signal (e.g. surface biotinylation MS in 2+ cell lines).
* `low` — indirect-only (fractionation, glycoproteomics without
  surface specification) OR a single mention without methodology
  detail OR review-level assertion with no primary citation traced.

**Why emit stances before the rationale?** So the structured per-claim
call commits FIRST and the rationale then summarizes the stances.
Writing the rationale first and back-filling stances to match leads to
prose-driven post-hoc rationalization; the stance map should drive the
prose, not the other way around.

**Worked SRC example** (the canonical 5b.8 case):

```
"claim_stances": [
  {"claim_id": "a1_evi_01", "stance": "supports_surface",    "weight": "high",
   "note": "eSrc translocation, in vitro + in vivo"},
  {"claim_id": "a1_evi_02", "stance": "supports_surface",    "weight": "high",
   "note": "antibody-mediated tumor killing in xenografts"},
  {"claim_id": "a1_evi_05", "stance": "contradicts_surface", "weight": "high",
   "note": "canonical inner-leaflet topology, decades of evidence"},
  {"claim_id": "a1_evi_06", "stance": "supports_surface",    "weight": "low",
   "note": "chick chondrogenic cell surfaceome MS, weak species transfer"},
  {"claim_id": "a1_evi_12", "stance": "supports_surface",    "weight": "high",
   "note": "non-permeabilized surface biotinylation"},
  {"claim_id": "a1_evi_15", "stance": "contradicts_surface", "weight": "high",
   "note": "canonical topology, second independent source"}
],
```

This gives the catalog `3 high-weight supports + 2 high-weight
contradicts` → flagged as a real biological disagreement (not an
artifact-suspect 1-vs-many).

## grade_rationale

Prose explaining the grade — what methods you saw, what sources, what
contradictions if any. Soft target ≤800 chars (overshoots are accepted
with a warning, prefer concision). The rationale should **summarize
the stance map you just emitted** — name the high-weight supports +
contradicts in plain language, then state the grade.

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
