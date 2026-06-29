# Deep-dive Modal run — operator runbook

How to drive the `surfaceome_v2` deep-dive across the candidate universe on
Modal: an **incremental, resumable campaign** you launch repeatedly (25 → 100 →
1000 → full) without ever re-spending on a gene that already completed.

This is the living how-to. For the app internals see
[`modal/README.md`](../../modal/README.md); for one-time setup (modal client,
auth, secret, Volume) follow its **One-time setup** section first.

---

## TL;DR — the whole campaign

Pick **one `run_id` for the entire campaign** and reuse it every launch. The
canonical full-run cohort is
[`data/processed/candidate_universe/candidate_universe_v3.tsv`](../../data/processed/candidate_universe/candidate_universe_v3.tsv)
(5,105 genes).

```bash
RUN=cu_v3_sonnet_2026_06
LIST=data/processed/candidate_universe/candidate_universe_v3.tsv

# 0. Preflight ($0 — no model calls, no spend)
uv run modal run modal/deep_dive_app.py::check_secret          # secret has all 7 keys?
uv run modal run modal/deep_dive_app.py::rate_limit_smoke      # central rate gate works?

# 1. Validation canary — 25 stratified genes, cost projection, search_log tripwire
uv run modal run modal/deep_dive_app.py::canary \
    --gene-list "$LIST" --run-id "$RUN" --n 25 --max-cost-per-gene-usd 5

# 2. Incremental batches — same run_id, bump --limit. Each launch auto-skips
#    everything already done at the current schema (any run_id) + quarantined genes.
uv run modal run modal/deep_dive_app.py::full_sweep --gene-list "$LIST" --run-id "$RUN" --limit 100
uv run modal run modal/deep_dive_app.py::full_sweep --gene-list "$LIST" --run-id "$RUN" --limit 1000

# 3. The rest — drop --limit (chunked, with the $18k total-cost circuit breaker)
uv run modal run modal/deep_dive_app.py::full_sweep --gene-list "$LIST" --run-id "$RUN"
```

**You never have to track what's done by hand.** Re-launching is always safe:
the dispatch filter skips any gene with a completed record at the current
`schema_version`. Stopped overnight, crashed, cost-capped — just launch the same
command again and it picks up where it left off.

---

## The dedup model (why re-launching is safe)

A gene is **skipped at dispatch** if either:

1. **Already complete at the current schema** — it has a `deep_dive_run` row at
   the current `schema_version`, in **any** `run_id`. (`deep_dive_run` rows exist
   only for genes whose record validated, so presence == success.) This is
   *global* and *schema-aware*:
   - **Global** → re-launching under a different batch tag never re-spends.
   - **Schema-aware** → bumping the schema (e.g. `2.14.1` → `2.15.0`) re-opens
     every stale gene for a fresh run automatically.
2. **Quarantined** — it blew the per-gene cost cap on a prior attempt
   (`cost_ceiling_pts` / `cost_ceiling_total`). Over-cap genes are **never
   auto-resumed**; they're surfaced for manual review (see *Cost controls*).

Overrides:

| Flag | Effect |
|---|---|
| `--force` | Bypass the schema-aware dedup — re-run already-complete genes (**re-spends**). Use to deliberately refresh. |
| `--include-quarantined` | Re-dispatch over-cap genes (do this only after raising the ceiling on purpose). |
| `--limit N` | Process at most N of the *remaining* genes this launch — the batch-size knob. |

> **Use one `run_id` per campaign.** The dedup is global, so a typo'd run_id
> won't cause re-spend — but a stable run_id keeps `deep_dive_run`, the
> quarantine scope, and the census all joined cleanly.

---

## Tracking progress

**Quick count (mid-run, no Volume pull needed)** — query private D1:

```sql
-- done so far at the current schema (across all run_ids):
SELECT COUNT(*) FROM deep_dive_run WHERE schema_version = '2.14.1';
-- this campaign only:
SELECT COUNT(*) FROM deep_dive_run WHERE run_id = 'cu_v3_sonnet_2026_06';
-- quarantined (need manual review):
SELECT gene_symbol, failure_mode FROM agent_run_intermediates
WHERE failure_mode IN ('cost_ceiling_pts','cost_ceiling_total');
```

`full_sweep` also prints `completed / failed / d1_failed / cost_capped /
running_cost` every 50 genes.

**Full cross-surface reconciliation** — pull the Volume first, then run the
census (per-gene status across Volume JSON + private D1 + public D1 +
quarantine):

```bash
uv run modal volume get surfaceome-annotations / data/annotations/
uv run python scripts/deep_dive_census.py \
    --run-id cu_v3_sonnet_2026_06 \
    --gene-list data/processed/candidate_universe/candidate_universe_v3.tsv \
    --annotations-dir data/annotations
```

Census exit codes: `0` all ok · `1` drift (must repair) · `2` incomplete/quarantined
(resume). Statuses: `ok`, `missing`, `quarantined`, and drift classes
(`private_missing`, `public_missing`, `public_stale`, `orphan_children`,
`json_missing`).

