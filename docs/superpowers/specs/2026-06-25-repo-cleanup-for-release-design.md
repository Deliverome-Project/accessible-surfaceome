# Repo cleanup for v0 public release — design

**Date:** 2026-06-25
**Author:** Becca Carlson (with Claude Code)
**Target branch:** `claude/quizzical-darwin-8923eb` → `main`
**Deliverable:** one PR titled `chore: repo cleanup for v0 release`

## Goal

Prepare `accessible-surfaceome` for public open-source release as both:

1. A **paper companion** — a scientist landing on the README from a manuscript can get the data, reproduce a figure, or run a sweep without fighting layout.
2. A **reusable codebase** — a contributor can find the right script in seconds and trust that everything in `scripts/` is current.

Constraints:

- **Light reorganization only.** Don't restructure `src/`; group `scripts/` into subdirs, leave everything else where it is.
- **Moderate deletion, verified.** Every deletion candidate has been cross-checked by a subagent against `scripts/`, `src/`, `tests/`, `data/analysis/figures/`, `viewer/lib/`, `cloudflare/`, root `*.md`. Two conflicts between agents were resolved in favor of "keep" (`paywall_bot_block_compare.py`, `candidate_universe_v2.tsv`).
- **CI green at every commit.** `bash scripts/check-py.sh` + `uv run pytest -q` + (when prompts move) `uv run python scripts/gen_prompt_review.py` must pass on each commit, not just the final one.

## Non-goals (intentionally out of scope)

- **Restructuring `src/accessible_surfaceome/`.** The package layout is fine. CLAUDE.md flags `agents/surfaceome_v1/` for eventual relocation; that stays a follow-up.
- **Resolving the HPA license label drift across all artifacts.** The `src/.../sources/hpa.py` label fix is in scope (small, mechanical), but a full audit of every `download_traceability.json` is not.
- **`viewer/app/prompts/` and `viewer/app/reproducibility/` documentation expansion.** They're production routes; making them more discoverable in `viewer/README.md` is a separate doc task.
- **Manuscript / paper content.** `paper/build.sh` chain stays as-is; the `.docx` is a personal artifact (gitignored).
- **Rotating the contact emails (`rebeccacarlson95@gmail.com`, `michael.smallegan@gmail.com`).** Intentional API-courtesy contact headers; already public via git history.
- **Adding a global `/sources` page on the viewer.** Decision: extend the per-gene `DataSourcesFooter` instead (Section 5).

## Section 1 — Deletions

### Data files / dirs (verified zero refs)

| Path | Size | Reason |
|---|---|---|
| `data/analysis/candidate_universe_agreement/` | 53 B | Stale agreement metric; no refs |
| `data/external/mygene_symbol_resolution/mygene_response.json` | 1.4 MB | One-shot cache from a superseded resolver path |
| `data/analysis/paywall_bot_block/probe_results/` | 1.6 MB | Intermediate probe results; not read by figure scripts |
| `data/analysis/paywall_bot_block/cohort_150_4bucket.json` | 75 KB | Intermediate bucketing; only `doi_agency_breakdown.tsv` is read |
| `data/analysis/cross_source_uniprot_audit/` | 8 KB | One-shot accession-collapse exploration |
| `data/eval/_backup_bench_truth_fc7ddee89155.tsv` | 41 KB | Explicit `_backup_` prefix |
| `data/eval/triage_haiku_live_run.tsv` + `triage_benchmark_v1_candidates.tsv` + `triage_benchmark_v1_negative_candidates.tsv` | 20 KB total | Exploratory Haiku / candidate runs |
| `data/eval/v1_cost_stress_test/` | 2 KB | v1 agent path deprecated per CLAUDE.md |
| `data/raw/hgnc_complete_set.tsv` | 159 KB | Duplicate of canonical `data/external/hgnc/hgnc_complete_set.tsv` |

### Docs

