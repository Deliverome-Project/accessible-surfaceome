# Cell states builder (A2 → StateContext list)

You receive an A2 `EvidenceClaim` ledger and emit a JSON ARRAY of
`StateContext` rows — one per orthogonal **cell state** that the
ledger reports modulates the protein's expression or surface
fractionation.

Where the `cell_types` builder answers "which cells express this
protein", you answer "under which **state condition** does the
literature report expression or surface presentation change". The two
ledgers are orthogonal: a single cell type can flip across multiple
states (a resting CD8 T cell vs. an activated one), and a single state
can apply across cell types (ER stress in beta cells, in cancer cells,
in primary fibroblasts).

## What counts as a cell state

A condition that *modulates* expression or surface presentation, not a
steady-state cell-type identity. Concretely:

* **Activation** — TCR / BCR engagement, cytokine-driven activation,
  pattern-recognition-receptor stimulation, agonist binding.
* **Exhaustion** — chronic-antigen-driven T-cell exhaustion, PD-1
  / TIM-3 / LAG-3 co-expression states.
* **EMT / MET** — epithelial-to-mesenchymal transition; relevant for
  cytoskeletal IFs (VIM-class), claudins, E-cadherin neighbors.
* **Cellular stress** — ER stress / UPR, oxidative stress, heat shock,
  hypoxia, nutrient deprivation, DNA damage response. **csGRP78
  (HSPA5) is the canonical example**: an ER-resident chaperone whose
  surface fraction increases under ER stress.
* **Differentiation stage** — naive vs. memory, immature vs. mature,
  progenitor vs. terminally-differentiated.
* **Cell cycle** — quiescence vs. proliferation, M-phase-specific
  surface markers.
* **Senescence** — replicative or stress-induced senescence
  (SASP-driven surface changes).
* **Polarization** — apical / basolateral, M1 / M2 macrophage,
  Th1 / Th2 / Th17 helper-T polarization.
* **Disease state** — tumor microenvironment, inflammatory state,
  fibrotic state, viral infection.

## What does NOT count (those belong elsewhere)

* **Cell-type identity** — "expressed in monocytes" is `cell_types`,
  not `cell_states`. A state can ride on top of a cell type
  ("activated monocytes show 2x surface staining") but the identity
  itself is not a state.
* **Tissue-level conditions** — "high in tumor vs. matched normal"
  is `accessibility_modulation` (anatomical) unless the prose binds
  the change to a specific cellular state.
* **Static subcellular relocalizations** — "constitutively dual-
  localized" is `subcellular_localization`'s `dual_localization`, not
  a state.

## Source claims

Read every A2 claim whose prose / quote binds expression or surface
fractionation to a state condition. Common phrasings:

* "induced by" / "upregulated by" / "translocates to the surface upon"
* "in activated [cell type], surface expression rose 5-fold"
* "under ER stress, the soluble fraction relocalizes to the plasma
  membrane"
* "EMT induced detectable cell-surface vimentin staining"
* "senescent fibroblasts shed more …"
* "in hypoxic conditions, surface fraction increased"

Claims that just report steady-state surface presence in a cell type
(no state-binding) do not feed this block.

## Schema fields

* **`state`** — a short label naming the state. Use the conventional
  literature term: `activated`, `exhausted`, `EMT`, `ER stress`, `hypoxic`,
  `senescent`, `M1-polarized`, `naive`, `memory`, `tumor`, `inflammatory`.
  Lowercase except when the literature term is canonically capitalized
  (e.g. `EMT`, `UPR`).
* **`descriptor`** — one short sentence describing what the literature
  says happens to expression or surface presentation in this state.
  Soft target ≤200 chars. Example: "ER stress (e.g. tunicamycin,
  thapsigargin) translocates a fraction to the plasma membrane;
  surface levels correlate with UPR magnitude."
* **`cited_evidence_ids`** — every `evidence_id` from the ledger whose
  claim contributed.

## Grouping

One row per distinct state. Multiple claims naming the same state
condition (e.g. several papers all reporting csGRP78 under various
ER stressors) collapse into one row with multiple `cited_evidence_ids`
and a descriptor that summarizes across them.

**You have no tools.** Cite-only over the ledger.

## Output

ONE fenced ```json block containing a JSON ARRAY. Empty `[]` is the
right answer when the literature only reports steady-state expression
across cell types (most non-stress / non-activation-modulated surface
proteins).
