# Repo Cleanup for v0 Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land a single PR (`chore: repo cleanup for v0 release`) that prepares accessible-surfaceome for public open-source release as a paper companion + reusable codebase. Delete 17 stale files, archive 31 one-shot scripts + 5 stale plans + 2 stale data outputs, regroup ~50 production scripts into 7 subdirs, remove JensenLab COMPARTMENTS, extend the viewer's data-sources footer, ship NOTICE.md + LICENSING.md, and rewrite the README with a scientist-facing quick-start.

**Architecture:** 12 logically-separate commits on `claude/quizzical-darwin-8923eb` against `main`. CI green per commit, bisectable by reverting individual commits. Each commit is one task in this plan; final task pushes and opens the PR.

**Tech Stack:** Python (uv + ruff + ty + pytest), Next.js 16 (viewer/), Cloudflare Workers (cloudflare/workers/surfaceome_api), D1 SQL (cloudflare/*.sql), git + gh CLI.

**Source spec:** [`docs/superpowers/specs/2026-06-25-repo-cleanup-for-release-design.md`](../specs/2026-06-25-repo-cleanup-for-release-design.md). Each task below maps to a section of the spec.

---

## File Structure Overview

### Created

- `NOTICE.md` (repo root) — upstream-source attribution per spec Section 5
- `data/archive/README.md` — explains what's in `data/archive/`
- `data/archive/candidate_universe_v3_dropped.tsv` — moved from `data/processed/candidate_universe/`
- `data/archive/uniprot_tm_signal_accs.tsv` — moved from `data/processed/triage_bench/`
- `docs/archive/README.md` — explains what's in `docs/archive/`
- `docs/archive/v1-cost-stress-test.md` — moved from `docs/eval/`
- `docs/archive/hspa1a-deep-dive-eval-2026-05.md` — moved from `docs/evals/`
- `docs/plans/archive/README.md` — explains shipped/deferred plans here
- `docs/plans/archive/2026-04-17-hpa-jensenlab-compartments-integration.md` — moved
- `docs/plans/archive/2026-04-17-uniprot-accession-reconciliation.md` — moved
- `docs/plans/archive/2026-06-02-fulltext-coverage-expansion-deferred.md` — moved
- `scripts/README.md` — tour of all subdirs (one-paragraph each)
- `scripts/archive/README.md` — explains the archive subdirs
- `scripts/archive/backfills/` + 6 moved scripts
- `scripts/archive/fixes/` + 6 moved scripts
- `scripts/archive/reruns/` + 4 moved scripts
- `scripts/archive/renderers/` + 4 moved scripts
- `scripts/archive/probes-research/` + 4 moved scripts
- `scripts/archive/builders-oneshot/` + 3 moved scripts
- `scripts/archive/d1-migrations/` + 4 moved scripts
- `scripts/build/` + ~14 moved scripts + `README.md`
- `scripts/upload/` + ~10 moved scripts + `README.md`
- `scripts/figures/` + 7 moved scripts + `README.md`
- `scripts/audit/` + ~11 moved scripts + `README.md`
- `scripts/cloud/` + 2 moved scripts + `README.md`
- `scripts/tsv-export/` + ~3 moved scripts + `README.md`
- `scripts/probes/` + 4 moved scripts + `README.md`

### Modified

- `.gitignore` — add `.zed/`, remove the JensenLab COMPARTMENTS ignore line
- `README.md` — Quick start block, JensenLab removal, script-path updates
- `CLAUDE.md` — script-path updates, JensenLab removal
- `AGENTS.md` — script-path updates, JensenLab removal
- `LICENSING.md` — expanded per spec Section 5
- `pyproject.toml` — drop `pypdfium2<5.9.0` constraint
- `cloudflare/d1_compara_schema.sql` — header comment per spec Section 6
- `cloudflare/d1_public_schema.sql` — drop `compartments_*` columns (if any)
- `cloudflare/d1_schema.sql` — drop `compartments_*` columns (if any)
- `src/accessible_surfaceome/sources/hpa.py` — three `"CC-BY-SA-3.0"` → `"CC-BY-4.0"`
- `src/accessible_surfaceome/merge/loaders.py` — drop `COMPARTMENTS_TSV`, `load_compartments`
- `src/accessible_surfaceome/merge/__init__.py` — drop imports + dict + iteration loops + docstring `7. **JensenLab COMPARTMENTS**` bullet
- `src/accessible_surfaceome/merge/gene_symbols.py` — drop `compartments_gene_symbol` entry
- `src/accessible_surfaceome/tools/gene_lookup.py` — drop `"compartments"` xref entries (lines 284, 525)
- `src/accessible_surfaceome/tools/_shared/models.py` — drop `"compartments"` from sources tuple (lines 151, 160 ONLY; biological compartment constants stay)
- `src/accessible_surfaceome/agents/_support/tool_registry.py` — drop JensenLab COMPARTMENTS mention (line 62)
- `src/accessible_surfaceome/audit/audit.py` — drop `COMPARTMENTS_TSV` block + processing (lines 8, 90–137)
- `src/accessible_surfaceome/audit/accession_collapse.py` — drop `load_compartments` import + dict entry
- `src/accessible_surfaceome/audit/blog_figures.py` — drop COMPARTMENTS docstring mentions
- `src/accessible_surfaceome/agents/_eval/database_baselines.py` — drop `compartments_surface_flag` baseline (line 53)
- `src/accessible_surfaceome/sources/_support/ensembl_mapping.py` — drop JensenLab COMPARTMENTS docstring/comment mentions
- `scripts/build/build_candidate_universe_v3.py` — drop `compartments_*` SELECT + output columns
- `scripts/upload/upload_candidate_universe_to_d1.py` — drop `compartments_*` columns
- `scripts/audit/audit_db_vs_sonnet_inclusion.py` — drop `compartments_surface_flag` baseline
- `LICENSING.md` — drop JensenLab COMPARTMENTS from the data-source list
- `data/processed/candidate_universe/candidate_universe_traceability.json` — auto-regenerates on build

**Not touched** (every match is the biological word, not the database):
- Three agent prompts under `src/.../agents/*/prompts/`
- `tests/test_cross_block_validators.py` (`dual_compartments` is biological)
- `src/.../sources/hpa.py` line 439 (biological compartments)
- `src/.../tools/_shared/models.py` lines 3609, 3613, 3660, 4341 (biological `_SECRETORY_PRIMARY_COMPARTMENTS` etc.)

**Not touched** (historical/archived content stays accurate as a point-in-time snapshot):
- `docs/reports/2026-04-17-jensenlab-compartments-integration.md`
- `docs/reports/2026-04-17-m1-candidate-universe-onepager.md`
- `docs/worked-examples/kaag1.md`
- `docs/plans/archive/2026-04-17-hpa-jensenlab-compartments-integration.md` (after Task 1 move)
- `data/external/hpa_subcellular_location/download_traceability.json` — regenerated
- `data/processed/hpa/hpa_build_traceability.json` — regenerated
- `viewer/components/surfaceome/DataSourcesFooter/DataSourcesFooter.tsx` — extend to 10 entries, 2-column
- `viewer/components/surfaceome/DataSourcesFooter/DataSourcesFooter.module.css` — grid + smaller font + mobile fallback
- `docs/prompt_review.html` — regenerated after prompt edits

### Deleted (file)

**Data:**
- `data/analysis/candidate_universe_agreement/` (entire dir)
- `data/external/mygene_symbol_resolution/mygene_response.json`
- `data/analysis/paywall_bot_block/probe_results/` (entire subdir)
- `data/analysis/paywall_bot_block/cohort_150_4bucket.json`
- `data/analysis/cross_source_uniprot_audit/` (entire dir)
- `data/eval/_backup_bench_truth_fc7ddee89155.tsv`
- `data/eval/triage_haiku_live_run.tsv`
- `data/eval/triage_benchmark_v1_candidates.tsv`
- `data/eval/triage_benchmark_v1_negative_candidates.tsv`
- `data/eval/v1_cost_stress_test/`
- `data/raw/hgnc_complete_set.tsv`
- `data/processed/jensenlab_compartments/` (entire dir, JensenLab removal)

**Docs:**
- `docs/audit/` (entire dir, 9 files)
- `docs/superpowers/` (entire dir, 5 files — Claude Code session scaffolding)
- `docs/operations/2026-06-07-stale-fixture-records-cleanup.md`
- `docs/plans/2026-06-01-pr47-deep-dive-insights.md`
- `docs/plans/claude-managed-agents-repo-guide.md`
- `docs/plans/2026-05-06-agent-roadmap.md`
- `docs/plans/2026-05-06-evidence-provenance-architecture.md`
- `docs/tools-design.md`

**Root / viewer / src:**
- `.pages-rebuild-marker`
- `.zed/settings.json`
- `viewer/app/homomer-demo/` (entire subdir incl. BSCL2, GJA1, AQP1, _demo-topologies.ts, homomer-demo.module.css)
- `src/accessible_surfaceome/sources/compartments.py`

---

## Verification commands (used throughout)

- **Python full check** — `bash scripts/check-py.sh` (ruff + ty + compile + pytest)
- **Pytest only** — `uv run pytest -q`
- **Prompt review regen** — `uv run python scripts/gen_prompt_review.py`
- **Viewer build** — `cd viewer && npm run lint && npm run build`
- **Candidate universe regen** — `uv run python scripts/build_candidate_universe_v3.py` (or moved path)
- **Repo-wide grep** — `grep -rln "PATTERN" --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.next --exclude-dir=.venv .`

---

## Task 1: Remove stale docs + archive shipped plans + drop Cloudflare Pages marker

**Spec:** Section 1 (docs + root deletions) + Section 2 (`docs/plans/archive/` and `docs/archive/` moves).

**Files (delete):**
- `docs/audit/` (entire dir, 9 files)
- `docs/superpowers/` — PRESERVE `docs/superpowers/specs/2026-06-25-repo-cleanup-for-release-design.md` and `docs/superpowers/plans/2026-06-28-repo-cleanup-for-release.md`, delete everything else
- `docs/operations/2026-06-07-stale-fixture-records-cleanup.md`
- `docs/plans/2026-06-01-pr47-deep-dive-insights.md`
- `docs/plans/claude-managed-agents-repo-guide.md`
- `docs/plans/2026-05-06-agent-roadmap.md`
- `docs/plans/2026-05-06-evidence-provenance-architecture.md`
- `docs/tools-design.md`
- `.pages-rebuild-marker`

**Files (move to archive — keep for provenance):**
- Create: `docs/plans/archive/README.md` + `docs/archive/README.md`
- Move: `docs/plans/2026-04-17-hpa-jensenlab-compartments-integration.md` → `docs/plans/archive/`
- Move: `docs/plans/2026-04-17-uniprot-accession-reconciliation.md` → `docs/plans/archive/`
- Move: `docs/plans/2026-06-02-fulltext-coverage-expansion-deferred.md` → `docs/plans/archive/`
- Move: `docs/eval/v1-cost-stress-test.md` → `docs/archive/`
- Move: `docs/evals/hspa1a-deep-dive-eval-2026-05.md` → `docs/archive/`

- [ ] **Step 1: Confirm targets exist**

```bash
ls docs/audit/ docs/superpowers/ docs/plans/ .pages-rebuild-marker docs/tools-design.md docs/operations/ 2>&1 | head -40
```

Expected: each path lists or shows as file; nothing already missing.

- [ ] **Step 2: Delete forensic audits dir**

```bash
git rm -r docs/audit/
```

- [ ] **Step 3: Delete superpowers cruft, but preserve THIS plan + spec**

The superpowers dir has the cleanup spec/plan you're executing — those must survive. Other files in `docs/superpowers/specs/` and `docs/superpowers/plans/` are session scaffolding from prior work and go away.

```bash
# Move the cleanup spec + plan to safety
mv docs/superpowers/specs/2026-06-25-repo-cleanup-for-release-design.md /tmp/cleanup-spec.md
mv docs/superpowers/plans/2026-06-28-repo-cleanup-for-release.md /tmp/cleanup-plan.md
git rm -r docs/superpowers/
mkdir -p docs/superpowers/specs docs/superpowers/plans
mv /tmp/cleanup-spec.md docs/superpowers/specs/2026-06-25-repo-cleanup-for-release-design.md
mv /tmp/cleanup-plan.md docs/superpowers/plans/2026-06-28-repo-cleanup-for-release.md
git add docs/superpowers/
```

- [ ] **Step 4: Delete remaining stale plans + root marker**

```bash
git rm docs/operations/2026-06-07-stale-fixture-records-cleanup.md
git rm docs/plans/2026-06-01-pr47-deep-dive-insights.md
git rm docs/plans/claude-managed-agents-repo-guide.md
git rm docs/plans/2026-05-06-agent-roadmap.md
git rm docs/plans/2026-05-06-evidence-provenance-architecture.md
git rm docs/tools-design.md
git rm .pages-rebuild-marker
```

- [ ] **Step 5: Create the doc archive dirs + READMEs**

```bash
mkdir -p docs/plans/archive docs/archive
```

Write `docs/plans/archive/README.md`:

```markdown
# docs/plans/archive/

Shipped / deferred plans kept for provenance. None of these describe
*current* work — they're snapshots of decisions for the historical record.

| File | Status |
|---|---|
| `2026-04-17-hpa-jensenlab-compartments-integration.md` | Shipped (M1 sources) |
| `2026-04-17-uniprot-accession-reconciliation.md` | Shipped (M1 accession path) |
| `2026-06-02-fulltext-coverage-expansion-deferred.md` | Deferred — decision record |
```

Write `docs/archive/README.md`:

```markdown
# docs/archive/

Stale evals + cost analyses kept for provenance.

| File | Why archived |
|---|---|
| `v1-cost-stress-test.md` | v1 agent path deprecated; cost model historical |
| `hspa1a-deep-dive-eval-2026-05.md` | One-off worked example (May 2026) |
```

- [ ] **Step 6: Move plans + evals to archive dirs**

```bash
git mv docs/plans/2026-04-17-hpa-jensenlab-compartments-integration.md docs/plans/archive/
git mv docs/plans/2026-04-17-uniprot-accession-reconciliation.md docs/plans/archive/
git mv docs/plans/2026-06-02-fulltext-coverage-expansion-deferred.md docs/plans/archive/
git mv docs/eval/v1-cost-stress-test.md docs/archive/v1-cost-stress-test.md
git mv docs/evals/hspa1a-deep-dive-eval-2026-05.md docs/archive/hspa1a-deep-dive-eval-2026-05.md
git add docs/plans/archive/README.md docs/archive/README.md
```

If `docs/eval/` or `docs/evals/` becomes empty after the move, remove it:

```bash
[ -z "$(ls docs/eval/ 2>/dev/null)" ] && rmdir docs/eval/ || ls docs/eval/
[ -z "$(ls docs/evals/ 2>/dev/null)" ] && rmdir docs/evals/ || ls docs/evals/
```

(Both dirs likely contain other files like `deep_dive_hspa1a.html` rendered evals — those stay where they are.)

- [ ] **Step 7: If `docs/operations/` is now empty, delete it**

```bash
[ -z "$(ls docs/operations/ 2>/dev/null)" ] && rmdir docs/operations/ || ls docs/operations/
```

- [ ] **Step 8: Run tests to confirm nothing depends on the deleted/moved docs**

```bash
bash scripts/check-py.sh
```

Expected: PASS. If a test references a moved-or-deleted doc by path, update the path (for moves) or restore + reclassify (for deletes).

- [ ] **Step 9: Commit**

```bash
git status
git commit -m "chore: remove stale forensic audits + v1 plans + Cloudflare Pages marker

Deletes:
- docs/audit/: 9 forensic snapshots from 2026-06-08/09
- docs/superpowers/: Claude Code session scaffolding (preserved the active
  cleanup spec + plan)
- docs/operations/: one stale maintenance note
- docs/plans/: PR forensics, deprecated Managed Agents guide, v1 roadmap +
  v1 evidence-provenance architecture
- docs/tools-design.md: Managed Agents architecture (deprecated)
- .pages-rebuild-marker: transient Cloudflare Pages workaround

Archives (moved, not deleted):
- docs/plans/archive/: shipped M1 plans + deferred fulltext-coverage
  decision record
- docs/archive/: v1-cost-stress-test + hspa1a-deep-dive-eval (May 2026)"
```

---

## Task 2: Remove superseded data dumps and backups

**Spec:** Section 1 (data deletions).

**Files:**
- Delete: `data/analysis/candidate_universe_agreement/`
- Delete: `data/external/mygene_symbol_resolution/mygene_response.json`
- Delete: `data/analysis/paywall_bot_block/probe_results/`
- Delete: `data/analysis/paywall_bot_block/cohort_150_4bucket.json`
- Delete: `data/analysis/cross_source_uniprot_audit/`
- Delete: `data/eval/_backup_bench_truth_fc7ddee89155.tsv`
- Delete: `data/eval/triage_haiku_live_run.tsv`
- Delete: `data/eval/triage_benchmark_v1_candidates.tsv`
- Delete: `data/eval/triage_benchmark_v1_negative_candidates.tsv`
- Delete: `data/eval/v1_cost_stress_test/`
- Delete: `data/raw/hgnc_complete_set.tsv`

- [ ] **Step 1: One-last-look grep — verify zero refs**

For each target, confirm no current code reads it (excluding the docs/audit dir we just removed):

```bash
for target in \
  "candidate_universe_agreement" \
  "mygene_response.json" \
  "probe_results" \
  "cohort_150_4bucket.json" \
  "cross_source_uniprot_audit" \
  "_backup_bench_truth_fc7ddee89155" \
  "triage_haiku_live_run" \
  "triage_benchmark_v1_candidates" \
  "triage_benchmark_v1_negative_candidates" \
  "v1_cost_stress_test"; do
  echo "=== $target ==="
  grep -rln "$target" --include="*.py" --include="*.md" --include="*.tsx" --include="*.ts" --include="*.yml" --include="*.toml" --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.next --exclude-dir=.venv . | grep -v "docs/superpowers/" || echo "(no refs)"
done
```

Expected: "(no refs)" for most. The `mygene_response.json`, `probe_results`, `_backup_bench_truth_fc7ddee89155` paths should have NO active refs. Any unexpected ref → investigate before deleting.

- [ ] **Step 2: Special-case the `data/raw/hgnc_complete_set.tsv` duplicate**

The canonical HGNC file is at `data/external/hgnc/hgnc_complete_set.tsv`. The `data/raw/` copy is stale. Confirm:

```bash
diff -q data/raw/hgnc_complete_set.tsv data/external/hgnc/hgnc_complete_set.tsv && echo "files identical (safe to drop /raw/)" || echo "files differ — investigate"
grep -rln "data/raw/hgnc_complete_set" --include="*.py" --include="*.md" --exclude-dir=.git . | grep -v "docs/superpowers/" || echo "(no refs to data/raw/ path)"
```

Expected: "files identical" OR "no refs to data/raw/ path". If files differ AND a script reads /raw/, do not delete; flag.

- [ ] **Step 3: Delete the data files / dirs**

```bash
git rm -rf data/analysis/candidate_universe_agreement/
git rm data/external/mygene_symbol_resolution/mygene_response.json
git rm -rf data/analysis/paywall_bot_block/probe_results/
git rm data/analysis/paywall_bot_block/cohort_150_4bucket.json
git rm -rf data/analysis/cross_source_uniprot_audit/
git rm data/eval/_backup_bench_truth_fc7ddee89155.tsv
git rm data/eval/triage_haiku_live_run.tsv
git rm data/eval/triage_benchmark_v1_candidates.tsv
git rm data/eval/triage_benchmark_v1_negative_candidates.tsv
git rm -rf data/eval/v1_cost_stress_test/
git rm data/raw/hgnc_complete_set.tsv
```

- [ ] **Step 4: If `data/external/mygene_symbol_resolution/` or `data/raw/` are now empty, remove them**

```bash
[ -z "$(ls data/external/mygene_symbol_resolution/ 2>/dev/null)" ] && rmdir data/external/mygene_symbol_resolution/
[ -z "$(ls data/raw/ 2>/dev/null)" ] && rmdir data/raw/
```

- [ ] **Step 5: Run tests**

```bash
bash scripts/check-py.sh
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git commit -m "chore: remove superseded data dumps and backups

- data/analysis/candidate_universe_agreement/ (stale agreement metric)
- data/external/mygene_symbol_resolution/mygene_response.json (superseded
  resolver cache; HGNC-ID resolver replaces it)
- data/analysis/paywall_bot_block/probe_results/ + cohort_150_4bucket.json
  (intermediate probes, only doi_agency_breakdown.tsv is canonical)
- data/analysis/cross_source_uniprot_audit/ (one-shot accession-collapse)
- data/eval/_backup_bench_truth_*.tsv (explicit _backup_ prefix)
- data/eval/triage_haiku_live_run.tsv + triage_benchmark_v1_candidates
  + _negative_candidates (exploratory Haiku/candidate runs)
- data/eval/v1_cost_stress_test/ (v1 deprecated per CLAUDE.md)
- data/raw/hgnc_complete_set.tsv (duplicate of data/external/hgnc/)"
```

---

## Task 3: Archive completed one-shot data outputs to data/archive/

**Spec:** Section 2 (data archives).

**Files:**
- Create: `data/archive/README.md`
- Move: `data/processed/candidate_universe/candidate_universe_v3_dropped.tsv` → `data/archive/candidate_universe_v3_dropped.tsv`
- Move: `data/processed/triage_bench/uniprot_tm_signal_accs.tsv` → `data/archive/uniprot_tm_signal_accs.tsv`

- [ ] **Step 1: Create `data/archive/` and its README**

```bash
mkdir -p data/archive
```

Write `data/archive/README.md`:

```markdown
# data/archive/

Completed one-shot outputs kept for provenance and historical reference.
Nothing here is read by current scripts; everything is bisectable from
git if a downstream caller ever needs to come back.

| File | Source | Why archived |
|---|---|---|
| `candidate_universe_v3_dropped.tsv` | `scripts/build_candidate_universe_v3.py` (v2 → v3 trim) | Records rows dropped by the v3 universe build; no current script reads it |
| `uniprot_tm_signal_accs.tsv` | one-shot TM-signal cutoff variant | Narrow alternative cutoff; never adopted |
```

- [ ] **Step 2: Re-verify no current refs to archive candidates**

```bash
grep -rln "candidate_universe_v3_dropped\|uniprot_tm_signal_accs" --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.next --exclude-dir=.venv . | grep -v "data/archive/" | grep -v "docs/superpowers/"
```

Expected: empty. If any active file references either, investigate before moving.

- [ ] **Step 3: Move files**

```bash
git mv data/processed/candidate_universe/candidate_universe_v3_dropped.tsv data/archive/candidate_universe_v3_dropped.tsv
git mv data/processed/triage_bench/uniprot_tm_signal_accs.tsv data/archive/uniprot_tm_signal_accs.tsv
git add data/archive/README.md
```

- [ ] **Step 4: Run tests**

```bash
bash scripts/check-py.sh
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git commit -m "chore: archive completed one-shot data outputs to data/archive/

Moved (not deleted) to keep provenance:
- candidate_universe_v3_dropped.tsv: rows trimmed during v2 -> v3 universe
- uniprot_tm_signal_accs.tsv: TM-signal cutoff variant (never adopted)"
```

---

## Task 4: Archive completed one-shot scripts to scripts/archive/

**Spec:** Section 2 (scripts archives, 31 scripts in 7 subdirs).

**Files:**
- Create: `scripts/archive/README.md`
- Create: `scripts/archive/{backfills,fixes,reruns,renderers,probes-research,builders-oneshot,d1-migrations}/` (7 dirs)
- Move 31 scripts (full list below)

**Subdir contents (full move map):**

```
scripts/archive/backfills/                          (6)
  scripts/backfill_deterministic_family.py
  scripts/backfill_ortholog_ecd_via_uniprot_features.py
  scripts/backfill_sequences_and_links.py
  scripts/backfill_sonnet_missing_uniprot.py
  scripts/backfill_sonnet_only_uniprots_to_d1.py
  scripts/backfill_surface_bind_attribution.py

scripts/archive/fixes/                              (6)
  scripts/fix_compara_ortholog_ecd_metadata.py
  scripts/fix_resolver_v3_collisions.py
  scripts/patch_deterministic_isoform_identity.py
  scripts/patch_deterministic_orthologs.py
  scripts/patch_deterministic_paralogs.py
  scripts/recompute_stale_ecd_rows.py

scripts/archive/reruns/                             (4)
  scripts/finalize_ortholog_rerun_to_d1.py
  scripts/refresh_record_post_llm_blocks.py
  scripts/rerun_changed_ortholog_topology.py
  scripts/surfaceome_v2_replay_synth.py

scripts/archive/renderers/                          (4)
  scripts/render_deep_dive_html.py
  scripts/render_haiku_probe_html.py
  scripts/render_paragraph_clip_probe_html.py
  scripts/render_surface_annotator_reference.py

scripts/archive/probes-research/                    (4)
  scripts/experiment_methods_temperature.py
  scripts/haiku_paraphrase_repair_probe.py
  scripts/paragraph_clip_probe.py
  scripts/paywall_bot_block_overview.py

scripts/archive/builders-oneshot/                   (3)
  scripts/build_genomewide_minus_m1.py
  scripts/build_reconfirm_sonnet_no_zero_db_gene_list.py
  scripts/build_structure_viewer_data.py

scripts/archive/d1-migrations/                      (4)
  scripts/apply_pubmed_ncbi_rescue_to_catalog.py
  scripts/d1_migrate_add_topology_paralogs.py
  scripts/diff_ortholog_model_selection.py
  scripts/plan_trim_select_run.py
```

Total: 31.

- [ ] **Step 1: Create archive structure + README**

```bash
mkdir -p scripts/archive/{backfills,fixes,reruns,renderers,probes-research,builders-oneshot,d1-migrations}
```

Write `scripts/archive/README.md`:

```markdown
# scripts/archive/

Completed one-shot scripts kept for provenance. **None of these run in the
current pipeline.** They are kept so a future archaeologist can trace how
past D1 schema migrations, resolver fixes, and one-time corrections were
applied.

| Subdir | What's here |
|---|---|
| `backfills/` | One-shot column / row backfills against D1 + on-disk records |
| `fixes/` | Targeted corrections to past states (resolver collisions, isoform metadata, ortholog metadata) |
| `reruns/` | Replays for specific cohorts / record subsets after a fix or upstream change |
| `renderers/` | HTML renderers for one-off evaluation pages (deep-dive previews, paragraph-clip probes) |
| `probes-research/` | Research probes — paywall bot-block analysis, Haiku paraphrase repair, paragraph-clipping |
| `builders-oneshot/` | Cohort/catalog builders run once (whole-genome-minus-M1, reconfirm-zero-DB gene list, structure-viewer data) |
| `d1-migrations/` | Schema migrations + one-time D1 transforms |

If a script here is needed again, prefer rewriting against the current
codebase to running this copy unmodified — paths and schemas have moved.
```

- [ ] **Step 2: Move scripts**

```bash
# backfills
for f in backfill_deterministic_family backfill_ortholog_ecd_via_uniprot_features backfill_sequences_and_links backfill_sonnet_missing_uniprot backfill_sonnet_only_uniprots_to_d1 backfill_surface_bind_attribution; do
  git mv "scripts/$f.py" "scripts/archive/backfills/$f.py"
done

# fixes
for f in fix_compara_ortholog_ecd_metadata fix_resolver_v3_collisions patch_deterministic_isoform_identity patch_deterministic_orthologs patch_deterministic_paralogs recompute_stale_ecd_rows; do
  git mv "scripts/$f.py" "scripts/archive/fixes/$f.py"
done

# reruns
for f in finalize_ortholog_rerun_to_d1 refresh_record_post_llm_blocks rerun_changed_ortholog_topology surfaceome_v2_replay_synth; do
  git mv "scripts/$f.py" "scripts/archive/reruns/$f.py"
done

# renderers
for f in render_deep_dive_html render_haiku_probe_html render_paragraph_clip_probe_html render_surface_annotator_reference; do
  git mv "scripts/$f.py" "scripts/archive/renderers/$f.py"
done

# probes-research
for f in experiment_methods_temperature haiku_paraphrase_repair_probe paragraph_clip_probe paywall_bot_block_overview; do
  git mv "scripts/$f.py" "scripts/archive/probes-research/$f.py"
done

# builders-oneshot
for f in build_genomewide_minus_m1 build_reconfirm_sonnet_no_zero_db_gene_list build_structure_viewer_data; do
  git mv "scripts/$f.py" "scripts/archive/builders-oneshot/$f.py"
done

# d1-migrations
for f in apply_pubmed_ncbi_rescue_to_catalog d1_migrate_add_topology_paralogs diff_ortholog_model_selection plan_trim_select_run; do
  git mv "scripts/$f.py" "scripts/archive/d1-migrations/$f.py"
done

git add scripts/archive/README.md
```

- [ ] **Step 3: Verify count is 31**

```bash
find scripts/archive -name "*.py" -type f | wc -l
```

Expected: `31`.

- [ ] **Step 4: Run tests**

```bash
bash scripts/check-py.sh
```

Expected: PASS. If a test imports one of the moved scripts, the test will fail with `ModuleNotFoundError`. Update the import path to point at `scripts/archive/<subdir>/<name>.py` — but flag this for review because it suggests the script is not truly one-shot.

- [ ] **Step 5: Commit**

```bash
git commit -m "chore: archive completed one-shot scripts to scripts/archive/

Moved 31 completed scripts into scripts/archive/{backfills,fixes,reruns,
renderers,probes-research,builders-oneshot,d1-migrations}/ to keep the
top-level scripts/ surface clean.

These ran once against a specific D1 state or an evaluation cohort and
are kept only for provenance. The README.md in scripts/archive/ explains
each subdir."
```

---

## Task 5: Regroup production scripts into scripts/{build,upload,figures,audit,cloud,tsv-export,probes}/

**Spec:** Section 3 (scripts/ regroup).

**Files:**
- Create: `scripts/{build,upload,figures,audit,cloud,tsv-export,probes}/` (7 dirs) + a `README.md` in each
- Create: `scripts/README.md` (tour of all subdirs)
- Move ~50 scripts (full map below)

**Subdir contents (full move map):**

```
scripts/build/                                       (~14)
  scripts/fetch_hgnc_complete_set.py
  scripts/fetch_ncbi_human_protein_coding.py
  scripts/build_candidate_universe_v3.py
  scripts/build_universe_v2.py
  scripts/build_gene_identifier_table.py
  scripts/build_topology_candidate_set.py
  scripts/build_triageable_catalog.py
  scripts/build_viewer_catalog.py
  scripts/build_search_catalog.py
  scripts/build_surface_bind_summary.py
  scripts/build_schweke_d1_table.py
  scripts/compute_paralog_ecd_similarity.py
  scripts/run_topology_sweep.py
  scripts/run_deeptmhmm_giants.py
  scripts/refresh_compara.sh

scripts/upload/                                      (~10)
  scripts/sync_public_d1.py
  scripts/sync_surface_bind_to_d1.py
  scripts/sync_figure_gists.sh
  scripts/upload_topology_to_d1.py
  scripts/upload_ortholog_ecd_to_d1.py
  scripts/upload_paralogs_to_d1.py
  scripts/upload_compara_to_d1.py
  scripts/upload_viewer_snapshots_to_d1.py
  scripts/upload_candidate_universe_to_d1.py
  scripts/upload_human_isoforms_topology_to_d1.py
  scripts/upload_v2_backfill_to_d1.sh
  scripts/run_v2_backfill_sweeps.sh

scripts/figures/                                     (7)
  scripts/db_vs_sonnet_whole_proteome.py
  scripts/ensemble_vs_best_db_vs_sonnet.py
  scripts/paywall_bot_block_compare.py
  scripts/triage_bench_db_barplot.py
  scripts/triage_bench_db_venn.py
  scripts/zero_db_rescues_by_triage.py
  scripts/embed_figure_gist_metadata.py

scripts/audit/                                       (~11)
  scripts/audit_resolver_hgnc_id_v3.py
  scripts/audit_resolver_hgnc_id_v3_extend.py
  scripts/audit_evidence_retrieval.py
  scripts/audit_deep_dive_orphans.py
  scripts/audit_db_vs_sonnet_inclusion.py
  scripts/audit_v2_deterministic_coverage.py
  scripts/check_schema_freshness.py
  scripts/check_triage_coverage.py
  scripts/check_viewer_types_sync.py
  scripts/update_version_fingerprints.py
  scripts/gen_prompt_review.py

scripts/cloud/                                       (2)
  scripts/apply_cf_edge_rules.py
  scripts/export_mainbench_to_tsv.py

scripts/tsv-export/                                  (2)
  scripts/augment_figure_tsvs_with_stable_ids.py
  scripts/export_whole_proteome_catalog_to_tsv.py

scripts/probes/                                      (4)
  scripts/probe_triage_fetch.py
  scripts/probe_pdf_fallback.py
  scripts/probe_cache_engagement.py
  scripts/probe_oa_buckets.py
```

**Stays at top-level (canonical entry points):**

```
scripts/triage_runner.py
scripts/surfaceome_v2_annotate.py
scripts/deep_dive_sweep.py
scripts/surfaceome_v2_replay_builders.py
scripts/bootstrap-worktree.sh
scripts/check-py.sh
scripts/setup-git-hooks.sh
scripts/d1_export_to_r2.sh
scripts/d1_triage_backup.sh
scripts/precommit
scripts/release/        (existing dir)
scripts/archive/        (created Task 4)
```

- [ ] **Step 1: Create subdirs**

```bash
mkdir -p scripts/{build,upload,figures,audit,cloud,tsv-export,probes}
```

- [ ] **Step 2: Move scripts (one git mv per move; safe to script)**

```bash
# scripts/build/
for f in fetch_hgnc_complete_set fetch_ncbi_human_protein_coding build_candidate_universe_v3 build_universe_v2 build_gene_identifier_table build_topology_candidate_set build_triageable_catalog build_viewer_catalog build_search_catalog build_surface_bind_summary build_schweke_d1_table compute_paralog_ecd_similarity run_topology_sweep run_deeptmhmm_giants; do
  git mv "scripts/$f.py" "scripts/build/$f.py"
done
git mv scripts/refresh_compara.sh scripts/build/refresh_compara.sh

# scripts/upload/
for f in sync_public_d1 sync_surface_bind_to_d1 upload_topology_to_d1 upload_ortholog_ecd_to_d1 upload_paralogs_to_d1 upload_compara_to_d1 upload_viewer_snapshots_to_d1 upload_candidate_universe_to_d1 upload_human_isoforms_topology_to_d1; do
  git mv "scripts/$f.py" "scripts/upload/$f.py"
done
git mv scripts/sync_figure_gists.sh scripts/upload/sync_figure_gists.sh
git mv scripts/upload_v2_backfill_to_d1.sh scripts/upload/upload_v2_backfill_to_d1.sh
git mv scripts/run_v2_backfill_sweeps.sh scripts/upload/run_v2_backfill_sweeps.sh

# scripts/figures/
for f in db_vs_sonnet_whole_proteome ensemble_vs_best_db_vs_sonnet paywall_bot_block_compare triage_bench_db_barplot triage_bench_db_venn zero_db_rescues_by_triage embed_figure_gist_metadata; do
  git mv "scripts/$f.py" "scripts/figures/$f.py"
done

# scripts/audit/
for f in audit_resolver_hgnc_id_v3 audit_resolver_hgnc_id_v3_extend audit_evidence_retrieval audit_deep_dive_orphans audit_db_vs_sonnet_inclusion audit_v2_deterministic_coverage check_schema_freshness check_triage_coverage check_viewer_types_sync update_version_fingerprints gen_prompt_review; do
  git mv "scripts/$f.py" "scripts/audit/$f.py"
done

# scripts/cloud/
git mv scripts/apply_cf_edge_rules.py scripts/cloud/apply_cf_edge_rules.py
git mv scripts/export_mainbench_to_tsv.py scripts/cloud/export_mainbench_to_tsv.py

# scripts/tsv-export/
git mv scripts/augment_figure_tsvs_with_stable_ids.py scripts/tsv-export/augment_figure_tsvs_with_stable_ids.py
git mv scripts/export_whole_proteome_catalog_to_tsv.py scripts/tsv-export/export_whole_proteome_catalog_to_tsv.py

# scripts/probes/
for f in probe_triage_fetch probe_pdf_fallback probe_cache_engagement probe_oa_buckets; do
  git mv "scripts/$f.py" "scripts/probes/$f.py"
done
```

- [ ] **Step 3: Write per-subdir READMEs (one paragraph each)**

For each of `scripts/build/`, `scripts/upload/`, `scripts/figures/`, `scripts/audit/`, `scripts/cloud/`, `scripts/tsv-export/`, `scripts/probes/`, write a `README.md` with one paragraph describing what's in the dir. Use this template for `scripts/build/README.md`:

```markdown
# scripts/build/

Data acquisition + derived-artifact build steps. Each script fetches an
upstream source or builds a downstream snapshot. Run order generally
follows: `fetch_*` → `build_*` → `compute_*` → `run_*_sweep`. See the
project README for the full data-flow diagram.

Outputs land in `data/external/` (raw) or `data/processed/` (derived).
Re-run `scripts/check-py.sh` after touching any builder to make sure the
schema fingerprints in `tests/version_fingerprints.json` still match.
```

Adapt for each subdir:
- `scripts/upload/` — Sync builders' outputs to D1 + R2 + figure gists.
- `scripts/figures/` — Canonical figure generators. Paired with `data/analysis/figures/make_<slug>.py` mirrors per CLAUDE.md's "canonical vs mirror" rule.
- `scripts/audit/` — Read-only analysis, drift detection, version fingerprints. Some gate commits via `.pre-commit-config.yaml`.
- `scripts/cloud/` — Cloudflare edge config + TSV exports from the public Worker.
- `scripts/tsv-export/` — Augment public TSVs with stable IDs + denormalize the most-common reanalysis joins.
- `scripts/probes/` — Validation probes that touch the network but make no model calls (`$0` to run). Use to debug triage fetch or PDF fallback chains.

- [ ] **Step 4: Write the top-level scripts/README.md**

```markdown
# scripts/

Top-level scripts in this directory are **canonical entry points** for
production sweeps. Sub-directories group the supporting build / upload /
audit pipeline by function so a scientist landing on the repo can find
the right script in seconds.

| Entry point | What it does |
|---|---|
| `triage_runner.py` | Genome-wide triage sweep against the candidate universe |
| `surfaceome_v2_annotate.py` | Per-gene deep-dive annotation (full v2 record) |
| `deep_dive_sweep.py` | Cohort orchestrator for parallel deep-dive batches |
| `surfaceome_v2_replay_builders.py` | Replay individual v2 block builders (cheap prompt iteration) |
| `bootstrap-worktree.sh` | Hydrate a fresh worktree per CLAUDE.md guidance |
| `check-py.sh` | ruff + ty + compile + pytest |
| `setup-git-hooks.sh`, `precommit` | Local hook plumbing |
| `d1_export_to_r2.sh`, `d1_triage_backup.sh` | Backup D1 → R2 |

| Subdir | What's in it |
|---|---|
| `build/` | Data acquisition + build steps (`fetch_*`, `build_*`, `compute_*`, `run_*_sweep`) |
| `upload/` | Sync derived artifacts to D1 + R2 + figure gists |
| `figures/` | Canonical figure generators (paired with `data/analysis/figures/make_*.py` mirrors) |
| `audit/` | Read-only audits, schema-fingerprint drift detection, prompt-review regen |
| `cloud/` | Cloudflare edge config + public-Worker TSV exports |
| `tsv-export/` | Augment public TSVs with stable IDs |
| `probes/` | $0 validation probes (no model calls) |
| `release/` | Release packaging (Zenodo deposit chain) |
| `archive/` | Completed one-shot scripts kept for provenance — do NOT re-run unmodified |

For details on each script's inputs/outputs, run the script with `--help`
or read the module docstring.
```

- [ ] **Step 5: Update CI workflows for moved script paths**

The reference-update happens fully in Task 11, but the CI workflows must be updated NOW so the build doesn't fail before that commit. Find and patch:

```bash
grep -rln "scripts/\(audit\|build\|cloud\|figures\|probes\|tsv-export\|upload\)" .github/workflows/ 2>/dev/null
# Run this version to find OLD paths that need updating:
grep -rln "scripts/\(audit_\|build_\|fetch_\|sync_\|upload_\|probe_\|paywall_\|triage_bench_db_\|gen_prompt_review\|apply_cf_edge\|export_mainbench\|augment_figure_tsvs\)" .github/workflows/ 2>/dev/null
```

For each match, prefix the script name with the appropriate subdir. Example:
- `scripts/build_search_catalog.py` → `scripts/build/build_search_catalog.py`
- `scripts/gen_prompt_review.py` → `scripts/audit/gen_prompt_review.py`

Same for `.pre-commit-config.yaml`, `.githooks/`, and `scripts/precommit`. Patch them in this commit so CI stays green.

- [ ] **Step 6: Run full check**

```bash
bash scripts/check-py.sh
```

Expected: PASS. If a `module` import error pops up, a Python file is doing `import scripts.foo` — fix to `scripts.build.foo` (or wherever) in this commit.

- [ ] **Step 7: Commit**

```bash
git commit -m "chore(scripts): regroup production scripts into build/upload/figures/audit/cloud/tsv-export/probes/

Top-level scripts/ is now a thin set of canonical entry points
(triage_runner, surfaceome_v2_annotate, deep_dive_sweep, +
bootstrap/check/d1-backup shell scripts). Everything else is grouped by
function so a scientist landing on the repo finds the right script fast.

Updated CI + pre-commit hook paths in the same commit so the build stays
green. Per-subdir README.md added under each new dir; scripts/README.md
gives the tour."
```

---

## Task 6: Drop viewer/app/homomer-demo/ and add .zed/ to .gitignore

**Spec:** Section 1 (viewer deletion) + Section 6 (small cleanups).

**Files:**
- Delete: `viewer/app/homomer-demo/` (entire subdir — BSCL2/, GJA1/, AQP1/, _demo-topologies.ts, homomer-demo.module.css)
- Delete: `.zed/settings.json`
- Modify: `.gitignore` (add `.zed/`)

- [ ] **Step 1: Confirm no nav refs from Shell.tsx**

```bash
grep -n "homomer-demo" viewer/components/Shell/Shell.tsx
```

Expected: no matches (per spec; the routes are orphans).

If anything matches, the spec was wrong and the routes are nav-reachable — flag for re-design.

- [ ] **Step 2: Delete homomer-demo**

```bash
git rm -rf viewer/app/homomer-demo/
```

- [ ] **Step 3: Delete .zed/settings.json**

```bash
git rm -rf .zed/
```

- [ ] **Step 4: Add `.zed/` to `.gitignore`**

Open `.gitignore` and add under the "# OS" or "# Claude Code local worktrees" section:

```
# Zed editor settings — local-only, not for the repo.
.zed/
```

- [ ] **Step 5: Run viewer build to confirm no incidental break**

```bash
cd viewer && npm run lint && npm run build && cd ..
```

Expected: PASS. The homomer-demo routes were standalone; removing them shouldn't break anything else. If a TypeScript error references `_demo-topologies` import, fix the caller (or restore the file and flag).

- [ ] **Step 6: Run Python check**

```bash
bash scripts/check-py.sh
```

Expected: PASS (Python unaffected).

- [ ] **Step 7: Commit**

```bash
git commit -m "chore(viewer): drop orphan homomer-demo routes; ignore .zed/

- viewer/app/homomer-demo/{BSCL2,GJA1,AQP1}/ + _demo-topologies.ts +
  homomer-demo.module.css: undocumented routes, not in Shell.tsx nav,
  generator script already removed; real per-gene HomoOligomerViewerCard
  handles all live homomer rendering.
- .zed/settings.json: personal IDE settings, shouldn't be public.
- .gitignore: add .zed/ to keep future Zed settings out of the repo."
```

---

## Task 7: Clarify cloudflare/d1_compara_schema.sql is reference-only

**Spec:** Section 6 (small cleanups).

**Files:**
- Modify: `cloudflare/d1_compara_schema.sql` (prepend header comment)

- [ ] **Step 1: Read current first 5 lines**

```bash
head -5 cloudflare/d1_compara_schema.sql
```

- [ ] **Step 2: Prepend header comment**

Edit the file. Insert at the very top:

```sql
-- NOTE: This file is a REFERENCE schema only.
-- Production tables are named differently (e.g. compara_ortholog_ecd
-- not compara_ortholog); see scripts/audit/audit_evidence_retrieval.py
-- and the live D1 console for current names. Do not apply this file
-- directly to production D1.
--
```

- [ ] **Step 3: Confirm nothing else applies the schema directly**

```bash
grep -rln "d1_compara_schema.sql" --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.next --exclude-dir=.venv .
```

Expected: only docs / README refs, no scripts that `wrangler d1 execute … --file cloudflare/d1_compara_schema.sql`. If a script DOES apply it, that script must be flagged (the header comment is then a lie).

- [ ] **Step 4: Commit**

```bash
git commit -m "chore(cloudflare): clarify d1_compara_schema.sql is reference-only

The actual production ortholog table is compara_ortholog_ecd, not
compara_ortholog as this schema file shows. Adding a header comment
so future readers don't try to apply this directly to D1."
```

---

## Task 8: Remove JensenLab COMPARTMENTS entirely

**Spec:** Section 7 (JensenLab removal).

**Verified ref scope** (precise grep already run during planning):
- True JensenLab refs are limited to `JensenLab`, `jensenlab_compartments`, `COMPARTMENTS_TSV`, and `compartments_<field>` patterns (`_surface_flag`, `_gene_symbol`, `_stars`, etc.). Generic "compartments" in agent prompts and tests is the biological term and is **left alone**.
- Touch sites enumerated in the Files block above.

- [ ] **Step 1: Whole-file deletes**

```bash
git rm src/accessible_surfaceome/sources/compartments.py
git rm -rf data/processed/jensenlab_compartments/
```

- [ ] **Step 2: Patch the merge layer**

Edit `src/accessible_surfaceome/merge/loaders.py`:
- Remove the `COMPARTMENTS_TSV` constant.
- Remove the entire `load_compartments()` function.

Edit `src/accessible_surfaceome/merge/__init__.py`:
- Drop the `load_compartments` and `COMPARTMENTS_TSV` imports.
- Drop the `"compartments"` entry from the loaders dict (line ~149).
- Drop `"compartments"` from the source-iteration loops (lines ~228, ~244).
- Drop `"compartments_surface_flag"` from the column list (line ~117).
- Edit the module docstring: remove the `7. **JensenLab COMPARTMENTS**` bullet and the note "COMPARTMENTS do not contribute to universe membership but their columns…".

Edit `src/accessible_surfaceome/merge/gene_symbols.py`:
- Remove the `compartments_gene_symbol` entry (line 64).

- [ ] **Step 3: Patch tools/ + audit/ + agents/ refs**

For each file below, open it, find the JensenLab/COMPARTMENTS refs at the line numbers listed, and remove the data-pipeline plumbing (preserving any docstring that has historical context — adjust to past tense where helpful). Run `bash scripts/check-py.sh` after each file is done to confirm no immediate breakage.

- `src/accessible_surfaceome/tools/gene_lookup.py` (lines 284–286, 525–526) — drop the `"compartments"` xref entries.
- `src/accessible_surfaceome/tools/_shared/models.py` (lines 151, 160 only) — drop `"compartments"` from the sources tuple and update the comment to reflect the 5-DB set. **Do NOT touch** lines 3609, 3613, 3660, 4341 — those are biological compartment constants.
- `src/accessible_surfaceome/agents/_support/tool_registry.py` (line 62) — drop the JensenLab COMPARTMENTS lane mention from the prose.
- `src/accessible_surfaceome/audit/audit.py` (lines 8, 90–137) — drop the JensenLab COMPARTMENTS opener comment and the `COMPARTMENTS_TSV` block + the `sources["compartments"] = …` assignment.
- `src/accessible_surfaceome/audit/accession_collapse.py` (lines 32, 53) — drop the `load_compartments` import and the `"compartments": load_compartments` dict entry.
- `src/accessible_surfaceome/audit/blog_figures.py` (lines 29, 32, 89) — drop the COMPARTMENTS docstring mentions; the file already excludes them from the published figures.
- `src/accessible_surfaceome/agents/_eval/database_baselines.py` (line 53) — drop the `compartments_surface_flag` baseline row from the eval baseline list.
- `src/accessible_surfaceome/sources/_support/ensembl_mapping.py` (lines 7, 16, 101) — drop JensenLab COMPARTMENTS docstring/comment mentions; no executing code references it.

- [ ] **Step 4: Patch the candidate-universe + upload + audit scripts**

`scripts/build/build_candidate_universe_v3.py`:
- Drop `MAX(c.compartments_surface_flag) AS compartments_flag` from the SELECT (line ~38).
- Drop `b.compartments_flag` from any downstream SELECTs (line ~61).
- Drop `"compartments_flag"` from the output column list (line ~105).
- Confirm `n_db_votes = uniprot+go+surfy+cspa+hpa` is unchanged (it never included compartments).

`scripts/upload/upload_candidate_universe_to_d1.py`:
- Drop `compartments_*` column references.

`scripts/audit/audit_db_vs_sonnet_inclusion.py`:
- Drop the `compartments_surface_flag` baseline.

- [ ] **Step 5: Patch D1 schemas + worker**

`cloudflare/d1_public_schema.sql`:
- Remove any `compartments_*` column definitions on `candidate_universe_public`.

`cloudflare/d1_schema.sql`:
- Same removal if present.

Worker check:

```bash
grep -rln "compartments" cloudflare/workers/ 2>/dev/null
```

If any match, edit those SQL fragments to drop the columns from the SELECTs.

- [ ] **Step 6: Remove JensenLab from .gitignore**

Edit `.gitignore`: remove the `JensenLab COMPARTMENTS` comment block and the `data/external/jensenlab_compartments/` line. Keep the surrounding DeepTMHMM block intact.

- [ ] **Step 7: Remove JensenLab from CLAUDE.md, AGENTS.md, README.md, LICENSING.md**

- `CLAUDE.md` — drop the COMPARTMENTS bullet under the gitignored-bulk-data section.
- `AGENTS.md` — drop `compartments.py` from the per-source module list.
- `README.md` — replace `"DeepTMHMM, COMPARTMENTS"` with `"DeepTMHMM"`; drop the `compartments.py` row in the `src/.../sources/` table.
- `LICENSING.md` — drop the JensenLab COMPARTMENTS entry from the data-source list.

Leave `docs/reports/2026-04-17-jensenlab-compartments-integration.md` and `docs/reports/2026-04-17-m1-candidate-universe-onepager.md` untouched — those are **historical M1 integration reports**; the references are correct as a snapshot of what M1 included.

- [ ] **Step 8: Regenerate the candidate-universe TSV + traceability**

```bash
uv run python scripts/build/build_candidate_universe_v3.py
```

Expected: completes; output TSV has no `compartments_*` columns. Confirm:

```bash
head -1 data/processed/candidate_universe/candidate_universe.tsv | tr '\t' '\n' | grep compartments
```

Expected: empty.

The traceability JSON at `data/processed/candidate_universe/candidate_universe_traceability.json` should auto-update during the build. Verify it no longer mentions JensenLab:

```bash
grep -i "jensen\|compartments" data/processed/candidate_universe/candidate_universe_traceability.json
```

Expected: empty.

- [ ] **Step 9: Re-verify zero residual refs (precise pattern, biological "compartments" allowed)**

```bash
grep -rn "JensenLab\|jensenlab_compartments\|COMPARTMENTS_TSV\|compartments_surface_flag\|compartments_gene_symbol\|compartments_stars\|compartments_predictions\|compartments_knowledge\|compartments_experiments\|compartments_textmining\|compartments_integrated\|compartments_flag" --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.next --exclude-dir=.venv --exclude-dir=archive --exclude-dir=superpowers .
```

Expected: only `docs/reports/2026-04-17-*` historical files + `docs/worked-examples/kaag1.md` (also historical). Any active code file matching → fix.

- [ ] **Step 10: Run full Python check + viewer build**

```bash
bash scripts/check-py.sh
cd viewer && npm run build && cd ..
```

Expected: PASS, PASS.

The prompt-leak tests live inside `scripts/check-py.sh`'s pytest, so they're already run. Because we did NOT touch any prompt files, `docs/prompt_review.html` does NOT need regeneration in this commit.

- [ ] **Step 11: Commit**

```bash
git commit -m "refactor(sources): remove JensenLab COMPARTMENTS (not in 5-DB vote)

COMPARTMENTS was carried as a side column but was never in the canonical
n_db_votes (UniProt + GO + SURFY + CSPA + HPA). Full removal here:

- src/.../sources/compartments.py: deleted
- merge layer: COMPARTMENTS_TSV, load_compartments() removed; dict and
  iteration loops cleaned in __init__.py; gene_symbols map trimmed
- tools/gene_lookup.py + tools/_shared/models.py: sources tuple and xrefs
  drop 'compartments' (biological compartment constants in models.py
  untouched)
- audit/audit.py, accession_collapse.py, blog_figures.py: drop COMPARTMENTS
  refs (loader, dict entry, docstring mentions)
- agents/_support/tool_registry.py + agents/_eval/database_baselines.py:
  drop COMPARTMENTS lane + baseline row
- sources/_support/ensembl_mapping.py: drop docstring mentions
- candidate-universe builder + upload + db_vs_sonnet inclusion audit:
  drop compartments_flag SELECT/output
- D1 public + private schemas: drop compartments_* columns
- data/processed/jensenlab_compartments/: snapshot removed
- README/AGENTS.md/CLAUDE.md/LICENSING.md: source list updated
- .gitignore: COMPARTMENTS bulk-data line removed (no longer downloaded)
- candidate-universe TSV + traceability regenerated

Agent prompts and tests are NOT touched — every 'compartments' match in
those files is the biological word (vesicular/subcellular compartments),
not the JensenLab database.

If COMPARTMENTS ever needs to come back, recover from git history."
```

---

## Task 9: Extend DataSourcesFooter to cover catalog vote DBs

**Spec:** Section 5 (viewer license citation).

**Files:**
- Modify: `viewer/components/surfaceome/DataSourcesFooter/DataSourcesFooter.tsx`
- Modify: `viewer/components/surfaceome/DataSourcesFooter/DataSourcesFooter.module.css`

- [ ] **Step 1: Read current footer**

```bash
cat viewer/components/surfaceome/DataSourcesFooter/DataSourcesFooter.tsx
cat viewer/components/surfaceome/DataSourcesFooter/DataSourcesFooter.module.css
```

- [ ] **Step 2: Rename heading + restructure JSX into two `<ul>` groups**

Edit `DataSourcesFooter.tsx`. Change:

```tsx
<aside className={styles.footer} aria-label="Data sources">
  <p className={`label-mono ${styles.label}`}>Data sources</p>
  <ul className={styles.list}>
    <li>AlphaFold DB structures — ...</li>
    ...
    <li>UniProt — CC BY 4.0 (UniProt Consortium)</li>
  </ul>
</aside>
```

to:

```tsx
<aside className={styles.footer} aria-label="Data sources and licenses">
  <p className={`label-mono ${styles.label}`}>Data sources &amp; licenses</p>
  <div className={styles.grid}>
    <div>
      <p className={styles.colHeading}>Catalog vote (5 databases)</p>
      <ul className={styles.list}>
        <li>UniProt — CC BY 4.0 (UniProt Consortium)</li>
        <li>Gene Ontology — CC BY 4.0 (The Gene Ontology Consortium)</li>
        <li>Human Protein Atlas — CC BY 4.0 (HPA, Uhlén et al. 2015)</li>
        <li>SURFY — academic research use (Bausch-Fluck et al. 2018)</li>
        <li>CSPA — academic research use (Bausch-Fluck et al. 2015, 2018)</li>
      </ul>
    </div>
    <div>
      <p className={styles.colHeading}>Deterministic features</p>
      <ul className={styles.list}>
        <li>AlphaFold DB structures — {df.structure.license} ({df.structure.attribution})</li>
        <li>DeepTMHMM topology — {deeptmhmm} · DTU Health Tech (Hallgren et al. 2022)</li>
        <li>
          Ensembl Compara orthologs &amp; paralogs
          {comparaVersion ? ` — ${comparaVersion} ` : " — "}
          open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
        </li>
        <li>
          Schweke homo-oligomer atlas ({CITATIONS.schwekeHomomer.authorYear},{" "}
          <a href={pubmedUrl(CITATIONS.schwekeHomomer.pmid)} target="_blank" rel="noopener noreferrer">PMID {CITATIONS.schwekeHomomer.pmid}</a>, Cell)
        </li>
        <li>
          SURFACE-Bind binding-site scoring ({CITATIONS.surfaceBind.authorYear},{" "}
          <a href={pubmedUrl(CITATIONS.surfaceBind.pmid)} target="_blank" rel="noopener noreferrer">PMID {CITATIONS.surfaceBind.pmid}</a>, PNAS)
        </li>
      </ul>
    </div>
  </div>
</aside>
```

Trim the longer Schweke/SURFACE-Bind text from the original to keep both columns roughly balanced.

- [ ] **Step 3: Update CSS — 2-column grid + smaller font + mobile fallback**

Edit `DataSourcesFooter.module.css`. Replace the `.list` rule with:

```css
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 24px;
  margin-top: 8px;
}

