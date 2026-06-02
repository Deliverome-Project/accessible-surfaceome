# PR #47 Deep-Dive Pipeline Insights — Tracking

Source: [PR #47](https://github.com/Deliverome-Project/accessible-surfaceome/pull/47) (Becca Carlson). 47 of 163 commits touch the deep-dive pipeline. Forensics performed 2026-06-01 against `pr-47-review` vs `main`.

This file tracks every observation Becca encoded as a prompt / schema / orchestrator change while iterating on real deep-dive outputs. The goal is to make sure every principled insight finds a home in the next deep-dive redesign, every overspecific bandaid gets lifted to its underlying principle, and every insight stranded in dead code (the LLM planner) gets ported to wherever the deterministic search plan now lives.

Companion: see [`2026-05-13-deep-dive-redesign-surface-accessibility.md`](2026-05-13-deep-dive-redesign-surface-accessibility.md) for the v1→v2 transition context.

## How to read this

Each insight has an ID (e.g. `A1.1`) so we can reference it in the redesign discussion. Each row is independently trackable — fill in the **Future home** line during the redesign pass.

**Status legend**
- `[x]` **homed** — landed in PR #47 in a place we want to keep
- `[~]` **migrate** — insight currently lives in dead code, v1-only, or the wrong stage; must be ported
- `[!]` **overspec** — gene-specific bandaid; lift the principle, drop the example
- `[?]` **verify** — claim to confirm before we trust the home
- `[ ]` **open** — no decision yet

**Scope tags**
- `v2` — production deep-dive (surfaceome_v2)
- `v1` — legacy deep-dive (not on production path)
- `schema` — shared record schema (affects both pipelines)
- `synth` — shared `surfaceome_synthesizer` Managed Agent (affects both pipelines)
- `plan` — dead-code planning prompts (need migration to deterministic plan)

---

---

## Synthesis (from workflow `wy6hz3e0r`, 2026-06-01)

Below: cluster-level findings from a 49-agent workflow that mapped each pipeline stage and proposed a home for every section-A insight. **The per-insight `Future home:` lines under each entry reflect those proposals.** Read this synthesis first to see the cross-cutting moves; then walk the per-insight detail.

### TL;DR

> The 38 insights cluster into three meta-themes: (1) a fundamental shape change in the biology ledger — collapsing the parallel TissueContext + CellTypeContextV1 arrays into a single ExpressionRow and deleting TherapeuticEngagement entirely (A1.1, A1.2, A1.3, A1.5) — which cascades through schema, two builders, two select prompts, the orchestrator post-pass, and the viewer; (2) a deterministic-over-prompt migration where retrieval expansions (six-organ tox panel, BBB/tumor-penetration/luminal access axes, secreted-form/soluble axis) move from retired LLM-planner prose into hand-coded kickoff_templates.py builders, and post-LLM derivations (secreted_form upgrade from topology, family healing, filter rollups) move from synthesizer prose into orchestrator + publish-time post-passes (A2.3, A2.4, A6.1, A6.2, A6.3, A11.1, A11.2, A11.3); (3) discipline tightenings inside existing stages — selector dedup keyed on methodology axes not citations (A3.3, A4.5, A9.1), WT-vs-variant preference (A4.3), OE-retention floor (A4.1), permeabilized-assay routing (A3.2), accessibility_modulation as contrast-not-context (A7.1, A7.2), and compartment-vs-subdomain routing (A5.1, A5.2, A5.3). Two stages — schema (12 insights) and builders (12 insights) — absorb most of the load and warrant coordinated PRs to avoid drift; one new pipeline stage (publish_self_heal) is needed to give the publish-time tag-healing logic a proper home. Open questions cluster around three decision points: TopicAnchor enum closure for new retrieval axes (A6.1, A6.2), whether to extend deterministic gates with shared helpers (A2.3/A2.4 topology gate), and the v1 surface_evidence_compiler scrub scope for therapeutic_engagement deletion (A1.5).

### New deterministic steps to create

#### `publish_self_heal`
- **Position**: Post-orchestrator, inside cloud/surface_annotation._publish_dict — runs on every write to viewer snapshot + D1 (both annotate-time and bulk-sync paths)
- **Addresses**: A11.1, A11.3, A11.4
- **What it does**: Idempotent deterministic-tag self-healing on every publish surface. Re-resolves curator-assigned ground-truth fields (today: hgnc_gene_groups / uniprot_family; tomorrow: any other stable-ID-keyed deterministic curator field) from the record's own stable identifier before the snapshot + D1 INSERT OR REPLACE. Includes a populated-to-empty regression guard that refuses to wipe a populated row with an empty one. Closes the backfill gap for records generated under a degraded resolver, hand-edited snapshots pushed via upload_viewer_snapshots_to_d1, and any future re-publish path. No LLM calls, no per-gene carveouts.
- **Implementation sketch**: Add _heal_family_in_place(record_dict) in src/accessible_surfaceome/cloud/surface_annotation.py (cheap-deterministic, ~60 LOC). Called from _publish_dict before serializing the JSON for snapshot + D1. The function (a) extracts hgnc_id from the record, (b) calls the stable-ID resolver (already imported from gene_lookup), (c) checks the populated-to-empty guard: if existing field is non-empty AND new value is empty, log warning and skip overwrite, (d) writes resolved tags back into the record_dict in place. Both publish_record (agent-time) and publish_record_dict (bulk-sync) share the same _publish_dict so neither path can drift. Pure stdlib + existing D1 client + existing resolver — no new dependencies.

#### `kickoff_topology_gating`
- **Position**: Inside deterministic_kickoff (kickoff_templates.py build_a1/a2/unified_kickoff signatures), gated on a single shared topology helper
- **Addresses**: A2.4, A6.1, A6.2, A6.3
- **What it does**: Adds three conditional retrieval expansions to the deterministic kickoff templates, all gated on a shared topology predicate is_likely_membrane_with_ecd(n_tmh, ecd_aa) -> bool: (1) soluble-form / serum-plasma-shed axis (A2.4) when TM>=1 + ECD>=30aa; (2) six-organ tox panel (liver, lung, kidney, GI, heart, brain) standing rows always (A6.2); (3) BBB / tumor-penetration / luminal-vs-abluminal access axes (A6.1) for genes with surface-localization signal. All anchors come from the protein-level vocabulary (ihc, surface_expression, flow_cytometry, surface_biotinylation, mass_spec_surfaceome) — never RNA-atlas (A6.3). Replaces the retired a2_plan_system.md LLM-planner prose.
- **Implementation sketch**: Step 1: add helper agents/_shared/topology_gate.py (or attach to deterministic_features module) exposing is_likely_membrane_with_ecd(n_tmh, ecd_aa) — single source of truth shared with orchestrator's secreted_form post-pass (A2.3). Step 2: in runner.py around line 1329, after _build_gene_context, fetch n_tmh + ecd_aa from topology_public via a single-row D1 query; pass both to build_kickoff(focus, n_tmh, ecd_aa) — on D1 failure, default to None so recall-biased gates still fire. Step 3: in kickoff_templates.py, extend the three build_*_kickoff signatures to accept n_tmh/ecd_aa; append per-organ SearchRequests for the tox panel, soluble-form anchors when topology gate passes, and BBB/tumor-vasc/luminal angles. Step 4: decide TopicAnchor enum strategy (see open question) — either extend TopicAnchor with new values (tox_panel, soluble_form, bbb, tumor_penetration, luminal_abluminal) and teach the dispatcher their query expansions, or keep enum closed and encode the axis in SearchRequest.intent string. Step 5: delete a2_plan_system.md (dead file). Step 6: add tests covering: TM=0 no soluble anchor, TM=1 has soluble anchor, tox panel always emitted, RNA-atlas anchors never appear.

#### `schema_validator_pack_subcellular_and_modulation`
- **Position**: Inside schema (models.py) — Pydantic @field_validator + @model_validator on three existing classes
- **Addresses**: A5.1, A5.2, A7.1, A7.2
- **What it does**: Mechanizes three routing/coherence rules at parse time so prompts can stop relitigating them with gene examples: (1) DualLocalization.compartment and MembraneSubdomain.subdomain must be SHORT canonical organelle/microdomain names (max ~40 chars, no parentheticals, no clause markers like 'upon', 'under', 'when') — A5.1; (2) MembraneSubdomain.subdomain rejects 'inner leaflet' / 'cytoplasmic face' strings, redirecting to dual_localization — A5.2; (3) AccessibilityModulationObservation requires baseline_context != modulating_state AND, when modulation_category=oncogenic_transformation, requires cancer-vocab regex in modulating_state/baseline_context — A7.1, A7.2. Each validator's error message points the LLM repair pass at the correct field/array.
- **Implementation sketch**: Edit src/accessible_surfaceome/tools/_shared/models.py: (1) add @field_validator on DualLocalization.compartment + MembraneSubdomain.subdomain checking length/parenthetical/clause-marker patterns; (2) extend MembraneSubdomain.subdomain validator to reject 'inner leaflet' / 'cytoplasmic face' with explicit redirect message; (3) add @model_validator on AccessibilityModulationObservation enforcing baseline != modulating_state (case-insensitive strip-compare); (4) extend the existing _check_category_conditionals validator with a trigger-to-required-vocab dict (seeded oncogenic_transformation -> cancer regex). All validators raise ValueError so the existing call_builder 2-retry repair loop kicks in. Add regression tests in tests/ with pinned anti-examples (HCC827/PC9/H1650 expression-context, SRC/LYN inner-leaflet, parenthetical conditional). Once validators land, trim the corresponding prompt sections in subcellular_localization_builder_system.md (A5.1, A5.2, A5.3 merge into a single 'routing rubric' subsection) and accessibility_modulation_builder_system.md (delete 13-line block from 4d0135f + the HCC827/PC9/H1650 example).

#### `filters_rationale_cite_validator`
- **Position**: Inside schema (models.py) — Pydantic validator on SynthesizerLLMFilters and Filters
- **Addresses**: A1.6, A8.2
- **What it does**: Soft schema validator (warning, not error) on each *_rationale string in SynthesizerLLMFilters + the 6 *_rationale fields in Filters, asserting at least one (a1_evi_NN) or (a2_evi_NN) token is present. Catches the failure mode where the synthesizer fills the rationale field but omits inline cites — the wrong-cite class A8.2 targets is not caught here (would need semantic checking), but the no-cite regression class is mechanizable cheaply and gives the prompt's cite-discipline rule a deterministic backstop.
- **Implementation sketch**: Edit src/accessible_surfaceome/tools/_shared/models.py: add a small helper _has_inline_evi_cite(s: str) -> bool checking for regex r'a[12]_evi_\d+'. Attach as @field_validator on each *_rationale field across SynthesizerLLMFilters + Filters with mode='after' that warnings.warn (not raise) when the helper returns False — matches _PROSE_TARGETS warn-only pattern already in use. Once landed, the synthesizer prompt's threat-language ('required', 'must') around inline cites can be trimmed (per A1.6 residue note) — the validator enforces what the prompt asks for.

#### `reagent_provenance_postpass`
- **Position**: Inside orchestrator_postpass — runs after builders complete, before filter derivation
- **Addresses**: A3.1
- **What it does**: Optional follow-up (low priority): deterministic regex post-pass that scans EvidenceClaim quotes for the reagent-list pattern ('anti-[TARGET] (Clone X, Vendor / RRID)') and back-fills any matching MethodObservation.antibodies[].clone / vendor / rrid fields in the methods block. Replaces the cross-claim-lookup paragraph (~15 lines) in methods_builder_system.md added by fef4f2e, which is the second-largest builder prompt (217 lines). Mechanizes a regex-friendly cross-reference so the methods builder doesn't have to do it.
- **Implementation sketch**: Add a function _backfill_antibody_provenance(record) in surfaceome_v1/orchestrator.py (importable per A11.3). Walks record.evidence_chain, applies a regex like r'anti-\s*' + re.escape(target_symbol) + r'(?:\s|,)*(?:[Cc]lone\s+([\w-]+))?(?:[,;]?\s*([\w\s]+?))?(?:[,;]?\s*(RRID:[\w_]+))?' across quote/context. For each match, finds the MethodObservation row by cited_evidence_id and fills the matching antibodies[].clone/vendor/rrid if currently null. Pure deterministic; no overwrite of populated fields. Tradeoff: conjugate-variant disambiguation (anti-EGFR vs anti-EGFR-Alexa Fluor 488) is imperfect with a regex — file as optional, not blocking. Once landed, trim methods_builder_system.md lines 144-162 to a single sentence pointing at the post-pass.

### Stages receiving multiple insights (coordinate as grouped PRs)

#### `schema` — bloat risk: **high**
- **Insights**: A1.1, A1.2, A1.4, A1.5, A1.6, A1.7, A1.8, A1.9, A1.10, A2.4, A5.1, A5.2, A6.1, A7.2, A8.2, A11.2
- **Coordination**: Schema is the heaviest hit (16 insights touch models.py). Three coherent sub-changes to land as separate atomic PRs, not one mega-PR: (PR-A) ExpressionRow unification + TherapeuticEngagement deletion (A1.1, A1.2, A1.3, A1.5) — single schema break, requires viewer snapshot republish via upload_viewer_snapshots_to_d1; landed together so the viewer never sees a half-migrated shape. (PR-B) Self-describing topology rows (A1.8, A1.9, A1.10) — additive (sequence + per-row identity + close-paralog gate + RepresentativeStructure), backward-compatible, no break. (PR-C) Validator pack (A5.1, A5.2, A7.1, A7.2, A8.2, A1.6) — parse-time enforcement, prompts trim in same PR so validator messages and prompt prose stay aligned. Sequence: PR-A first (biggest break, deserves dedicated review), then PR-B and PR-C in parallel. The 3367-line models.py is already flagged-large; resist any urge to add per-gene carveouts or long enum doc-strings — every new enum value or validator should justify its line cost.

#### `builders` — bloat risk: **med**
- **Insights**: A1.1, A1.2, A1.3, A1.4, A1.5, A3.1, A3.2, A3.3, A5.1, A5.2, A5.3, A6.1, A6.2, A7.1, A7.2
- **Coordination**: 12 insights converge here. Two builders absorb most of the change: (1) NEW expression_builder (replaces tissues + cell_types per A1.1) — owns A1.1, A1.2, A1.3, A1.4; the prompt itself absorbs the disease-context routing rule (A1.2), normal-AND-disease row emission (A1.3), and the two-axis modulation taxonomy (A1.4). (2) subcellular_localization_builder absorbs A5.1, A5.2, A5.3 as ONE 'routing rubric' subsection — three currently-separate paragraphs collapse into adjacent rules. Builder concurrency drops 8 -> 7 (tissues+cell_types -> 1 expression builder). The methods_builder at 217 lines is already the largest; A3.1, A3.2, A3.3 each add or trim — net should be neutral or slightly smaller once the reagent_provenance_postpass (new step) absorbs the cross-claim-lookup paragraph. The therapeutic_engagement builder + prompt delete entirely (A1.5). When schema validators (A5.1, A5.2, A7.1, A7.2) land in models.py, the builder prompts can SHRINK — drop the gene-specific anti-examples, point at the validator message. Net direction: prompts should be smaller after this cycle, not larger.

#### `orchestrator_postpass` — bloat risk: **low**
- **Insights**: A1.1, A2.3, A2.4, A4.1, A6.1, A7.2, A11.1, A11.2, A11.3, A11.4
- **Coordination**: 10 insights but no bloat — orchestrator_postpass is cheap-deterministic by design and each new step is bounded. New step 7b (secreted_form upgrade from isoform topology — A2.3) is the biggest add; per insight notes it appears to be missing from the current worktree, so first task is to confirm whether PR #47 actually merged or the work was reverted. Step 7c (filter rollups via _derive_filters — A11.2) is already in place. Step 7e/d candidates: reagent_provenance_postpass (new step, A3.1, low priority) and kickoff_topology_gating coordination (A2.4, A6.1 share the topology gate with A2.3 — extract is_likely_membrane_with_ecd as a shared helper used by both kickoff and post-pass). Family attach (A11.1) MOVES OUT of orchestrator_postpass to the new publish_self_heal stage. Ordering invariant: post-pass steps must run after step 7 deterministic_features fetch + before step 8 _derive_filters; document this in code comments so future refactors don't reorder. Every new step must be a module-level importable function (A11.3) so backfill scripts inherit automatically. CLI publish policy (A11.4) stays at the scripts/ boundary, not in orchestrator_postpass.

#### `deterministic_kickoff` — bloat risk: **low**
- **Insights**: A2.4, A6.1, A6.2, A6.3, A10.1
- **Coordination**: All five insights collapse into one consolidated step (kickoff_topology_gating, see new_deterministic_steps). The kickoff_templates.py module is cheap-deterministic (~204 LOC) with room to grow — adding ~6-10 SearchRequests for the tox panel + soluble-form axis + BBB/tumor-penetration angles is a one-tuple-per-line addition. Key discipline: anchors come from protein-level vocabulary (A6.3) — never RNA-atlas. The retired a2_plan_system.md is dead code that should be deleted in the same PR. A10.1 closes the open-A1 iteration question: single-pass is intentional for BOTH A1 and A2; selector follow-up search angles belong here, not in selector prompts. Add a kickoff_templates.py docstring note documenting the lineage so future contributors don't reach back into a2_select_system.md to add retrieval rules.

#### `synthesizer` — bloat risk: **high**
- **Insights**: A1.6, A1.7, A2.1, A2.2, A2.3, A8.1, A8.2, A11.2
- **Coordination**: Synthesizer prompt is already at 475 lines / bloat-threshold per the atlas. Coordinated approach: any addition here MUST be paired with a deletion or move. (1) A1.6 + A8.2 prompt cite-discipline rules can be TRIMMED once filters_rationale_cite_validator lands in schema — the validator enforces what the prompt asks for (residue note). (2) A2.1 secreted-form severity rule keeps the two-bucket grading but DROPS the EGFR/sEGFR/cetuximab named example (move to test fixture). (3) A2.2 secreted_form scope (target vs ligand) keeps the 10-line block from 8eeae25 but DROPS the (ADAM17, etc.) parenthetical. (4) A2.3 secreted_form post-pass means the synthesizer's 'set secreted_form.present=false when literature absent' instruction needs a note acknowledging the deterministic post-pass override. (5) A1.7 executive_summary.one_paragraph tightening is a one-line edit. (6) A8.1 cited_evidence_ids rule mirrors restricted_subdomain paragraph for co_receptor_requirements — additive, ~3 lines. Net direction: should be ROUGHLY NEUTRAL on line count after deletions — flag any synthesizer-prompt PR that grows the prompt by more than +10 lines as a bloat trigger requiring justification. Managed Agent auto-sync means a stale prompt is a $0.10-0.20 cost on every run — drift detection is the safety net.

#### `a1_select` — bloat risk: **high**
- **Insights**: A3.1, A4.1, A4.2, A4.3, A4.4, A4.5, A9.1, A10.1
- **Coordination**: Already 339 lines — at the prompt ceiling per the atlas. Coordinated trim: (1) A4.1 OE-retention block (lines 258-274) STAYS structurally, parenthetical example trimmed; (2) A4.3 WT-vs-variant preference RESTORES the 5-7 line bullet deleted by df016bc, with EGFRvIII as a parenthetical e.g. only; (3) A4.5 dedup-by-methodology adds ONE clause (~1 line) to existing 'collapse duplicates' bullet, not a new section; (4) A9.1 dedup principle is the same as A4.5 — same one-clause addition serves both; (5) A4.2 OE-surface-qualifying-clip routing rule replaces one gene-specific phrase with a principle; (6) A3.1 reagent-list discipline ABSTRACTS the PMC8584739 / CD81 / Clone AY13 examples — moves them to test fixtures; (7) A10.1 audit-and-remove any residual 'request follow-up searches' language. Net direction: lines OUT (A3.1 example lift + A4.4 dead-file delete already done) should roughly equal lines IN (A4.3 restoration + A4.5 clarification). Flag any a1_select PR that grows past ~350 lines.

#### `a2_select` — bloat risk: **med**
- **Insights**: A1.1, A1.2, A4.5, A9.1, A10.1
- **Coordination**: Currently 296 lines, already near upper edge. After A1.1 ExpressionRow unification, the prompt's 6-bucket selection scheme over the (TissueContext + CellTypeContextV1) menu collapses to a 5-bucket scheme over (ExpressionRow + state + subcellular + anatomical + accessibility_modulation) — net should be slightly smaller. A4.5 + A9.1 add ONE methodology-axes-not-citations clause to the existing 'collapse duplicates' bullet (~1 line). A10.1 audit for any residual 'request follow-up searches' wording. Coordinated with the a1_select PR so both selectors land the dedup clarification in matched language.

#### `deterministic_features` — bloat risk: **low**
- **Insights**: A1.8, A1.9, A1.10, A2.3, A2.4
- **Coordination**: Three additive enrichments to d1_deterministic.py — all backward-compatible. (1) A1.8 + A1.9 extend the SELECT in _fetch_canonical_topology / _fetch_isoform_topologies / _fetch_paralogs to pull sequence + per-row identity + a close-paralog gate (CLOSE_PARALOG_THRESHOLD = 80.0 ECD identity). (2) A1.10 adds fetch_representative_structure via PDBe SIFTS to StructureFeatures. (3) A2.3 + A2.4 share the is_likely_membrane_with_ecd topology helper used by both kickoff (deterministic_kickoff) and the secreted_form upgrade post-pass (orchestrator_postpass) — extract once, consume from two sites. Net: ~50-80 LOC added to d1_deterministic.py + a new shared topology_gate helper. No bloat risk — the module is mechanical fetcher code with room to grow.

### Cross-cutting principles

- Schema enforcement beats prompt enforcement. When a rule can be checked at parse time (compartment routing, modulation-state inequality, inline-cite presence, oncogenic-transformation cancer-vocab pairing), put it in a Pydantic validator and let the call_builder repair loop handle the retry. Prompt prose that says 'do not X' accumulates gene-specific carve-outs and erodes under model rewrites; validators do not.
- Examples belong in tests, not in prompts. Every gene-specific anti-example currently in a prompt (EGFR for sEGFR/cetuximab, HCC827/PC9/H1650 for expression-context, SRC/LYN for inner-leaflet, EGFRvIII for variant-trafficking, PMC8584739 / CD81 / Clone AY13 for reagent lists, ADAM17 for ligand-shedding) should be lifted to a test fixture so the principle is preserved with zero overspec risk in the model-facing prompt. The commit message is fine; the prompt body should be abstract.
- Retrieval expansions belong in deterministic kickoff, not selector follow-ups. The single-pass MAX_PLAN_ITERATIONS=1 invariant was a deliberate retirement of LLM-driven follow-up search; reintroducing it on either A1 or A2 reopens the cost wound. Every 'should we ask for more papers?' urge resolves to 'add a tuple to kickoff_templates.py'.
- Derivations from already-assembled blocks belong in orchestrator post-pass, not synthesizer. Counts, stance arithmetic, threshold banding, boolean rollups, and topology-derived corrections (secreted_form from no-TM isoforms, family from hgnc_id) are deterministic; the synthesizer authors prose and enum judgments only. The publish layer is the consistency seam for stable-ID-keyed self-healing.
- Helpers shared between v1 and v2 (or between annotate-time and bulk-sync, or between kickoff and post-pass) MUST live in one importable module — duplicate logic across orchestrators / scripts / call sites silently drifts. _derive_filters in v1 already proves the pattern; the new is_likely_membrane_with_ecd topology gate (shared between deterministic_kickoff and orchestrator_postpass secreted_form upgrade) should follow the same rule.
- ONE STAGE OWNS A CONCERN. When a principle could plausibly live in trim, select, builder, and synthesizer — pick the latest stage that has full information and put it there alone. Trim is recall-biased and must not encode select-time judgments. Select must not anticipate builder field routing. Synthesizer must not re-state builder discipline. Reading the same rule in three places means three places to drift.
- Self-describing rows over inheritance chains. Every per-row schema entity (ExpressionRow, OrthologEntry, IsoformTopology) must carry its own context fields (disease_context, sequence, per_residue_topology) — no viewer-side fallback that walks from a row to a paired row to learn its disease state or topology. The unified ExpressionRow (A1.1) is the canonical example; A1.8/A1.9 extend the same pattern to topology rows.
- Schema deletion beats schema downgrade. When a record block is not a surface-accessibility signal, delete it entirely (therapeutic_engagement) rather than keeping it as a noise-carrying field. An orphan field accrues prompt mentions, render code, viewer types, and test fixtures that all silently steer the agent toward filling it.
- Publish-by-default with explicit opt-out is the only invariant that prevents D1/viewer drift. A record change that lands only in the JSON silently leaves the live site serving the stale shape. Every write path (annotate-time + bulk-sync + future batch runners) must go through the same publish_record primitive so neither path can diverge.
- Stable-ID-keyed lookups (hgnc_id), never symbol-keyed. Re-asserted by A11.1 self-healing on every publish path: any deterministic curator field that can be recomputed from hgnc_id should be recomputed at publish time, not trusted from the in-memory record. Symbol-keyed re-resolution silently misroutes ~0.2% of genes (the COX1/WAS class).

### Open questions for the user (must decide before implementation)

**Q1.** TopicAnchor enum strategy for new retrieval axes (A6.1, A6.2, A2.4): extend the closed Literal with new values (tox_panel or six per-organ values, soluble_form/serum_plasma_shed, bbb/tumor_penetration/luminal_abluminal) and teach the topic_search dispatcher their query expansions — clean schema, requires upstream search-tool work — OR keep enum closed and ride the new SearchRequests on existing anchors (surface_expression) with the axis encoded in SearchRequest.intent string, relying on the dispatcher to inject the term from intent — zero schema churn but the new requests near-duplicate existing ones and depend on dispatcher behavior with intent strings? The principled answer is enum-extension; the cheap answer is intent-encoding.

**Q2.** Is PR #47 actually merged into the claude/practical-almeida-0e9fa3 branch this worktree is on? Multiple insights (A1.1 ExpressionRow, A2.3 step 7b _secreted_isoform_ids helper, A1.5 therapeutic_engagement deletion in v2 paths, A1.10 RepresentativeStructure, A8.2 inline-cite synth prompt edit) are documented as homed via PR #47 commits but their files do not show those changes in this worktree. Either the PR has not merged, the work was reverted, or the tracking doc is stale. Need a definitive answer before any new work assumes PR #47 has landed.

**Q3.** ~~Scope of the therapeutic_engagement scrub (A1.5)~~ **DECIDED 2026-06-01**: strip from v2 production path (plan_trim_select prompts: `a1_select_system.md` L63/L70/L145, `a1_trim_system.md` L17 surface_form_rationale, `select_system.md` L53 claim_type list, `plan_trim_select/render_html.py` L134). **Leave v1 untouched** (surface_evidence_compiler Managed Agent stays as-is for v1 historical reproducibility per CLAUDE.md).

**Q4.** Should the publish_self_heal stage (new step) absorb only deterministic-tag healing (family today, future curator-keyed fields), or also own the populated-to-empty regression guard and snapshot-to-D1 write-ordering invariants currently in _publish_dict? Narrow scope keeps the stage focused; broad scope captures the publish-is-the-consistency-seam principle but blurs into general publish-layer responsibility.

**Q5.** For the schema-PR sequencing: land PR-A (ExpressionRow unification + TherapeuticEngagement deletion) as one atomic break with a coordinated viewer republish, OR split into two PRs (deletion first, unification second) for easier review? Atomic minimizes the half-migrated viewer window; split minimizes per-PR review surface.

**Q6.** Filters_rationale_cite_validator (new schema validator, A1.6/A8.2): warn-only via warnings.warn (matches _PROSE_TARGETS pattern, no run-fail) or hard-raise to trigger call_builder repair? Warn-only protects throughput at the cost of letting no-cite records ship; hard-raise costs ~1 builder retry per missing cite but enforces the discipline structurally. Lean warn-only since the synthesizer is a Managed Agent with no in-process repair loop — a raise here would fail the run.

**Q7.** Optional reagent_provenance_postpass (A3.1, new step): land now to trim methods_builder_system.md by ~15 lines (already 217 lines, second-largest builder prompt), or defer because conjugate-variant disambiguation (anti-EGFR vs anti-EGFR-Alexa Fluor 488) is imperfect with a regex and the existing prompt-based cross-reference handles it correctly? Lean defer.

---

## A. Strong, principled insights — carry forward

### A1. Schema cleanup (the cleanup *is* the insight)

#### A1.1 — Unify tissues + cell_types into one `ExpressionRow`
- Status: `[x] homed`
- Scope: schema, v2
- Insight: tissues and cell_types are the same pivot; splitting them forced readers to cross-reference rows to learn which cell type was observed in which tissue
- Commit: `4d7e6a7`
- Current home: `tools/_shared/models.py` (`ExpressionRow`), `surfaceome_v2/builders/expression.py`, `surfaceome_v2/prompts/expression_builder_system.md`
- Future home: **schema** + builders, a2_trim, a2_select, orchestrator_postpass (overspec risk after move: low)
  - Principle (restated): Tissues and cell-types describe the same pivot — a per-(tissue × cell_type × disease_context) expression observation.
  - Coordinate with: A1.2, A1.3, A8.1, A11.4

#### A1.2 — Disease context belongs on cells, not inherited from tissue rows
- Status: `[x] homed`
- Scope: schema, v2
- Insight: cell-of-origin rows had no disease context of their own; now each cell carries `disease_context`/`disease_label`/`level`
- Commit: `c09a9f7`
- Current home: `tools/_shared/models.py` (per-cell fields on `ExpressionRow`)
- Future home: **schema** + builders (overspec risk after move: low)
  - Principle (restated): The row that carries the observation carries its own disease context (disease_context enum + disease_label free text + present/level).
  - Coordinate with: A1.1, A1.3, A1.4

#### A1.3 — Keep normal-tissue baselines next to disease rows even when surface levels are identical
- Status: `[x] homed`
- Scope: v2 (builder prompt)
- Insight: off-tumor toxicity baseline is load-bearing information; dropping it when levels match the tumor erases the toxicity read
- Commit: `bf12948` (negative form — "emit disease-context only when different from normal"); reversed in expression builder rewrite
- Current home: `surfaceome_v2/prompts/expression_builder_system.md`
- Future home: **builders** (overspec risk after move: low)
  - Principle (restated): Off-tumor toxicity baselines are load-bearing even when surface levels match the disease read.
  - Coordinate with: A1.1, A1.2, A6.2

#### A1.4 — `ModulationDirection` (up/down) is distinct from `AccessibilityImplication` (favorable/restricted)
- Status: `[x] homed`
- Scope: schema, v2
- Insight: viewer needs the directional arrow independent of the risk verdict; separating the two enums lets the chip and the risk grade move independently
- Commit: `eb1b57a`, `0ea5cc4`
- Current home: `tools/_shared/models.py` (`ModulationDirection` enum on `AccessibilityModulationObservation.direction`)
- Future home: **schema** + builders (overspec risk after move: low)
  - Principle (restated): A modulation row carries two orthogonal axes: (a) the up/down direction of the surface pool change (increases / decreases / bidirectional / no_change / unclear), and (b) the accessibility implication ...
  - Coordinate with: A7.1, A7.2, A2.1, A2.3

#### A1.5 — Drop `therapeutic_engagement` entirely; it is not a surface-accessibility signal
- Status: `[x] homed`
- Scope: schema, v2
- Insight: therapeutic engagement conflates pharmacology with compartment biology — not a surface-reachability claim
- Commit: `f1448bc`
- Current home: removed from `_shared/models.py`, `surfaceome_v2/builders/__init__.py`, prompts
- Future home: **schema** + builders, synthesizer, orchestrator_postpass (overspec risk after move: low)
  - Principle (restated): If a structured record block is not a surface-accessibility signal, drop it entirely from the schema and pipeline rather than keeping it as a noise-carrying field.
  - ⚠ Open question: The plan_trim_select prompts at src/accessible_surfaceome/agents/plan_trim_select/prompts/{a1_trim_system.md, a1_select_system.md, select_system.md} are shared by the v2 production path and still reference `therapeutic_engagement` (claim_type lists, surface_form_rationale, "the therapeutic_engagemen...
  - Coordinate with: A1.1, A1.2, A1.3, A1.4, A1.6, A1.7, A2.1, A2.2, A2.3

#### A1.6 — Every filter chip needs an inline-cited rationale
- Status: `[x] homed`
- Scope: schema, synth
- Insight: bare chip flags lose user trust; each chip should carry a one-line "why" with `(a1_evi_NN)` / `(a2_evi_NN)` inline cites
- Commit: `f499efa`
- Current home: `_shared/models.py` (`*_rationale` fields on `Filters`), `surfaceome_synthesizer/prompts/system.md` (rollup contract), `surfaceome_v1/orchestrator.py` (`_derive_filters` for the deterministically-composed two)
- Future home: **schema** + synthesizer, orchestrator_postpass (overspec risk after move: low)
  - Principle (restated): Every filter chip surfaced in the catalog must carry a one-line rationale with inline `(a1_evi_NN)` / `(a2_evi_NN)` evidence-id citations, so the chip is self-auditable.
  - ⚠ Open question: The 5 deep-block-backed chips (co_receptor_requirements, restricted_subdomain, shed_form, secreted_form, epitope_masking) carry their rationale in the accessibility_risks sub-block per the f499efa design. Should the viewer's chip-expansion code render `accessibility_risks.X.rationale` for those, or ...
  - Coordinate with: A8.1, A8.2

#### A1.7 — `accessibility_context_summary` belongs on every record
- Status: `[x] homed`
- Scope: schema, synth
- Insight: a single "when/where surface-accessible" headline is the load-bearing artefact of the §03 panel; it was implicit before
- Commit: in synthesizer rewrite (`d459630` and earlier)
- Current home: `_shared/models.py`, synthesizer prompt
- Future home: **synthesizer** + schema (overspec risk after move: low)
  - Principle (restated): Every record must carry a single-sentence headline that tells the reader WHEN and WHERE the protein is surface-accessible — not just a generic "consultant blurb." This headline is the load-bearing art...
  - Coordinate with: A1.6, A8.1, A8.2

#### A1.8 — Topology records should carry their sequence + %identity vs canonical
- Status: `[x] homed` (schema) / `[?] verify` (v2 computation)
- Scope: schema, v1 / v2 gap
- Insight: any downstream consumer should be able to do residue-level alignment without re-fetching UniProt; isoform/ortholog/paralog rows should be self-describing
- Commit: `0a68616`, `e0f4bc4`, `patch_deterministic_isoform_identity.py`
- Current home (schema): `IsoformTopology`, `OrthologEntry`, `ParalogEntry` in `_shared/models.py`
- Current home (computation): `surfaceome_v1/d1_deterministic.py` + backfill scripts
- Future home: **deterministic_features** + schema (overspec risk after move: low)
  - Principle (restated): Topology records must be self-describing: each isoform/ortholog/paralog row that carries a `per_residue_topology` string should also carry the amino-acid `sequence` it indexes 1:1 and, where there is ...
  - Coordinate with: A1.9

#### A1.9 — Paralogs ≥80% identity deserve full topology + sequence; far paralogs do not
- Status: `[x] homed` (schema) / `[?] verify` (v2 computation)
- Scope: schema
- Insight: bloating records with topology for distant paralogs is noise; close paralogs are the ones a reader can reason about
- Commit: `0a68616` (threshold `CLOSE_PARALOG_THRESHOLD = 80.0`)
- Current home: `_shared/models.py` (`ParalogEntry`), `compute_paralog_ecd_similarity.py`
- Future home: **deterministic_features** + schema (overspec risk after move: low)
  - Principle (restated): Records should carry the deterministic detail readers can actually reason about — and only that.
  - ⚠ Open question: Implement A1.9 + A1.8 together (they share the OrthologEntry-style self-describing-row pattern and the same D1 LEFT JOIN against topology_public), or land A1.8 first as the precedent and only then bring A1.9 over the same code path?
  - Coordinate with: A1.8

#### A1.10 — One representative PDB pointer, not a flat list
- Status: `[x] homed`
- Scope: schema
- Insight: `surface_bind.pdbs` was a flat list with no metadata; a reader wants "the experimental structure" (best coverage × resolution), single-sorted by PDBe SIFTS
- Commit: `e0f4bc4`
- Current home: `_shared/models.py` (`RepresentativeStructure`), `tools/pdbe_structures.py` (NEW)
- Future home: **schema** + deterministic_features (overspec risk after move: low)
  - Principle (restated): A protein's PDB entries should surface as ONE representative pointer (the highest-coverage, best-resolution structure) with coverage and resolution metadata attached — not a flat list of PDB IDs with no ranking metadata.
  - Coordinate with: A1.8, A1.9, A11.3
---

### A2. Secreted form / soluble isoforms

#### A2.1 — Grade `secreted_form.severity` by documented decoy behavior, not by mere existence of a soluble form
- Status: `[x] homed`
- Scope: synth
- Insight: synthesizer was conflating "topology-annotated soluble isoform exists" (weak signal) with "documented circulating form competing with therapeutics" (real decoy); severity tiering separates them
- Commit: `f2880ca`
- Current home: `surfaceome_synthesizer/prompts/system.md` (severity rubric)
- Future home: **synthesizer** + orchestrator_postpass, deterministic_kickoff (overspec risk after move: low)
  - Principle (restated): Severity of a soluble-form risk is a function of DOCUMENTED decoy behavior in the ledger (measured circulation in serum/plasma, or competition with a therapeutic binder), not of the mere existence of an annotated/predicted soluble isoform.
  - Coordinate with: A2.3, A2.4, A2.2

#### A2.2 — `secreted_form` is about the TARGET being soluble, not its ligand being shed
- Status: `[x] homed`
- Scope: synth
- Insight: a recurring conflation; the field documents whether the *target* exists in a soluble form, not whether the ligand is shed
- Commit: `8eeae25`
- Current home: synthesizer prompt
- Future home: **synthesizer** (overspec risk after move: low)
  - Principle (restated): `secreted_form` is a per-target accessibility risk: it fires only when the TARGET protein itself exists as a free soluble species (proteolytically shed ectodomain of the target, or a TM-less splice isoform of the target).
  - Coordinate with: A2.1, A2.3

#### A2.3 — Synthesizer runs before isoform topology is available → upgrade `secreted_form` deterministically post-pass
- Status: `[x] homed`
- Scope: v2 orchestrator
- Insight: the right pattern is deterministic enrichment AFTER the LLM, not "ask the LLM harder"; TM=0 + ECD ≥30aa → auto-upgrade to `present=True, severity="low", evidence_strength="weak", source="alternative_splicing"`
- Commit: `47933e0`, `896ebc1`, `79a2860` (helper extraction + test)
- Current home: `surfaceome_v2/orchestrator.py` step 7b, `_secreted_isoform_ids` helper
- Future home: **orchestrator_postpass** + deterministic_features (overspec risk after move: low)
  - Principle (restated): When an LLM stage receives an incomplete information set by ordering (e.g., synthesizer runs before isoform topology is fetched from D1), do not "ask the LLM harder" or feed it more data — instead, de...
  - ⚠ Open question: Is PR #47 actually merged into the `claude/practical-almeida-0e9fa3` branch this worktree is on? If yes, where did the step 7b block + `_secreted_isoform_ids` helper + test file go (search across worktree finds zero hits)? If no, A2.3 should be marked status=open-pending-merge in the plan doc, not [...
  - Coordinate with: A1.8, A1.9, A2.1, A2.2, A2.4, A11.2, A11.3

#### A2.4 — Retrieve the soluble-form literature (serum/plasma sEGFR-style)
- Status: `[~] migrate`
- Scope: plan (currently dead code)
- Insight: searching specifically for soluble form measured in serum/plasma + ligand/antibody competition is the only way to grade `secreted_form` above severity=low; needs to be a conditional search angle
- Commit: `f2880ca` (lives in `a2_plan_system.md`, dead code)
- Current home: `plan_trim_select/prompts/a2_plan_system.md` (dead)
- Future home: **deterministic_kickoff** + orchestrator_postpass (overspec risk after move: low)
  - Principle (restated): Soluble/shed extracellular forms (target-protein-as-free-fragment in serum/plasma) are a distinct retrieval axis from generic "shedding" papers and are predictable per topology — gate the retrieval at...
  - ⚠ Open question: Should the topology gate be a single shared helper (e.g. `is_likely_membrane_with_ecd(n_tmh, ecd_aa) -> bool`) consumed by both the kickoff dispatcher AND the orchestrator's secreted_form post-pass (A2.3)? If yes, where does it live — `agents/_shared/topology_gate.py` or attached to the deterministi...
  - Coordinate with: A2.1, A2.2, A2.3, A6.1, A6.2, A6.3

---

### A3. Methods + antibody linking

#### A3.1 — Reagent-list sentences enable downstream clone linking
- Status: `[x] homed`
- Scope: v2 (trim + select)
- Insight: many papers report clones/vendors once in a "Materials / Antibodies" sentence then say "stained with anti-X" downstream; if trim drops the reagent sentence as "not a surface claim", every antibody comes back `clone=null`
- Commit: `a2ef76f`, `fef4f2e`
- Current home: `plan_trim_select/prompts/a1_trim_system.md`, `a1_select_system.md` (auxiliary-sentence retention rule)
- Future home: **a1_trim** + a1_select, builders (overspec risk after move: low)
  - Principle (restated): Trim stages must retain consolidated reagent-list / Materials sentences even when each sentence is not itself a surface claim — they are the single source of antibody clone / vendor / RRID provenance that downstream method-observation rows require.
  - ⚠ Open question: Should reagent-list cross-referencing (the methods_builder paragraph in fef4f2e) be migrated to a deterministic orchestrator post-pass step? It is regex-mechanizable ("anti-[TARGET] (Clone X)" → fill matching MethodObservation.antibodies[].clone), which would remove ~15 lines from an already-217-lin...
  - Coordinate with: A3.3, A4.1, A4.2, A4.3, A4.5

#### A3.2 — Permeabilized assays prove localization but cannot prove surface accessibility
- Status: `[x] homed`
- Scope: v2 (builder prompt)
- Insight: keep `expression_only` tier when a permeabilized assay describes membrane localization — use `surface_claim_type` to record the localization observation without falsely upgrading to surface evidence
- Commit: `30a6c86`
- Current home: `surfaceome_v2/prompts/methods_builder_system.md`
- Future home: **builders** (overspec risk after move: low)
  - Principle (restated): Permeabilized assays prove localization (where the protein was seen) but cannot prove surface accessibility (whether antibodies or drugs can reach it from outside).
  - Coordinate with: A3.3, A4.2, A4.5, A5.3

#### A3.3 — Collapse method rows only when `(evidence_id, method_subclass, expression_system)` all match
- Status: `[x] homed`
- Scope: v2 (builder prompt)
- Insight: distinct assay conditions (permeabilized vs non-permeabilized) deserve separate rows; collapsing them erases the surface-vs-total readout
- Commit: `8b8ac38`
- Current home: `surfaceome_v2/prompts/methods_builder_system.md`
- Future home: **builders** + orchestrator_postpass (overspec risk after move: low)
  - Principle (restated): Two structured rows are redundant only when they share the same source citation AND the same fundamental assay discriminators (method subclass + expression system).
  - Coordinate with: A3.2, A4.5, A9.1, A11.2
---

### A4. Overexpression (OE) precedent retention

#### A4.1 — Always keep one OE-surface clip, even if endogenous siblings outrank it
- Status: `[x] homed`
- Scope: v2 (select prompt + deterministic filter)
- Insight: OE precedent answers a distinct question ("can it traffic to surface when overexpressed?"); endogenous evidence does not subsume it; pruning every OE clip silently kills the `overexpression_surface_localization_observed` filter
- Commit: `a2ef76f`
- Current home: `plan_trim_select/prompts/a1_select_system.md`, `surfaceome_v1/orchestrator.py` (`_derive_filters` `overexpression_surface_localization_observed`)
- Future home: **a1_select** + orchestrator_postpass (overspec risk after move: low)
  - Principle (restated): When a selector enforces a "prefer X over Y" ranking rule between two evidence categories, it must also enforce a floor: retain ≥1 representative of the dispreferred category if a downstream deterministic filter depends on its presence.
  - Coordinate with: A4.5, A4.2, A4.3, A11.2

#### A4.2 — OE = cell-surface readout on intact transfected cells (not in-vitro biochemistry)
- Status: `[x] homed`
- Scope: v2 (select prompt)
- Insight: SPR / BLI / ECD-on-chip match "surface" semantically but are biochemistry, not localization; OE precedent must be flow / non-perm IF / antibody-or-ligand binding to live transfectants
- Commit: `7a4572d`
- Current home: `plan_trim_select/prompts/a1_select_system.md`
- Future home: **a1_select** + deterministic_kickoff (overspec risk after move: low)
  - Principle (restated): An OE-surface qualifying clip is a cell-surface readout on INTACT transfected/OE cells (live-cell or non-perm flow, non-perm IF, antibody or ligand binding to live transfectants).
  - Coordinate with: A4.1, A4.3, A4.4, A4.5, A3.2

#### A4.3 — Prefer wild-type / canonical over disease variants at SELECTION
- Status: `[x] homed`
- Scope: v2 (select prompt)
- Insight: variants (EGFRvIII, fusions, constitutive mutants) only prove the variant traffics; WT transfer is the precedent readers need for validation experiments
- Commit: `78e5d2a`
- Current home: `a1_select_system.md`
- Future home: **a1_select** (overspec risk after move: low)
  - Principle (restated): At A1 selection, when picking the overexpression-precedent clip, prefer a wild-type / canonical-isoform OE-surface readout over a disease-variant readout (oncogenic deletions, gene fusions, constituti...
  - Coordinate with: A4.1, A4.2, A4.4, A4.5

#### A4.4 — Do NOT gate OE retrieval on the "wild-type" keyword
- Status: `[~] migrate`
- Scope: plan (currently dead code)
- Insight: real WT-transfectant papers almost never use the phrase "wild-type"; WT preference belongs at the SELECTION layer, not in search queries
- Commit: `9b1815a`, `16b31c8`
- Current home: `a1_plan_system.md` (dead) — the *principle* is also in `a1_select_system.md` (live), but the corresponding deterministic search plan must be confirmed to not include the keyword gate
- Future home: **deterministic_kickoff** + a1_select (overspec risk after move: low)
  - Principle (restated): Search-plan queries for overexpression / surface-localization literature must NOT include the "wild-type" keyword as a filter, because real WT-transfectant papers rarely use that phrase explicitly — gating on it suppresses recall.
  - Coordinate with: A4.3

#### A4.5 — Dedup OE within methodology, not across; cell-line redundancy ≠ methodology redundancy
- Status: `[x] homed`
- Scope: v2 (select prompt)
- Insight: every distinct surface assay deserves its own row; OE-vs-endogenous redundancy is not a dedup target
- Commit: `a2ef76f`
- Current home: `a1_select_system.md`
- Future home: **a1_select** + a2_select (overspec risk after move: low)
  - Principle (restated): When applying dedup discipline at selection, "distinct" is defined along methodology axes (assay class, host system, construct configuration), not along cell-line label or paper identity.
  - Coordinate with: A4.1, A9.1, A3.3
---

### A5. Subcellular localization discipline

#### A5.1 — `compartment` is a short canonical NAME, not a sentence with conditions
- Status: `[!] overspec`
- Scope: v2 (builder prompt)
- Insight: agent was packing condition clauses ("endosome (upon EGF ligand stimulation)") into the compartment field; field discipline is the principle
- Commit: `74f7133`
- Current home: `surfaceome_v2/prompts/subcellular_localization_builder_system.md`
- Future home: **schema** + builders (overspec risk after move: low)
  - Principle (restated): Compartment / subdomain field values are SHORT canonical organelle or microdomain names — not sentences and not clause-packed strings.
  - Coordinate with: A5.2, A5.3

#### A5.2 — Inner leaflet / cytoplasmic face is NOT surface-accessible
- Status: `[!] overspec`
- Scope: v2 (builder prompt)
- Insight: cytoplasmic-face lipidation belongs in `dual_localization`, not `membrane_subdomains`; SRC/LYN myristoylation/palmitoylation is the canonical confusion
- Commit: `74f7133`
- Current home: subcellular_localization builder prompt
- Future home: **builders** + schema (overspec risk after move: low)
  - Principle (restated): Inner-leaflet / cytoplasmic-face lipidated proteins are not surface-accessible.
  - Coordinate with: A5.1, A5.3

#### A5.3 — Plasma-membrane subdomains ≠ whole compartments
- Status: `[x] homed`
- Scope: v2 (builder prompt)
- Insight: lipid raft / inner leaflet / apical-basolateral belong in `membrane_subdomains`, not as endosome/Golgi/etc.
- Commit: `74f7133`
- Current home: subcellular_localization builder prompt
- Future home: **builders** (overspec risk after move: low)
  - Principle (restated): Plasma-membrane subdomains (lateral microdomains of the outer leaflet — e.g.
  - ⚠ Open question: PR #47 (commit 74f7133) appears to be the single source of homing for A5.1, A5.2, and A5.3 simultaneously. Status of the PR — is the plan still to merge PR #47 as a unit, or should these three insights be cherry-picked into a separate atomic PR ahead of the larger PR-47 viewer/render changes? The pr...
  - Coordinate with: A5.1, A5.2
---

### A6. Anatomical accessibility / tox-organ coverage

#### A6.1 — Surface-reachability ≠ surface-presence
- Status: `[~] migrate`
- Scope: plan (currently dead code) + v2 (builder prompt)
- Insight: tumor vasculature, BBB, mucosal compartments are their own evidence axis — a protein can be highly expressed but unreachable by a drug; anatomical accessibility is distinct from surface localization
- Commit: `06eab63`
- Current home: `a2_plan_system.md` (dead), `surfaceome_v2/prompts/anatomical_accessibility_builder_system.md` (mostly cosmetic in this PR)
- Future home: **deterministic_kickoff** + builders, schema (overspec risk after move: low)
  - Principle (restated): Surface-reachability is a distinct evidence axis from surface-presence: a protein can be highly expressed yet physically unreachable by a systemically dosed binder because an anatomical barrier (tumor...
  - ⚠ Open question: The current closed TopicAnchor enum (surface_expression, topology, ihc, flow_cytometry, surface_biotinylation, mass_spec_surfaceome, structure, ptm, shedding) has no value that distinctly expresses tumor-penetration / BBB / luminal-vs-abluminal axes. Two paths: (1) re-use `surface_expression` anchor...
  - Coordinate with: A6.2, A6.3, A1.1, A5.3

#### A6.2 — Six high-consequence tox organs are mandatory coverage
- Status: `[~] migrate`
- Scope: plan (currently dead code) + v2 (builder prompt)
- Insight: liver / lung / kidney / GI / heart / brain are the panel; every gene must have coverage even when "absent" is the right answer
- Commit: `aa9ae48`
- Current home: `a2_plan_system.md` (dead), expression / tissues builders
- Future home: **deterministic_kickoff** + builders (overspec risk after move: low)
  - Principle (restated): The six high-consequence tox organs (liver, lung, kidney, GI, heart, brain) are a mandatory normal-tissue coverage axis for every gene because on-target / off-tumor toxicity is determined by surface expression in these organs.
  - ⚠ Open question: The TopicAnchor Literal is currently closed and method-flavored (surface_expression, topology, ihc, flow_cytometry, etc.) — no tissue/organ anchors. To wire tox-panel retrieval cleanly there are two paths: (1) extend the TopicAnchor enum with a `tox_panel` value (or six per-organ values) and teach t...
  - Coordinate with: A6.3, A6.1, A1.3

#### A6.3 — Don't use RNA-atlas-only searches for tox; transcript ≠ surface exposure
- Status: `[~] migrate`
- Scope: plan (currently dead code)
- Insight: tox-context retrieval must seek protein-level / surface-level evidence, not just bulk RNA; credible negatives count
- Commit: `aa9ae48`
- Current home: `a2_plan_system.md` (dead)
- Future home: **deterministic_kickoff** (overspec risk after move: low)
  - Principle (restated): Tox-organ retrieval must route through protein/surface-level evidence channels (IHC, IF, flow, surface biotinylation, mass-spec surfaceome) — never RNA-atlas-only categories.
  - Coordinate with: A6.1, A6.2

---

### A7. Accessibility modulation precision

#### A7.1 — Emit a row only when ledger documents a real CHANGE in surface accessibility
- Status: `[!] overspec`
- Scope: v2 (builder prompt)
- Insight: rows were being emitted for mere expression context ("cells express EGFR") instead of actual surface-state transitions; the principle is "documented change between two named states", not "mention of the protein"
- Commit: `e6da597`
- Current home: `surfaceome_v2/prompts/accessibility_modulation_builder_system.md`
- Future home: **builders** + schema (overspec risk after move: low)
  - Principle (restated): An accessibility_modulation row is a CONTRAST, not a CONTEXT.
  - Coordinate with: A1.1, A1.2, A7.2

#### A7.2 — Don't map non-cancer diseases to `oncogenic_transformation` trigger
- Status: `[!] overspec`
- Scope: v2 (builder prompt / orchestrator)
- Insight: trigger taxonomy bleed; non-cancer disease state should not slot into the oncogenic bucket
- Commit: `4d0135f`
- Current home: builder prompt / `_derive_filters`
- Future home: **schema** + orchestrator_postpass (overspec risk after move: low)
  - Principle (restated): Closed-enum taxonomy buckets must be mutually exclusive at the schema layer.
  - ⚠ Open question: Validator-hard (raise ValueError, force builder repair loop) vs orchestrator-coerce (set bad trigger to null, log warning, never fail the run)? Recommendation: validator-hard with the existing 2-retry call_builder budget — if the builder cannot fix in 2 tries the row is genuinely confused and droppi...
  - Coordinate with: A7.1, A1.4

---

### A8. Citation precision (synthesizer)

#### A8.1 — Cite the claim, not the background
- Status: `[x] homed`
- Scope: synth
- Insight: `co_receptor_requirements` should cite papers on partner-dependency itself, not generic surface-expression / signaling papers; `restricted_subdomain` should cite spatial-distribution evidence, not bare surface-residence
- Commit: `d459630`
- Current home: `surfaceome_synthesizer/prompts/system.md`
- Future home: **synthesizer** (overspec risk after move: low)
  - Principle (restated): For each accessibility_risks sub-block, cited_evidence_ids must reference claims that DIRECTLY substantiate that sub-block's specific assertion, not generic surface-expression / surface-residence claims.
  - Coordinate with: A8.2, A1.6

#### A8.2 — Cite the LLM rollups inline in chip rationales
- Status: `[x] homed`
- Scope: synth
- Insight: every chip rationale must be auditable from the chip — inline `(a1_evi_NN)` / `(a2_evi_NN)` cites
- Commit: `d459630`
- Current home: synthesizer prompt
- Future home: **synthesizer** + schema (overspec risk after move: low)
  - Principle (restated): Each LLM-rollup chip rationale must embed the specific supporting evidence id(s) inline as `(a1_evi_NN)` / `(a2_evi_NN)` tokens so the viewer can linkify each cite next to the claim and a reader can audit any chip from the chip itself.
  - ⚠ Open question: Worth adding a soft schema validator on `SynthesizerLLMFilters.*_rationale` that warns (not errors) when the string lacks any `(a[12]_evi_NN)` token? It only catches the no-cite failure (LLM omitted all cites) — not the wrong-cite class that d459630 targets — but it would tripwire prompt-drift / par...
  - Coordinate with: A1.6, A8.1
---

### A9. Coverage > consensus deduplication

#### A9.1 — One strong clip per (source, claim_type); every distinct surface assay gets its own row
- Status: `[x] homed`
- Scope: v2 (select prompts)
- Insight: the old "minimize claims" budget-driven rule erased methodology diversity; coverage of distinct assays is the right optimization
- Commit: implied in `a2ef76f` and the dedup-section rewrites in `a1_select_system.md` / `a2_select_system.md`
- Current home: both select prompts
- Future home: **a1_select** + a2_select (overspec risk after move: low)
  - Principle (restated): When deduplicating the evidence ledger, the unit of redundancy is (source, methodology, claim_type) — not the underlying conclusion.
  - Coordinate with: A3.3, A4.5, A4.1
---

### A10. Iteration on biology context (A2 only)

#### A10.1 — A2 selector can request follow-up searches mid-loop
- Status: `[x] homed` (A2) / `[ ] open` (A1 symmetry)
- Scope: v2 (select prompt)
- Insight: biology context is complex enough that one-shot retrieval misses controversies / high-impact genetics / subcellular ambiguity; iteration is worth the cost
- Commit: `7acf299`
- Current home: `a2_select_system.md` iteration section
- Future home: **deterministic_kickoff** + a1_select, a2_select (overspec risk after move: low)
  - Principle (restated): When a selector encounters thin coverage (sparse tissues, unresolved controversies, ambiguous subcellular call, missing high-impact genetics), the correction belongs UPSTREAM in the deterministic kick...
  - Coordinate with: A2.4, A4.4, A6.1, A6.2, A6.3

---

### A11. Deterministic enrichment moves to publish time (the right pattern)

#### A11.1 — Family tag self-heal at publish
- Status: `[x] homed`
- Scope: v2 orchestrator
- Insight: v2 had been shipping records with empty family fields because v2 orchestrator didn't call `_attach_deterministic_families`
- Commit: `a0364e8`
- Current home: `surfaceome_v2/orchestrator.py` step 7a
- Future home: **NEW STEP — new:publish_self_heal** + orchestrator_postpass (overspec risk after move: low)
  - Principle (restated): Curator-assigned ground-truth tags keyed on a stable ID must be re-asserted at every publish path, not only at generation, so already-published or degraded-at-generation records repair themselves on next write.
  - ⚠ Open question: Should the new publish_self_heal stage absorb only deterministic-tag healing (family today, future curator-keyed fields), or also own the populated-to-empty regression guard and snapshot-to-D1 write-ordering invariants currently in _publish_dict? Narrow scope keeps the stage focused; broad scope cap...
  - Coordinate with: A11.3, A11.4, A11.2

#### A11.2 — Filters derivation: v2 calls v1's `_derive_filters`
- Status: `[x] homed`
- Scope: v2 orchestrator
- Insight: v2 was emitting only 3 LLM rollups, leaving 14+ filter fields at defaults; deterministic derivation post-synthesis fills them
- Commit: `f499efa`
- Current home: `surfaceome_v2/orchestrator.py` step 7c, `surfaceome_v1/orchestrator.py` `_derive_filters` (shared)
- Future home: **orchestrator_postpass** + synthesizer, schema (overspec risk after move: low)
  - Principle (restated): Filter rollup fields that are mechanically derivable from already-assembled record blocks (evidence stances, accessibility_risks, deterministic_features, filters_llm) MUST be computed by a determinist...
  - Coordinate with: A11.1, A11.3, A11.4, A1.6, A8.2, A2.3

#### A11.3 — Backfill scripts mirror in-orchestrator logic
- Status: `[x] homed`
- Scope: v2 orchestrator + backfill
- Insight: deterministic enrichment paths exposed as scripts so older records can reach the new shape without an LLM re-run
- Commit: `backfill_deep_block_rollups.py`, `backfill_deterministic_family.py`, `backfill_sequences_and_links.py`, `backfill_surface_bind_attribution.py`, `patch_deterministic_isoform_identity.py`
- Current home: scripts directory
- Future home: **orchestrator_postpass** + scripts (overspec risk after move: low)
  - Principle (restated): Deterministic post-pass logic (filter derivation, headline-risk scrubbing, feature fetch, family attachment) must be importable as plain functions from the orchestrator module so backfill scripts can ...
  - Coordinate with: A11.1, A11.2, A2.3

#### A11.4 — v2 annotate publishes to viewer snapshot + public D1 by default
- Status: `[x] homed`
- Scope: v2 orchestrator
- Insight: previously a record could land on disk via `--persist` but never reach D1, so the Worker kept serving stale schema; publishing-by-default enforces D1↔snapshot↔record consistency
- Commit: `09cfd54`
- Current home: `scripts/surfaceome_v2_annotate.py`, `cloud/surface_annotation.py:publish_record`
- Future home: **validate-current-home** + orchestrator_postpass (overspec risk after move: low)
  - Principle (restated): The CLI driver that wraps a deep-dive run owns publish-time persistence policy: a validated record must reach all three surfaces (on-disk artifact, viewer snapshot, public D1) by default, with explici...
  - Coordinate with: A11.1, A11.2, A11.3
---

## B. Reactive / overspecific edits — extract principle, drop example

These are individually correct but encode gene-specific examples that won't scale. Each `[!] overspec` row above already lists the example to lift. Aggregated here for a single redesign sweep:

- **B.1** — Drop `HCC827 / PC9 / H1650` EGFR cell-line list from `accessibility_modulation_builder_system.md`; replace with "drug-naive baseline ≠ modulation". (see [A7.1](#a71--emit-a-row-only-when-ledger-documents-a-real-change-in-surface-accessibility))
- **B.2** — Drop `5A6` / `AY13` clone identifiers from `methods_builder_system.md` example. (see [A3.1](#a31--reagent-list-sentences-enable-downstream-clone-linking))
- **B.3** — Drop SRC/LYN-by-name myristoylation/palmitoylation example from `subcellular_localization_builder_system.md`; generalize to "cytoplasmic-face lipid anchor ≠ surface-accessible". (see [A5.2](#a52--inner-leaflet--cytoplasmic-face-is-not-surface-accessible))
- **B.4** — Drop `EGF ligand stimulation` example from the compartment-discipline section; generalize to "conditions/clauses do not belong in the `compartment` field". (see [A5.1](#a51--compartment-is-a-short-canonical-name-not-a-sentence-with-conditions))
- **B.5** — Audit the synthesizer's worked chip-rationale examples for EGFR tie-ins; replace with neutral or rotating examples. (see [A1.6](#a16--every-filter-chip-needs-an-inline-cited-rationale))
- **B.6** — `4d0135f` "don't map non-cancer disease → oncogenic_transformation" is a single-gene patch; promote to a "trigger taxonomy is mutually exclusive" check in the schema or derivation. (see [A7.2](#a72--dont-map-non-cancer-diseases-to-oncogenic_transformation-trigger))

---

## C. Insights stranded in dead code (planning prompts) — must migrate

Becca added **169 lines** across `a1_plan_system.md` (66+) and `a2_plan_system.md` (103+). The LLM planner has since been replaced by a deterministic kickoff template, so these edits are not running. Each insight below needs a home in the deterministic plan (or its successor):

- **C.1** — OE search must hit ANY heterologous host (CHO, COS-7, 293T, Expi293, primary lines), not just HEK293-centric. → cross-references [A4.4](#a44--do-not-gate-oe-retrieval-on-the-wild-type-keyword)
- **C.2** — Soluble / shed-ectodomain search angle, gated on topology hint (TM-less isoform present or known-ligand-shedding gene). → cross-references [A2.4](#a24--retrieve-the-soluble-form-literature-serumplasma-segfr-style)
- **C.3** — Anatomical-accessibility depth (BBB / tumor penetration / mucosal compartments) as explicit search angles. → cross-references [A6.1](#a61--surface-reachability--surface-presence)
- **C.4** — Tox-organ panel of six (liver/lung/kidney/GI/heart/brain) as mandatory per-gene coverage. → cross-references [A6.2](#a62--six-high-consequence-tox-organs-are-mandatory-coverage)
- **C.5** — Don't use RNA-atlas-only retrievers for tox; require protein/surface-level evidence. → cross-references [A6.3](#a63--dont-use-rna-atlas-only-searches-for-tox-transcript--surface-exposure)
- **C.6** — Dual-localization + membrane-subdomain push, paired with fractionation literature so `fraction_estimate` actually fills.
- **C.7** — Triage prior shapes search intensity (canonical surface → standard coverage; contextual → extra `topic_search`; intracellular → ectopic chase). → check the deterministic plan already encodes this, otherwise migrate.

---

## D. Web search shortcut — your specific concern

Web search was enabled on the **methods builder only** ([f2d569d](https://github.com/Deliverome-Project/accessible-surfaceome/pull/47/commits/f2d569d)). Mechanics + concerns:

- **D.1** Mechanics
  - Anthropic server-side `web_search_20250305`, `max_uses: 8` per gene
  - Wired in `surfaceome_v2/builders/_common.py` via optional `tools` param on `call_builder`
  - Graceful degradation if web search disabled (downgrades to cite-only, no crash)
  - Prompt guardrail: "Use web search SOLELY to resolve antibody reagent metadata" — only three scalar `AntibodyRef` fields (`monoclonal_or_polyclonal`, `antibody_epitope_region`, `validation_strength`)
  - Hard rule: every `cited_evidence_ids` value must appear in the input ledger as an `evidence_id`

- **D.2** Why this still shortcuts the evidence flow
  - Metadata enters the record without going through retrieval → triage → trim → select. It's not a clip; it's a field value the agent typed in after a side-channel search. The audit chain is broken for those three fields.
  - It sets a pattern. Future prompt iterations may rely on "the agent can just look it up". Becca's antibody prompt is now ~118 lines; if more fields get this treatment, our ledger stops being the source of truth.
  - The prompt does the right thing here but the constraint isn't loud — eight searches is plenty of headroom to drift into surface-claim territory.

- **D.3** Proposed reformulation (to discuss)
  - Route the same web-search calls through a **first-class evidence tool** that produces clip-like artifacts (source ID + extracted-text payload) which the ledger picks up as a normal evidence row. Then the synthesizer cites it the same way it cites a paper. This preserves the audit chain and keeps the ledger as source of truth.
  - Future home:

---

## E. v1 changes with v2 implications — gap, not bug

The schema additions from §A1.8–A1.10 ride on the shared schema, but the **computation** lives in `surfaceome_v1/d1_deterministic.py`. The existence of so many backfill scripts strongly suggests v2 was NOT populating these at annotate time.

- **E.1** — Verify: does fresh v2 annotate populate `IsoformTopology.full_length_pct_identity_to_canonical` / `ecd_pct_identity_to_canonical` / `ecd_pct_similarity_to_canonical` / `sequence`? If not, port the BLOSUM62 alignment helper from v1.
  - Trace: `surfaceome_v1/d1_deterministic.py` → `merge/isoform_identity.py` (new) → ?  How is it called?
  - Future home:

- **E.2** — Verify: does fresh v2 annotate populate `ParalogEntry.per_residue_topology` / `tm_helix_count` / `ecd_length_residues` / `sequence` for ≥80%-identity paralogs? If not, port.
  - Trace: `surfaceome_v1/d1_deterministic.py` (paralog enrichment) → `compute_paralog_ecd_similarity.py`
  - Future home:

- **E.3** — Verify: does fresh v2 annotate populate `OrthologEntry.sequence`? If not, port.
  - Future home:

- **E.4** — Verify: does fresh v2 annotate populate the AFDB/PDB URL fields on `deterministic_features`? If not, port. (Backfill script `backfill_sequences_and_links.py` exists, suggesting no.)
  - Future home:

- **E.5** — Verify: does fresh v2 annotate compute `RepresentativeStructure` for the canonical UniProt?
  - Trace: `tools/pdbe_structures.py` (NEW) — who calls it during annotate?
  - Future home:

If any of E.1–E.5 are "no", the cure is to extract a shared `compute_deterministic_features(uniprot_acc, ...)` helper called by both v1 and v2 orchestrators, rather than duplicating the logic.

---

## Open questions for the redesign discussion

- **Q1** — Is the deterministic kickoff template the right place for C.1–C.7, or should we revisit having a (constrained) LLM planner that consumes triage signal + topology and emits a search-angle list? The principle of "search what the gene needs, not boilerplate" is worth preserving even if the LLM-vs-deterministic axis flips again.
- **Q2** — Should A1 (surface evidence) get the same iteration loop as A2 (biology), or is its single-pass design correct because surface evidence is more retrieval-tractable?
- **Q3** — D.3 above: do we want to formalize "web-search-as-tool-evidence" as a first-class evidence source with its own provenance row, or do we want to keep web search out of the deep-dive pipeline entirely and run a separate metadata-enrichment pass?
- **Q4** — Are the four v1-only computation paths (isoform identity, paralog topology, ortholog sequence, AFDB/PDB) appropriate to keep in v1's `d1_deterministic.py` and call from v2, or should they move to a shared `tools/deterministic_features/` module that neither pipeline owns?

---

## Maintenance

Update status flags as we work through the redesign. When an insight finds its future home, fill in **Future home:** with the path (and PR/commit when landed) and flip status to `[x]`.
