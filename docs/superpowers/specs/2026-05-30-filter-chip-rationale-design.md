# Filter-chip rationale + signal-panel relocation — design

**Date:** 2026-05-30
**Branch:** `claude/pedantic-mendel-d0be83`
**Status:** approved by user, implementing

## Problem

PR #38 promoted the LLM feature-chip groups (biology / expression / risks)
*out* of the §01 at-a-glance signal panel and into three standalone
top-level tabs. The user wants the chips back in the signal panel as the
single at-a-glance home, the dedicated tabs to carry *extended* info, and —
critically — **every single filter chip to have a rationale associated with
it** (in the record, surfaced on the chip and on its tab).

## Decisions (from brainstorming)

1. Chips live in the **signal panel only**; the three tab cards drop their
   `<FeatureChips>` row.
2. Tabs get extended info: surface currently-unrendered record fields
   (`biological_context.cell_types`, `cell_states`) **and** per-chip
   rationale prose.
3. Every chip's rationale must exist **in the record** ("fix the records,
   not the viewer"). Add schema fields + update the synthesizer prompt +
   re-annotate, rather than deriving prose in the viewer.

## The 11 filter chips → rationale source

| # | Chip (`filters.*`) | Tab | Rationale source |
|---|---|---|---|
| 1 | `has_known_ligand` | Biology | **NEW** `has_known_ligand_rationale` (synthesizer) |
| 2 | `surface_specificity` | Biology | **NEW** `surface_specificity_rationale` (synthesizer) |
| 3 | `co_receptor_dependency` | Biology | existing `accessibility_risks.co_receptor_requirements.rationale` |
| 4 | `has_restricted_subdomain` | Biology | existing `accessibility_risks.restricted_subdomain.rationale` |
| 5 | `expression_level` | Expression | **NEW** `expression_level_rationale` (synthesizer) |
| 6 | `expression_breadth` | Expression | **NEW** `expression_breadth_rationale` (synthesizer) |
| 7 | `overexpression_surface_localization_observed` | Expression | **NEW** `..._rationale` (orchestrator-composed, cites triggering methods) |
| 8 | `has_shed_form` | Risks | existing `accessibility_risks.shed_form.mechanism` |
| 9 | `has_secreted_form` | Risks | existing `accessibility_risks.secreted_form.source`/rationale |
| 10 | `low_endogenous_expression` | Risks | **NEW** `low_endogenous_expression_rationale` (orchestrator-composed from `expression_level`) |
| 11 | `has_epitope_masking` | Risks | existing `accessibility_risks.epitope_masking.rationale` |

- **5 chips** (3,4,8,9,11) already carry rationale in deep blocks — viewer maps to them.
- **4 chips** (1,2,5,6) are LLM-emitted rollups with no deep block — synthesizer emits new rationale.
- **2 chips** (7,10) are orchestrator-derived booleans — orchestrator composes a deterministic rationale string referencing the source it derived from.

## Implementation parts

### A. Schema (`src/accessible_surfaceome/tools/_shared/models.py`)
- `SynthesizerLLMFilters`: add `surface_specificity_rationale`,
  `expression_level_rationale`, `expression_breadth_rationale`,
  `has_known_ligand_rationale` (str, `_PROSE_TARGETS` ~300 chars each).
- `Filters`: mirror those 4 + add `overexpression_surface_localization_observed_rationale`
  and `low_endogenous_expression_rationale` (orchestrator-composed).

### B. Synthesizer prompt (managed agent — auto-syncs on next annotate run)
- `agents/surfaceome_synthesizer/prompts/system.md` + `task_template.md`:
  instruct B to emit the 4 new rationale fields alongside the rollups it
  already produces.

### C. Orchestrator (v2 Filters composition)
- Thread the 4 synthesizer rationale fields into the assembled `Filters`.
- Compose the 2 derived-boolean rationale strings deterministically.

### D. Viewer
- `FiltersCard`: restore an `llm` provenance group (biology+expression+risks
  chips) above the Deterministic block; thread each chip's rationale into its
  `StatusPill title=` / InfoTip.
- Remove `<FeatureChips>` from BiologicalContextCard / ExpressionCard /
  AccessibilityRisksCard.
- Render per-chip rationale prose on each tab; map chips 3,4,8,9,11 to their
  existing deep-block rationale and 1,2,5,6,7,10 to the new fields.
- New subsection on Expression tab: `biological_context.cell_types`
  (cell-ontology IDs + `present_in_tissues`); render `cell_states` when present.

### E. Re-annotate + publish
- Full v2 re-run for **EGFR, SRC, GPR75** in parallel (~$2/gene, authorized).
- Publish default-on → `data/annotations/`, viewer snapshot, public D1.
- Verify every chip has a non-empty rationale in each re-generated record.

## Test genes
EGFR (P00533), SRC (P12931), GPR75 (O95800) — large-ECD RTK / ECD-less
kinase / orphan GPCR, covering the rationale edge cases.