.colHeading {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-text-secondary, #666);
  margin: 0 0 4px 0;
}

.list {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
}

.list li {
  margin-bottom: 4px;
}

@media (max-width: 600px) {
  .grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }
}
```

Keep the existing `.footer` and `.label` rules.

- [ ] **Step 4: Lint + build the viewer**

```bash
cd viewer && npm run lint && npm run build && cd ..
```

Expected: PASS.

- [ ] **Step 5: Manual visual check**

Start the dev server and visit a gene page:

```bash
cd viewer && npm run dev &
DEV_PID=$!
sleep 5
open http://localhost:3000/EGFR
sleep 30
kill $DEV_PID
```

(Or do this interactively — make sure the footer renders as 2 columns at desktop width and collapses to 1 column when the window narrows below ~600 px.)

- [ ] **Step 6: Run viewer tests**

```bash
cd viewer && npm test && cd ..
```

Expected: PASS. There's no existing test for DataSourcesFooter; the lint + build covers TS errors and the manual check covers visual layout.

- [ ] **Step 7: Run Python check (no impact expected)**

```bash
bash scripts/check-py.sh
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git commit -m "feat(viewer): extend DataSourcesFooter to cover catalog vote DBs (2-col)

The per-gene footer now lists all 10 data sources:
- Left column: catalog vote (UniProt, GO, HPA, SURFY, CSPA)
- Right column: deterministic features (AlphaFold DB, DeepTMHMM, Ensembl
  Compara, Schweke, SURFACE-Bind)

