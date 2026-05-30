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
- `cell_types` — free-text list of cell types specifically named for
  this tissue ("Purkinje cells", "alpha cells"). May be empty.
- `cell_states` — free-text list of cell states ("activated",
  "stress-induced"). May be empty.
- `cited_evidence_ids` — every `evidence_id` whose claim contributed.

## Grouping (CRITICAL)

**One row per (tissue, disease_context) pair, NOT one row per claim.**
If three claims from three different papers all report `cerebellum` as
`high` in normal tissue, emit ONE row with three `cited_evidence_ids`.

The same tissue can legitimately appear twice with different
`disease_context` (e.g. one row for kidney/normal, another for
kidney/tumor) — that's allowed.

When sources disagree about presence level for the same
(tissue, disease_context), use `present="mixed"` and note both reads in
`cited_evidence_ids`. Don't pick a winner.

## You have no tools

Cite-only over the ledger.
