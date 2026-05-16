# Handoff: per-agent clip-judge + block builders

**Date:** 2026-05-16
**Prior state:** PR [#33](https://github.com/Deliverome-Project/accessible-surfaceome/pull/33) lands the single-agent plan→trim→select MVP + the evidence-pipeline quality fixes that preceded it.
**Next agent's job:** finish the architecture so it produces full `SurfaceomeRecord`s, not just an `EvidenceClaim` ledger.

## What's done (in PR #33, on `claude/happy-robinson-edab10`)

- Soft-target prose caps (`_warn_prose_overshoot` validator pattern in [models.py](src/accessible_surfaceome/tools/_shared/models.py)) — 16 prose fields lose hard `max_length=` and gain warning-only overshoot detection.
- Verbatim-quote caps 200 → 600 chars across `CandidateSnippet.text` / `EvidenceClaimDraft.quote` / `EvidenceSpan.quote` / `EvidenceClaim.quote`; `context_excerpt` 500 → 1500.
- [`evidence_retrieval._trim_to_quote_cap`](src/accessible_surfaceome/tools/evidence_retrieval.py) with tiered clause-boundary snapping (sentence-end + semicolon: 150 chars, colon: 120, comma: 60).
- [`extract_paper_drafts`](src/accessible_surfaceome/tools/evidence_retrieval.py) helper exported and wired into [`gene_literature._fetch_abstract`](src/accessible_surfaceome/tools/gene_literature.py) + the `fetch_fulltext` branch — every paper-body fetch now ships `evidence_claim_drafts` automatically.
- A1 + A2 prompt updates: `evidence_tier=secondary` demotion guidance for schematic / aim-statement / scoring-rubric quotes; "adopt gene_literature drafts verbatim — do NOT retype prose" warning.
- New agent package [src/accessible_surfaceome/agents/plan_trim_select/](src/accessible_surfaceome/agents/plan_trim_select/) — single-agent MVP that emits a flat `list[EvidenceClaim]`.
- Driver: [scripts/plan_trim_select_run.py](scripts/plan_trim_select_run.py).
- Design doc: [docs/plans/2026-05-16-clip-and-judge-flow.html](docs/plans/2026-05-16-clip-and-judge-flow.html).

## Validation state

Three reference runs land at `data/eval/v1_cost_stress_test/`:

| gene | pipeline | claims | anchored | cost |
|---|---|---|---|---|
| CD81 | v1 baseline (round 5) | 27 | 88.9% | $1.35 |
| EGFR | v1 baseline (round 7) | 44 | 93.2% | $1.20 |
| GPR75 | v1 baseline | 25 | 76.0% | $1.32 |
| GPR75 | **plan-trim-select MVP (3 iters)** | **13** | **100%** | **$0.21** |

Plan-trim-select gets to 100% anchoring + 6× cheaper. Coverage is thinner (13 vs 25) but iteration loop pulled in cryo-EM data the baseline missed entirely. **Coverage parity needs the per-agent + block-builder phases below.**

## Architectural goal — three phases, three test gates

### Phase 1: per-agent specialization (incremental from MVP)

Today's MVP is one agent emitting a unified ledger. The user's direction is to keep A1 and A2 with different foci but share the document repository / clip pool.

**Build:**
- Joint planner — one Sonnet call serving both A1+A2 needs
- Shared execution → one pool of `EvidenceClaimDraft`s (no duplicated fetching)
- Per-paper Haiku trim runs TWICE: A1-focused prompt (surface methodology + topology + therapeutic engagement + contradictions), A2-focused prompt (tissue/cell context + accessibility modulation + subcellular + anatomical orientation)
- A1 selector + A2 selector run in parallel against their respective trimmed menus
- Iteration loop applies per-agent

**File layout:**
- Add `prompts/a1_trim_system.md`, `prompts/a2_trim_system.md`, `prompts/a1_select_system.md`, `prompts/a2_select_system.md`
- Refactor `runner.py` to accept an `agent_focus` parameter ("a1" | "a2") and run the trim+select with the right prompts; the orchestrator wires both into the same plan
- Selector schema stays the same (`SelectionResponse`); the system prompt is what specializes

**Test gates:**
- Each agent's ledger ≥95% anchored (the by-construction property must hold)
- A1 ledger has ≥60% of claims in `{surface_expression, topology, methodological, contradictory}`
- A2 ledger has ≥60% of claims in `{tissue_expression}` plus modulation-flavored
- Combined claim count ≥ baseline GPR75 (25) — recall parity
- Total cost ≤$0.40/gene

**Test genes:** GPR75 + EGFR. Compare ledger composition + anchoring vs MVP.

**Commit gate:** one PR for this phase.

### Phase 2: block builders (8 small specialized Sonnet calls)

Today the selector emits a flat `EvidenceClaim` list. The v1.0.0 schema needs structured blocks with derived fields the selector can't produce in one pass (whole-ledger judgments, prose synthesis across multiple claims, conditional-validator-gated sub-fields).

**Build:**

A1-side block builders (each takes a ledger slice + the block schema, emits the structured block):
- `methods_builder` — input: claims with surface-assay `evidence_type`; output: `list[MethodObservation]` with `AntibodyRef` details extracted from `quote + context_excerpt`. Antibody clone/RRID/validation_strategy aren't in `EvidenceClaim` fields; the builder re-reads each clip's full context to extract them.
- `therapeutic_engagement_builder` — input: drug/clinical claims; output: single `TherapeuticEngagementContext` with prose `description` + `surface_form_rationale` (which form does each drug engage?).
- `contradiction_builder` — input: `claim_type=contradictory` claims; output: `list[Contradiction]` with `contradiction_type` + `severity_for_surface_accessibility` per row.
- `evidence_grade_builder` — input: entire A1 ledger; output: `evidence_grade` enum + `grade_rationale` prose.

A2-side block builders:
- `tissues_builder` — input: `tissue_expression` claims; output: `list[TissueContext]` with `present` enum synthesized per tissue from multiple expression observations.
- `cell_types_builder` — input: cell-context claims; output: `list[CellTypeContextV1]`. **Skip `ontology_id` for MVP** — leave as `None`; CL: lookup is out of scope (add later via a deterministic ontology resolver).
- `subcellular_localization_builder` — input: compartment-relevant claims; output: `SubcellularLocalization` with `primary_compartment` + `dual_localization[]` + `membrane_subdomains[]`.
- `anatomical_accessibility_builder` — input: orientation-relevant claims; output: `list[AnatomicalAccessibilityObservation]`.
- `accessibility_modulation_builder` — **the heaviest builder**. Input: state-dynamics claims; output: `list[AccessibilityModulationObservation]` with `category` (12 values) + `baseline_context` → `modulating_state` + prose `change` + `accessibility_implication` + conditional sub-fields. The model_validator on this class enforces category-conditional pairing rules — the prompt must encode them.

**Test gates:**
- A1 emits a valid `SurfaceEvidenceDraft` (passes Pydantic + `_check_citations_resolve`)
- A2 emits a valid `BiologicalContextDraft` (passes Pydantic + conditional validators)
- Expert audit of `AccessibilityModulationObservation[]` rows on GPR75 — score against the v1 baseline's modulation rows
- Per-block cost ≤$0.05; total block-builder spend ≤$0.25/gene

**Commit gate:** second PR for this phase.

### Phase 3: wire into orchestrator + end-to-end vs baseline

**Build:**
- New `surfaceome_v2.annotate(gene)` orchestrator entry alongside existing `surfaceome_v1.annotate(gene)`
- Calls plan-trim-select-per-agent (Phase 1) → block builders (Phase 2) → existing B synthesizer + existing deterministic block
- Side-by-side comparator: runs v1 + v2 on same gene, dumps both records, computes diff stats

**Test gates:**
- `SurfaceomeRecord` validates against v1.0.0 schema
- Anchored rate ≥95% across 3-gene panel (CD81 / EGFR / GPR75)
- Expert audit shows quality match-or-beat vs baseline on ≥2/3 genes
- End-to-end cost ≤$1.00/gene

**Commit gate:** third PR for this phase. Cut a release if v2 ships behind a flag.

## Key files to read first

- [docs/plans/2026-05-16-clip-and-judge-flow.html](docs/plans/2026-05-16-clip-and-judge-flow.html) — design doc, includes the future tool-surface (Tier A-E) reference for later
- [docs/eval/methodology.md](docs/eval/methodology.md) — the testing-and-improving loop (instrument → run real → audit critically → name the failure mode → fix at lowest layer)
- [src/accessible_surfaceome/agents/plan_trim_select/runner.py](src/accessible_surfaceome/agents/plan_trim_select/runner.py) — the MVP runner (refactor target for Phase 1)
- [src/accessible_surfaceome/agents/plan_trim_select/schemas.py](src/accessible_surfaceome/agents/plan_trim_select/schemas.py) — the I/O schemas + `SearchRequest` validator pattern (extend for per-agent context if needed)
- [src/accessible_surfaceome/tools/_shared/models.py](src/accessible_surfaceome/tools/_shared/models.py) lines 1376-1670 — `MethodObservation`, `BiologicalContext`, `AccessibilityModulationObservation` (the schema blocks the builders must produce)
- [src/accessible_surfaceome/agents/surface_evidence_compiler/runner.py](src/accessible_surfaceome/agents/surface_evidence_compiler/runner.py) — the existing A1 runner, useful as a reference for `SurfaceEvidenceDraft` emission patterns

## Known traps + state to be aware of

- **EuropePMC 404s on specific PMC fulltext URLs** (`PMC10777681`, `PMC7824747`) — pre-existing fragility in `evidence_retrieval`. The plan-trim-select runner's per-search try/except contains the blast radius but loses that category's contribution. If Phase 1 testing shows persistent recall loss from this, consider fixing `evidence_retrieval` to skip-on-404 internally instead of raising.
- **`ontology_id` for cell types** — selector doesn't have CL: vocabulary memorized. The MVP plan-trim-select agent doesn't even attempt it. Phase 2 should leave it `None`; add ontology resolution as a later post-process.
- **Soft-target validator warnings fire on long prose fields** — they're logged but don't fail validation. If Phase 2's block-builder prompts produce very long `change` / `accessibility_implication` strings (>300 chars), the warning will fire but the record will validate. That's the designed behavior.
- **A1/A2 currently use `a1_evi_` / `a2_evi_` prefix conventions on `evidence_id`**. The plan-trim-select MVP uses `pts_evi_`. Phase 1 per-agent must restore the prefix discipline so the existing `SurfaceEvidenceDraft._check_claim_id_prefix` validator passes when block builders produce drafts.
- **`SurfaceomeRecord._check_wb_pairing`** validator requires that `evidence_type=western_blot` claims are paired with a fractionation/biotinylation step from the same source. Block builders need to respect this when producing `methods[]`.
- **The deterministic block (`canonical_topology`, `ecd_length_residues`, etc.) is orchestrator-built**, not agent-emitted. Phase 3 doesn't need to touch this — just thread it through the same way `surfaceome_v1.annotate` does.

## Starting prompt for the next agent

> I'm picking up work from PR #33 (clip-and-judge MVP). Read [docs/plans/2026-05-16-clip-and-judge-handoff.md](docs/plans/2026-05-16-clip-and-judge-handoff.md), then start Phase 1 (per-agent specialization).
>
> Before writing code: read the existing MVP at [src/accessible_surfaceome/agents/plan_trim_select/runner.py](src/accessible_surfaceome/agents/plan_trim_select/runner.py), the v1 A1 runner at [src/accessible_surfaceome/agents/surface_evidence_compiler/runner.py](src/accessible_surfaceome/agents/surface_evidence_compiler/runner.py), and the BiologicalContext schema starting at [models.py:1652](src/accessible_surfaceome/tools/_shared/models.py:1652). Compare the data the MVP currently produces (run `uv run python scripts/plan_trim_select_run.py GPR75` if needed; output lands at `.runs/plan_trim_select_GPR75.json`) against what the schema actually demands.
>
> Then propose the per-agent file structure (how do `a1_trim_system.md` / `a2_trim_system.md` differ; does the orchestrator run a joint planner or two planners; how is `agent_focus` threaded through). Don't write code until that's agreed.
>
> When Phase 1 lands and passes its test gates (see handoff doc), commit + PR + move to Phase 2 (block builders). Block builders are 8 small specialized Sonnet calls — see handoff doc for the full per-builder list and per-block test gates.
>
> Quality bar is "excellent" — every claim 100% anchored by construction, every structured block validates against the v1.0.0 Pydantic schema, and the records pass expert audit at least as well as the v1 baseline. The methodology doc at [docs/eval/methodology.md](docs/eval/methodology.md) is the testing-and-improving loop to follow.