CSS Grid 1fr 1fr at ≥ 600px; single column below. Body font drops to 12px
so the footer doesn't dominate the page. Section heading: 'Data sources &
licenses'."
```

---

## Task 10: License hygiene — NOTICE.md, LICENSING.md, HPA label fix, pypdfium2

**Spec:** Section 5 (NOTICE + LICENSING) + Section 6 (pypdfium2).

**Files:**
- Create: `NOTICE.md` (repo root)
- Modify: `LICENSING.md`
- Modify: `src/accessible_surfaceome/sources/hpa.py` (three `CC-BY-SA-3.0` → `CC-BY-4.0`)
- Modify: `data/external/hpa_subcellular_location/download_traceability.json` (regenerate after source change)
- Modify: `data/processed/hpa/hpa_build_traceability.json` (regenerate after source change)
- Modify: `pyproject.toml` (drop pypdfium2 constraint)

- [ ] **Step 1: Write NOTICE.md**

Create `NOTICE.md` at repo root with the full skeleton from spec Section 5 (without JensenLab — already removed in Task 8):

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

- [ ] **Step 2: Expand LICENSING.md**

Read the current placeholder:

```bash
cat LICENSING.md
```

Replace its content with a per-source redistribution clause document. Section template:

```markdown
# Licensing & redistribution

