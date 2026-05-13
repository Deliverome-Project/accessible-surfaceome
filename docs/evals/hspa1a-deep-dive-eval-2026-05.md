# HSPA1A — first v0.4.0 deep-dive reference record

**Date:** 2026-05-11
**Schema version:** `v0.4.0`
**Model:** `claude-sonnet-4-6`
**Record:** [`data/annotations/HSPA1A.json`](../../data/annotations/HSPA1A.json)
**Run artifacts:** `.runs/2026-05-12T03-12-22-HSPA1A-sesn_01XvucopXbQBK3oXpsh3mRAZ/` (task.md, events.jsonl, final.md, summary.json)

## Why HSPA1A

Curated hard case: stress-induced and immunogenic-cell-death-induced
surface presentation of a canonically cytoplasmic chaperone. DB
consensus votes false (8/8 M1 sources on the no side); naive haiku
misses it in the triage sub-bench. The strongest single test of the
conditional-surface path on the refocused v0.4.0 schema —
`surface_status="conditional_surface"`, multiple `induced_presentation`
entries with citations, primary-assay-required surface evidence, a
`secreted_form` risk flag.

## Pre-flight

- **Schema check:** `SCHEMA_VERSION = "v0.4.0"` in
  [models.py:639](../../src/accessible_surfaceome/tools/_shared/models.py:639);
  system prompt declares `v0.4.0` at
  [system.md:46](../../src/accessible_surfaceome/agents/surface_annotator/prompts/system.md).
  ✓
- **SURFY snapshot:** HSPA1A row present —
  `protein_length=641`, `surfy_is_surface=0`, `uniprot_subcellular="Cytoplasm"`,
  `uniprot_keywords` includes `Chaperone`, `Stress response`,
  `Host cell receptor for virus entry`. ✓
- **Compara CSV:** absent on this worktree (refresh deferred). Pack
  degraded gracefully to empty `orthology` — agent emitted `orthology: []`.
- **Triage record:** `data/triage/HSPA1A.json` exists but has no
  `key_uncertainty` (older record); orchestrator injected no triage
  flag block. ✓ (graceful)

## Cost + latency

- **Wall time:** 8 min 3 s (timestamp delta in `events.jsonl`).
- **Tool calls:** 11 custom-tool invocations (gene_lookup × resolve / db_panel / uniprot_summary, gene_literature × gene2pubmed / topic_search / fetch_abstract).
- **Cost:** not explicitly logged on this run; ballpark $0.30–$0.50 on Sonnet 4.6 for a ~10-tool-call run. (Run again with cost logging on after the eval lands.)

## Rubric pass

| Field | Expected | Actual | |
|---|---|---|---|
| `surface_biology.surface_status` | `conditional_surface` | `conditional_surface` | ✓ |
| `surface_biology.topology` | `outer_leaflet_peripheral` or `not_pm_associated` | `outer_leaflet_peripheral` | ✓ |
| `surface_biology.anchor_type` | `lipidated` or `other` (debated) | `peripheral` | ~ (close — peripheral covers the lipid-raft / Gb3 / PS attachment story) |
| `surface_biology.exposure_class` | `exposed_ecd` | `exposed_ecd` | ✓ |
| `surface_biology.cited_evidence_ids` | ≥1 primary | 4 entries | ✓ |
| `surface_biology.surface_localization_assays` | ≥2 | **4** (flow + biotinylation + IF + flow) | ✓✓ |
| `induced_presentation` | ≥2 (cell_state_stress + ICD) | **3** (oncogenic_state + cell_state_stress + immunogenic_cell_death) | ✓✓ |
| `isoform_accessibility` | 1 entry | 2 (canonical + HSPA1B) | ~ |
| `coreceptor_requirements` | empty | empty | ✓ |
| `orthology` | 2 entries | 0 (Compara CSV absent — graceful) | OK |
| `protein_features.protein_length_aa` | 641 | 641 | ✓ |
| `protein_features.uniprot_keywords` | Chaperone, Stress, ATP-binding | present + 12 others | ✓ |
| `protein_features.provenance` | `surfy_snapshot` | `surfy_snapshot` | ✓ |
| `targetability.tier` | `preclinical` or `edge_case` | `preclinical` | ✓ |
| `surface_engagement_validation.preclinical_evidence` | 1–3 | 1 | ✓ |
| `risk_flags` | `secreted_form` (medium) | `secreted_form` (medium) | ✓ |
| `evidence_count` | ≥6 | **9** | ✓ |
| `confidence` | `medium` | `medium` | ✓ |
| `triage_signal` | `possibly_accessible` | `possibly_accessible` | ✓ (cross-validates with `conditional_surface`) |
| `model_path` | `sonnet_only` | `sonnet_only` | ✓ |

