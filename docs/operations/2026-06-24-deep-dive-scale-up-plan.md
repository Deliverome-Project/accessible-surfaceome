# Deep-Dive Scale-Up Plan

Status as of 2026-06-24 after two Modal canaries under
`modal_smoke_v3_20260624_3gene`.

## Current Readiness

- Modal canary has run six genes successfully: `RYK`, `TMED10`, `VSIG10L`,
  `TMDD1`, `VOPP1`, `GABBR2`.
- Private D1 resume works for completed rows via `(run_id, gene_symbol)`.
- Modal Volume JSON writes work at `surfaceome-annotations/<run_id>/<symbol>.json`.
- Public D1 publish works; the six smoke records are visible through the Worker.
- Cloudflare targeted cache purge works after the API token scope update.
- Europe PMC `PPR...` preprint IDs no longer poison a whole result page; they are
  skipped until the downstream `Paper` contract supports non-PMID IDs.
- `scripts/audit_deep_dive_orphans.py` found zero orphan child rows for the smoke
  run.

## Remaining Gaps

### 1. Centralized External API Rate Limiting

Status: implemented in this branch; local tests and Modal smoke pass.

Implementation:

- `RateLimiter` now supports an external gate hook.
- `modal/deep_dive_app.py` installs a single-container `rate_limit_gate` inside
  each worker.
- NCBI key buckets are hashed before leaving the worker process, so raw API keys
  are not sent as Modal function arguments.

Validation:

```bash
uv run pytest -q tests/test_ratelimit.py
uv run modal run modal/deep_dive_app.py::rate_limit_smoke --n 4 --interval-s 0.2
```

### 2. Merge Local Fixes Before Production

Status: open.

Required changes currently in the working tree:

- Modal image-context ignore list (`.claude`, root `node_modules`, local caches).
- Centralized Modal rate gate.
- Europe PMC `PPR...` skip behavior and tests.
- JSON-to-private-D1 backfill for missing parent rows.

Do not launch a multi-day run from an unmerged local state.

### 3. Backfill From Modal Volume JSON When Private D1 Parent Rows Are Missing

Status: implemented in this branch.

Existing coverage:

- `scripts/audit_deep_dive_orphans.py` repairs parent rows whose evidence or
  search-log children are incomplete.
- `scripts/backfill_deep_dive_from_json.py` inserts missing private
  `deep_dive_run` parent + child rows from `<annotations_dir>/<run_id>/*.json`.

Command:

```bash
uv run modal volume get surfaceome-annotations / data/annotations/

uv run python scripts/backfill_deep_dive_from_json.py \
  --run-id candidate_universe_v3_sonnet_2026_06_stage1

uv run python scripts/backfill_deep_dive_from_json.py \
  --run-id candidate_universe_v3_sonnet_2026_06_stage1 \
  --execute
```

Residual caveat:

- The canonical JSON does not carry original spend/latency/tool-call totals.
  Missing rows backfilled without `--metadata-tsv` use zero for those fields.
  That preserves resume correctness but undercounts cost. If run metadata is
  available, pass a TSV with `gene_symbol`, `cost_usd`, `latency_s`, and
  `n_tool_calls`.
- The private D1 row records the current checkout's composite prompt SHA. Run
  JSON backfill before prompt edits, or from the same commit/image used for the
  sweep, so prompt provenance stays aligned.

### 4. Post-Run Public Publish And Intermediates Audit

Status: missing as a single command.

Private `deep_dive_run` success is not enough. A production run should also audit:

- every valid private row has `agent_run_intermediates` for the same
  `cohort_run_id`;
- every valid private row has a public `surface_annotation` row with matching
  `cohort_run_id`;
- Worker `/v1/genes` contains the expected symbols after cache purge.

### 5. Cost-Cap Overshoot

Status: operator-controlled.

`full_sweep` launches in chunks. Total-cost cap is checked between chunks, so
overshoot is bounded by roughly:

```text
chunk_size * max_cost_per_gene_usd
```

Use smaller chunks for staged scale-up:

```bash
--chunk-size 25
```

Increase only after observed spend and latency stabilize.

## Recommended Next Run

Use a fresh run id and a staged chunk:

```bash
uv run modal run modal/deep_dive_app.py::full_sweep \
  --gene-list data/processed/candidate_universe/candidate_universe_v3.tsv \
  --run-id candidate_universe_v3_sonnet_2026_06_stage1 \
  --max-cost-per-gene-usd 8 \
  --max-total-cost-usd 500 \
  --chunk-size 25
```

Post-run checks:

```bash
uv run python scripts/audit_deep_dive_orphans.py \
  --run-id candidate_universe_v3_sonnet_2026_06_stage1

uv run python scripts/backfill_deep_dive_from_json.py \
  --run-id candidate_universe_v3_sonnet_2026_06_stage1

uv run modal volume ls surfaceome-annotations \
  /candidate_universe_v3_sonnet_2026_06_stage1
```
