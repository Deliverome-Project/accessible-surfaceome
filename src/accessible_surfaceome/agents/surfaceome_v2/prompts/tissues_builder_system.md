# Tissues builder (A2 → TissueContext list)

You receive an A2 `EvidenceClaim` ledger and emit a JSON ARRAY of
`TissueContext` rows.

## Source claims

Claims with `claim_type=tissue_expression` are the primary input. Read
their `claim` prose and `quote` — extract tissue identity, present-level
(high/moderate/low/absent), disease context (normal/tumor), cell types
when stated, cell states when stated.

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
