# Tagged Sites — Plan 5: Literature tag-site agent (production sourcing)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the agentic tag-site prompt into a runnable **production** pipeline that, given a gene + the **computed sequence and topology**, retrieves literature and emits `literature_retrieved` `TaggedSite` records into `viewer/public/tag-sites/{SYMBOL}.json` — with every site's residue junction mechanically verified against the sequence, and recall measured against the 23 curated controls.

**Architecture:** A pipeline under `src/accessible_surfaceome/agents/tag_site/` with two **run modes** (spec §9): `benchmark` (gene + name only — scores the retrieval skill) and `production` (gene + name + computed `sequence`/`per_residue_topology` — sources display data and pins exact residues). The LLM/retrieval step (bio-research MCP: PubMed/bioRxiv/Consensus + web) is not unit-testable; everything around it is: prompt assembly, output-schema validation, residue-junction verification (reuse Python parity of `verifyJunction`), EC classification, and the recall scorer. Emits via Plan 4's `emit_tag_sites_json` merge-writer (so literature + deterministic coexist per gene).

**Tech Stack:** Python 3, pytest, the repo's agent framework (`src/accessible_surfaceome/agents/`), bio-research MCP tools, jsonschema.

**Parent spec:** §7.1, §8, §9 · **Depends on:** Plan 1 (schema), Plan 4 (Task 1 `tagged_site` builder, Task 5 emit-writer, Task 6 controls fixture + scorer). Best sequenced after Plan 4.

---

### Task 1: Output JSON schema + validator

**Files:**
- Create: `src/accessible_surfaceome/agents/tag_site/schema.py` (jsonschema for the agent's raw output — the prompt's JSON block)
- Create: `src/accessible_surfaceome/agents/tag_site/validate.py` (`validate_agent_output(obj) -> (ok, errors)`)
- Test: `tests/test_tag_site_agent_schema.py`

