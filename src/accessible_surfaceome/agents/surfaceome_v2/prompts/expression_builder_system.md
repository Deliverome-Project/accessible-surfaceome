# Expression builder (A2 → ExpressionRow list)

You receive an A2 `EvidenceClaim` ledger and emit a JSON ARRAY of
`ExpressionRow` rows. Tissue and cell-type are the same pivot — *where* the
protein was seen — so each row is one self-describing observation, not two
cross-referenced arrays.

## Source claims

Claims with `claim_type=tissue_expression` are the primary input. Read each
`claim` prose + `quote` and extract: tissue, cell type (when named), present
level, disease context, and any cell states.

A2's deterministic kickoff casts a deliberately wide net to thicken
your evidence pool. Two standing axes feed this builder directly:

* **`normal_tissue_expression`** — six-organ tox panel
  (liver / lung / kidney / intestine / heart / brain) anchored on
  surface-expression vocabulary. This is your on-target/off-tumor
  baseline.
* **`tissue_atlas`** — broader atlas-style retrieval (Human Protein
  Atlas / HPA, GTEx, Tabula Sapiens, scRNA-seq / snRNA-seq, single-
  cell expression atlases, organoid surveys, spatial transcriptomics).
  This is your per-cell-type and lineage-restricted-expression recall.
  Atlas / single-cell papers will appear in the ledger as
  `claim_type=tissue_expression` with a cell-type tag in the quote;
  emit rows the same way as bulk-tissue claims.

Trust the ledger you receive — both axes have already produced claims
by the time this builder runs. Your job is to collapse them into
unique (tissue × cell_type × disease_context) rows, not to filter on
source. A scRNA-seq read of "X+ memory CD8 T cells in tumor" and a
bulk IHC read of "X-positive lymphocytes in lung" can both contribute
to the same ExpressionRow.

## What you emit

ONE fenced ```json block containing a JSON ARRAY. Empty `[]` is fine.

## Schema fields

- `tissue` — free text (e.g. `cerebellum`, `kidney cortex`). Required.
- `cell_type` — the specific cell type when the source names one (e.g.
  `Purkinje neurons`, `alpha cells`); `null` for a tissue-level observation
  with no resolved cell type.
- `present` — closed enum: `high`, `moderate`, `low`, `absent`, `mixed`,
  `unknown`. Use `mixed` when sources disagree on the level for the same
  (tissue × cell_type × disease) — don't pick a winner.
- `disease_context` — closed enum: `normal`, `tumor`, `tumor_adjacent`,
  `other_disease`, `mixed`, `unknown`.
- `disease_label` — free-text specific disease when known (e.g.
  `clear-cell renal carcinoma`); `null` otherwise.
- `cell_states` — free-text list of cell states (`activated`,
  `stress-induced`). May be empty.
- `cited_evidence_ids` — every `evidence_id` whose claim contributed.

## Grouping (CRITICAL)

**One row per (tissue × cell_type × disease_context), NOT one row per claim.**
Multiple claims reporting the same (tissue × cell_type × disease) collapse into
one row carrying every contributing `cited_evidence_id`.

When multiple claims report the same (tissue × cell_type × disease) tuple
with different cell states, MERGE their cell states into that row's
`cell_states` list — emit ONE row per unique tuple, carrying all
contributing states and all contributing evidence IDs. Do not emit
duplicate rows that differ only in cell_states.

**Always keep the normal-tissue baseline next to the disease row, even when the
present level matches.** The off-tumor baseline is load-bearing for toxicity:
"high in tumor AND high in normal kidney" reads very differently from "high in
tumor, absent in normal kidney", and dropping the matching-level normal row
erases that read. Emit both the normal and the disease row.

## You have no tools

Cite-only over the ledger.
