# Internalization evidence — design spec

**Date:** 2026-08-04
**Status:** Approved design, pre-implementation
**Scope:** Add structured protein-internalization evidence to the surfaceome
pipeline and viewer, as a standalone pass decoupled from the v2 deep-dive.

---

## 1. Motivation

Internalization (receptor-mediated endocytosis / turnover) is the property
that decides whether a surface-accessible protein can *deliver a payload*
inside the cell — the central question for ADCs, degrader-antibody handles,
and receptor-mediated LNP/BBB delivery. Today the surfaceome record captures
internalization only as scattered free prose inside `accessibility_modulation`
and `subcellular_localization` (e.g. EGFR's "EGF-induced internalization
transiently reduces surface pool"). There is no grade, no assay/cell-line/
ligand structure, no quantitative rate, and nothing filterable or comparable
across genes.

`deliverome-internal` already prototyped two of the needed pieces separately —
a categorical agentic grade (`InternalizationAssessment`: axis classifier +
confidence + rationale + web sources) and a quantitative k_e table (HER2 ADC,
per cell-line × treatment) — plus a canonical delivery positive-controls
registry (`controls.json`). This spec unifies those into one structured,
PMID-anchored record and surfaces it on the gene page.

## 2. Goals / non-goals

**Goals**
- A structured, per-gene internalization record capturing: high/low grade,
  quantitative rate (when reported), assay type, cell line, cell context
  (primary vs. line), internalization mode (basal / native-ligand /
  therapeutic), mechanism, and differences across conditions/cells.
- **Two independent grading tracks:** (1) PMID-anchored literature; (2) a
  frontier-model *parametric-knowledge* grade from sequence + topology, run
  with **both Opus and Sonnet**, per isoform.
- Merge into the viewer as a side card and per-gene markdown export.
- A small hand-picked control set spanning low→high internalization for
  development + a recall sanity-check.

**Non-goals (v1)**
- No catalog-wide filter facet yet (gene-page card only; facet is a later
  follow-up once coverage across the canonical set is high).
- No whole-cohort coverage — canonical deep-dive genes only (~2,243).
- No formal scored benchmark / precision-recall harness — recall
  sanity-check only.
- No web-search / patent sources — PMID-anchored literature only.
- **No changes to the deep-dive `SurfaceomeRecord`** — the internalization
  record is a separate artifact in its own D1 table with its own
  `schema_version`.

## 3. Architecture & data flow

A standalone pass, fully decoupled from the v2 deep-dive, following the same
*separate-storage + Worker-enriches* pattern the deterministic features use:

```
scripts/internalization_annotate.py   (--symbol X | --canonical | --limit N | --no-publish)
  → agents/internalization/ runner
      Track 1: PMID-anchored literature pass
      Track 2: model-prior pass (Opus + Sonnet, sequence + topology, per isoform)
  → validate Pydantic record  (before any D1 write)
  → cloud/internalization_annotation.publish_record
      → private D1  internalization_annotation
      → public  D1  internalization_annotation_public  (column-whitelisted mirror)
      → targeted edge-cache purge (/v1/genes/{SYMBOL})
  → Worker /v1/genes/{SYMBOL}  LEFT JOINs the public row → adds `internalization` to the gene payload
      → viewer InternalizationCard renders it (only when present)
      → per-gene .md export gets a `## Internalization` section
```

**Why a separate D1 table** (rather than merging into
`surface_annotation.annotation_json`): keeps the two passes independent (a
deep-dive re-run cannot clobber internalization and vice-versa); gives the
internalization record its own `schema_version`; matches the "separate pass /
side block" decision. The Worker folds it into the existing gene response via
LEFT JOIN, so the viewer still does a single fetch — the same enrichment
mechanism already used for deterministic features (see the
`deterministic-features-dual-pattern` memory).

**Cohort selector.** The pass targets the canonical set defined by
`passes_canonical` in
[`src/accessible_surfaceome/release/catalog_presets.py`](../../../src/accessible_surfaceome/release/catalog_presets.py)
(mirror: [`viewer/lib/catalog-presets.ts`](../../../viewer/lib/catalog-presets.ts)),
~2,243 genes after PR #130. Reference the predicate, not a frozen list, so the
cohort tracks the definition. `--canonical` batches over it; `--symbol`
handles one gene; `--limit N` caps for testing.

## 4. The internalization record

One `internalization_annotation` row per gene. Own `schema_version` (start at
`0.1.0`). New Pydantic models live in a dedicated module
(`src/accessible_surfaceome/agents/internalization/models.py`) or beside the
shared models — TBD during implementation; they do **not** extend
`SurfaceomeRecord`.

### 4.1 Top level

```
InternalizationRecord
  schema_version: str
  gene: GeneIdentifier            # reuse existing
  literature: LiteratureTrack
  model_priors: list[ModelPriorTrack]   # one per model (opus, sonnet)
  provenance: {generated_at, runner_version, prompt_sha, cohort_run_id?}
```

### 4.2 Track 1 — literature (PMID-anchored)

```
LiteratureTrack
  grades_by_mode: {
    basal:         ModeGrade
    native_ligand: ModeGrade
    therapeutic:   ModeGrade
  }                              # ModeGrade = {grade, confidence, rationale, cited_source_ids}
  overall_grade:      high | low | no | unknown
  overall_confidence: high | moderate | low
  rationale: str                 # strongest evidence + biggest caveat (prose, PMID-linkable)
  cross_condition_note: str      # differences across conditions/cells
  species_scope: Species         # human-first; non-human downgrades confidence
  species_inferred: bool
  observations: list[InternalizationObservation]
  sources: list[InternalizationSource]
  n_observations: int
```

`InternalizationObservation` — one row per measured condition:

```
  assay_type: enum + assay_type_other_label
    antibody_uptake · ligand_uptake · adc_internalization · radioligand_immunopet
    · ph_sensitive_dye · acid_strip_flow · surface_biotinylation · live_imaging
    · receptor_recycling · endocytosis_inhibitor · other · unknown
  cell_line: str | None                        # e.g. "SK-BR-3"
  cell_context: primary | cell_line | tumor_cell_line | ipsc_or_stem | in_vivo | other | unknown
  internalization_mode: basal | native_ligand | therapeutic | unknown
  ligand_name: str | None
  mechanism: clathrin | caveolin | macropinocytosis | clathrin_independent
             | receptor_mediated_unspecified | other | unknown | None
  magnitude: high | moderate | low | none | unknown
  quant:                                        # hybrid — numeric when normalizable, prose otherwise
    rate_metric: ke_h_inv | percent_internalized | half_life | fold_change | other | None
    rate_value: float | None
    rate_unit: str | None
    time_point: str | None
    quant_summary: str                          # always present; prose fallback
  controls_note: str | None                     # assay controls used: acid-strip, 4°C surface-only,
                                                #   permeabilization, endocytosis inhibitor, etc.
  condition_note: str
  cited_source_ids: list[str]
```

`InternalizationSource` — self-contained sub-ledger, reusing the existing
`SourceRef` / `EvidenceSpan` shapes from
[`models.py`](../../../src/accessible_surfaceome/tools/_shared/models.py):
PMID + verbatim quote + section + `char_offset` + `quote_sha256`. Every
observation cites by `source_id` → natively satisfies the viewer's PMID+link
rule. Span verification (substring-anchored) mirrors the deep-dive's
`EvidenceClaim → Evidence` promotion.

### 4.3 Track 2 — model priors (parametric knowledge, NO PMIDs)

For each model (Opus, Sonnet), feed the amino-acid **sequence + topology of
the canonical isoform and each alternative isoform** and ask for a grade from
the model's own knowledge — no literature retrieval.

```
ModelPriorTrack
  model: str                     # e.g. "claude-opus-…", "claude-sonnet-…"
  scope: "intrinsic_propensity"  # fixed — see honesty guardrails below
  overall_grade:      high | low | no | unknown
  overall_confidence: high | moderate | low
  per_isoform: list[{
    isoform_id: str
    is_canonical: bool
    length_aa: int
    topology_summary: str        # TM count, N/C-term sidedness, cytoplasmic-tail presence
    endocytic_motifs_noted: str | None   # YXXΦ / dileucine / NPXY etc. the model flags
    grade: high | low | no | unknown
    confidence: high | moderate | low
    rationale: str
  }]
  model_reasoning: str
```

**Honesty guardrails (load-bearing):**
1. **Scoped to intrinsic/basal endocytic propensity** (± native-ligand
   potential). A model cannot know *therapeutic* internalization from sequence
   — it depends on an external binder — so this track never emits a
   therapeutic grade. The prompt states this explicitly.
2. **No PMIDs; rendered visually distinct** from Track 1 (a "model estimate —
   not citation-backed" badge + tooltip) so it is never mistaken for evidence.
   Where literature is `unknown`, the prior still gives a defensible estimate;
   literature-vs-prior and Opus-vs-Sonnet agreement are themselves signals.

**Input sourcing.** Isoform *sequences* and topology are **not** in the
surfaceome record (`IsoformRecord` carries only id/name/canonical/length).
Fetch them from UniProt via the resolved `uniprot_acc` — the
`gene_lookup(mode="uniprot_summary")` path already returns
`topology_features` + `isoforms`; extend/adjacent-fetch to obtain per-isoform
FASTA. Confirm the exact fetch path during implementation; sequence is
required, topology attached when available (else `topology_summary` notes it
is absent and the model reasons from sequence alone).

## 5. The pass (`src/accessible_surfaceome/agents/internalization/`)

In-process `messages.create` with structured output (same style as v2
builders). Per gene:

1. Resolve identifiers via `resolve_by_hgnc_id` / the `gene_identifier` table
   (stable-ID rule — never key off the bare symbol).
2. **Track 1 (literature):**
   a. Build an internalization-targeted query set: alias OR-set ×
      {internalization, endocytosis, receptor uptake, antibody/ADC
      internalization, k_e, recycling}.
   b. **Reuse existing discovery + body-fetch infra** — the EuropePMC +
      PubTator union and the `abstract_triage` PMC-JATS → Unpaywall-PDF fetch
      chain from `plan_trim_select`. Light refactor to expose the reusable
      helpers (probably under `agents/_support/`); do not fork them.
   c. Triage abstracts for internalization relevance → fetch bodies → extract
      observations with span-anchored quotes → grade per mode.
3. **Track 2 (model priors):** fetch canonical + isoform sequences/topology →
   one call per model (Opus, Sonnet) → per-isoform + overall grade.
4. Assemble `InternalizationRecord` → **validate the Pydantic model before any
   D1 write** (per the `validate-records-before-d1-write` rule) → publish.

- **Entry:** `scripts/internalization_annotate.py` (`--symbol`, `--canonical`,
  `--limit`, `--no-publish`).
- **Publisher:** `cloud/internalization_annotation.py::publish_record`, a
  mirror of
  [`cloud/surface_annotation.publish_record`](../../../src/accessible_surfaceome/cloud/surface_annotation.py:730)
  → private + public D1 + targeted edge-cache purge. Auto-skips the D1 push
  with a warning (not an error) when `CLOUDFLARE_*` env vars are absent, so CI
  without secrets still runs.
- **`$0` probe:** a discovery/fetch probe (no model calls), analogous to
  `scripts/probe_triage_fetch.py`, to validate the literature retrieval before
  spending tokens.

## 6. Storage — D1

- `internalization_annotation` (private) + `internalization_annotation_public`
  (column-whitelisted mirror). Schema added to
  [`cloudflare/d1_schema.sql`](../../../cloudflare/d1_schema.sql) +
  [`cloudflare/d1_public_schema.sql`](../../../cloudflare/d1_public_schema.sql).
  Columns: `gene_symbol`, `hgnc_id`, `schema_version`, `internalization_json`,
  denormalized rollups for cheap indexing (`overall_grade`, `therapeutic_grade`,
  `basal_grade`, `native_ligand_grade`, `model_prior_opus_grade`,
  `model_prior_sonnet_grade`), `generated_at`, `runner_version`, `prompt_sha`.
  Idempotent UPSERT on `(gene_symbol, schema_version)`.
- Apply DDL one statement at a time via `D1Client.query()` (HTTP API doesn't
  batch multi-statements) — the CLAUDE.md pattern.

## 7. Worker + viewer + markdown

- **Worker** (`cloudflare/workers/surfaceome_api/`): `/v1/genes/{SYMBOL}` LEFT
  JOINs `internalization_annotation_public` and adds an `internalization` key
  to the gene payload (null when absent). Edge-cacheable like the other GETs.
- **Viewer types** (`viewer/lib/surfaceome-types.ts`): add
  `internalization?: Internalization | null` (TS mirror of the Pydantic model,
  both tracks).
- **Card** (`viewer/components/surfaceome/InternalizationCard/`): modeled on
  `AccessibilityRisksCard`. `SectionCard` wrapper → Track-1 subsections
  (grades-by-mode pills, then per-observation rows with `StatusPill` +
  `ChipLabelValue` for assay/cell-context/mode/magnitude, `EvidenceChipList`
  for cites, `linkifyEvidenceRefs` on prose) → Track-2 block with the
  Opus/Sonnet per-isoform grades under a clearly-labeled "model estimate — not
  citation-backed" badge. Spread into `GeneDetail`'s `sections` array **only
  when `rec.internalization` is present**.
- **Markdown export** (`viewer/scripts/build-markdown-exports.mjs`): add a
  `## Internalization` section (literature grades-by-mode + observations +
  model-prior grades + a `**Definitions.**` line). The api-source build path
  picks up the block automatically via the Worker JOIN.
