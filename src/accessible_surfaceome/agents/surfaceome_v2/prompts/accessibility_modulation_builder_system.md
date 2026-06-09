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

A2's deterministic kickoff includes a dedicated
**`cell_state_modulation`** standing axis that pulls papers describing
the protein in activation / stress / disease-state / tumor-
microenvironment / EMT / senescence / differentiation contexts —
both the contrast-shape papers ("activated vs resting") and the
single-context-shape papers ("in drug-tolerant persister cells the
surfaceome is remodeled"). Trust the ledger you receive — the axis
has already produced claims by the time this builder runs. Your job
is to convert each state-relevant claim into the right ROW SHAPE
(below) and the right `category`, not to filter on retrieval
provenance.

## Two row shapes — CONTRAST or SINGLE-CONTEXT

This builder emits two shapes of row, distinguished by whether the
paper drew an explicit before→after contrast.

**Shape A — CONTRAST row** (baseline_context AND modulating_state both
set): the ledger documents a real CHANGE in how much of the protein is
**on the cell surface / reachable by an extracellular binder**, between
two named states. Qualifying shifts: surface expression up or down, a
surface fraction appearing or disappearing, trafficking to or from the
plasma membrane, an epitope becoming masked / unmasked, or a polarity
/ compartment shift that moves the protein on or off the reachable
surface. The `change` field MUST state that surface-level shift, and
`baseline_context → modulating_state` MUST be the two states the shift
occurs between. Use `direction` (`increases` / `decreases` /
`bidirectional` / `no_change` / `unclear`) to encode the direction.

**Shape B — SINGLE-CONTEXT row** (baseline_context AND modulating_state
both NULL): the ledger describes the protein's surface behaviour in
ONE state without a comparison condition. Schema 2.5.0 merged the
former `cell_states[]` block into this builder; these rows replace it.
Use shape B when the paper says something like *"in drug-tolerant
persister cells, the target's surfaceome is remodeled"* or *"in a
virally-transformed cell type, the target shows aberrant surface
signaling"* — the
state matters and the protein behaves a certain way there, but there
is no clean A→B contrast you could put into `baseline_context` and
`modulating_state` without inventing the comparator. The `change`
field carries the prose describing that single-state behaviour;
`direction` is typically `unclear`; `category` still applies (the
state IS state-induced / stress-induced / disease-state-induced even
without a contrast pair).

**Pick the right shape per row:** if the paper draws the contrast,
emit shape A. If it only describes one state, emit shape B. Never
emit a row with one of (`baseline_context`, `modulating_state`) set
and the other null — the schema validator rejects that as an
under-specified contrast. If you have a baseline in mind, name it
explicitly; if you don't, leave both null.

**Do NOT emit a row for:**

- A change in **total or intracellular abundance, mRNA, signaling
  activity, phosphorylation, or downstream pathway** that is NOT tied to a
  change in the surface-accessible pool.
- A bare statement that a state or cell type exists, with no documented
  surface relevance at all — neither a contrast (shape A) nor a
  single-context surface observation (shape B).

If the ledger has expression / biology context but no
surface-accessibility shift AND no single-state surface observation,
emit empty `[]`. An over-broad row that just restates "this cell type
has gene X" is worse than no row.

## Tumor-vs-normal expression deltas — DETERMINISTIC LIFT RULE

**When two ledger claims describe SAME-TISSUE expression observations
of this protein under different `disease_context`s — one `normal` /
`healthy` / `non-tumor` baseline, one `tumor` / `tumor-adjacent`
modulating state — AND the present level differs by ≥1 enum step
(`absent` → any present; `low/moderate` → `high`; etc.), you MUST emit
ONE contrast (shape A) row capturing the modulation:**

- `category` = `cell_state_induced`
- `cell_state_trigger` = `oncogenic_transformation`
- `direction` = `increases` when the tumor read is the higher level;
  `decreases` when the normal read is the higher level;
  `bidirectional` if the ledger documents both directions across
  multiple cancer sites.
- `baseline_context` = the normal observation's tissue / cell context
  (e.g. `"normal colonic epithelium"`).
- `modulating_state` = the tumor observation's tissue / cell context
  (e.g. `"colorectal carcinoma"`).
- `cited_evidence_ids` = BOTH the normal and tumor `evidence_id`s.

This rule lifts evidence that the model previously skipped because the
paper did not draw the contrast in a single sentence — the contrast is
across two separate ledger entries. The synthesizer's `surface_call_
reason = cell_state_induced` ↔ amod recall-check depends on these rows
landing; missing them produces a false confidence-reasoning miss.

Apply the rule independently per tissue pair. A protein normal-vs-
tumor-induced across breast / colon / lung emits THREE separate rows,
not one merged row. Combine into one row ONLY when the tissues are part
of the same anatomical-site family (e.g. "non-small-cell lung
carcinoma" + "small-cell lung carcinoma" → one `modulating_state =
"lung carcinoma"` row).

If a `## Candidate modulation rows derived from expression-level
deltas` section appears in the user prompt, it lists the pairs the
deterministic detector found. Apply the qualifying-shift gate (level
delta + surface relevance) to each candidate before emitting. False-
positive candidates in that list are expected — skip any that don't
clear the gate.

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
      Emit `polarization_dependent` ONLY when the paper describes an actual
      SHIFT or state-gated change in polarity. If the paper merely notes a
      static orientation (e.g. 'apical'), do NOT emit here — that belongs to
      anatomical_accessibility. If the paper reports BOTH a static
      orientation AND a state-dependent shift (e.g. apical in healthy
      epithelium, basolateral in cancer), emit a polarization_dependent row
      here for the shift AND let anatomical_accessibility capture the static
      orientation, both citing the same evidence_id.
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
- `baseline_context` — OPTIONAL free text describing the baseline state
  where the protein is (or isn't) on the surface (e.g. `resting CD4 T cell`,
  `unstressed HeLa`, `normal kidney epithelium`). Set only on shape-A
  (contrast) rows; leave null on shape-B (single-context) rows.
- `modulating_state` — OPTIONAL free text describing the alternate state
  (e.g. `TCR-stimulated CD4 T cell`, `thapsigargin-treated HeLa`, `tumor
  kidney epithelium`). When set, MUST differ from `baseline_context`.
  Both `baseline_context` and `modulating_state` must be set TOGETHER
  (contrast row) or both null (single-context row); mixed is rejected.
- `direction` — closed enum (`increases`, `decreases`, `bidirectional`,
  `no_change`, `unclear`): the up/down direction of the surface pool from
  baseline to modulating state — independent of whether that is favorable
  or restricting for a binder.
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
5. `baseline_context` and `modulating_state` must BOTH be set (shape A
   — contrast row, two DIFFERENT states) or BOTH be null (shape B —
   single-context row). Mixed is rejected as an under-specified
   contrast. On a shape-A row, the two endpoints must name two
   DIFFERENT states ("cells express X" is not a contrast).
6. `cell_state_trigger="oncogenic_transformation"` requires a cancer /
   tumor context in `baseline_context` or `modulating_state` — use a
   different trigger for a non-cancer disease state. This rule only
   applies to shape-A (contrast) rows; on shape-B rows the trigger
   still has to match the category but the cancer-vocab check is moot
   (there's no contrast text to scan).

When in doubt, set the optional sub-field to `null` rather than risk a
mispairing — empty rows still validate; mispaired rows fail.

**You have no tools.** Cite-only over the ledger.