This repository is MIT-licensed (see [LICENSE](LICENSE)). The MIT grant covers
the **code** in this repository. Data derived from third-party sources retains
the license of its origin; see [NOTICE.md](NOTICE.md) for the full source list.

## CC-BY-4.0 attribution requirements

UniProt, Gene Ontology, Human Protein Atlas, HGNC, AlphaFold DB are
CC-BY-4.0. Downstream users must attribute the source per the license URL.
Attribution is satisfied by the per-gene DataSourcesFooter in the viewer
and the NOTICE.md file.

## Academic / non-commercial use sources

The following sources permit academic research use; commercial use
requires permission from the upstream authors:

- CSPA (Bausch-Fluck et al. 2015, 2018)
- SURFY (Bausch-Fluck et al. 2018)
- DeepTMHMM (Hansen et al. 2022) — predictions are redistributed under
  this academic-use understanding
- SURFACE-Bind (Khakzad et al. 2024)

The derived `candidate_universe.tsv` is a composite incorporating
academic-use sources, so the composite inherits the academic-only
restriction for any field that is downstream of those sources. If your
use is commercial, contact the upstream authors for clarification.

## Fair use of evidence snippets

`viewer/public/data/surfaceome/*.json` records contain verbatim quotes
(20–100 words each) drawn from primary literature. Each is attributed to
its source publication (PubMed ID, author, year). Reproduction is
intended as scholarly annotation under fair use; quotes are short, used
for the purpose of commentary, and do not substitute for the original.

