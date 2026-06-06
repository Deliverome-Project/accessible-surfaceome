# Contradiction builder (A1 → Contradiction list)

You receive an `EvidenceClaim` ledger and emit a JSON ARRAY of
`Contradiction` rows — one per piece of evidence that contradicts the
"this protein is surface accessible" hypothesis.

## When to emit a row

Emit a row for each claim whose `claim_type=contradictory`. Also
consider claims with `direction=refutes` even if `claim_type` is
something else — those are also contradictory.

If the ledger has none, emit an empty array `[]`.

## What you emit

ONE fenced ```json block containing a JSON ARRAY.

## Schema fields

- `claim` — prose describing the contradiction (free text, up to ~3
  sentences).
- `contradiction_type` — closed enum: `intracellular_pool`,
  `alternative_localization`, `secreted_only`, `cell_line_specific_absence`,
  `antibody_conflict`, `proteomics_conflict`, `isoform_conflict`,
  `other`.
- `severity_for_surface_accessibility` — closed enum: `high`, `moderate`,
  `low`, `unclear`. `high` when the contradiction would meaningfully
  weaken a target-discovery decision; `low` for incidental cell-line
  blips.
- `likely_explanation` — optional free-text reconciliation prose, e.g.
  "permeabilized IF picks up the ER pool that nonperm staining doesn't
  see" or "isoform-2 lacks the transmembrane segment."
- `cited_evidence_ids` — every `evidence_id` whose claim contributed to
  this row.

## Grouping

Multiple ledger claims describing the SAME contradiction (e.g. two
papers both reporting an intracellular pool) collapse into ONE row with
multiple cited_evidence_ids.

**You have no tools.** Cite-only over the ledger.
