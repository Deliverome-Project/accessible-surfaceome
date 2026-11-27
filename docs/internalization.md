# Internalization Pipeline (`schema_version 0.3.0`)

Standalone two-track annotation pipeline measuring how readily human cell-surface proteins internalize from the plasma membrane, covering the **3,213-gene internalization cohort** (`L1 ∪ Canonical ∪ Likely`; frozen manifest at `data/processed/internalization/cohort_l1_canonical_likely_2026-11-26.tsv`).

## Track hierarchy

1. **Literature track (primary — catalog column & top of gene Internalization tab)**
   PMID/DOI-anchored, span-verified experimental evidence graded by mode. Drives the catalog's `Intern · lit` column (`intern_lit_grade`) and filter group.
2. **Sequence prior (secondary — gene Internalization tab below Literature)**
   Blind model estimate of intrinsic/basal endocytic propensity from amino-acid sequence and DeepTMHMM E/C topology alone (`very_high` → `very_low` | `unknown`), noting cytoplasmic sorting motifs (`YXXΦ`, `NPXY`, dileucine, acidic clusters). Omitted from the catalog table because observed literature evidence is preferred when ranking targets.

## Literature pipeline architecture

Implemented under `src/accessible_surfaceome/agents/internalization/` (`LIT_PROMPT_VERSION = "0.2.2"`):

1. **Deterministic discovery (`literature_discovery.py`):**
   - UniProt-cached protein names, HGNC aliases, CD designations, and trailing-number stem fallbacks (with disease-alias filtering).
   - Five EuropePMC REST queries (broad internalization, measurement/delivery/negative terms, citation-sorted kinetics, citation-sorted classics, and a `$0` `SRC:PPR` bioRxiv/medRxiv preprint pass) plus PubTator3 entity search.
   - Fail-loud guard: raises a retryable error if `>= 3/5` EuropePMC queries fail rather than publishing a degraded PubTator-only record.
2. **Abstract triage (`literature_triage.py` — `claude-haiku-5-5`, thinking disabled):**
   - Classifies every discovered abstract (`worth_fetching`, `abstract_only`, `modulator_only`, `irrelevant`), separating cross-gene perturbation papers from direct measurements of the target protein.
   - Adaptive web scout (`claude-haiku-5-5` with `web_search`) runs when deterministic discovery yields thin evidence, with a 30-day disk cache.
3. **Full-text retrieval + paper selection (`literature_select.py` — `claude-sonnet-5-5`):**
   - Ranks candidate papers by mode coverage, quantitative kinetics, primary/in vivo context, and `citedByCount`.
   - Fetches NCBI PMC `efetch` XML (primary) → EuropePMC `fullTextXML` (fallback) → Unpaywall / DataCite / bioRxiv OA PDFs.
   - Tracks `missed_preprint_body` when bioRxiv returns HTTP `429` on cloud IPs so blocked preprints can be rescued locally.
4. **Evidence-grounded grading (`literature_grade.py` — `claude-sonnet-5-5`):**
   - Extracts structured `InternalizationObservation` rows (`assay_type`, `internalization_mode`, `species`, `cell_line`, `expression_context`, `binder_type`, `binder_valency`, `mechanism`, `post_uptake_fate`, `magnitude`, `quant`, verbatim quote spans verified against the fetched text).
   - Emits per-mode grades (`basal`, `native_ligand`, `therapeutic`, `pathogen_entry`) on `high | moderate | low | no | unknown`, rolled up to `overall_grade` + `overall_confidence`, plus `predominant_fate`, `ligand_dependence_summary`, `epitope_or_valency_dependence_note`, and separate `modulator_observations`.

### Kinetics normalization rules (`schema_version 0.3.0`)

- **Continuous kinetic fits (`derived_ke_min_inv`, `derived_t_half_min`):** populated from direct `k_int` / `t_half` measurements or exact linear continuous conversions (`percent_per_min` → $X / 100\;\text{min}^{-1}$; `percent_per_hour` → $X / 6000\;\text{min}^{-1}$), with `derived_kinetics_basis` recording the derivation and an `in_vivo` PK-fit guard preventing systemic plasma half-lives from being conflated with cellular $k_e$.
- **Single-endpoint uptake (`apparent_t_half_min`):** strictly separated from fitted `derived_t_half_min` and computed only for single-timepoint `percent_internalized` measurements at $\le 4\;\text{h}$ (`1 - f = \exp(-k_{\text{app}} t)`).

## Durability, incremental updates & operations

- **3-way persistence:**
  1. Public D1 `surface_internalization` via read-back-merge (preserves `model_priors` when updating `literature`; prompt-SHA dedup on `lit_prompt_sha` makes resume automatic).
  2. Cloudflare R2 `r2://deliverome-d1-backups/internalization_lit_intermediates/{GENE}/latest.json.gz` (+ `{run_id}.json.gz`) storing discovery, Haiku triage verdicts, clips, and the embedded final record for `--from-r2 --skip-discovery` incremental runs and local bioRxiv rescue.
  3. Per-run JSONL ledger under `data/runs/internalization_lit/{run_id}/ledger.jsonl`.
- **Commands:**
  - Modal sweep: `uv run --extra modal modal run modal/internalization_lit_app.py::full_sweep --execute --max-budget-usd 3000 --wave-size 150`
  - Local bioRxiv rescue (reusing R2 discovery + triage): `uv run python scripts/internalization_lit_sweep.py --genes-file <missed_preprint_genes.txt> --from-r2 --skip-discovery --force --execute`
  - Refresh citation bibliography metadata in D1: `uv run python scripts/build/build_paper_metadata_table.py --internalization-only --execute`
  - 24-gene benchmark scorer: `uv run python scripts/benchmark_internalization_lit.py` (`data/eval/internalization_benchmark_v1.tsv`).

## API & Viewer surface

- `GET /v1/catalog` (`row_schema` 12+): exposes `intern_lit_grade` (literature overall grade, displayed as the `Intern · lit` catalog column), `intl` (slim scalar projection `{ conf, basal, native, therapeutic, pathogen, fate, primary, quant, fitted, binders[], mechs[] }` backing the deeper Internalization catalog filter group), `intern_lit` (`1` when literature exists), and `intern` (sequence-prior canonical grade).
- `GET /v1/internalization/{SYMBOL}`: returns the full `InternalizationRecord` (`literature`, `model_priors`, and joined `papers` metadata keyed by `source_id`), or `null` outside the cohort.
- Viewer gene page (`Internalization` tab): renders **Literature** first (overall grade, confidence, fate, primary/in vivo badge, fastest fitted `t½`, trafficking/ligand/valency summaries, per-mode cards, filterable & sortable observations table with binder/valency/system/fate/kinetics and clickable evidence drawer chips, cross-gene modulators) followed by **Sequence prior** below.
