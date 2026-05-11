# Cloudflare integrations

## triage_results — D1 database for reproducible triage runs

A separate D1 database from the existing `signups` one on the Deliverome
Pages project. Stores one row per (model × prompt-variant × replicate × gene)
triage call with full reproducibility metadata: the prompt SHA, the
benchmark version, the schema version, and the agent's full
`verdict_reasoning` prose.

### Provisioning (one-time, from your local machine)

You need the Cloudflare account at
[dash.cloudflare.com/8e7d57ba080f9fec53b320a1b9449b18](https://dash.cloudflare.com/8e7d57ba080f9fec53b320a1b9449b18)
and `wrangler` installed (`npm i -g wrangler`).

```sh
# 1. Log in (opens a browser to the Cloudflare auth flow).
wrangler login

# 2. Create the database — captures the database UUID.
wrangler d1 create triage_results
#   ┌─────────────────────────────────────────────┐
#   │ name = "triage_results"                     │
#   │ database_id = "xxxxxxxx-xxxx-xxxx-xxxx-..." │   ← save this
#   └─────────────────────────────────────────────┘

# 3. Apply the schema to the remote DB.
wrangler d1 execute triage_results \
    --remote \
    --file=cloudflare/d1_triage_schema.sql

# 4. Sanity-check that the tables exist.
wrangler d1 execute triage_results --remote --command \
    "SELECT name FROM sqlite_master WHERE type='table';"
#   Expected: prompt_version, benchmark_version, triage_run, sqlite_sequence
```

### Bind the new D1 to the Deliverome Pages project

In the Cloudflare dashboard:

1. Navigate to the project
   ([Pages → deliverome → Settings → Bindings → Production](https://dash.cloudflare.com/8e7d57ba080f9fec53b320a1b9449b18/pages/view/deliverome/settings/production)).
2. Under **D1 database bindings**, click **Add binding**.
3. Variable name: `TRIAGE_RESULTS` (or whatever the worker code expects).
4. D1 database: pick `triage_results` from the dropdown.
5. Repeat under the Preview tab if you want the same binding in preview deploys.

The signups DB stays untouched — these are two independent bindings.

### Environment variables for the Python uploader

The uploader in `src/accessible_surfaceome/cloud/d1_client.py` posts
directly to D1's HTTP API (not via a worker), so it needs:

```sh
# Account UUID — same hex that appears in the dashboard URL.
CLOUDFLARE_ACCOUNT_ID=8e7d57ba080f9fec53b320a1b9449b18

# UUID returned by `wrangler d1 create triage_results` above.
CLOUDFLARE_D1_TRIAGE_ID=<uuid-from-step-2>

# API token with D1:Edit on this account. Create at
# https://dash.cloudflare.com/profile/api-tokens → "Custom token" →
# permissions: Account > D1 > Edit, scoped to your account.
CLOUDFLARE_API_TOKEN=<token>
```

Add these to your `.env` file at the repo root (template in `.env.example`).

### Uploading triage runs

After running `scripts/triage_subbench_runner.py` (or any future runner
that drops per-cell JSON records under `data/eval/triage_subbench_v1/`):

```sh
# Dry run — print what would be uploaded.
uv run python scripts/upload_triage_runs_to_d1.py --dry-run

# Actual upload, fresh run_id.
uv run python scripts/upload_triage_runs_to_d1.py

# Or tag the upload with a meaningful run_id so you can pivot on it later.
uv run python scripts/upload_triage_runs_to_d1.py --run-id 2026-05-10_subbench_haiku_sonnet
```

The uploader is idempotent on `(run_id, gene, model, variant, replicate,
prompt_sha)` — re-running with the same `--run-id` skips duplicates.

### Schema overview

Three tables and one view (see `d1_triage_schema.sql` for the canonical
definition):

| table              | rows | purpose                                                |
|--------------------|------|---------------------------------------------------------|
| `prompt_version`   | per unique prompt SHA | content-addressed snapshots; editing a prompt creates a new row |
| `benchmark_version`| per (bench_version, gene_symbol) | point-in-time ground-truth labels |
| `triage_run`       | per API call | every replicate, with full telemetry + prose reasoning |

| view                  | purpose                                  |
|-----------------------|------------------------------------------|
| `triage_cell_summary` | pre-aggregated per-cell accuracy + cost  |

Common queries:

```sql
-- Per-cell summary (the same data the local barplots show).
SELECT model, prompt_variant, n_runs, n_correct, verdict_accuracy,
       total_cost_usd, mean_web_searches
FROM triage_cell_summary
ORDER BY verdict_accuracy DESC;

-- Pull the agent's reasoning for every Sonnet web_naive error on this run_id.
SELECT t.gene_symbol, t.predicted_verdict, t.verdict_reasoning
FROM triage_run t
WHERE t.run_id = '2026-05-10_subbench_haiku_sonnet'
  AND t.model = 'claude-sonnet-4-6'
  AND t.prompt_variant = 'web_naive'
  AND t.correct = 0;

-- Find which proteins regressed when adding NCBI to web.
SELECT a.gene_symbol,
       a.predicted_verdict AS web_pred,
       b.predicted_verdict AS web_ncbi_pred,
       a.truth_verdict
FROM triage_run a
JOIN triage_run b
  ON a.gene_symbol = b.gene_symbol
 AND a.model = b.model
 AND a.replicate = b.replicate
 AND a.run_id = b.run_id
WHERE a.prompt_variant = 'web_naive' AND a.correct = 1
  AND b.prompt_variant = 'web_ncbi' AND b.correct = 0;
```

---

## Backups & disaster recovery

Three layers of protection, in increasing manual effort:

### Layer 1 — Cloudflare Time Travel (automatic)

D1's built-in point-in-time recovery is on by default for every D1
database, no configuration required. Workers Free retains **7 days**,
Workers Paid retains **30 days** of bookmarks (one every ~5 minutes).
This covers accidental DELETEs, table drops, schema mistakes, etc.

To list available restore points and restore:

```sh
# What bookmarks are available?
wrangler d1 time-travel info triage_results

# Restore to a specific point in time (ISO 8601 timestamp).
wrangler d1 time-travel restore triage_results \
    --timestamp '2026-05-10T20:00:00Z'

# Or by bookmark id (returned from the info call).
wrangler d1 time-travel restore triage_results --bookmark <bookmark-id>
```

Restore is destructive — the database is rewound to the chosen point and
everything after is lost. For most accidents this is what you want.

### Layer 2 — Periodic SQL exports (belt-and-suspenders)

Snapshot the database to a portable SQL file:

```sh
bash scripts/d1_triage_backup.sh
```

This runs `wrangler d1 export` and writes
`data/processed/cloudflare/d1_backups/triage_results_<UTC-timestamp>.sql`
plus a sha256 companion file. Re-import a dump with:

```sh
wrangler d1 execute triage_results --remote \
    --file=data/processed/cloudflare/d1_backups/triage_results_20260510T200000Z.sql
```

Run the export weekly (or before any schema migration) to keep an
offline-grep-able trail beyond the Time Travel window.

### Layer 3 — The on-disk JSON records (canonical source of truth)

D1 is a queryable mirror; the source of truth lives at
`data/eval/triage_subbench_v1/<model>/<variant>/<gene>_run<N>.json` for
every triage call we've ever made. These records are git-LFS-tracked
and committed.

If D1 is wiped catastrophically (lost auth, account closure, schema
corruption), recovery is a single command:

```sh
uv run python scripts/upload_triage_runs_to_d1.py \
    --run-id <whatever-tag-you-want-to-recover-under>
```

The uploader is idempotent on `(run_id, gene, model, variant, replicate,
prompt_sha)` — re-uploads skip duplicates, fresh runs go in.

To verify the on-disk records and D1 agree:

```sh
uv run python scripts/d1_triage_verify.py
```

This compares the union of all sweeps in D1 against every JSON record,
flags missing keys and predicted-verdict disagreements, and exits
non-zero if anything's out of sync.

### Suggested cadence

| event | action |
|---|---|
| After every triage sweep | run uploader — records auto-flow to D1 |
| Weekly | run `d1_triage_backup.sh` for offline SQL snapshot |
| Before schema migration | back up + verify, run migration, verify again |
| After noticing weirdness | run `d1_triage_verify.py` first |
| Catastrophic D1 loss | re-run the uploader; on-disk JSON is canonical |
