# Pre-cohort audit: R2 audit-offload + reproducibility/resume metadata

Date: 2026-06-08. Audience: whoever's launching the ~6,500-gene v2 cohort
sweep next week. Read-only investigation; no production code edits made.

## TL;DR

**R2 wiring.** The R2 client + slim-fallback's R2 upload exist on
`claude/flamboyant-varahamihira-9405b4` and `claude/abcb9-consistency-postpass`
(commit `cfb37efbf`, "feat: R2 audit offload …"). They are **not on the
current `claude/eloquent-cori-5b6b55` branch and not on `main`** — the
cohort run will silently skip R2 unless one of those branches is merged
first. Live D1 has 63 `agent_run_intermediates` rows; the heaviest is
TGOLN2 at 897 KB (99.7% of the 900 KB cap). The R2 path therefore hasn't
fired yet, but it *will* fire on the cohort for genes like TGOLN2, HMGB1,
GPR75, CD63, C3, TACSTD2 that hover near the cap. `r2_client.put_object`
works against the live bucket (synthetic 1 MB PUT/GET succeeded);
`r2_client.head_object` is **broken** — the REST endpoint returns 405 on
HEAD.

**Reproducibility metadata.** Most of what makes a run reproducible IS
saved somewhere, but it's spread across three D1 tables with no joining
key, and several load-bearing fields are missing:
* No `cohort_run_id` on `agent_run_intermediates` (you can't query "all
  rows from the cohort sweep" without a fragile timestamp-window query).
* **`deep_dive_sweep.py` does NOT call `publish_intermediates` at all**
  — the cohort's 6,500 intermediates blobs would never reach D1.
* No `code_sha` (git rev) — a bug-fix between two same-`prompt_corpus_version`
  runs is invisible.
* No `model_id` on intermediates (hardcoded `AGENT_MODEL =
  "claude-sonnet-4-6"`; if it changes, old rows look identical to new).
* No `api_response_id` / `api_model` capture per `messages.create`
  (`triage_run` has these columns but v2 doesn't populate them).
* No explicit `temperature` on any `messages.create` (defaults to 1.0,
  not captured).

**Priority for the cohort:** P0 = cherry-pick R2 + cost-ceiling
commits, add `cohort_run_id`, **wire intermediates into the sweep
driver**. P1 = `code_sha` + `model_id` + `failure_mode`. P2 = fix
`head_object` + API response capture.

---

## Part 1 — R2 audit

### 1. Does `r2_client.py` exist + does its surface match the plan?

**✓ on the planning branch, ✗ on current `main` + this worktree.**

`cfb37efbf:src/accessible_surfaceome/cloud/r2_client.py` (212 lines)
matches the commit description: REST API at
`https://api.cloudflare.com/client/v4/accounts/{id}/r2/buckets/{bucket}/objects/{key}`,
`R2Config.from_env()` reads only `CLOUDFLARE_ACCOUNT_ID` +
`CLOUDFLARE_API_TOKEN` (no new secrets), bucket default
`"deliverome-d1-backups"`, three public functions (`put_object`,
`head_object`, `intermediates_object_key`), never raises.

**Defect: `head_object`.** Cloudflare's REST endpoint for an object
does NOT accept HEAD. The synthetic probe (§4) shows `HTTP 405`. The
function returns `None` 100% of the time. Back-fill scripts that use
it to ask "did this gene's R2 blob land?" get the wrong answer. Replace
with `Range: bytes=0-15` GET or list-objects-with-prefix. Not blocking
for the cohort write path; blocking for post-mortem analytics.

### 2. Is it actually called from `intermediates.publish_intermediates`?

**✓ on `cfb37efbf`, ✗ on current HEAD.** Logic on cfb37: serialize →
if >900 KB then `r2_client.put_object` the FULL blob → slim D1-side via
`_slim_intermediates_for_d1` (drops PTS `search_log`/`triage_actions`/
`pretrim_audits`/`iteration_log`) → stitch `_r2_full_audit_key` +
`_r2_full_audit_bucket` markers into the slim blob → push slim to D1.
On R2 failure, write `_r2_full_audit_status="upload_failed"` instead.
Defensive: if slim still >900 KB, skip D1 push but R2 copy survives.

The wiring is clean. **It just isn't on the current branch.** HEAD's
`intermediates.py` is the pre-edf495 version (no slim, no R2): blobs
>900 KB fall through to "log warning + skip push" → audit blob lost.

### 3. On-disk shape of slim-path rows

Not yet observed: 0 rows on the slim path. Live D1 probe (against
production `surfaceome_agents`, 2026-06-08) returns 63 total rows. Top 5
by size:

| gene | bytes | prompt_corpus | created_at |
|---|---|---|---|
| TGOLN2 | 897,261 | 2.14.0 | 2026-06-07T23:51 |
| GPR75 | 840,555 | 2.16.0 | 2026-06-08T01:35 |
| CD63 | 784,764 | 2.35.0 | 2026-06-08T20:50 |
| C3 | 773,372 | 2.35.0 | 2026-06-08T20:51 |
| HMGB1 | 772,729 | 2.24.0 | 2026-06-08T03:27 |

TGOLN2 is at 99.7% of cap; on the cohort, expect 1–5% of genes
(proportional to literature density) to spill into R2.

### 4. Synthetic 1 MB probe

Ran inline against the prod bucket via the cfb37 endpoint shape:

```
Synthetic blob: 950,060 bytes
PUT  agent_run_intermediates/_PROBE_TGOLN2_DELETEME/.../...json → 200
HEAD → 405                            ← head_object would return None
GET  → 200 (950,060 bytes, round-trip OK, ['probe','filler','valid'])
DELETE → 200 (cleanup)
```

PUT works; the existing `CLOUDFLARE_API_TOKEN` has R2:Edit scope. GET
round-trips identically. HEAD is broken (§1).

### 5. Live R2 bucket scan

List `deliverome-d1-backups` with `prefix=agent_run_intermediates/`:
**0 objects.** Consistent with no D1 row having exceeded 900 KB and the
spillover code not being on the deployed branch.

### Part 1 fix list

| # | Fix | When |
|---|---|---|
| 1 | **Cherry-pick `cfb37efbf` + `edf495f86` onto the cohort branch.** Without these, the >900 KB genes (TGOLN2 class) lose their entire intermediates blob. | P0 — pre-cohort |
| 2 | After first cohort heavy gene lands, list `agent_run_intermediates/{gene}/` and confirm the slim D1 row carries the matching `_r2_full_audit_key`. | P1 — during cohort |
| 3 | Replace `head_object`'s HEAD with Range-GET. | P2 — post-cohort |

---

## Part 2 — Reproducibility / resume metadata audit

For each candidate field, grade is ✓ (saved properly), ⚠ (partially or
hard-to-query), or ✗ (not saved).

| Field | Grade | Notes |
|---|---|---|
| `prompt_corpus_version` (column) | ✓ | But only the *label*; see prompt_corpus_sha below. |
| `schema_version` (column) | ✓ | |
| `created_at` (column) | ✓ | |
| `record_valid` (column) | ✓ | |
| Full intermediates blob (PTS, builders, synth, risks, det_features) | ✓ | |
| `cost_total_usd`, `cost_per_pipeline` | ✓ | Post-edf495 only. |
| Per-step `timing` (with tokens, cost) | ⚠ | Written to `.runs/` but NOT into the D1 intermediates blob — lost on Modal shutdown. |
| `triage_summary_json` | ✓ | Post-edf495. |
| `bundle` (resolved identifiers) | ✓ | Post-edf495. |
| Per-builder `n_repair_attempts` | ✗ | Builders DO have a repair loop (`builders/_common.py:172`); count is silently discarded. |
| Synthesizer `n_repair_attempts` | ✓ | |
| `model_id` (e.g. `claude-sonnet-4-6`) | ⚠ | Hardcoded constant at `orchestrator.py:115`. `deep_dive_run.model` captures it for that table; intermediates row doesn't. |
| `api_model` (dated alias from `response.model`) | ✗ | `triage_run` has the column; v2 never populates. |
| `api_response_id` | ✗ | |
| `temperature` / `max_tokens` | ✗ | No `messages.create` call passes `temperature`; SDK default 1.0. Not captured. |
| `random_seed` | n/a | Anthropic SDK has no `seed` param. |
| `code_sha` (git rev) | ✗ | Bug-fix between same-prompt_corpus_version runs is invisible. |
| `prompt_corpus_sha` (fingerprint over all `.md` files) | ⚠ | `_version_guard.prompt_corpus_fingerprint()` computes it but doesn't persist it. Mismatched-vs-golden test catches drift at commit-time only. |
| `cohort_run_id` | ✗ | `publish_intermediates` has no `run_id` param. The single biggest gap. |
| `triage_source` (link back to the `triage_run` row) | ✗ | |
| `failure_mode` (structured: cost_ceiling / synth_no_draft / validation_failed / no_bundle) | ✗ | Free-text `error` only — string-match for cohort-level analytics is fragile. |
| PTS A1/A2 paper overlap | ✗ | Cheap set intersection; informs replay cost. |

### Critical gap: the cohort sweep driver doesn't publish intermediates

`scripts/deep_dive_sweep.py::annotate_one` (the cohort worker) writes
through `D1DeepDiveSink` only. It does NOT call
`publish_intermediates`. The intermediates path is exclusive to the
single-gene CLI driver `scripts/surfaceome_v2_annotate.py:146`. So:

* When the cohort sweep launches, **none of the ~6,500 intermediates
  blobs reach D1** — regardless of whether the R2 spillover is wired.
* The R2 audit is moot until the sweep also publishes intermediates.

This needs to be plumbed in: `annotate_one` should call
`publish_intermediates(gene_symbol=..., intermediates=result.intermediates,
schema_version=..., record_valid=..., cohort_run_id=run_id)` after the
sink insert.

### Cohort resume — what works today

`D1DeepDiveSink.already_done()` reads `deep_dive_run` by `(run_id,
gene_symbol)` and the worker skips rows in the existing set. Resume is
robust *for the surface_annotation records* but says nothing about the
intermediates blobs — those wouldn't be there to skip anyway (see
above). Once `publish_intermediates` is wired into the sweep, the same
`(cohort_run_id, gene_symbol)` SELECT-existing pattern should drive
intermediates resume too.

---

## Prioritized fix list

### P0 — block the cohort

1. **Cherry-pick `cfb37efbf` (R2 client + slim-fallback's R2 upload) and
   `edf495f86` (slim-fallback + cost ceiling + cost/bundle/triage persist)
   onto the cohort branch.** Without these, ~1–5% of genes silently lose
   their entire intermediates blob.
2. **Add `cohort_run_id` to `agent_run_intermediates` + plumb through
   `publish_intermediates`.** Idempotent `ALTER TABLE ADD COLUMN
   cohort_run_id TEXT` + index. Reuse the same UUID `deep_dive_run.run_id`
   uses so the tables join.
3. **Wire `publish_intermediates` into `deep_dive_sweep.py::annotate_one`.**
   The sweep driver currently never calls it — the production cohort
   wouldn't capture any intermediates rows at all today.

### P1 — add this week

4. **`code_sha` into intermediates.** Cheap (`subprocess.run(["git",
   "rev-parse", "HEAD"])` at module load with Modal `GIT_COMMIT` env-var
   fallback).
5. **`model_id` + `prompt_corpus_sha` into intermediates.** One-line
   additions in `publish_intermediates`.
6. **`failure_mode` enum** in each early-return branch (~10 lines).
   Strong cohort-level analytics signal.
7. **`triage_source` link** (prior-triage `run_id` + `model` +
   `prompt_variant`) so a record can be traced through the triage layer.
8. **Spot-check** the first heavy cohort gene's R2 key landed (one
   list-objects call).

### P2 — nice-to-have

9. Per-builder `n_repair_attempts`.
10. `api_response_id` + `api_model` per `messages.create`.
11. Capture explicit `temperature` (currently default 1.0); consider
    lowering to 0.2 for the cohort.
12. Fix `r2_client.head_object`.
13. Capture PTS A1/A2 paper overlap.
14. Mirror per-step `timing` into the D1 intermediates blob (currently
    only in `.runs/` on the local machine — lost on Modal).

---

## Why no edits committed

* `code_sha` would need a `subprocess.run` plus a Modal fallback story;
  not 1-2 lines.
* `model_id` is a one-line addition, but HEAD's `intermediates.py` is
  the pre-slim/pre-R2 version. Adding it here would conflict with
  `cfb37efbf`'s heavily-rewritten `publish_intermediates`. Better to
  add in the cherry-pick PR (P0 #1) than seed a conflict.

The high-leverage action is the P0 list above, not anything that fits
in a one-line edit on this read-only branch.

## Files referenced (absolute paths)

* `/Users/rebeccacarlson/Git/accessible-surfaceome/.claude/worktrees/eloquent-cori-5b6b55/src/accessible_surfaceome/cloud/intermediates.py` (HEAD: pre-slim)
* `cfb37efbf:src/accessible_surfaceome/cloud/r2_client.py` (planning branch only)
* `src/accessible_surfaceome/_version_guard.py:40` (`PROMPT_CORPUS_VERSION`)
* `src/accessible_surfaceome/agents/surfaceome_v2/orchestrator.py:115` (`AGENT_MODEL`), `:699` (intermediates assembly), `:1490+` (record assembly), `:1056-1100` (synth call site)
* `src/accessible_surfaceome/agents/_support/timing.py` (per-step timing)
* `src/accessible_surfaceome/cloud/deep_dive_upload.py:69-86` (`_build_composite_prompt`)
* `scripts/surfaceome_v2_annotate.py:146` (single-gene publish call)
* `scripts/deep_dive_sweep.py:132-210` (cohort sweep — does NOT call `publish_intermediates`)
* `cloudflare/d1_schema.sql:625-657` (`agent_run_intermediates` DDL)

---

## Schema migration runbook — extend `surface_annotation` PK to include `prompt_corpus_version`

**Status:** TODO. The columns (`prompt_corpus_version`, `cohort_run_id`) are
already added — only the PK extension is deferred.

**Why deferred:** SQLite has no in-place `ALTER TABLE ... ADD PRIMARY KEY` /
`ALTER TABLE ... DROP PRIMARY KEY`. The migration is the standard rename-
swap dance, which on a live D1 database with the current 65-row
`surface_annotation` table risks silently dropping the cache_purge
invariant if mid-flight any agent tries to write while the temp table
exists. Worth the explicit operator confirmation.

**Why the deferral is safe today:**

* The current PK `(gene_symbol, schema_version)` still tie-breaks the
  Worker's `ORDER BY schema_version DESC LIMIT 1` SELECTs correctly.
* The `INSERT OR REPLACE` upsert in `publish_record._publish_dict`
  combined with the staleness + regression guards prevent a same-
  schema-version, same-gene write from overwriting a populated row
  with a degraded one.
* The new `(gene_symbol, prompt_corpus_version)` index added in the
  same schema rev gives O(log N) per-corpus lookups for analytics
  that need to ask "show me the 2.28-corpus row for CD63" without
  requiring the PK extension.

**The migration (run on the production `surfaceome_public` D1 in a
maintenance window):**

```sql
-- 1. New table with the extended PK shape.
CREATE TABLE surface_annotation_new (
    gene_symbol         TEXT NOT NULL,
    uniprot_acc         TEXT,
    schema_version      TEXT NOT NULL,
    annotation_json     TEXT NOT NULL,
    confidence          TEXT,
    triage_signal       TEXT,
    surface_status      TEXT,
    model_path          TEXT,
    evidence_count      INTEGER,
    primary_evidence_count INTEGER,
    annotated_at        TEXT NOT NULL,
    synced_at           TEXT NOT NULL DEFAULT (datetime('now')),
    prompt_corpus_version TEXT NOT NULL DEFAULT '0.0.0',
    cohort_run_id       TEXT,
    PRIMARY KEY (gene_symbol, schema_version, prompt_corpus_version)
);

-- 2. Copy data, defaulting any NULL prompt_corpus_version to '0.0.0'.
INSERT INTO surface_annotation_new
SELECT gene_symbol, uniprot_acc, schema_version, annotation_json, confidence,
       triage_signal, surface_status, model_path, evidence_count,
       primary_evidence_count, annotated_at, synced_at,
       COALESCE(prompt_corpus_version, '0.0.0'),
       cohort_run_id
  FROM surface_annotation;

-- 3. Verify row counts match.
SELECT COUNT(*) FROM surface_annotation;       -- N
SELECT COUNT(*) FROM surface_annotation_new;   -- must equal N

-- 4. Rename, then re-apply indexes on the new table.
DROP TABLE surface_annotation;
ALTER TABLE surface_annotation_new RENAME TO surface_annotation;

CREATE INDEX IF NOT EXISTS idx_surface_annotation_uniprot
    ON surface_annotation (uniprot_acc);
CREATE INDEX IF NOT EXISTS idx_surface_annotation_surface_status
    ON surface_annotation (surface_status);
CREATE INDEX IF NOT EXISTS idx_surface_annotation_prompt_corpus
    ON surface_annotation (gene_symbol, prompt_corpus_version);
CREATE INDEX IF NOT EXISTS idx_surface_annotation_cohort
    ON surface_annotation (cohort_run_id);
```

Run via `D1Client.query()` one statement at a time (D1's HTTP API
doesn't accept multi-statement batches). Take a Time-Travel-pinned R2
backup before step 1 — the public D1 already has nightly R2 dumps via
`.github/workflows/d1-backup.yml` so the recovery surface is layered.

**After the migration**, drop the TODO comment in
`cloudflare/d1_public_schema.sql` (the only operator-side change is
remembering to call `publish_record(..., cohort_run_id=...)` from the
sweep — already wired today).

---

## 2026-06-08 — slim implementation of P0 + cohort_run_id

Landed in branch ``claude/eloquent-cori-5b6b55``:

1. ``scripts/deep_dive_sweep.py::annotate_one`` now calls
   ``publish_intermediates(...)`` after every gene (success or fail) and
   threads ``cohort_run_id`` through. Per-sweep CLI flag
   ``--cohort-run-id`` defaults to ``--run-id`` when not specified.
2. ``cloud/intermediates.publish_intermediates`` accepts ``cohort_run_id``
   and writes it to the new ``agent_run_intermediates.cohort_run_id``
   column. Schema bumped (idempotent ``ALTER TABLE ADD COLUMN`` swallowed
   on existing DBs via ``ensure_schema``).
3. ``cloud/surface_annotation.publish_record`` accepts ``cohort_run_id``
   and denormalizes ``prompt_corpus_version`` off the record into the
   new ``surface_annotation`` columns of the same names.
4. Mid-gene PTS checkpoint + $5 PTS cost cap in the orchestrator —
   recovers ~$1.35 / retried-gene on the ~5% failure rate.

Items NOT in this slice:

* PR54's $7 total cost ceiling (already on this branch).
* PR54's R2 client (already on this branch).
* The Worker code path for the new ``prompt_corpus_version`` column —
  the Worker continues to tie-break on ``schema_version`` until the PK
  migration above lands. Reader code still works because the latest
  row wins per the existing tie-break.
