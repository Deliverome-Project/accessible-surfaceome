# Modal apps

Two apps live here: the deep-dive sweep (below) and the DeepTMHMM2
topology sweep ([jump](#deeptmhmm2-topology-sweep)). They share the one-time
setup but nothing else — separate Modal apps, volumes and cost profiles.

## Deep-dive sweep

This directory hosts the Modal app that fans the surfaceome_v2 deep-dive
annotator out across the candidate universe (v3 cohort: 5,105 genes,
`data/processed/candidate_universe/candidate_universe_v3.tsv`).

> **Driving an actual campaign?** Read the operator runbook —
> [`docs/operations/deep-dive-modal-runbook.md`](../docs/operations/deep-dive-modal-runbook.md).
> It covers the $0 preflight, the validation canary, the incremental
> `--limit` rollout (25 → 100 → 1000 → full), progress tracking, cost
> controls, resume/recovery, and post-run validation. This README is the
> app-internals + one-time-setup reference.

## One-time setup

1. Install the modal client (kept out of the main dep tree on purpose):

   ```bash
   uv sync --extra modal
   ```

2. Authenticate. This drops a token under `~/.modal.toml`:

   ```bash
   uv run modal token new
   ```

3. Bundle the secrets the workers need:

   ```bash
   uv run modal secret create surfaceome-env \
       ANTHROPIC_API_KEY=... \
       NCBI_API_KEYS=key1,key2,key3 \
       CLOUDFLARE_API_TOKEN=... \
       CLOUDFLARE_ACCOUNT_ID=... \
       CLOUDFLARE_D1_SURFACEOME_AGENTS_ID=... \
       CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID=... \
       CLOUDFLARE_ZONE_ID=... \
       UNPAYWALL_EMAIL=... \
       ACCESSIBLE_SURFACEOME_REQUIRE_D1=1
   ```

   (Mirror whatever keys `accessible_surfaceome.cloud.d1_client.D1Client`
   reads from `.env`.)

4. The shared `surfaceome-annotations` Volume is created automatically on
   first run; nothing to do up front.

## Workflow

Always run the canary first. It exits without launching the full sweep
so you can review the projected cost.

```bash
# No-model smoke for the centralized Modal rate gate.
uv run modal run modal/deep_dive_app.py::rate_limit_smoke \
    --n 4 \
    --interval-s 0.2

# 50-gene canary, stratified by sonnet_verdict
uv run modal run modal/deep_dive_app.py::canary \
    --gene-list data/processed/candidate_universe/candidate_universe.tsv \
    --run-id candidate_universe_v1_sonnet_2026_05 \
    --n 50

# Full sweep (after canary review). Dispatched in chunks of 200; aborts
# between chunks if running cost passes the cap.
uv run modal run modal/deep_dive_app.py::full_sweep \
    --gene-list data/processed/candidate_universe/candidate_universe.tsv \
    --run-id candidate_universe_v1_sonnet_2026_05 \
    --max-total-cost-usd 18000
```

Both entrypoints stream per-gene JSON to the `surfaceome-annotations`
Volume (under `<run_id>/<symbol>.json`) and best-effort-mirror to the
`deep_dive_run` table in `surfaceome_agents` D1. Dispatch is
**resume-aware and schema-aware, globally**: a gene is skipped if it
already has a completed record at the current `schema_version` in *any*
`run_id` (plus over-cap genes quarantined for manual review). So
re-launching is always safe — bump `--limit` to walk through the cohort
in batches. `--force` re-runs already-complete genes; see the runbook.

## Pulling JSON files back

```bash
# Pulls everything; files land under data/annotations/<run_id>/<symbol>.json
uv run modal volume get surfaceome-annotations / data/annotations/
```

Use `modal volume ls surfaceome-annotations` to inspect what's there
without downloading.

## Recovery from JSON

If JSON landed on the Volume but the private D1 parent row did not, resume
will not see that gene and a rerun can re-spend. Pull the Volume snapshot,
then backfill missing private rows from JSON:

```bash
uv run modal volume get surfaceome-annotations / data/annotations/

# Dry-run report.
uv run python scripts/cloud/backfill_deep_dive_from_json.py \
    --run-id candidate_universe_v1_sonnet_2026_05

# Execute D1 inserts for missing parent rows.
uv run python scripts/cloud/backfill_deep_dive_from_json.py \
    --run-id candidate_universe_v1_sonnet_2026_05 \
    --execute

# Then verify existing parent rows have complete children.
uv run python scripts/audit/audit_deep_dive_orphans.py \
    --run-id candidate_universe_v1_sonnet_2026_05
```

The JSON record does not carry original cost/latency. Backfilled rows use
zero for `cost_usd`, `latency_s`, and `n_tool_calls` unless you pass
`--metadata-tsv` with those fields. The private D1 row also records the
current checkout's composite prompt SHA, so run this recovery before
changing prompts, or from the same commit/image used for the sweep.

## Tuning

- `cpu=0.5`, `memory=2048`, `timeout=20*60` — fine for most genes; the
  v2 pipeline is I/O-bound on UniProt/NCBI/Anthropic calls.
- **Concurrency is OTPM-derived, not a fixed fan-out.** `max_containers`
  / `max_inputs` resolve from env at launch (default ~64 concurrent genes,
  sized to keep Anthropic OTPM under 2M/min — see the runbook's
  *Concurrency tuning*). Each launch prints the projected OTPM vs the
  ceiling. Tune via `SURFACEOME_MAX_CONTAINERS` / `SURFACEOME_MAX_INPUTS`
  / `SURFACEOME_PER_GENE_OUTPUT_TOKENS` / `SURFACEOME_GENE_WALL_S`.
- `rate_limit_gate` — a single-container **reservation** gate all workers
  call before live HTTP requests. It computes the next free slot per
  host/NCBI-key and *returns* the wait (the worker sleeps locally — the
  gate never blocks), so one slow host can't stall others. Raw NCBI keys
  are hashed before they leave the worker. Run `rate_limit_smoke` after
  changing Modal plumbing.
- `--chunk-size 200` (full sweep only) — genes are dispatched in
  chunks of this size; each chunk is drained fully before the next
  launches. Smaller chunks → tighter cost-cap enforcement (bounded
  overshoot of `chunk_size × max_cost_per_gene_usd`) but lower peak
  utilization of the worker pool. Default 200 keeps the pool
  saturated while bounding overshoot to ~$100 of typical spend.

## Local equivalent

For smoke tests (no Modal account needed), use the same helpers
in-process:

```bash
uv run python scripts/build/deep_dive_sweep.py \
    --gene-list data/processed/candidate_universe/candidate_universe.tsv \
    --run-id smoke_test_2026_05 \
    --canary 3 --concurrency 1 --no-d1
```


# DeepTMHMM2 topology sweep

`deeptmhmm2_app.py` runs [DeepTMHMM2](https://github.com/fteufel/DeepTMHMM2)
(`dtm2`) over every human proteoform already in the public `topology_public`
table — 20,224 forms, 12.5M residues. DeepTMHMM v1 populated that table;
v2 adds beta barrels, reentrant loops, interfacial helices and a membrane-type
call, so this is a second annotation of the same inputs rather than a
replacement of the first.

## Why it reads its input from D1

`topology_public` stores each proteoform's input sequence. Reusing those exact
sequences — rather than re-fetching FASTAs — is what makes v1 and v2
comparable row-for-row. The query groups on `uniprot_acc_full`, the stable ID;
`gene_symbol` is denormalized in that table and is not a join key.

## v1 rows are not at risk

The primary key is `(topology_version, cohort, uniprot_acc_full)` and the
uploader uses `INSERT OR IGNORE`, so a new `topology_version` is a disjoint
namespace. Nothing in this app writes to D1 at all: both entrypoints stream to
the `surfaceome-topology2` Volume, and publishing is a separate reviewed step
that asserts the v1 row count is unchanged either side of it.

## GPU bands

ESM2 attention is quadratic in length, so one 14,507-aa proteoform can OOM a
GPU that handles the p99 comfortably. Three bands, sized from the measured
length distribution (p50 456 aa, p90 1,187, p99 3,038):

| Band | Forms | Residues | GPU | Shard |
|---|---:|---:|---|---:|
| ≤ 2,500 aa | 19,882 | 11.2M | T4 | 200 |
| 2,500–6,000 aa | 329 | 1.2M | A10G | 20 |
| > 6,000 aa | 13 | 110k | A10G | 1 |

The middle band is the point: routing all 342 over-2,500 forms to their own
container would burn 342 A10G starts for sequences a shared container handles
fine. The canary reports measured throughput per band, so the thresholds can be
retuned from evidence rather than from this guess.

## Workflow

```bash
# Canary: 50 proteoforms sampled across the length distribution.
# Prints GPU-seconds, a per-1k-residue rate and a projected full-sweep cost.
uv run modal run modal/deeptmhmm2_app.py::canary --n 50

# Full sweep, only after reviewing that projection.
uv run modal run modal/deeptmhmm2_app.py::full_sweep --run-id dtm2_2026_09_28

# Pull the raw dtm2 output back for review.
uv run modal volume get surfaceome-topology2 dtm2_2026_09_28
```

The canary samples with a stride rather than taking the first `n`: the query is
ordered by length, so the head would project the whole sweep from the shortest
proteoforms and undercount by a wide margin.

The workers are given their sequences in the payload and hold no credentials —
only the local entrypoint reads D1.
