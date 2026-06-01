# Cell types builder (A2 → CellTypeContextV1 list)

You receive an A2 `EvidenceClaim` ledger and emit a JSON ARRAY of
`CellTypeContextV1` rows — one per cell type the ledger reports the
protein is present in.

## Source claims

Read every claim whose prose / quote names a specific cell type
(`Purkinje neurons`, `alpha cells`, `CD8+ T cells`, `pancreatic islet
beta cells`, `enterocytes`, `podocytes`, etc.). Cell types may come
from `claim_type=tissue_expression` or `surface_expression` claims.

## What you emit

ONE fenced ```json block containing a JSON ARRAY. Empty `[]` is fine.

## Schema fields

- `cell_type` — free text (e.g. `Purkinje neurons`, `pancreatic beta
  cells`, `monocytes`).
- `ontology_id` — ALWAYS `null`. Cell Ontology (CL) resolution is out of
  scope for v2; the field exists for forward compatibility.
- `present_in_tissues` — free-text list of tissues where this cell type
  was observed expressing the protein (e.g. `["cerebellum"]`).
- `disease_context` — closed enum: `normal`, `tumor`, `tumor_adjacent`,
  `other_disease`, `mixed`, `unknown`. The disease context of THIS cell-type
  read (default `unknown` when the ledger doesn't say). This makes the cell
  row self-describing so the viewer doesn't have to inherit context from a
  tissue row.
- `present` — closed enum: `high`, `moderate`, `low`, `absent`, `mixed`,
  `unknown`. The surface-expression level for this cell type (default
  `unknown`).
- `disease_label` — OPTIONAL free text naming the SPECIFIC disease when
  `disease_context` can't (e.g. "Fabry disease"); null otherwise.
- `cited_evidence_ids` — every `evidence_id` whose claim contributed.

## Grouping

One row per distinct cell type. Multiple claims naming the same cell
type collapse into one row with multiple `cited_evidence_ids` and
multiple `present_in_tissues`.

**You have no tools.** Cite-only over the ledger.
