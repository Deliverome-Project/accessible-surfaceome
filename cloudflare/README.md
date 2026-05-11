# Cloudflare integrations

## surfaceome_agents — D1 database for reproducible agent runs

A separate D1 database from the existing `signups` one on the Deliverome
Pages project. Holds BOTH:

- **`triage_run`** — one row per `surface_triage` agent call (model ×
  prompt-variant × replicate × gene) with full reproducibility metadata:
  the prompt SHA, the benchmark version, the schema version, and the
  agent's full `verdict_reasoning` prose.
- **`deep_dive_run`** plus its child tables `deep_dive_evidence` and
  `deep_dive_search_log` — one row per `surface_annotator` invocation
  with the full `SurfaceomeRecord` payload, every Evidence claim, and
  every SearchEntry from the agent's tool-use trace.

One DB instead of two because the most valuable analytics are cross-
table joins (the `triage_vs_deep_dive` view): "what did the deep dive
find for proteins the triage flagged contextual at high cost?". This
also conserves Pages D1-binding slots (free plan caps at 5/project).

### Provisioning (one-time, from your local machine)

You need the Cloudflare account at
[dash.cloudflare.com/8e7d57ba080f9fec53b320a1b9449b18](https://dash.cloudflare.com/8e7d57ba080f9fec53b320a1b9449b18)
with `wrangler` available. Wrangler is pinned at the repo root via
`/package.json` — run `npm ci` from the repo root to install it under
`node_modules/.bin/wrangler`, and prefix calls with `npx --yes wrangler ...`
so the pinned version always wins over any global install. (CI runs
`npm ci` in `.github/workflows/d1-backup.yml` the same way.)

```sh
# 1. Log in (opens a browser to the Cloudflare auth flow).
npx --yes wrangler login

# 2. Create the database — captures the database UUID.
npx --yes wrangler d1 create surfaceome_agents
#   ┌─────────────────────────────────────────────┐
#   │ name = "surfaceome_agents"                     │
#   │ database_id = "xxxxxxxx-xxxx-xxxx-xxxx-..." │   ← save this
#   └─────────────────────────────────────────────┘

# 3. Apply the schema to the remote DB.
npx --yes wrangler d1 execute surfaceome_agents \
    --remote \
    --file=cloudflare/d1_schema.sql

# 4. Sanity-check that the tables exist.
npx --yes wrangler d1 execute surfaceome_agents --remote --command \
    "SELECT name FROM sqlite_master WHERE type='table';"
#   Expected: prompt_version, benchmark_version, triage_run, sqlite_sequence
```

### Bind the new D1 to the Deliverome Pages project

In the Cloudflare dashboard:

1. Navigate to the project
   ([Pages → deliverome → Settings → Bindings → Production](https://dash.cloudflare.com/8e7d57ba080f9fec53b320a1b9449b18/pages/view/deliverome/settings/production)).
2. Under **D1 database bindings**, click **Add binding**.
3. Variable name: `SURFACEOME_AGENTS` — short, parallels the existing `SIGNUPS`
   binding, and stays accurate once deep-dive tables share this DB.
4. D1 database: pick `surfaceome_agents` from the dropdown.
5. Repeat under the Preview tab if you want the same binding in preview deploys.

The signups DB stays untouched — these are two independent bindings.

### Environment variables for the Python uploader

The uploader in `src/accessible_surfaceome/cloud/d1_client.py` posts
directly to D1's HTTP API (not via a worker), so it needs:

```sh
# Account UUID — same hex that appears in the dashboard URL.
CLOUDFLARE_ACCOUNT_ID=8e7d57ba080f9fec53b320a1b9449b18

# UUID returned by `npx --yes wrangler d1 create surfaceome_agents` above.
CLOUDFLARE_D1_SURFACEOME_AGENTS_ID=<uuid-from-step-2>

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

Six tables and three views (see `d1_schema.sql` for the canonical
definition):

| table | rows | purpose |
|---|---|---|
| `prompt_version` | per unique prompt SHA | content-addressed prompt snapshots; editing a prompt creates a new row |
| `benchmark_version` | per (bench_version, gene_symbol) | point-in-time ground-truth labels |
| `triage_run` | per `surface_triage` API call | every replicate, full telemetry + `verdict_reasoning` |
| `deep_dive_run` | per `surface_annotator` invocation | full `SurfaceomeRecord` JSON + denormalised headline / counts |
| `deep_dive_evidence` | per Evidence claim | source DB, URL, verbatim span, claim_kind — joins to `deep_dive_run` |
| `deep_dive_search_log` | per SearchEntry | every tool consultation in order |

| view | purpose |
|---|---|
| `triage_cell_summary` | pre-aggregated per-cell triage accuracy + cost |
| `deep_dive_latest` | most-recent `deep_dive_run` per gene (collapses replicates) |
| `triage_vs_deep_dive` | every triage call joined to the latest deep dive for that gene |

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
npx --yes wrangler d1 time-travel info surfaceome_agents

# Restore to a specific point in time (ISO 8601 timestamp).
npx --yes wrangler d1 time-travel restore surfaceome_agents \
    --timestamp '2026-05-10T20:00:00Z'

# Or by bookmark id (returned from the info call).
npx --yes wrangler d1 time-travel restore surfaceome_agents --bookmark <bookmark-id>
```

Restore is destructive — the database is rewound to the chosen point and
everything after is lost. For most accidents this is what you want.

### Layer 2 — Periodic SQL exports (belt-and-suspenders)

Snapshot the database to a portable SQL file:

```sh
bash scripts/d1_triage_backup.sh
```

This runs `npx --yes wrangler d1 export` and writes
`data/processed/cloudflare/d1_backups/surfaceome_agents_<UTC-timestamp>.sql`
plus a sha256 companion file. Re-import a dump with:

```sh
npx --yes wrangler d1 execute surfaceome_agents --remote \
    --file=data/processed/cloudflare/d1_backups/surfaceome_agents_20260510T200000Z.sql
```

Run the export weekly (or before any schema migration) to keep an
offline-grep-able trail beyond the Time Travel window.

### Layer 2.5 — Automated SQL exports → R2 bucket (CI-driven)

The GitHub workflow `.github/workflows/d1-backup.yml` triggers
`scripts/d1_export_to_r2.sh` on every push to `main` that touches:

- `cloudflare/d1_schema.sql` (schema changes)
- `data/eval/triage_subbench_v1/**` (new triage run records)
- `data/annotations/**` (new deep-dive records)
- `data/triage/**` (production triage outputs)
- `src/accessible_surfaceome/cloud/**` (uploader code)
- `scripts/upload_triage_runs_to_d1.py` / `d1_export_to_r2.sh`

Each run produces an offsite SQL dump in the R2 bucket
`deliverome-d1-backups` under the dated key
`d1-backups/surfaceome_agents/<YYYY>/<MM>/surfaceome_agents_<UTC>.sql`
and updates the stable pointer `d1-backups/surfaceome_agents/latest.sql`.
A small JSON manifest (sha256 + byte count) lands next to each dump for
integrity checks.

**One-time R2 setup** (run locally with `wrangler`):

```sh
# Create the R2 bucket the CI workflow targets.
npx --yes wrangler r2 bucket create deliverome-d1-backups

# Set repo secrets in GitHub Settings → Secrets and variables → Actions:
#   CLOUDFLARE_API_TOKEN   — scoped to D1:Edit + R2:Edit
#   CLOUDFLARE_ACCOUNT_ID  — same hex as the dashboard URL
```

Manual trigger from your local machine:

```sh
bash scripts/d1_export_to_r2.sh            # CI mode: dump → R2, no local copy
bash scripts/d1_export_to_r2.sh --keep-local  # also keep a local file
```

Inspect / restore from R2:

```sh
# List recent dumps.
npx --yes wrangler r2 object list deliverome-d1-backups --prefix d1-backups/surfaceome_agents/

# Pull the latest pointer locally.
npx --yes wrangler r2 object get deliverome-d1-backups \
    d1-backups/surfaceome_agents/latest.sql \
    --output ./latest.sql

# Re-import into D1 (DESTRUCTIVE — wipes current tables before applying).
npx --yes wrangler d1 execute surfaceome_agents --remote --file=./latest.sql
```

R2 is durable, cross-region, and outside the Time Travel window — this
is the layer that protects against an account-level disaster.

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
| Any commit touching D1 paths | **CI automatically runs `d1_export_to_r2.sh`** (see `.github/workflows/d1-backup.yml`) — fresh dump lands in R2 with a dated key + `latest.sql` pointer |
| Before schema migration | run `d1_triage_verify.py`, `d1_triage_backup.sh`, migrate, verify again |
| After noticing weirdness | run `d1_triage_verify.py` first |
| Catastrophic D1 loss | restore from `r2://deliverome-d1-backups/d1-backups/.../latest.sql`, then re-run uploader for any post-backup runs (on-disk JSON is the deeper-than-D1 canonical source) |