- [ ] **Step 1: Failing test** — a well-formed agent output (matching the prompt's `sites[]` schema: `rank`, `site_type`, `insert_after_residue`, `residue_before/after`, `topology_state`, `tag_type`, `evidence_type`, `functional_or_expression_impact_measured`, `confidence`) validates; a missing `insert_after_residue` fails; an unknown `evidence_type` fails.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** the jsonschema mirroring the prompt's Output format (the `evidence_type` enum verbatim from the prompt), and `validate_agent_output`.
- [ ] **Step 4: Run → PASS.** — [ ] **Step 5: Commit** — `feat(tag-site-agent): output schema + validator`

---

### Task 2: Prompt assembly (benchmark vs production run modes)

**Files:**
- Create: `src/accessible_surfaceome/agents/tag_site/prompt.py` (`build_prompt(gene, protein_name, *, mode, sequence=None, topology=None)`)
- Create: `src/accessible_surfaceome/agents/tag_site/prompt_body.md` (the agentic prompt, ported from `deliverome-internal/data/analysis/agentic_tag_site_benchmark/prompt.md`)
- Test: `tests/test_tag_site_prompt.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_tag_site_prompt.py
from src.accessible_surfaceome.agents.tag_site.prompt import build_prompt

def test_benchmark_mode_excludes_sequence():
    p = build_prompt("AXL", "AXL receptor tyrosine kinase", mode="benchmark")
    assert "AXL" in p and "P30530" not in p  # only symbol+name
    assert "COMPUTED SEQUENCE" not in p

def test_production_mode_injects_sequence_and_topology():
    p = build_prompt("AXL", "AXL receptor tyrosine kinase", mode="production",
                     sequence="MABC...", topology="SSOOO...")
    assert "COMPUTED SEQUENCE" in p and "MABC" in p
    assert "COMPUTED TOPOLOGY" in p and "SSOOO" in p

def test_production_requires_sequence():
    import pytest
    with pytest.raises(ValueError):
        build_prompt("AXL", "AXL", mode="production")  # sequence/topology missing
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** `build_prompt`: load `prompt_body.md`; in `production` mode append a clearly-delimited `## COMPUTED SEQUENCE` / `## COMPUTED TOPOLOGY` block and instruct the agent to (a) name exact `insert_after_residue` and (b) copy `residue_before/after` from the provided sequence (so they're verifiable); raise `ValueError` if `production` and sequence/topology are missing. Keep `benchmark` mode verbatim symbol+name only.
- [ ] **Step 4: Run → PASS.** — [ ] **Step 5: Commit** — `feat(tag-site-agent): benchmark/production prompt assembly`

---

### Task 3: Normalize agent output → verified TaggedSite records

**Files:**
- Create: `src/accessible_surfaceome/agents/tag_site/normalize.py`
- Test: `tests/test_tag_site_normalize.py`

- [ ] **Step 1: Failing test** — `normalize_output(agent_obj, gene, acc, sequence, topology)`:
  - maps each agent `site` to a `TaggedSite` with `provenance="literature_retrieved"`, `det_path=None`;
  - **drops any site whose `residue_before/after` mismatches the sequence** at `insert_after_residue` (the anti-fabrication gate), returning the drop count;
  - derives `compartment`/`extracellular` from topology (parity with `deriveCompartment`);
  - maps `site_type` → `site_kind` (`terminal_n`/`terminal_c`/`internal`).
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** `normalize.py` (residue verification identical in spirit to `viewer/lib/tag-sites-derive.ts:verifyJunction`; reuse `tagged_site`-style dict construction with `provenance="literature_retrieved"`).
- [ ] **Step 4: Run → PASS.** — [ ] **Step 5: Commit** — `feat(tag-site-agent): normalize + verify agent output to TaggedSite`

---

### Task 4: Runner (production) + recall harness (benchmark)

**Files:**
- Create: `src/accessible_surfaceome/agents/tag_site/run.py` (CLI)
- Test: `tests/test_tag_site_recall.py`

- [ ] **Step 1:** Implement `run.py`: for each gene, resolve name/acc/sequence/topology from the `SurfaceomeRecord`; `build_prompt(mode="production")`; invoke the agent (repo agent framework + bio-research MCP), retry once on schema-invalid output; `normalize_output`; `emit_tag_sites_json` (Plan 4 Task 5). A `--benchmark` mode runs `mode="benchmark"` and scores against `tests/fixtures/positive_controls.tsv` using the Plan 4 Task 6 scorer (site recall, residue-exactness ±k, EC agreement, **fabrication rate** = normalized sites dropped for residue mismatch / proposed).
- [ ] **Step 2: Test the scorer wiring** — `test_recall_scorer_counts_hits`: feed a synthetic agent output + a synthetic control row and assert the scorer reports the expected recall / fabrication numbers (pure function; no live agent).
- [ ] **Step 3: Run → PASS.**
- [ ] **Step 4: Live smoke** (manual, network) — run production mode on TFRC; confirm `viewer/public/tag-sites/TFRC.json` now carries agent-sourced `literature_retrieved` sites merged with the deterministic ones; residues verify. Record recall from `--benchmark` on the 18 control proteins in the PR.
- [ ] **Step 5: Commit** — `feat(tag-site-agent): production runner + control recall/fabrication harness`

---

## Self-Review

**Spec coverage:** §7.1 production agent grounded on computed sequence+topology → Tasks 2, 3, 4; §9 benchmark vs production run modes → Task 2; §8 validation (recall, residue-exactness, EC agreement, fabrication rate) → Task 4; anti-fabrication residue gate → Task 3; merge with deterministic sites → Task 4 (reuses Plan 4 emit). ✓

**Placeholder scan:** the LLM/MCP invocation in Task 4 Step 1 is described, not coded, because it is inherently non-deterministic and platform-specific (repo agent framework) — every deterministic surround (schema, prompt assembly, normalization/verification, scoring) is full TDD. This is the appropriate boundary.

**Type consistency:** `build_prompt`, `validate_agent_output`, `normalize_output`, `emit_tag_sites_json` used consistently; output records match `viewer/lib/tag-sites-types.ts` (`provenance="literature_retrieved"`, `det_path=None`).

**Dependency note:** MCP-authenticated retrieval (PubMed/bioRxiv/Consensus) must be available in the run environment; headless/cron runs without those connectors will produce empty results (fail loudly, don't fabricate).