- **Tooltips** (`viewer/lib/tooltips.tsx`, PMIDs in `viewer/lib/citations.ts`):
  define the assay-type taxonomy, the grade rubric, k_e (h⁻¹), and the
  model-prior disclaimer. Every threshold/definition tooltip cites a PMID +
  link per the viewer citation rule.

## 8. Controls

Development/tuning starts with a hand-picked **6-gene set spanning low→high**
(chosen to test *specificity*, not just recall — a known non-internalizer is
included):

| Gene | Expected grade | Primary mode | Rationale |
|---|---|---|---|
| TFRC (CD71) | high | basal + native (transferrin) | Textbook rapid constitutive recycler; RMT-delivery gold standard |
| EGFR | high | native ligand (EGF) | Robust ligand-induced endocytosis; low basal — mode-contrast to TFRC |
| ERBB2 / HER2 | medium | therapeutic (T-DM1) | Modest, slow, recycling internalizer — payload delivery works despite it |
| FOLR1 | medium | native + therapeutic | Folate/antibody-driven endocytosis (mirvetuximab); moderate rate |
| ENPP3 | medium (sparse lit.) | therapeutic (AGS-16C3F) | Real ADC target with thin literature — tests graceful degradation + the model-prior track |
| MS4A1 / CD20 | low | — (non-internalizing) | Canonical non-internalizer; rituximab is ADCC/CDC, not payload uptake — deliberate negative control |

