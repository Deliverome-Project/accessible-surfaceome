# `scripts/`

Standalone data builders, figure generators, audits, D1/edge tooling, probes,
TSV exporters, and the release ritual. The few real **entry points** live at the
top level; everything else is grouped into subdirectories by role. Run any script
with `uv run python scripts/<subdir>/<name>.py` (shell scripts with `bash`).

## Entry points (top level)

| Script | What it does |
|---|---|
| `surfaceome_v2_annotate.py <GENE>` | Deep-dive one gene end-to-end (publishes to D1). |
| `triage_runner.py --model … --d1` | Run the triage benchmark / genome-wide sweep. |
| `build_candidate_universe_v3.py` | Rebuild the M1 candidate universe from the five sources. |
| `build_figure_tsvs.py` | Single source of truth for figure DATA — the per-figure bundled TSVs. |
| `build_figure_index.py` | Rebuild `paper/figure_index.md` + the by-paper-number symlinks. |
| `build_positive_control_lists.py` | Rebuild the ADC / TCE / ViralZone positive-control sets. |
| `check-py.sh` | Local CI gate (ruff + ty + compile + pytest + viewer-types sync). |
| `check_viewer_types_sync.py` | TS↔Pydantic drift check; wired into `check-py.sh` + pre-commit (kept at root by design). |
| `bootstrap-worktree.sh`, `setup-git-hooks.sh` | Dev-environment setup. |

## Subdirectories

| Dir | What's here |
|---|---|
| `figures/` | Canonical figure generators — one `figures/<slug>.py` per published figure, each mirrored by `data/analysis/figures/make_<slug>.py` (kept in lockstep by [`tests/test_figure_canonical_mirror_sync.py`](../tests/test_figure_canonical_mirror_sync.py)). Also the figure tooling: `augment_figure_tsvs_with_stable_ids.py`, `embed_figure_gist_metadata.py`, `sync_figure_gists_bundle_data.py`, `sync_figure_gists.sh`, and the multi-figure `triage_bench_*` generators. |
| `build/` | Dataset / table builders and the topology + deep-dive sweep drivers (`build_*`, `fetch_*`, `run_topology_sweep.py`, `deep_dive_sweep.py`, `compute_paralog_ecd_similarity.py`, `gen_prompt_review.py`, `update_version_fingerprints.py`, `refresh_compara.sh`). |
| `cloud/` | D1 upload/sync + Cloudflare edge (`upload_*_to_d1.py`, `sync_*.py`, `apply_cf_edge_rules.py`, `d1_export_to_r2.sh`, `d1_triage_backup.sh`, the Schweke ingestion trio, and the live D1 repair tools). |
| `audit/` | Validation and diagnostics (`audit_*`, `check_schema_freshness.py`, `check_triage_coverage.py`, `deep_dive_census.py`, `plan_trim_select_*`, `surfaceome_v2_replay_*`). Mostly $0, no model calls. |
| `probes/` | Fetch / paywall / cache / OA / TTFB diagnostics (`probe_*`, `paywall_bot_block_overview.py`, `ttfb_check.py`, and the probe HTML renderers). |
| `tsv-export/` | TSV exporters for benchmark + feature tables (`export_*`). |
| `release/` | Citable-snapshot release ritual — see [`release/README.md`](release/README.md). |
| `precommit/` | Local pre-commit hook scripts (`forbid_env_files.sh`, `scan_secrets.py`). |
| `archive/` | Finished one-shot migrations, backfills, and fixes — already run, kept for provenance. Not expected to be re-run; internal `scripts/<name>` paths inside archived shells may be stale. |

## Canonical generator ↔ gist mirror

Every published figure has two source files: the canonical generator
`scripts/figures/<slug>.py` (project `_plotting_config` styling, reads in-repo
TSVs / D1) and the standalone gist mirror `data/analysis/figures/make_<slug>.py`.
Edit **both in the same commit** — the layout/model drift guard in
[`tests/test_figure_canonical_mirror_sync.py`](../tests/test_figure_canonical_mirror_sync.py)
fails CI if they diverge. See CLAUDE.md "Canonical generator vs gist mirror".