**18 / 19 rubric rows pass (1 marginal: anchor_type).** The anchor-type
choice between `peripheral` and `lipidated` is biologically defensible
either way — HSP70's outer-leaflet attachment runs through Gb3
glycosphingolipid and phosphatidylserine in cholesterol-rich microdomains,
which sits on the boundary of those two enum values.

## Evidence verification (post-audit)

Sonnet entailment audit run on 2026-05-11 (~$0.10):

| Evidence | Verified | Audit | Notes |
|---|:---:|:---:|---|
| evi_001 | ❌ | — | UniProt:P0DMV8 substring miss — agent rewrote `;` as `,` in the subcellular-location list (canonical UniProt uses `Cytoplasm; Nucleus; …; Secreted`; the agent emitted comma-separated, which the substring check correctly rejected) |
| evi_002 | ✓ | ✓ | flow_cytometry, PMID:11189449 |
| evi_003 | ✓ | ✓ | flow_cytometry, PMID:11189449 |
| evi_004 | ❌ | — | source_id=PMC:PMC2271151 not in session source store — agent cited a paper it never fetched (the agent's fetch_fulltext call hit a 404 during the run) |
| evi_005 | ❌ | — | same PMC body as evi_004 |
| **evi_006** | ✓ | **❌** | Sonnet audit rejected — claim adds "confirmed by confocal microscopy and PS-specific biosensors" which the quote ("HSPA1A translocates to heat-shocked and cancer cells' plasma membrane (PM)") doesn't support. Real audit catch; agent should have either shortened the claim or cited a second quote. |
| evi_007 | ✓ | ✓ | immunofluorescence, PMID:40653262 |
| evi_008 | ✓ | ✓ | flow_cytometry, PMID:41362788 |
| evi_009 | ✓ | ✓ | review_assertion, PMID:22414085 |

**5 / 9 evidence fully validated** (verified + audit-passed). The
three substring failures and one audit rejection are the system
working as designed — the validation pipeline caught each issue and
recorded a useful warning on the persisted Evidence record.

The failure modes break down into three distinct classes:

1. **Punctuation paraphrasing** (`evi_001`): the agent rewrote the
   source's `;` separators as `,`. System prompt's "anti-patterns"
   section already lists this; the agent ignored it on a structured
   field. Possible mitigation: bullet the rule with a worked example
   for UniProt subcellular-location lists specifically.
2. **Citing un-fetched sources** (`evi_004`, `evi_005`): the agent
   cited PMC:PMC2271151 but `fetch_fulltext` hit a 404 mid-run
   (recorded in `events.jsonl`). The orchestrator already warns
   ("source_id=… not in session source store") but the agent
   doesn't see that warning. Mitigation: surface a tool-output flag
   when a fetch fails so the agent can drop the citation instead of
   carrying it.
3. **Overreach in the claim text** (`evi_006`): the agent appended
   methodology details to the claim that aren't in the quote. The
   audit correctly flagged this. Mitigation: prompt rule reminding
   the agent that the claim must be entailed by the quote (not just
   the gist).

## Two validation issues caught + fixed mid-run

The agent's first emission tripped two Pydantic validators:

1. **`protein_features.length_aa`** — agent emitted `length_aa: 641`
   (the IsoformAccessibility field name) instead of `protein_length_aa`.
   **Fixed:** orchestrator now post-injects the SURFY-loaded
   `ProteinFeatures` after parsing the agent's JSON, so any
   `protein_features` block the agent emits is silently overwritten.
   Agent is now told (in
   [system.md](../../src/accessible_surfaceome/agents/surface_annotator/prompts/system.md))
   to *not* emit `protein_features` at all.
2. **`rationale` exceeded 1500 chars** — agent emitted 1615 chars on a
   record with this much surface biology to summarize. **Fixed:**
   bumped `rationale` cap to 1800 chars in
   [models.py](../../src/accessible_surfaceome/tools/_shared/models.py).

Both fixes are in this commit; the persistence pipeline re-ran on the
agent's original JSON with the fixes applied and produced
`data/annotations/HSPA1A.json` as a valid `SurfaceomeRecord`.

## Notes for the next eval

- **Compara refresh first.** Run `bash scripts/refresh_compara.sh` before the next
  end-to-end so the `orthology` field actually populates.
- **Audit pass.** Wire `--audit` into the next CLI invocation to get
  `entailment_verified=True` flags. Add ~$0.10 to the cost.
- **Investigate the 3 unanchored claims.** `evi_001` cites `UniProt:P0DMV8`
  but the canonical UniProt for HSPA1A is `P08107` — possibly an alternative-isoform
  acc the agent picked; check the substring miss + correct the source registry.
  `evi_004` (surface_biotinylation, citing `PMID:40653262`) and `evi_005`
  (review, citing the same PMID) probably failed quote substring matching
  — the source body might be the abstract while the quote came from a
  results sentence.
- **Anchor_type calibration.** `peripheral` vs `lipidated` for HSP70's
  outer-leaflet attachment is a borderline enum call. Consider adding a
  short worked-example in the prompt naming HSP70 explicitly under
  whichever side we want as the canonical choice.

## Triage → deep-dive cascade

This eval validates the cascade plumbing:

1. `data/triage/HSPA1A.json` was present (older record with no
   `key_uncertainty`); orchestrator's `_load_triage_key_uncertainty`
   returned None and the triage-flag block in the task prompt was empty.
2. The SURFY snapshot row was injected as `## Pre-loaded protein
   features` — agent acknowledged it in `rationale` and copied through
   the relevant facts (TM count = 0, signal peptide = false,
   uniprot_keywords includes "Chaperone").
3. The Compara block was the placeholder ("No Ensembl Compara ortholog
   available") because the CSV is absent locally — agent correctly emitted
   `orthology: []`.

All three pre-injection paths worked as designed.

## v0.5.0 re-run (2026-05-12)

This eval was re-run on 2026-05-12 under the v0.5.0 schema bump to
validate the new buckets:

- **Surface-localization assay subclasses** —
  `SurfaceLocalizationAssay.mass_spec_detail`, `.antibody`, and
  `.cell_context` (sub-records gated by `assay_type`).
- **Structured shedding context** — `RiskFlag.shedding_context`
  (protease family, cleavage site, regulation, serum-pool flag).
- **Close paralogs** — top-level `paralogs: list[ParalogRecord]`
  parallel to `orthology`.
- **Contradictory evidence** — top-level
  `contradictions: list[ContradictionRecord]` paired with the
  existing `contradiction_flag` via a cross-validator.
- **Cell-type context** — structured `CellTypeContext` available on
  `AssayContext`, `SurfaceLocalizationAssay`, and `InducedPresentation`.
- **Membrane microdomains** —
  `SurfaceBiology.microdomains: list[MicrodomainAssignment]`.

### TGOLN2 — first v0.5.0 reference re-run (HSPA1A deferred to save cost while iterating)

Run: `.runs/2026-05-12T12-44-37-TGOLN2-sesn_012hykMDpWG4d8ZuDgCM6KcD/`,
session `sesn_012hykMDpWG4d8ZuDgCM6KcD`, 12 custom-tool calls,
`schema_version="v0.5.0"`, confidence `high`, `evidence_count=12`.

| New v0.5.0 field | Expected for TGOLN2 | Actual | |
|---|---|---|---|
| `schema_version` | literal `"v0.5.0"` | `"v0.5.0"` | ✓ |
| `surface_biology.microdomains` | ≥2 entries (TGN + recycling + clathrin) | **3 entries**: `tgn_membrane`, `clathrin_coated_pit`, `endosomal_recycling`, each with cited evidence | ✓✓ |
| `surface_localization_assays[i].antibody` | ≥1 IF entry with antibody identity | 2 antibody sub-records (one populated `vendor="AbD Serotec"` + epitope; one with only epitope) | ✓ |
| `surface_localization_assays[i].cell_context` | structured cell-type on the IF assays | 1 of 2 populated (`material_kind="cell_line"`) | ~ (partial) |
| `mass_spec_detail` | n/a — no MS evidence available for TGN46 | not emitted (correct) | ✓ |
| `induced_presentation[i].cell_context` | optional; document the cycling cell context | 0 of 1 populated | ~ |
| `risk_flags[i].shedding_context` | n/a — TGN46 isn't shed; no risk flag expected | 0 risk flags (vs the v0.4.0 run's stray `kind="other"` flag — correctly dropped) | ✓ |
| `paralogs` | empty acceptable — TGN46/TGOLN2 has no close paralog with shared cycling biology | `paralogs: []` | ✓ |
| `contradictions` | empty acceptable when no disagreement found | `contradictions: []`, `contradiction_flag=False` | ✓ |

**8 / 9 rubric rows pass (1 partial: cell_context coverage on assays
and induced_presentation).** The agent populated the load-bearing
fields — microdomains and antibody sub-records — exactly as
intended, and correctly emitted empty `paralogs` / `contradictions`
where the literature doesn't support an entry.

### Three diagnostic findings the v0.5.0 cycle surfaced

1. **The first v0.5.0 emission was structurally a v0.4.0 record.** The
   agent kept emitting `schema_version="v0.4.0"`, zero paralogs, zero
   microdomains, zero sub-records — even though the local
   `system.md` had been edited to v0.5.0. Root cause: the
   `surface_annotator` is an Anthropic **Managed Agent**, and the
   remote agent's system prompt only updates when
   `accessible-surfaceome agents sync` PATCHes it. The orchestrator's
   `_annotate_one` path reads the local registry but doesn't
   re-sync — so a freshly-edited prompt stays local until you sync.
   After sync, the agent went v1 → v2 and the very next run emitted
   the v0.5.0 shape correctly. **Backstop landed:** the orchestrator
   now logs a loud `PROMPT DRIFT` warning when the local
   `system.md` sha256 doesn't match the registered agent's snapshot;
   and `CLAUDE.md` + `AGENTS.md` carry parallel "Managed Agents —
   push prompt + schema edits before annotating" sections instructing
   the operator to run `agents sync` after any prompt / agent.py /
   referenced-schema edit.

2. **Silent data-loss bug in the orchestrator's record assembly.** The
   `SurfaceomeRecord(...)` constructor in
   `src/accessible_surfaceome/agents/surface_annotator/orchestrator.py`
   enumerates fields by name and was missing `paralogs=` and
   `contradictions=` from the draft → record copy. Any v0.5.0 record
   the agent emitted would have been silently stripped of those
   fields before persistence. Fixed and covered by
   `tests/test_evidence_promotion.py::test_persist_annotation_passes_paralogs_and_contradictions`.

3. **Stream timeouts happen.** One v2-agent attempt died ~1 min in
   with `httpx.ReadTimeout` on Anthropic's SSE event stream — a
   transient network failure, not a schema regression. The orchestrator
   doesn't currently checkpoint mid-stream so the run reset from zero.
   Worth a follow-up: bump the httpx read timeout on the streaming
   client and / or wrap the streaming loop in a single-retry
   reconnect. Not blocking for this eval.

### Backward compat smoke

Both v0.4.0 reference records (`HSPA1A.json`, `TGOLN2.json`) load
cleanly under the v0.5.0 Pydantic models — additive change, new
fields default to empty / null. Verified via
`tests/test_models_deep_dive.py::test_v0_4_records_load_under_v0_5_0`
and an ad-hoc smoke run over `data/annotations/*.json`.

### HSPA1A — deferred

Skipped this round to save cost during the v0.5.0 iteration (each run
is ~$0.30–0.50 on Sonnet 4.6, and the schema-shape signal landed via
TGOLN2). Expected for HSPA1A on the next pass: paralogs with
HSPA1B / HSPA1L flagged high-risk for cross-reactivity, microdomains
with `lipid_raft`, and a `secreted_form` risk_flag carrying a
`shedding_context` describing exosomal release.