Exact representative PMIDs are pinned during curation (not yet hand-verified).
`scripts/internalization_controls_report.py` runs the pass over this set and
reports per-gene predicted-vs-expected + (later, over the full `controls.json`
port) recall = fraction of known internalizers graded `high`.

Later expansion: port
`deliverome-internal/.../canonical_delivery_positive_controls/controls.json`
(~76 approved/clinical/preclinical ADC · BBB-RMT · kidney targets — needs LFS
hydration) into `data/eval/internalization_controls.tsv` with stable IDs.

## 9. Testing & quality gates

- New literature + model-prior prompts are **gene-agnostic** → must pass
  `tests/test_prompts_no_gene_names.py` + `tests/test_prompt_no_specific_proteins.py`.
  Wire the new prompt directory into the scanners.
- Extend `scripts/gen_prompt_review.py` to render the new prompts + their new
  closed enums (same-commit regen rule).
- Pydantic schema-drift test for `InternalizationRecord`; validate before
  every D1 write.
- Worker JOIN coverage; viewer build green; `bash scripts/check-py.sh` +
  `uv run ty check` green.
- `$0` probe run over the 6 controls before any cohort sweep.

## 10. Open items to resolve during implementation

- Exact UniProt per-isoform FASTA + topology fetch path for Track 2.
- Module home for the new Pydantic models (dedicated module vs. shared
  `models.py`).
- Whether `gen_prompt_review` / the leak-test scanners already glob the new
  prompt dir or need an explicit include.
- Denormalized D1 rollup column list final shape (for the eventual catalog
  facet).

## 11. Rollout order

1. Pydantic models + schema-drift test.
2. Literature pass (Track 1) + `$0` probe, validated on the 6 controls.
3. Model-prior pass (Track 2, Opus + Sonnet).
4. Publisher + D1 tables + Worker JOIN.
5. Viewer card + types + markdown export + tooltips.
6. Controls report; then `--canonical` sweep.
7. Prompt-review regen + leak tests + full check-py + pre-commit.