| Path | Reason |
|---|---|
| `docs/audit/` (entire dir, 9 files) | 2026-06-08/09 forensic snapshots; one-off debug runs |
| `docs/superpowers/` (entire dir, 5 files) | Claude Code session scaffolding; **not appropriate for a public release repo** |
| `docs/operations/2026-06-07-stale-fixture-records-cleanup.md` | Low-level maintenance note |
| `docs/plans/2026-06-01-pr47-deep-dive-insights.md` | PR forensics snapshot |
| `docs/plans/claude-managed-agents-repo-guide.md` | Deprecated beta-API guide |
| `docs/plans/2026-05-06-agent-roadmap.md` | v1 roadmap; v1 removed |
| `docs/plans/2026-05-06-evidence-provenance-architecture.md` | v1 schema design; superseded |
| `docs/tools-design.md` | Managed Agents architecture; deprecated |

### Root / viewer

| Path | Reason |
|---|---|
| `.pages-rebuild-marker` | Transient Cloudflare Pages workaround |
| `.zed/settings.json` (also add `.zed/` to `.gitignore`) | Personal IDE settings; shouldn't be public |
| `viewer/app/homomer-demo/` (entire subdir incl. `BSCL2/`, `GJA1/`, `AQP1/`, `_demo-topologies.ts`, `homomer-demo.module.css`) | Undocumented routes, not in `Shell.tsx` nav, generator script (`synthesize_demo_topology.py`) already removed |

## Section 2 — Archives (move, don't delete)

Move to `data/archive/` (one new dir) and `docs/plans/archive/` (one new subdir). Each archive dir gets a one-line `README.md` explaining what's in it and that the contents are kept for provenance.

### `data/archive/`

- `data/processed/candidate_universe/candidate_universe_v3_dropped.tsv` (138 KB, v3 drop log)
- `data/processed/triage_bench/uniprot_tm_signal_accs.tsv` (27 KB, TM-signal cutoff variant)

### `docs/plans/archive/`

- `docs/plans/2026-04-17-hpa-jensenlab-compartments-integration.md` (M1, shipped)
- `docs/plans/2026-04-17-uniprot-accession-reconciliation.md` (M1, shipped)
- `docs/plans/2026-06-02-fulltext-coverage-expansion-deferred.md` (deferred decision record)

### `docs/archive/`

- `docs/eval/v1-cost-stress-test.md`
- `docs/evals/hspa1a-deep-dive-eval-2026-05.md`

### `scripts/archive/` (new)

Move 31 completed one-shot scripts here, with subdirs by category. Top-level `scripts/README.md` calls out that `archive/` exists for provenance and is not run.

```
scripts/archive/
├── README.md                        # explains: these are completed migrations / probes, kept for git audit
├── backfills/                       # 6 scripts
│   ├── backfill_deterministic_family.py
│   ├── backfill_ortholog_ecd_via_uniprot_features.py
│   ├── backfill_sequences_and_links.py
│   ├── backfill_sonnet_missing_uniprot.py
│   ├── backfill_sonnet_only_uniprots_to_d1.py
│   └── backfill_surface_bind_attribution.py
├── fixes/                           # 6 scripts
│   ├── fix_compara_ortholog_ecd_metadata.py
│   ├── fix_resolver_v3_collisions.py
│   ├── patch_deterministic_isoform_identity.py
│   ├── patch_deterministic_orthologs.py
│   ├── patch_deterministic_paralogs.py
│   └── recompute_stale_ecd_rows.py
├── reruns/                          # 4 scripts
│   ├── finalize_ortholog_rerun_to_d1.py
│   ├── refresh_record_post_llm_blocks.py
│   ├── rerun_changed_ortholog_topology.py
│   └── surfaceome_v2_replay_synth.py
├── renderers/                       # 4 scripts (HTML renderers for one-shot reports)
│   ├── render_deep_dive_html.py
│   ├── render_haiku_probe_html.py
│   ├── render_paragraph_clip_probe_html.py
│   └── render_surface_annotator_reference.py
├── probes-research/                 # 4 scripts (no committed outputs)
│   ├── experiment_methods_temperature.py
│   ├── haiku_paraphrase_repair_probe.py
│   ├── paragraph_clip_probe.py
│   └── paywall_bot_block_overview.py
├── builders-oneshot/                # 3 scripts (one-shot universe/catalog builders)
│   ├── build_genomewide_minus_m1.py
│   ├── build_reconfirm_sonnet_no_zero_db_gene_list.py
│   └── build_structure_viewer_data.py
└── d1-migrations/                   # 4 scripts
    ├── apply_pubmed_ncbi_rescue_to_catalog.py
    ├── d1_migrate_add_topology_paralogs.py
    ├── diff_ortholog_model_selection.py
    └── plan_trim_select_run.py      # superseded by plan_trim_select_dual_run.py
```

