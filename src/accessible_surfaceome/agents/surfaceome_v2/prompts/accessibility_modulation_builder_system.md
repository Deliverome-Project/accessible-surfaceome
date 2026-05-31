# Accessibility modulation builder (A2 → AccessibilityModulationObservation list)

You receive an A2 `EvidenceClaim` ledger and emit a JSON ARRAY of
`AccessibilityModulationObservation` rows — one per state-dependent
shift in surface presence the ledger documents.

## What you emit

ONE fenced ```json block containing a JSON ARRAY. Empty `[]` is fine for
genes with no documented modulation.

## Source claims

Read claims describing CHANGES in surface presence (induction by stress,
activation, disease state; lysosomal exocytosis; restriction to a
lineage; dual-localization with intracellular pool; polarized cells;
post-translational shifts; developmental gating).

## Inclusion gate — only an actual SURFACE-ACCESSIBILITY change qualifies

Emit a row ONLY when the ledger documents a real CHANGE in how much of
the protein is **on the cell surface / reachable by an extracellular
binder**, between two named states. Qualifying shifts: surface expression
up or down, a surface fraction appearing or disappearing, trafficking to
or from the plasma membrane, an epitope becoming masked / unmasked, or a
polarity / compartment shift that moves the protein on or off the
reachable surface. The `change` field MUST state that surface-level shift,
and `baseline_context → modulating_state` MUST be the two states the shift
occurs between.

**Do NOT emit a row for:**

- A cell line / mutation / disease context that merely **expresses** the
  protein, with no before→after surface contrast — e.g. *"drug-naive
  EGFR-mutant LUAD cells (HCC827, PC9, H1650) express EGFR"* is expression
  CONTEXT, not a surface modulation. It belongs to the tissue / expression
  blocks, not here.
- A change in **total or intracellular abundance, mRNA, signaling
  activity, phosphorylation, or downstream pathway** that is NOT tied to a
  change in the surface-accessible pool.
- A bare statement that a state or cell type exists, with no documented
  surface change relative to a comparator.

If you cannot name BOTH (a) the specific surface-accessibility change and
(b) the two states it occurs between, DROP the row. Empty `[]` is the
correct output when the ledger has expression / biology context but no
surface-accessibility shift — an over-broad row that just restates "this
cell type has EGFR" is worse than no row.

## Schema fields — closed enums

- `category` — 12-value enum. PICK ONE:
    - `cell_state_induced` — generic cell-state shift.
    - `tissue_restricted_surface` — surface presence restricted to one
      lineage / tissue type.
    - `lysosomal_exocytosis` — surface presence depends on lysosomal
      fusion / exocytosis.
    - `dual_localization` — splits between PM and another compartment.
    - `stable_surface_attachment` — baseline stable; no major modulation
      (use sparingly).
    - `activation_induced` — induced by immune / receptor activation
      (TCR, BCR, cytokine).
    - `stress_induced` — induced by ER / oxidative / heat / DNA-damage
      stress.
    - `disease_state_induced` — induced specifically in disease (tumor,
      autoimmune, infection).
    - `polarization_dependent` — depends on apical-basolateral polarity.
    - `post_translational_dependent` — depends on PTM (cleavage,
      phosphorylation, glycosylation).
    - `developmental_stage` — gated by developmental window.
    - `none` — no modulation documented.
    - `other` — anything else (requires `category_other_label`).
    - `unknown`.
- `category_other_label` — REQUIRED iff `category="other"`; otherwise
  MUST be `null`.
- `cell_state_trigger` — closed enum (`ER_stress`, `heat_shock`,
  `oxidative_stress`, `DNA_damage_response`, `apoptosis`, `necroptosis`,
  `oncogenic_transformation`, `infection_viral`, `infection_bacterial`,
  `immune_activation`, `antigen_stimulation`, `cytokine_stimulation`,
  `hypoxia`, `nutrient_deprivation`, `hyperthermia`, `mechanical_stress`,
  `other`, `unknown`). MAY be set ONLY when `category` is in
  `{cell_state_induced, stress_induced, activation_induced,
  disease_state_induced, lysosomal_exocytosis}`. Otherwise MUST be `null`.
  **Set it ONLY when the inducing state genuinely matches one of the
  listed cell-state mechanisms.** The enum covers cell-state *stressors*
  (stress / oncogenic / infection / immune / metabolic / mechanical) —
  it is NOT a disease vocabulary. For a `disease_state_induced` row whose
  disease is NOT one of those mechanisms — e.g. a genetic, developmental,
  or neurodegenerative disease such as **Familial Dysautonomia** — leave
  `cell_state_trigger` `null`; the disease itself belongs in
  `baseline_context` / `modulating_state` (e.g. baseline "healthy
  iPSC-derived neurons" → modulating "FD-patient iPSC-derived neurons").
  **NEVER use `oncogenic_transformation` unless the modulating state is an
  actual cancer / malignant transformation** — it is not a catch-all for
  "some disease". When no listed mechanism fits, prefer `null` over a
  wrong-but-plausible pick (`other`/`unknown` are last resorts).
- `restricted_lineage` — closed enum (`germline_reproductive`,
  `embryonic_developmental`, `hematopoietic`, `neural`, `epithelial`,
  `endothelial`, `muscle`, `endocrine`, `specialized_somatic_other`,
  `other`, `unknown`). MAY be set ONLY when
  `category="tissue_restricted_surface"`. Otherwise MUST be `null`.
- `dual_loc_partner_compartment` — closed enum (`ER`, `Golgi`,
  `endosome`, `lysosome`, `mitochondrion`, `nucleus`, `cytosol`,
  `secretory_vesicle`, `other`, `unknown`). MAY be set ONLY when
  `category="dual_localization"`. Otherwise MUST be `null`.
- `baseline_context` — free text describing the baseline state where
  the protein is (or isn't) on the surface (e.g. `resting CD4 T cell`,
  `unstressed HeLa`, `normal kidney epithelium`).
- `modulating_state` — free text describing the alternate state (e.g.
  `TCR-stimulated CD4 T cell`, `thapsigargin-treated HeLa`, `tumor
  kidney epithelium`).
- `change` — prose ≤300 chars describing what actually shifts.
- `accessibility_implication` — prose ≤300 chars describing what the
  shift means for binder access.
- `cited_evidence_ids` — every `evidence_id` whose claim contributed.

## CATEGORY-CONDITIONAL PAIRING — VALIDATOR RULES

These rules are validator-enforced; violations cause schema validation
to fail. Re-read this list before emitting EACH row:

1. `category="other"` ⇒ `category_other_label` is a non-empty string.
   Any other `category` ⇒ `category_other_label` is `null`.
2. `cell_state_trigger` may be non-null ONLY when `category` ∈
   {`cell_state_induced`, `stress_induced`, `activation_induced`,
   `disease_state_induced`, `lysosomal_exocytosis`}.
3. `restricted_lineage` may be non-null ONLY when
   `category == "tissue_restricted_surface"`.
4. `dual_loc_partner_compartment` may be non-null ONLY when
   `category == "dual_localization"`.

When in doubt, set the optional sub-field to `null` rather than risk a
mispairing — empty rows still validate; mispaired rows fail.

## You have no tools

Cite-only over the ledger.