> Mid-run, prefer the D1 count. The census's Volume-JSON check needs `modal
> volume get` first — without it, it mis-reports completed genes as
> `json_missing`.

---

## Where each gene lands (the four surfaces)

Per gene, a successful run writes:

1. **Modal Volume JSON** — `surfaceome-annotations:<run_id>/<symbol>.json` (the
   canonical artifact; pull with `modal volume get`).
2. **Private D1** `deep_dive_run` (+ `deep_dive_evidence` / `deep_dive_search_log`
   children) — the "what's done" ledger.
3. **Public D1** `surface_annotation` — what the Worker serves to the viewer.
4. (The committed `viewer/public/data/*.json` snapshot is **not** written per-run
   — public D1 is the live source; snapshots are regenerated at release
   checkpoints only.)

All four writes are best-effort and degrade safely — a D1 hiccup logs and
continues, never crashing the sweep.

---

## Cost controls

| Knob | Default | What it caps |
|---|---|---|
| `--max-cost-per-gene-usd` | `$10` | Per-gene total. A gene exceeding it aborts → **quarantined**. |
| *(internal)* PTS sub-cap | `$5` | The plan-trim-select phase. A runaway gene aborts **before** the expensive builders, and is quarantined (`cost_ceiling_pts`). |
| `--max-total-cost-usd` | `$18000` | `full_sweep` only — a chunked circuit breaker. Drains the current chunk, then aborts between chunks if running cost exceeds it. Bounded overshoot ≤ `chunk_size × max_cost_per_gene_usd`. |

`canary` has **no** total cap — its budget is implicitly `n × max_cost_per_gene_usd`
(25 × $5 ≈ $125 worst case). Use `--max-cost-per-gene-usd 5` on the validation
canary to tighten.

The full cohort (5,105 genes × ~$2–3) ≈ **$10–15k**, under the $18k default.

---

## Resume & recovery

**Automatic resume (the common case):** just re-launch with the same `run_id`.
Completed genes are skipped (dedup); a gene that crashed mid-build resumes from a
durable **PTS checkpoint** in `agent_run_intermediates` — it rebuilds the
plan-trim-select dual without re-paying for it (~67% of per-gene cost). Over-cap
genes are quarantined and skipped.

**JSON landed but private D1 row didn't** (rare — JSON write succeeded, D1 parent
insert failed entirely): resume wouldn't see the gene and a rerun could
re-spend. Backfill the parent from JSON:

```bash
uv run modal volume get surfaceome-annotations / data/annotations/
uv run python scripts/backfill_deep_dive_from_json.py --run-id cu_v3_sonnet_2026_06          # dry-run
uv run python scripts/backfill_deep_dive_from_json.py --run-id cu_v3_sonnet_2026_06 --execute
uv run python scripts/audit_deep_dive_orphans.py     --run-id cu_v3_sonnet_2026_06 --execute  # repair child rows
```

**Public D1 / viewer drift:** if the census reports `public_missing` /
`public_stale`, re-publish from the pulled snapshots:

```bash
uv run python scripts/upload_viewer_snapshots_to_d1.py --execute   # pushes + purges edge cache
```

---

## Post-run validation

```bash
# 1. Reconcile every surface (see Tracking → census).
# 2. Content drift check against the curated validation genes (needs .env):
uv run pytest -q tests/test_pipeline_validation_genes.py
# 3. Backfill the n_papers_found discovery signal on committed snapshots (no LLM):
uv run python scripts/backfill_n_papers_found.py --execute
uv run python scripts/upload_viewer_snapshots_to_d1.py --execute
```

---

## Concurrency tuning

Fan-out is sized to keep Anthropic **OTPM (2M output tok/min)** under its ceiling
— *not* to max raw container count. The default is ~64 concurrent genes (down
from a naive 800, which would churn 429s). All env-tunable on the driver at
launch:

| Env var | Default | Meaning |
|---|---|---|
| `SURFACEOME_MAX_CONTAINERS` | OTPM-derived (~64) | Max worker containers. |
| `SURFACEOME_MAX_INPUTS` | `1` | Concurrent genes per container. Total = containers × inputs. |
| `SURFACEOME_PER_GENE_OUTPUT_TOKENS` | `90000` | Per-gene output estimate that drives the recommendation. |
| `SURFACEOME_GENE_WALL_S` | `300` | Per-gene wall-clock estimate. |

Each launch prints `concurrency: N genes in flight … projected OTPM ≈ X.XM /
2M`. If that's near 100%, dial `SURFACEOME_MAX_CONTAINERS` down. Setting only
`MAX_INPUTS` won't blow the budget — containers auto-derive so the *total* stays
within the OTPM-safe recommendation (an explicit `MAX_CONTAINERS` over the limit
is honored but warns).

The cross-container courtesy rate limiting (NCBI per-key, Europe PMC, PubTator,
Unpaywall/DataCite/Crossref) runs through the central `rate_limit_gate`; validate
it with `rate_limit_smoke` after any Modal-plumbing change.

---

## Entrypoint / flag reference

| Entrypoint | Purpose | Key flags |
|---|---|---|
| `check_secret` | $0 secret-presence preflight | — |
| `rate_limit_smoke` | $0 central rate-gate check | `--n`, `--interval-s`, `--worker` |
| `canary` | Stratified validation sample + cost projection | `--n`, `--max-cost-per-gene-usd`, `--force` |
| `full_sweep` | Incremental / full campaign | `--limit`, `--max-cost-per-gene-usd`, `--max-total-cost-usd`, `--chunk-size`, `--include-quarantined`, `--force` |

Local in-process equivalent (no Modal account, for smoke tests):
`scripts/deep_dive_sweep.py --gene-list … --run-id … --canary 3 --no-d1`
(supports the same `--limit` / `--force` / `--include-quarantined`).