**Two scripts initially flagged for archive that are KEPT in active scripts/ after re-verification:**

- `paywall_bot_block_compare.py` — first agent listed this as a canonical figure generator (paired with `data/analysis/figures/make_paywall_bot_block.py`). Stays in `scripts/figures/`.
- `surfaceome_v2_replay_builders.py` — orchestrator docstrings reference it as the canonical pattern for cheap prompt iteration. Stays in `scripts/`.

## Section 3 — `scripts/` regroup

Top-level `scripts/` becomes a thin set of canonical entry points + 8 subdirs.

```
scripts/
├── README.md                         # NEW: tour of subdirs (2-line per dir)
├── triage_runner.py
├── surfaceome_v2_annotate.py
├── deep_dive_sweep.py
├── surfaceome_v2_replay_builders.py
├── bootstrap-worktree.sh
├── check-py.sh
├── setup-git-hooks.sh
├── d1_export_to_r2.sh
├── d1_triage_backup.sh
├── precommit
├── release/                          # existing
├── build/                            # fetch_*, build_*, compute_*, run_topology_*, run_deeptmhmm_*
├── upload/                           # upload_*, sync_*, run_v2_backfill_sweeps.sh, upload_v2_backfill_to_d1.sh
├── figures/                          # canonical figure generators
├── audit/                            # audit_*, check_*, update_version_fingerprints.py, gen_prompt_review.py
├── cloud/                            # apply_cf_edge_rules.py, export_mainbench_to_tsv.py
├── tsv-export/                       # augment_figure_tsvs_with_stable_ids.py, export_whole_proteome_catalog_to_tsv.py
├── probes/                           # probe_triage_fetch.py, probe_pdf_fallback.py, probe_cache_engagement.py, probe_oa_buckets.py
└── archive/                          # see Section 2
```

Detailed contents per subdir are in the agent-research artifacts; the move map will be encoded in the implementation plan.

### Reference-updating

A single `git mv` per moved script. After all moves, update the **referencing files**:

- `CLAUDE.md` — every script path mentioned; replace `scripts/foo.py` → `scripts/build/foo.py` etc.
- `AGENTS.md` — same.
- `README.md` — same, plus new Quick start (Section 4).
- `.github/workflows/*.yml` — every `scripts/*.py` path.
- `.githooks/`, `.pre-commit-config.yaml`, `scripts/precommit` — same.
- `pyproject.toml` — CLI entry-points if any reference moved scripts (none do today, but verify).
- `src/accessible_surfaceome/**/*.py` — any subprocess / import refs.
- `tests/**/*.py` — any path constants.
- `docs/**/*.md` — references in plans / reports.

Tracking spreadsheet (move map) lives in the implementation plan, not this design doc.

## Section 4 — README rework

### New Quick start block

Inserted at line ~17 of `README.md`, after the headline philosophy paragraph and before `## Why this exists`:

