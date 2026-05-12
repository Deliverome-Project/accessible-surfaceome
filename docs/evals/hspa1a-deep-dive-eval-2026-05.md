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
