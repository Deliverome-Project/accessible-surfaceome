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
  doesn't prove extracellular exposure. This grade EXPLICITLY includes
  permeabilized immunofluorescence with strong plasma-membrane / PM-rim
  colocalization (e.g. co-stain with a PM marker), ESPECIALLY when the
  deterministic canonical topology already places the ECD extracellular.
- `conflicting` — **reserved for true logical / mechanistic
  inconsistency**. The bar is high: two pieces of evidence cannot
  BOTH be true given a plausible mechanism. Example: one paper
  reports the protein is constitutively absent from the cell entirely
  (gene not expressed in any context) AND another paper reports
  direct surface staining in that same baseline context — the two
  claims can't be reconciled without one being wrong.
  **Context- or cell-state-dependent variation is NOT conflicting.**
  A protein that's inner-leaflet anchored in normal cells but
  surface-exposed in cancer cells (e.g. SRC's ALE-mediated
  topology inversion) is **state-dependent**, not conflicting —
  both observations are coherent under a plausible mechanism
  (different cell state ⇒ different topology). Same for:
    * tissue-restricted surface expression vs broad RNA absence
      (cell-type variation, not conflict)
    * activation-induced surface presentation vs resting-state
      intracellular (state variation, not conflict)
    * isoform-specific surface exposure vs canonical-isoform
      intracellular (isoform variation, not conflict)
  These cases should be graded by the strength of the SURFACE
  evidence in the relevant context (e.g. `direct_multi_method` if
  there's solid surface methodology for the cancer / activated /
  alt-isoform state) and have the context variation captured via
  `state_dependence=high` + the biological_context section, NOT
  by collapsing the call to `conflicting`.
- `weak` — db_annotations / review_assertions / RNA-level only, OR
  permeabilized reads with NO membrane-localized signal — i.e. reserve
  `weak` for genuinely non-localizing or assertion-only evidence. Do NOT
  put permeabilized IF with strong PM / PM-rim colocalization here; that
  lifts to `supportive_but_indirect` (above).

  NOTE: this is the gene-level evidence_grade tiebreaker ONLY. Permeabilized
  assays still stay `expression_only` on the METHODS side
  (methods_builder) — a permeabilized assay can't PROVE surface
  accessibility — so the underlying claim's relevance stays
  `expression_only` even when perm-IF-with-PM-colocalization lifts the
  GRADE from `weak` to `supportive_but_indirect`.

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
  **in a logically incompatible way** with the positive evidence.
  High bar: same context, same conditions, mechanistically
  incompatible. A definitive nonperm negative-staining result in
  the same cell line + same activation state as a positive surface
  claim → contradicts. A canonical-topology description that just
  describes the BASELINE state in a different context (e.g. normal
  vs cancer cells, resting vs activated) → NOT a contradiction,
  use `tangential` instead. State / cell-type / isoform variation
  is captured by `state_dependence` + biological_context, not by
  forcing the grade to `conflicting`.
* `tangential` — the claim informs the picture but doesn't commit to
  either pole. Includes: cell-type expression context unrelated to
  the surface call, mechanistic biology that explains BUT DOESN'T
  REFUTE the surface evidence (e.g. canonical topology that
  describes baseline biology for a state-conditional surface form),
  background biology relevant to interpretation.
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

**Worked SRC example** (the canonical 5b.8 case, with the
state-dependent-is-not-conflicting refinement applied):

```
"claim_stances": [
  {"claim_id": "a1_evi_01", "stance": "supports_surface",    "weight": "high",
   "note": "eSrc translocation in cancer cells, in vitro + in vivo"},
  {"claim_id": "a1_evi_02", "stance": "supports_surface",    "weight": "high",
   "note": "antibody-mediated tumor killing in xenografts (cancer state)"},
  {"claim_id": "a1_evi_05", "stance": "tangential",          "weight": "high",
   "note": "canonical inner-leaflet topology — describes baseline state, NOT a contradiction (different state)"},
  {"claim_id": "a1_evi_06", "stance": "supports_surface",    "weight": "low",
   "note": "chick chondrogenic cell surfaceome MS, weak species transfer"},
  {"claim_id": "a1_evi_12", "stance": "supports_surface",    "weight": "high",
   "note": "non-permeabilized surface biotinylation"},
  {"claim_id": "a1_evi_15", "stance": "tangential",          "weight": "high",
   "note": "canonical topology, baseline state (not a refutation of cancer-state surface form)"}
],
```

The canonical inner-leaflet claims (a1_evi_05, a1_evi_15) describe
SRC's BASELINE state in normal cells. They DON'T contradict the
cancer-state surface form — the two coexist under the ALE-driven
topology-inversion mechanism. Marking them `contradicts_surface`
forces the grade to `conflicting`, which is wrong here. They're
`tangential` to the surface call (they inform the baseline picture
that `state_dependence=high` captures) and the grade is
`direct_single_method` — anchored on the eSrc papers' direct surface
methodology, with the state-conditionality flagged separately.

Only mark a canonical-topology claim as `contradicts_surface` when
it's incompatible with the surface-positive evidence under EVERY
plausible mechanism (e.g. a definitive negative-staining result
under the same conditions as a positive-staining claim).

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

**You have no tools.** Cite-only over the ledger.
