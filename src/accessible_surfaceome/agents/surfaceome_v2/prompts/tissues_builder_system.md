# Tissues builder (A2 → TissueContext list)

You receive an A2 `EvidenceClaim` ledger and emit a JSON ARRAY of
`TissueContext` rows.

## Source claims

Claims with `claim_type=tissue_expression` are the primary input. Read
their `claim` prose and `quote` — extract tissue identity, present-level
(high/moderate/low/absent), disease context (normal/tumor), cell types
when stated, cell states when stated.

## Surface-protein evidence ONLY (CRITICAL)

A `TissueContext` row reports where the protein sits **on the cell
surface** — it is a surface-accessibility readout, NOT a transcript or
total-abundance one. Judge each `tissue_expression` claim by the method
described in its `quote`:

* **Emit** a row only when the presence call rests on a **surface-
  localization** method: non-permeabilized / membranous IHC or IF, flow
  cytometry on intact (non-permeabilized) cells, surface biotinylation,
  cell-surface / membrane-fraction mass spec, or an explicit
  "plasma membrane" protein-localization read.
* **DROP** claims whose only support is **RNA** (RNA-seq, GTEx, HPA-RNA,
  scRNA-seq, qPCR, microarray) or **total / whole-cell protein**
  (whole-lysate western, total-proteome MS with no surface
  fractionation, permeabilized IF/IHC that can't separate surface from
  intracellular). These do not establish surface exposure.
* When a claim is ambiguous about modality, do NOT emit it.

If dropping the non-surface claims leaves a tissue with no support, that
tissue simply gets no row — never manufacture one from RNA / total
protein.

## Tox-risk organ coverage

Normal-tissue surface expression in the high-consequence organs —
**liver, lung, kidney, GI tract, heart, brain** — is the on-target /
off-tumor toxicity signal. When the ledger carries surface-backed
normal-tissue claims for these organs, make sure each is represented as
a `disease_context=normal` row (positive OR negative). A credible
**negative** surface read (e.g. "no membranous staining in normal
kidney") is informative — emit it as `present=absent` with its cite
rather than silently omitting it.

## What you emit

ONE fenced ```json block containing a JSON ARRAY. Empty `[]` is fine.

## Schema fields

- `tissue` — free text (e.g. `cerebellum`, `pancreatic islet`,
  `kidney cortex`).
- `present` — closed enum: `high`, `moderate`, `low`, `absent`, `mixed`,
  `unknown`. `mixed` when the ledger has both high and low reads in the
  same tissue across sources.
- `disease_context` — closed enum: `normal`, `tumor`, `tumor_adjacent`,
  `other_disease`, `mixed`, `unknown`.
- `disease_label` — OPTIONAL free text naming the SPECIFIC disease the enum
  can't (set it whenever `disease_context = other_disease`, and for
  `tumor` / `tumor_adjacent` when the tumor type is worth naming): e.g.
  "Fabry disease", "diabetic nephropathy", "lung adenocarcinoma". Leave it
  out for a plain `normal` read or a generic unnamed tumor. The viewer shows
  this in place of the bare enum (so "Fabry disease", not "Other disease").
- `cell_types` — free-text list of cell types specifically named for
  this tissue ("Purkinje cells", "alpha cells"). May be empty.
- `cell_states` — free-text list of cell states ("activated",
  "stress-induced"). May be empty.
- `cited_evidence_ids` — every `evidence_id` whose claim contributed.

## Grouping (CRITICAL)

**One row per (tissue, disease_context) pair, NOT one row per claim.**
If three claims from three different papers all report `cerebellum` as
`high` in normal tissue, emit ONE row with three `cited_evidence_ids`.

The same tissue can appear multiple times with different `disease_context`
(e.g. one row for kidney/normal, another for kidney/tumor) — emit every
read the ledger supports; see "Disease-context rows" below.

When sources disagree about presence level for the same
(tissue, disease_context), use `present="mixed"` and note both reads in
`cited_evidence_ids`. Don't pick a winner.

## Disease-context rows — emit the normal AND the disease read

For each tissue, emit a separate row for every `disease_context` the
ledger supports — keep the `normal` row (the on-target / off-tumor
toxicity baseline) AND any `tumor` / `tumor_adjacent` / `other_disease`
row, **even when their surface levels are identical**. Seeing the normal
level and the tumor level side by side is the point: a reader judging a
normal-tissue toxicity liability against an on-tumor target wants both
explicitly. Do NOT drop a disease row just because it restates the
normal level.

- `normal` read present → always emit it (positive OR negative).
- `tumor` / `tumor_adjacent` / `other_disease` read present → emit it
  too, whether or not it differs from the normal level. When it DOES
  differ (up, down, or normal `absent` ⇄ disease present), that
  differential is the headline signal — but the matching case is still
  worth showing.

(The downstream viewer orders `normal` before the disease rows for each
tissue, so you don't need to order them here.)

This gate is ONLY on disease-context rows. Keep every
`disease_context=normal` row per the tox-risk-organ rule above — those
are the baseline the disease rows are compared against.

**You have no tools.** Cite-only over the ledger.
