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

## Section 5 — License hygiene

### `NOTICE.md` (new at repo root)

Lists every upstream source and its license. Skeleton:

```markdown
# NOTICE

This project redistributes data derived from the following sources.
Each retains the license of its origin.

## Code
- Project code: MIT — Copyright Michael Smallegan and Rebecca Carlson

## Public data sources
- UniProt — CC-BY-4.0 — https://www.uniprot.org/help/license
- HGNC — CC-BY-4.0 — https://www.genenames.org/about/license/
- Gene Ontology — CC-BY-4.0 — http://geneontology.org/page/use-and-license
- Human Protein Atlas — CC-BY-4.0 — https://www.proteinatlas.org/about/licence
- JensenLab COMPARTMENTS — CC-BY-4.0 — https://compartments.jensenlab.org/About
- NCBI Gene — public domain (US Government work)

## Academic / non-commercial use sources
- CSPA (Bausch-Fluck et al. 2015, 2018) — academic research use; commercial use requires permission from authors
- SURFY (Bausch-Fluck et al. 2018) — academic research use
- DeepTMHMM (Hansen et al.) — academic research use; redistributed predictions only

## Atlas data
- Schweke et al. 2024 homo-oligomerization atlas — per-paper data availability statement

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

- Repeats CC-BY-4.0 attribution requirements (UniProt, HGNC, GO, HPA, JensenLab).
- States the academic-only constraint on CSPA, SURFY, DeepTMHMM.
- Notes that the candidate-universe TSV is a derived composite governed by the most-restrictive included source (currently the academic-only sources).

### `src/accessible_surfaceome/sources/hpa.py` label fix

Three occurrences of `"CC-BY-SA-3.0"` → `"CC-BY-4.0"`. Regenerate `data/external/hpa_subcellular_location/download_traceability.json` and `data/processed/hpa/hpa_build_traceability.json` after the source change.

## Section 6 — Other small cleanups bundled in

- **Drop `pypdfium2<5.9.0` constraint** from `pyproject.toml` `[tool.uv]`. The 7-day supply-chain cooldown has elapsed.
- **Add `.zed/` to `.gitignore`** alongside the delete.
- **`cloudflare/d1_compara_schema.sql`**: prepend a 2-line header comment noting it's a reference schema (production tables are `compara_ortholog_ecd`).

## Section 7 — Execution sequencing

Single PR off `claude/quizzical-darwin-8923eb` → `main`, 10 commits. Tests must pass on every commit.

1. `chore: remove stale forensic audits + v1 plans + Cloudflare Pages marker`
2. `chore: remove superseded data dumps and backups`
3. `chore: archive completed one-shot data outputs to data/archive/`
4. `chore: archive completed one-shot scripts to scripts/archive/`
5. `chore(scripts): regroup production scripts into build/upload/figures/audit/cloud/tsv-export/probes/`
6. `chore(viewer): drop orphan homomer-demo routes; ignore .zed/`
7. `chore(cloudflare): clarify d1_compara_schema.sql is reference-only`
8. `chore(licenses): NOTICE.md, expanded LICENSING.md, HPA label fix, drop pypdfium2 cooldown`
9. `chore: update CLAUDE.md / AGENTS.md / hooks / CI for new script paths`
10. `docs(readme): scientist-facing quick-start + nav rework`

After commit 10, push and:

```bash
gh pr create --base main --title "chore: repo cleanup for v0 release" --body "<HEREDOC>"
```

PR body recaps each commit, lists what reviewers should verify (CI green, viewer loads, figure scripts still run, no broken links in CLAUDE.md/AGENTS.md), and links to this design doc.

## Verification gates per commit

- `bash scripts/check-py.sh` (ruff + ty + compile + pytest)
- `uv run pytest -q`
- After commits 4, 5, 9, 10: `uv run python scripts/gen_prompt_review.py` if any prompt or moved-script path is touched
- After commit 10: `cd viewer && npm run lint && npm run build` to confirm the homomer-demo removal didn't break anything
- After all commits: open `https://surfaceome.deliverome.org` locally (`cd viewer && npm run dev`) and spot-check the gene viewer + `/prompts` + `/reproducibility` + `/api` routes

## Risk register

| Risk | Mitigation |
|---|---|
| A "delete" target is silently referenced by a deleted-but-once-published doc URL | Subagents excluded refs from already-flagged-for-deletion files; deletions are still bisectable per commit |
| `scripts/` move breaks a CLAUDE.md / AGENTS.md command path | Reference-update commit (#9) is in scope and gated by check-py |
| Pre-commit hook references stale script paths | `.githooks/` + `.pre-commit-config.yaml` audited; refs updated in commit #9 |
| The HPA license label was load-bearing somewhere I missed | grep for `"CC-BY-SA-3.0"` across the whole repo before commit #8 to find every occurrence |
| Viewer build fails after homomer-demo removal | Commit #6 is gated on `cd viewer && npm run build` |
| One reviewer wants the deletions split into multiple PRs | The commit structure makes it trivial to cherry-pick; not splitting up front |