## Fonts

Manrope and Playfair Display are bundled under the SIL Open Font License
1.1 — see https://openfontlicense.org for terms.
```

- [ ] **Step 3: Fix the HPA license label**

```bash
grep -n "CC-BY-SA-3.0" src/accessible_surfaceome/sources/hpa.py
```

Expected: 3 lines. Edit each to `"CC-BY-4.0"`. Update the comment that says "License: CC-BY-SA-3.0." to read "License: CC-BY-4.0 (per https://www.proteinatlas.org/about/licence)."

- [ ] **Step 4: Regenerate the HPA traceability JSONs**

The traceability JSONs are produced by the HPA source `download` / `build` subcommands. Re-run them so the new license label is captured:

```bash
uv run python -m accessible_surfaceome.sources.hpa download
uv run python -m accessible_surfaceome.sources.hpa build
```

Expected: re-runs complete; the traceability JSONs now contain `"license": "CC-BY-4.0"`. Confirm:

```bash
grep -i "license" data/external/hpa_subcellular_location/download_traceability.json data/processed/hpa/hpa_build_traceability.json
```

Expected: all four `license` lines now say `CC-BY-4.0`.

- [ ] **Step 5: Drop pypdfium2 constraint from pyproject.toml**

```bash
grep -n "pypdfium2" pyproject.toml
```

Look for `constraint-dependencies = ["pypdfium2<5.9.0"]` under `[tool.uv]`. Remove that constraint (delete the whole `constraint-dependencies = [...]` line if pypdfium2 is the only entry; otherwise just remove the pypdfium2 string from the list).

- [ ] **Step 6: Refresh the lockfile**

```bash
uv lock
```

Expected: lockfile updates; pypdfium2 may move to a newer version. If a downstream check fails, restore the constraint and flag.

- [ ] **Step 7: Repo-wide grep for stale `CC-BY-SA-3.0` refs**

```bash
grep -rln "CC-BY-SA-3.0\|CC BY-SA 3.0\|CC-BY-SA 3.0" --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.next --exclude-dir=.venv --exclude-dir=archive --exclude-dir=superpowers . 2>/dev/null
```

Expected: empty (every occurrence fixed). If any remains in active code/docs, fix it in this commit.

- [ ] **Step 8: Run full test suite**

```bash
bash scripts/check-py.sh
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git commit -m "chore(licenses): NOTICE.md, expand LICENSING.md, HPA label fix, drop pypdfium2 cooldown