```markdown
## Quick start

**Access the data without setup:**
- Web viewer: https://surfaceome.deliverome.org/genes/GPR75
- JSON API: `curl https://api.deliverome.org/surfaceome/v1/genes/GPR75`
- Citable snapshot: Zenodo DOI [10.5281/zenodo.20805384](https://doi.org/10.5281/zenodo.20805384)

**Reproduce a figure from the paper:**
Every published figure has a standalone gist script in [`data/analysis/figures/`](data/analysis/figures/). Run with `uv run make_<slug>.py` — no `pip install` needed (PyPA inline script metadata).

**Run locally:**
```bash
uv sync
uv run accessible-surfaceome agents annotate GPR75            # single gene, ~5 min, ~$0.50
uv run python scripts/triage_runner.py --replicates 1 --d1    # cohort triage sweep, ~2 h, ~$30
```

See [`scripts/README.md`](scripts/README.md) for a tour of the script subdirs.
```

### Other README edits

- Update any path that moved (e.g. `scripts/figures/triage_bench_db_venn.py`).
- Add "see [NOTICE.md](NOTICE.md)" callout near the License section.
- Trim the **major phases** section if any of the operational detail is now covered by subdir READMEs.

## Section 5 — License hygiene + viewer license citation

### Critical context: the **canonical catalog vote is 5 DBs**

Per `scripts/build_candidate_universe_v3.py:40`, the catalog `n_db_votes` is the
sum of `uniprot_surface_flag + go_surface_flag + surfy_surface_flag +
cspa_surface_flag + hpa_surface_flag`. JensenLab COMPARTMENTS and DeepTMHMM are
**collected as side columns but NOT in the vote**.

The NOTICE and viewer-licensing surfaces in this section reflect that fact.
JensenLab is removed entirely (Section 7). DeepTMHMM stays — it's the canonical
topology call surfaced in `DataSourcesFooter`.

### `NOTICE.md` (new at repo root)

```markdown
# NOTICE

This project redistributes data derived from the following sources.
Each retains the license of its origin.

## Code
- Project code: MIT — Copyright Michael Smallegan and Rebecca Carlson

## Catalog vote sources (the 5 DBs that contribute to n_db_votes)
- UniProt — CC-BY-4.0 — https://www.uniprot.org/help/license
- Gene Ontology — CC-BY-4.0 — http://geneontology.org/page/use-and-license
- Human Protein Atlas — CC-BY-4.0 — https://www.proteinatlas.org/about/licence
- CSPA (Bausch-Fluck et al. 2015, 2018) — academic research use; commercial use requires permission from authors
- SURFY (Bausch-Fluck et al. 2018) — academic research use

## Deterministic-features sources (per-gene topology, structure, orthologs, complexes, binding)
- HGNC — CC-BY-4.0 — https://www.genenames.org/about/license/
- NCBI Gene — public domain (US Government work)
- AlphaFold DB — CC-BY-4.0 — https://alphafold.ebi.ac.uk/faq
- DeepTMHMM (Hansen et al.) — academic research use; redistributed predictions only
- Ensembl Compara — Apache-2.0 — https://www.ensembl.org/info/about/legal/disclaimer.html
- Schweke et al. 2024 homo-oligomerization atlas — per-paper data availability
- SURFACE-Bind (Khakzad et al. 2024) — academic research use

## Fonts
- Manrope — SIL Open Font License 1.1
- Playfair Display — SIL Open Font License 1.1

## Cached evidence snippets
Verbatim quotes in `viewer/public/data/surfaceome/*.json` are 20–100 words each,
attributed to their primary source, and reproduced under fair use for scholarly
annotation.
```

### `LICENSING.md` expansion

Current file is a placeholder. Replace with a per-source redistribution clause that:

- Repeats CC-BY-4.0 attribution requirements (UniProt, HGNC, GO, HPA, AlphaFold DB).
- States the academic-only constraint on CSPA, SURFY, DeepTMHMM, SURFACE-Bind.
- Notes that the candidate-universe TSV is a derived composite governed by the most-restrictive included source (currently the academic-only sources).

### `src/accessible_surfaceome/sources/hpa.py` label fix

Three occurrences of `"CC-BY-SA-3.0"` → `"CC-BY-4.0"` (verified at https://www.proteinatlas.org/about/licence). Regenerate `data/external/hpa_subcellular_location/download_traceability.json` and `data/processed/hpa/hpa_build_traceability.json` after the source change.

### Viewer license citation — extend `DataSourcesFooter` to cover catalog DBs

Today the per-gene `DataSourcesFooter`
([viewer/components/surfaceome/DataSourcesFooter/DataSourcesFooter.tsx](viewer/components/surfaceome/DataSourcesFooter/DataSourcesFooter.tsx))
lists 6 deterministic-features sources only (AlphaFold DB, DeepTMHMM, Ensembl
Compara, Schweke, SURFACE-Bind, UniProt). The 5 catalog-vote DBs that decide
*whether the gene is in the catalog at all* (UniProt, GO, SURFY, CSPA, HPA) are
not cited anywhere on the viewer.

**Change:**

1. Add 4 new lines (GO, SURFY, CSPA, HPA — UniProt is already there).
2. Restructure the list as **two columns** with a smaller body font so it doesn't
   dominate the gene page. Use CSS Grid `grid-template-columns: 1fr 1fr` with
   `gap: 12px 24px`. Font drops from the current `var(--font-size-body)` to
   `12px` (or whatever maps to `label-mono` in the design tokens).
3. Group visually: first column = **catalog-vote DBs (5)**, second column =
   **deterministic-features sources (~6, count after adding the new lines)**.
4. Section heading bumps to `Data sources & licenses`.
5. The new HPA + UniProt + GO + CSPA + SURFY lines render attribution similar to
   the existing pattern (license + URL or author/year/PMID), with explicit
   academic-only callouts for CSPA + SURFY.

Mobile fallback: single column at narrow widths (`@media (max-width: 600px)`).

## Section 6 — Other small cleanups bundled in

- **Drop `pypdfium2<5.9.0` constraint** from `pyproject.toml` `[tool.uv]`. The 7-day supply-chain cooldown has elapsed.
- **Add `.zed/` to `.gitignore`** alongside the delete.
- **`cloudflare/d1_compara_schema.sql`**: prepend a 2-line header comment noting it's a reference schema (production tables are `compara_ortholog_ecd`).

## Section 7 — JensenLab COMPARTMENTS removal (full)

JensenLab COMPARTMENTS is not in the canonical catalog vote (Section 5) and is
not surfaced in the viewer. Per the architectural call, strip it from the
codebase entirely. The data is recoverable from git if it ever needs to come
back.

**Removal sites (one commit, mechanical):**

1. **Source module** — `git rm src/accessible_surfaceome/sources/compartments.py`.
2. **Merge loader** — delete `COMPARTMENTS_TSV` constant + `load_compartments()`
   function from `src/accessible_surfaceome/merge/loaders.py`. Delete any
   call-site in `src/accessible_surfaceome/merge/`.
3. **Build script columns** — in `scripts/build_candidate_universe_v3.py`:
   drop `compartments_surface_flag`, `compartments_flag`,
   `MAX(c.compartments_surface_flag) AS compartments_flag`, and any JOIN clauses
   onto the compartments snapshot. Same for `scripts/build_universe_v2.py` if it
   references compartments.
4. **Committed snapshot** — `git rm -r data/processed/jensenlab_compartments/`.
5. **`.gitignore` entry** — remove the `data/external/jensenlab_compartments/`
   line (and the surrounding comment block about the COMPARTMENTS downloader).
6. **README.md** — remove JensenLab from the source list. Replace
   `"DeepTMHMM, COMPARTMENTS"` with `"DeepTMHMM"`. Drop the `compartments.py`
   mention from the `src/.../sources/` table row.
7. **AGENTS.md** — drop `compartments.py` from the per-source module list.
8. **CLAUDE.md** — drop any operational references (none expected).
9. **Tests** — `tests/test_compartments*.py` (if any) — `git rm`.
10. **Output schema** — verify the candidate-universe TSV column count drops the
    `compartments_*` columns, then re-run `augment_figure_tsvs_with_stable_ids.py`
    to refresh the figure-input TSVs.
11. **D1 schema** — verify no `compartments_*` columns in
    `cloudflare/d1_public_schema.sql` or `cloudflare/d1_schema.sql`; remove if
    present.

**Verification gates for the JensenLab removal commit:**

- `bash scripts/check-py.sh` (the merge tests + universe builder must still pass without compartments)
- `uv run pytest -q`
- `uv run python scripts/build_candidate_universe_v3.py` runs to completion locally and the resulting TSV has no `compartments_*` columns
- `cd viewer && npm run build` (viewer is unaffected, but build confirms no incidental breakage)

## Section 8 — Execution sequencing

Single PR off `claude/quizzical-darwin-8923eb` → `main`, 12 commits. Tests must pass on every commit.

1. `chore: remove stale forensic audits + v1 plans + Cloudflare Pages marker`
2. `chore: remove superseded data dumps and backups`
3. `chore: archive completed one-shot data outputs to data/archive/`
4. `chore: archive completed one-shot scripts to scripts/archive/`
5. `chore(scripts): regroup production scripts into build/upload/figures/audit/cloud/tsv-export/probes/`
6. `chore(viewer): drop orphan homomer-demo routes; ignore .zed/`
7. `chore(cloudflare): clarify d1_compara_schema.sql is reference-only`
8. `refactor(sources): remove JensenLab COMPARTMENTS (not in 5-DB vote)`
9. `feat(viewer): extend DataSourcesFooter to cover catalog vote DBs (2-col, smaller font)`
10. `chore(licenses): NOTICE.md, expanded LICENSING.md, HPA label fix, drop pypdfium2 cooldown`
11. `chore: update CLAUDE.md / AGENTS.md / hooks / CI for new script paths`
12. `docs(readme): scientist-facing quick-start + nav rework`

After commit 12, push and:

```bash
gh pr create --base main --title "chore: repo cleanup for v0 release" --body "<HEREDOC>"
```

PR body recaps each commit, lists what reviewers should verify (CI green, viewer loads with the new 2-col footer, figure scripts still run, no broken links in CLAUDE.md/AGENTS.md, candidate-universe TSV has no compartments columns), and links to this design doc.

## Verification gates per commit

- `bash scripts/check-py.sh` (ruff + ty + compile + pytest)
- `uv run pytest -q`
- After commits 4, 5, 8, 11, 12: `uv run python scripts/gen_prompt_review.py` if any prompt or moved-script path is touched
- After commit 6, 9: `cd viewer && npm run lint && npm run build` to confirm the homomer-demo removal + DataSourcesFooter changes didn't break anything
- After commit 8: `uv run python scripts/build_candidate_universe_v3.py` runs locally and the resulting TSV has no `compartments_*` columns
- After all commits: open `https://surfaceome.deliverome.org` locally (`cd viewer && npm run dev`) and spot-check the gene viewer (2-column DataSourcesFooter renders) + `/prompts` + `/reproducibility` + `/api` routes

## Risk register

| Risk | Mitigation |
|---|---|
| A "delete" target is silently referenced by a deleted-but-once-published doc URL | Subagents excluded refs from already-flagged-for-deletion files; deletions are still bisectable per commit |
| `scripts/` move breaks a CLAUDE.md / AGENTS.md command path | Reference-update commit (#9) is in scope and gated by check-py |
| Pre-commit hook references stale script paths | `.githooks/` + `.pre-commit-config.yaml` audited; refs updated in commit #9 |
| The HPA license label was load-bearing somewhere I missed | grep for `"CC-BY-SA-3.0"` across the whole repo before commit #8 to find every occurrence |
| Viewer build fails after homomer-demo removal | Commit #6 is gated on `cd viewer && npm run build` |
| One reviewer wants the deletions split into multiple PRs | The commit structure makes it trivial to cherry-pick; not splitting up front |
| JensenLab removal misses a hidden caller in `src/.../merge/` | Reference-update commit (#8) is preceded by a repo-wide grep for `compartments\|jensen`; CI must pass before commit lands |
| DataSourcesFooter 2-col layout breaks on mobile | Mobile fallback to single column at `max-width: 600px`; manual viewer build + screenshot before merging |
