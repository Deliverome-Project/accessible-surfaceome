# Tagged Sites — Plan 6: Internalization-evidence agent (§08 data source)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A runnable pipeline that, given a gene, retrieves published internalization evidence and emits `InternalizationFile` JSON into `viewer/public/internalization/{SYMBOL}.json` — one row per measurement, `ligand_status` first-class, quantitative rows and qualitative statements kept as separate evidence classes — powering the §08 tab (Plan 3).

**Architecture:** Same shape as Plan 5, under `src/accessible_surfaceome/agents/internalization/`. Ports the internalization-benchmark prompt (`deliverome-internal/data/analysis/agentic_internalization_benchmark/prompt.md`). Retrieval + LLM reuse the **project stack** — `tools/evidence_retrieval.py` (an internalization-tuned `EvidenceCategory`) + `agents/surfaceome_v2/builders/_common.py:call_builder` — **not MCP**. Testable surrounds: output schema, normalization (nulls preserved, qualitative kept separate and never promoted to a quantitative row), and the emit-writer. The retrieval + `call_builder` step is the one non-unit-testable part.

**Tech Stack:** Python 3, pytest, repo agent framework, the project retrieval stack (`tools/evidence_retrieval.py`) + `call_builder` (Anthropic SDK), jsonschema. **No MCP.**

**Parent spec:** §5.2, §7.3 · **Depends on:** Plan 1 (`InternalizationFile` shape), Plan 3 (consumer). Reuses Plan 5's agent-invocation harness pattern.

---

### Task 1: Output schema + validator

**Files:**
- Create: `src/accessible_surfaceome/agents/internalization/schema.py`, `validate.py`
- Test: `tests/test_internalization_agent_schema.py`

- [ ] **Step 1: Failing test** — a well-formed output (per the internalization prompt: `measurements[]` with `cell_type`, `assay`, `ligand_status`, `rate`, `rate_class`, `n_replicates`, `source`; plus `qualitative_statements[]`) validates; a measurement with `rate_class` above `not quantified` but no `rate` is flagged; a qualitative statement in the measurements array is rejected.
- [ ] **Step 2: Run → FAIL.** — [ ] **Step 3: Implement** the jsonschema (enums: `ligand_status ∈ {constitutive, ligand-driven, not stated}`, `rate_class ∈ {quantified, not quantified}`), + `validate_agent_output`. — [ ] **Step 4: PASS.** — [ ] **Step 5: Commit** — `feat(internalization-agent): output schema + validator`

---

### Task 2: Prompt assembly

**Files:**
- Create: `src/accessible_surfaceome/agents/internalization/prompt.py`, `prompt_body.md` (ported)
- Test: `tests/test_internalization_prompt.py`

- [ ] **Step 1: Failing test** — `build_prompt(gene, protein_name)` embeds gene+name and the three benchmark rules (one row per measurement; ±ligand first-class; nulls-are-results / qualitative-is-separate).
- [ ] **Step 2: FAIL → Step 3: Implement** (load `prompt_body.md`, inject gene/name). — [ ] **Step 4: PASS.** — [ ] **Step 5: Commit** — `feat(internalization-agent): prompt assembly`

---

### Task 3: Normalize → InternalizationFile

**Files:**
- Create: `src/accessible_surfaceome/agents/internalization/normalize.py`
- Test: `tests/test_internalization_normalize.py`

- [ ] **Step 1: Failing test** — `normalize_output(obj, gene, acc)`:
  - maps each measurement to an `InternalizationMeasurement` dict matching `viewer/lib/tag-sites-types.ts` (field-name parity: `cell_type`, `assay`, `ligand_status`, `ligand`, `rate`, `rate_class`, `n_replicates`, `source`);
  - preserves nulls (`rate: None` stays, becomes "not stated" only at display time — Plan 3);
  - keeps `qualitative_statements` in their own list and **never** promotes one to a measurement;
  - clamps `rate_class` to `not quantified` when `rate` is null (a qualitative claim can't be "quantified").
- [ ] **Step 2: FAIL → Step 3: Implement.** — [ ] **Step 4: PASS.** — [ ] **Step 5: Commit** — `feat(internalization-agent): normalize to InternalizationFile`

---

### Task 4: Emit-writer + runner

**Files:**
- Create: `src/accessible_surfaceome/agents/internalization/emit.py` (`emit_internalization_json(gene, acc, measurements, qualitative, out_dir)`)
- Create: `src/accessible_surfaceome/agents/internalization/run.py` (CLI)
- Test: `tests/test_internalization_emit.py`

- [ ] **Step 1: Failing test** — emit writes `{out_dir}/{SYMBOL}.json` with `has_data = (len(measurements) + len(qualitative)) > 0`, exact `InternalizationFile` keys; round-trips through `parseInternalizationFile` shape.
- [ ] **Step 2: FAIL → Step 3: Implement** `emit.py`; then `run.py`: resolve name/acc from the record, `build_prompt`, invoke agent (retry once on invalid schema), `normalize_output`, `emit_internalization_json`.
- [ ] **Step 4: PASS.**
- [ ] **Step 5: Live smoke** (manual, network) — run on TFRC; confirm `viewer/public/internalization/TFRC.json` is regenerated with real measurements and the §08 tab (Plan 3) renders them.
- [ ] **Step 6: Commit** — `feat(internalization-agent): emit-writer + runner`

---

## Self-Review

**Spec coverage:** §7.3 internalization retrieval (one row per measurement, ±ligand first-class, nulls preserved, qualitative separate) → Tasks 1–3; §5.2 data source for the §08 tab → Task 4; output matches `InternalizationFile` (consumed by Plan 3) → Task 3. ✓

**Placeholder scan:** retrieval + `call_builder` LLM invocation (Task 4) described not coded (same boundary as Plan 5); all deterministic surrounds are full TDD.

**Type consistency:** `build_prompt`, `validate_agent_output`, `normalize_output`, `emit_internalization_json` consistent; records match `viewer/lib/tag-sites-types.ts` `InternalizationMeasurement`/`InternalizationFile` and Plan 3's `parseInternalizationFile` guard.

**Dependency note:** the internalization benchmark ships a prompt but **no curated ground-truth set** (spec: "Scoring not yet implemented") — so there is no recall harness here (unlike tag sites). Fabrication control relies on the schema + the prompt's nulls-are-results discipline; add a curated internalization control set later to enable scoring.