- NOTICE.md: new file enumerating every upstream source + license,
  split by catalog-vote vs deterministic-features.
- LICENSING.md: replace placeholder with per-source redistribution
  guidance, including academic-only callouts for CSPA / SURFY /
  DeepTMHMM / SURFACE-Bind.
- src/.../sources/hpa.py: CC-BY-SA-3.0 -> CC-BY-4.0 in three places
  (verified at https://www.proteinatlas.org/about/licence).
  Traceability JSONs regenerated.
- pyproject.toml: drop pypdfium2<5.9.0 supply-chain cooldown (elapsed)."
```

---

## Task 11: Update CLAUDE.md / AGENTS.md / hooks / CI for new script paths

**Spec:** Section 8 (commit #11).

**Files:**
- Modify: `CLAUDE.md` (every `scripts/<name>.py` ref → `scripts/<subdir>/<name>.py`)
- Modify: `AGENTS.md` (same)
- Modify: `.github/workflows/*.yml` (any leftover refs)
- Modify: `.githooks/*`, `.pre-commit-config.yaml`, `scripts/precommit` (any leftover refs)
- Modify: `src/accessible_surfaceome/**/*.py` (any `subprocess` calls referencing scripts)
- Modify: `tests/**/*.py` (any path constants)

Note: CI workflows + pre-commit refs were patched in Task 5 so the build stayed green. This task handles the remaining refs across docs + source.

- [ ] **Step 1: Enumerate refs**

```bash
grep -rn "scripts/\(audit_\|build_\|fetch_\|sync_\|upload_\|probe_\|paywall_\|triage_bench_db_\|zero_db_rescues\|db_vs_sonnet\|ensemble_vs_best\|gen_prompt_review\|apply_cf_edge\|export_mainbench\|augment_figure_tsvs\|export_whole_proteome\|embed_figure_gist\|run_topology\|run_deeptmhmm\|compute_paralog\)" --include="*.md" --include="*.py" --include="*.yml" --include="*.toml" --include="*.sh" --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.next --exclude-dir=.venv --exclude-dir=archive .
```

Expected: list of files with old paths. For each match, prefix the script name with the appropriate subdir:

| Pattern | New prefix |
|---|---|
| `audit_*`, `check_*`, `gen_prompt_review`, `update_version_fingerprints` | `scripts/audit/` |
| `build_*`, `fetch_*`, `compute_*`, `run_*_sweep`, `run_deeptmhmm_*` | `scripts/build/` |
| `sync_*`, `upload_*`, `run_v2_backfill_*` | `scripts/upload/` |
| `db_vs_sonnet_*`, `ensemble_vs_best_*`, `paywall_bot_block_compare`, `triage_bench_db_*`, `zero_db_rescues_*`, `embed_figure_gist_*` | `scripts/figures/` |
| `apply_cf_edge_rules`, `export_mainbench_to_tsv` | `scripts/cloud/` |
| `augment_figure_tsvs_*`, `export_whole_proteome_catalog_*` | `scripts/tsv-export/` |
| `probe_*` | `scripts/probes/` |

- [ ] **Step 2: Patch CLAUDE.md**

Open `CLAUDE.md`. For every match from step 1 that's in CLAUDE.md, replace the script path with the new subdir-prefixed path. Use `Edit` with `replace_all: true` per pattern where safe.

- [ ] **Step 3: Patch AGENTS.md**

Same as step 2 for `AGENTS.md`.

- [ ] **Step 4: Patch any source-code subprocess refs**

```bash
grep -rln "subprocess\..*scripts/" src/ tests/ 2>/dev/null
```

For each match, patch the path.

- [ ] **Step 5: Patch remaining markdown docs**

```bash
grep -rln "scripts/\(audit_\|build_\|fetch_\|sync_\|upload_\|probe_\|paywall_\|triage_bench_db_\|zero_db_rescues\|db_vs_sonnet\|ensemble_vs_best\|gen_prompt_review\|apply_cf_edge\|export_mainbench\|augment_figure_tsvs\|export_whole_proteome\|embed_figure_gist\|run_topology\|run_deeptmhmm\|compute_paralog\)" docs/ 2>/dev/null
```

Patch each. Skip `docs/plans/archive/` if any of the M1 / shipped plans there reference old paths — that's historical content.

- [ ] **Step 6: Final ref check**

```bash
grep -rn "scripts/\(audit_\|build_\|fetch_\|sync_\|upload_\|probe_\|paywall_\|triage_bench_db_\|zero_db_rescues\|db_vs_sonnet\|ensemble_vs_best\|gen_prompt_review\|apply_cf_edge\|export_mainbench\|augment_figure_tsvs\|export_whole_proteome\|embed_figure_gist\|run_topology\|run_deeptmhmm\|compute_paralog\)" --include="*.md" --include="*.py" --include="*.yml" --include="*.toml" --include="*.sh" --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.next --exclude-dir=.venv --exclude-dir=archive --exclude-dir=plans/archive .
```

Expected: empty.

- [ ] **Step 7: Run all the gates**

```bash
bash scripts/check-py.sh
cd viewer && npm run build && cd ..
uv run python scripts/audit/gen_prompt_review.py
```

Expected: PASS, PASS, PASS.

- [ ] **Step 8: Commit**

```bash
git commit -m "chore: update CLAUDE.md / AGENTS.md / hooks / CI for new script paths

Sweep every scripts/<name>.py reference in:
- CLAUDE.md, AGENTS.md
- docs/ (excluding plans/archive/ which is historical)
- src/ subprocess calls
- tests/ path constants

to the new scripts/{audit,build,upload,figures,cloud,tsv-export,probes}/
layout from Task 5. CI workflows + pre-commit refs were already patched
in Task 5 to keep the build green during the rename."
```

---

## Task 12: README scientist-facing quick-start + nav rework

**Spec:** Section 4.

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read current README around line 17**

```bash
head -30 README.md
```

Find the line right after the headline philosophy paragraph and before `## Why this exists`.

- [ ] **Step 2: Insert Quick start block**

Insert before `## Why this exists`:

````markdown
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

````

- [ ] **Step 3: Sweep remaining script-path references in README**

The README mentions several specific scripts. Update each path to its new subdir:

```bash
grep -n "scripts/" README.md
```

Patch each match per the table in Task 11 step 1.

- [ ] **Step 4: Add NOTICE.md callout in the License section**

Find the License section near the bottom of the README. Add a line:

```markdown
See [NOTICE.md](NOTICE.md) for upstream-data attribution and [LICENSING.md](LICENSING.md) for redistribution guidance.
```

- [ ] **Step 5: Run gates**

```bash
bash scripts/check-py.sh
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git commit -m "docs(readme): scientist-facing quick-start + nav rework

- New Quick start block above the fold: viewer URL, API curl example,
  Zenodo DOI, figure-gist instructions, single-gene + cohort run
  commands.
- Updated remaining scripts/<name>.py refs to the new
  scripts/{audit,build,...}/ subdir layout.
- Added NOTICE.md + LICENSING.md callouts near the License section."
```

---

## Task 13: Push and open the PR

**Files:** none modified; this is the handoff.

- [ ] **Step 1: Confirm commit count and order**

```bash
git log --oneline main..HEAD
```

Expected: 12 commits, in the order from spec Section 8 (forensic deletes → data deletes → data archive → script archive → script regroup → viewer cleanup → cloudflare clarify → JensenLab → DataSourcesFooter → licenses → ref updates → README).

- [ ] **Step 2: Last-pass green check**

```bash
bash scripts/check-py.sh
cd viewer && npm run lint && npm run build && cd ..
```

Expected: PASS, PASS.

- [ ] **Step 3: Push**

```bash
git push -u origin claude/quizzical-darwin-8923eb
```

- [ ] **Step 4: Create PR**

```bash
gh pr create --base main --title "chore: repo cleanup for v0 release" --body "$(cat <<'EOF'
## Summary

Cleanup pass to prepare \`accessible-surfaceome\` for public open-source
release as both a paper companion and a reusable codebase.

12 logically-separate commits, CI green per commit, bisectable.

## What changed

| Commit | Topic |
|---|---|
| 1 | Remove stale forensic audits + v1 plans + Cloudflare Pages marker |
| 2 | Remove superseded data dumps and backups |
| 3 | Archive completed one-shot data outputs to \`data/archive/\` |
| 4 | Archive 31 completed one-shot scripts to \`scripts/archive/\` |
| 5 | Regroup production scripts into \`scripts/{build,upload,figures,audit,cloud,tsv-export,probes}/\` |
| 6 | Drop orphan viewer/app/homomer-demo routes; ignore \`.zed/\` |
| 7 | Clarify \`cloudflare/d1_compara_schema.sql\` is reference-only |
| 8 | Remove JensenLab COMPARTMENTS (not in 5-DB vote) |
| 9 | Extend viewer DataSourcesFooter to cover catalog vote DBs (2-col) |
| 10 | NOTICE.md, expanded LICENSING.md, HPA label fix, drop pypdfium2 cooldown |
| 11 | Update CLAUDE.md / AGENTS.md / hooks / CI for new script paths |
| 12 | README scientist-facing quick-start + nav rework |

## Design doc

[docs/superpowers/specs/2026-06-25-repo-cleanup-for-release-design.md](docs/superpowers/specs/2026-06-25-repo-cleanup-for-release-design.md)

## What reviewers should verify

- [ ] CI passes
- [ ] Viewer builds and the gene page renders with the new 2-column DataSourcesFooter
- [ ] \`uv run python scripts/build/build_candidate_universe_v3.py\` produces a TSV with **no** \`compartments_*\` columns
- [ ] CLAUDE.md / AGENTS.md command paths all resolve to existing files
- [ ] Figure scripts under \`scripts/figures/\` still match their \`data/analysis/figures/make_*.py\` mirrors (per the layout-fingerprint guard test)
- [ ] No broken links in README's Quick start

EOF
)"
```

- [ ] **Step 5: Report the PR URL back**

The `gh pr create` command prints the URL. Report it.

---

## Self-Review

### Spec coverage

| Spec section | Plan task |
|---|---|
| §1 deletes — data | Task 2 |
| §1 deletes — docs | Task 1 |
| §1 deletes — root + viewer | Task 6 |
| §2 archive — data | Task 3 |
| §2 archive — docs/plans + docs/archive | Task 1 (folded with stale-docs deletes since same commit topic) |
| §2 archive — scripts | Task 4 |
| §3 scripts regroup | Task 5 |
| §4 README | Task 12 |
| §5 license hygiene — NOTICE, LICENSING, HPA | Task 10 |
| §5 viewer DataSourcesFooter extension | Task 9 |
| §6 small cleanups — pypdfium2 | Task 10 |
| §6 small cleanups — .zed | Task 6 |
| §6 small cleanups — cloudflare header | Task 7 |
| §7 JensenLab removal | Task 8 |
| §8 execution sequencing → 12 commits | Tasks 1–12 |
| Push + PR creation | Task 13 |

**Gap found and fixed:** spec §2's `docs/plans/archive/` + `docs/archive/` moves are now folded into Task 1 (steps 5-6) since they share the "stale-docs cleanup" commit topic.

### Placeholder scan

- No "TBD" / "TODO" / "fill in" markers.
- Step 3 of Task 5 (per-subdir READMEs) gives the `scripts/build/` template inline and only describes the others — that's borderline; the executing engineer must adapt the template per subdir. Acceptable: the template is concrete and the variations are one-line shifts in topic.
- Task 8 Step 4 prompt edits don't show the exact prompt text to remove (because the prompt files are too long to inline). Acceptable: the engineer must grep, read, and decide what to cut — they have the tool to do that.

### Type / signature consistency

- The DataSourcesFooter rewrite in Task 9 uses `df.structure.license`, `df.structure.attribution`, `df.orthologs.mouse[0]?.compara_version`, `df.paralogs[0]?.compara_version`, `df.canonical_topology.tool_version`, and `CITATIONS.schwekeHomomer` / `CITATIONS.surfaceBind` — these all exist today per the file I read at the start. After JensenLab removal in Task 8, none of these are affected.
- The `n_db_votes` formula stays unchanged in Task 8 because JensenLab wasn't in it.

