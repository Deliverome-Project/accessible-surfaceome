# Expression builder (A2 → ExpressionRow list)

You receive an A2 `EvidenceClaim` ledger and emit a JSON ARRAY of
`ExpressionRow` rows. Each row is ONE surface-expression read keyed by a
**tissue** and/or a **cell type of origin** plus a **disease context** — the
unified pivot that replaced the old separate tissue / cell-type tables.

## Source claims

Claims with `claim_type=tissue_expression` (and any `surface_expression`
claim that names a tissue or cell type) are the input. Read each claim's
`claim` prose and `quote` — extract the tissue, the cell type when named,
the present-level (high/moderate/low/absent), and the disease context
(normal/tumor/…).

## Surface-protein evidence ONLY (CRITICAL)

An `ExpressionRow` reports where the protein sits **on the cell surface** —
a surface-accessibility readout, NOT a transcript or total-abundance one.
Judge each claim by the method in its `quote`:

* **Emit** a row only when the call rests on a **surface-localization**
  method: non-permeabilized / membranous IHC or IF, flow cytometry on intact
  (non-permeabilized) cells, surface biotinylation, cell-surface /
  membrane-fraction mass spec, or an explicit "plasma membrane" read.
* **DROP** claims supported only by **RNA** (RNA-seq, GTEx, HPA-RNA,
  scRNA-seq, qPCR, microarray) or **total / whole-cell protein**
  (whole-lysate western, total-proteome MS with no surface fractionation,
  permeabilized IF/IHC that can't separate surface from intracellular).
* When a claim is ambiguous about modality, do NOT emit it.

Never manufacture a row from RNA / total protein — a tissue or cell type
with no surface support simply gets no row.

## Tox-risk organ coverage

Normal-tissue surface expression in the high-consequence organs —
**liver, lung, kidney, GI tract, heart, brain** — is the on-target /
off-tumor toxicity signal. When the ledger carries surface-backed
normal-tissue claims for these organs, emit a `disease_context=normal`
row (positive OR negative). A credible **negative** read (e.g. "no
membranous staining in normal kidney") is informative — emit it as
`present=absent` with its cite rather than omitting it.

## What you emit

ONE fenced ```json block containing a JSON ARRAY. Empty `[]` is fine.

## Schema fields

- `tissue` — free-text tissue / organ (e.g. `cerebellum`, `kidney cortex`).
  Set it whenever the read names a tissue; `null` only when the source gives
  a bare cell type with no tissue.
- `cell_type` — free-text cell of origin (e.g. `Purkinje neurons`,
  `pancreatic beta cells`, `podocytes`, `CD8+ T cells`). `null` for a
  tissue-level read with no cell breakdown.
- `present` — closed enum: `high`, `moderate`, `low`, `absent`, `mixed`,
  `unknown`. `mixed` when the ledger has both high and low reads for the
  same (tissue, cell_type, disease_context) across sources.
- `disease_context` — closed enum: `normal`, `tumor`, `tumor_adjacent`,
  `other_disease`, `mixed`, `unknown`.
- `disease_label` — OPTIONAL free text naming the SPECIFIC disease the enum
  can't (set it whenever `disease_context = other_disease`, and for
  `tumor` / `tumor_adjacent` when the tumor type is worth naming): e.g.
  "Fabry disease", "diabetic nephropathy", "lung adenocarcinoma". Leave it
  out for a plain `normal` read or a generic unnamed tumor. The viewer shows
  this in place of the bare enum (so "Fabry disease", not "Other disease").
- `cell_states` — free-text list of cell states ("activated",
  "stress-induced"). May be empty.
- `cited_evidence_ids` — every `evidence_id` whose claim contributed.

## Grouping (CRITICAL)

**One row per (tissue, cell_type, disease_context) triple, NOT one row per
claim.** If three papers report `cerebellum` / `Purkinje neurons` / `normal`
as `high`, emit ONE row with three `cited_evidence_ids`.

- A tissue-level read (no cell type) → `tissue` set, `cell_type` null.
- A cell-of-origin read → `cell_type` set, `tissue` set to the tissue it was
  observed in (null if the source names no tissue). The same cell type in
  two tissues → two rows.
- When sources disagree on level for the same triple, use `present="mixed"`
  and keep both cites. Don't pick a winner.

## Disease-context rows — emit the normal AND the disease read

For a given tissue / cell type, emit a separate row for every
`disease_context` the ledger supports — keep the `normal` row (the
off-tumor toxicity baseline) AND any `tumor` / `tumor_adjacent` /
`other_disease` row, **even when their surface levels are identical**.
Seeing the normal level and the disease level side by side is the point.
Do NOT drop a disease row just because it restates the normal level. When
it DOES differ (up, down, or normal `absent` ⇄ disease present) that
differential is the headline signal — but the matching case is still worth
showing. (The viewer orders `normal` before the disease rows, so you don't
need to order them here.)

**You have no tools.** Cite-only over the ledger.
