# Evidence grade builder (A1 → grade + claim_stances + rationale + non_surface_expression + excluded_as_ligand_engagement)

**What "surface accessibility" means here:** the protein is at the
outer face of the plasma membrane of the cell that expresses it, or
becomes stably anchored to it. Evidence that the protein engages the
surface of a *different* cell as a soluble ligand is biology, not
surface accessibility of this protein. Grade against THIS bar — not
against the directness of the assay method in isolation.

You receive the FULL A1 `EvidenceClaim` ledger and emit ONE JSON object
with five keys, **in this order** (so the structured per-claim call
comes first; the rationale then summarizes the stances rather than the
reverse):

```
{
  "evidence_grade": "<one of the five enum values>",
  "claim_stances": [<ClaimStanceRow entries — one per claim that informed the grade>],
  "grade_rationale": "<≤800 char prose>",
  "non_surface_expression": [<NonSurfaceExpression rows>],
  "excluded_as_ligand_engagement": [<ExcludedClaim rows>]
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
  surface-exposed in cancer cells (e.g. an inner-leaflet kinase's
  ALE-mediated topology inversion) is **state-dependent**, not
  conflicting —
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

**Worked example — state-conditional surface form with a non-surface
baseline** (the canonical 5b.8 case, with the state-dependent-is-not-
conflicting refinement applied). Pull the SPECIFIC baseline-state
biology and cancer-state mechanism from the gene's actual evidence
ledger; the shape below is the template, not the content:

```
"claim_stances": [
  {"claim_id": "a1_evi_01", "stance": "supports_surface",    "weight": "high",
   "note": "outer-leaflet translocation in cancer cells, in vitro + in vivo"},
  {"claim_id": "a1_evi_02", "stance": "supports_surface",    "weight": "high",
   "note": "antibody-mediated tumor killing in xenografts (cancer state)"},
  {"claim_id": "a1_evi_05", "stance": "tangential",          "weight": "high",
   "note": "canonical baseline topology — describes the baseline state, NOT a contradiction (different state)"},
  {"claim_id": "a1_evi_06", "stance": "supports_surface",    "weight": "low",
   "note": "non-human cell-line surfaceome MS, weak species transfer"},
  {"claim_id": "a1_evi_12", "stance": "supports_surface",    "weight": "high",
   "note": "non-permeabilized surface biotinylation"},
  {"claim_id": "a1_evi_15", "stance": "tangential",          "weight": "high",
   "note": "canonical topology, baseline state (not a refutation of cancer-state surface form)"}
],
```

The canonical-baseline-topology claims (a1_evi_05, a1_evi_15) describe
the target's BASELINE state in normal cells. They DON'T contradict the
cancer-state surface form — the two coexist under the state-conditional
mechanism. Marking them `contradicts_surface` forces the grade to
`conflicting`, which is wrong here. They're `tangential` to the surface
call (they inform the baseline picture that `state_dependence=high`
captures) and the grade is `direct_single_method` — anchored on the
cancer-state-surface papers' direct surface methodology, with the
state-conditionality flagged separately.

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

### Citation discipline — inline cites on every specific claim

**Every numbered item, named experiment, mechanism, or method-specific
assertion in `grade_rationale` REQUIRES an inline `(aN_evi_NN)` cite
immediately after the claim, drawn from `claim_stances`.** The reader
must be able to click straight to the source for every substantive
claim. Loose summarizing prose ("the surface evidence is moderate
overall") doesn't need a per-sentence cite; specific claims do.

A specific claim is anything that:
- enumerates separate experiments (`(1)`, `(2)`, `(3)` lists)
- names an experimental method (live-cell flow, surface biotinylation,
  crosslinking, photoaffinity labeling, knockin / knockout, cryo-EM,
  proteinase-K protection, ChIP, etc.)
- names a mechanism, observation, or result (e.g. "ciliary PM
  localization in hypothalamic neurons", "competitive displacement",
  "VPS35-mediated retromer recycling")
- names a cell line, tissue, species, or assay condition

The schema enforces this: when `grade_rationale` contains
structured-claim markers AND `claim_stances` has ≥2 rows AND zero
inline cites are present, validation FAILS. Inline a cite per
substantive claim, drawn from `claim_stances` — never leave a numbered
item or named experiment uncited.

### Per-claim specificity

Each substantive claim in the rationale should also name (in addition
to its inline cite):
- the **assay readout** (what was measured — surface staining, flow MFI,
  crosslink band, localization pattern, structural complex)
- the **cell type / species** (mouse hypothalamic neurons, human
  monocytes, hepatocytes, etc.)
- the **permeabilization status** when relevant (live-cell, nonperm,
  permeabilized — say `permeabilization unspecified` rather than
  glossing it over)

A specific, citable, method-anchored claim looks like:
> *"endogenous epitope-tagged knockin mice showed compartment-specific
> PM localization in a defined neuronal population by IF (perm status
> unspecified) with an internal loss-of-function-mutant mislocalization
> control (a1_evi_07)"*

A vague claim that fails the discipline looks like:
> *"adaptor-mediated retromer recycling to the hepatocyte PM"* — no
> method, no perm status, no cite.

### Worked example — citation-disciplined rationale

Shape only; the prose is for a hypothetical class A GPCR. Apply the
SAME structure to whatever gene you're grading.

```
"grade_rationale": "Three direct lines of evidence support surface
exposure: (1) endogenous epitope-tagged knockin mice showing
compartment-specific PM localization in a defined neuronal population
by IF (perm status not specified) with a loss-of-function-mutant
mislocalization control (a1_evi_07); (2) photoaffinity crosslinking of
a small-molecule analogue on membrane fractions of human endothelial
cells with competitive displacement (a1_evi_12); (3) adaptor-mediated
retromer recycling restoring the protein at the hepatocyte plasma
membrane after internalization (a1_evi_11). None are live-cell nonperm
flow with KO control, and (2)/(3) are indirect — fractionation-based
and trafficking-inferred respectively — so the picture is strong
indirect evidence anchored by the canonical class A GPCR topology.
Graded supportive_but_indirect."
```

Every numbered item carries its `(aN_evi_NN)` chip. The reader can
click each to verify.

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

## excluded_as_ligand_engagement

Audit trail of A1 ledger claims that describe **the protein as a soluble
ligand engaging a surface receptor on another cell**, NOT the protein
being on the outer face of the plasma membrane that expresses it. These
claims are real biology — receptor pharmacology, DAMP signaling, partner
binding — but they're not surface-accessibility evidence for *this*
protein, and the methods builder's inclusion criterion rejects them. Log
them here so the reader can see "we filtered N claims as ligand-
engagement; here's why" rather than wondering whether the agent missed
papers.

Each row:

```
{
  "evidence_id": "<one of the input ledger's evidence_ids>",
  "reason": "<short why, ≤240 chars, name the receptor the protein was binding>"
}
```

**When a claim belongs here:**
- The protein is studied as an extracellular factor / DAMP / cytokine /
  chemokine / alarmin engaging a named receptor on another cell.
- Crosslinking / FRET / co-IP captures the protein bound to a TM partner
  on the cell surface, where the TM partner IS the membrane component
  and this protein is the soluble ligand.
- Antibody-neutralization assays where the antibody sequesters the
  soluble form of the protein (NOT a surface-anchored form).
- ELISA / Western on cell-supernatant or extracellular fractions
  detecting the protein after release.

Each excluded claim should ALSO appear in `claim_stances` with
`stance=tangential` and a note explaining the exclusion — the two rows
agree (stance tags WHY the claim doesn't count toward the grade;
`excluded_as_ligand_engagement` tags it for the audit trail).

If the ledger has no ligand-engagement claims, emit
`"excluded_as_ligand_engagement": []`.

## Empty cases

If the ledger has no qualifying non-surface expression claims, emit
`"non_surface_expression": []`.

**You have no tools.** Cite-only over the ledger.
