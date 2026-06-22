# Modal deep-dive sweep

This directory hosts the Modal app that fans the surfaceome_v2 deep-dive
annotator out across the 5,680-gene candidate universe.

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
`deep_dive_run` table in `surfaceome_agents` D1. The full sweep is
resume-aware — re-running with the same `--run-id` skips genes already
in D1.

## Pulling JSON files back

```bash
# Pulls everything; files land under data/annotations/<run_id>/<symbol>.json
uv run modal volume get surfaceome-annotations / data/annotations/
```

Use `modal volume ls surfaceome-annotations` to inspect what's there
without downloading.

## Tuning

- `cpu=0.5`, `memory=2048`, `timeout=20*60` — fine for most genes; the
  v2 pipeline is I/O-bound on UniProt/NCBI/Anthropic calls.
- `@modal.concurrent(max_inputs=4)` — 4 genes per worker amortizes
  cold-start + uses the same vCPU during HTTP waits.
- `max_containers=200` — caps fan-out so NCBI (10 req/s per key) and
  Anthropic (tier-dependent RPM) don't get hammered. Raise once
  observed-RPM headroom is confirmed.
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
uv run python scripts/deep_dive_sweep.py \
    --gene-list data/processed/candidate_universe/candidate_universe.tsv \
    --run-id smoke_test_2026_05 \
    --canary 3 --concurrency 1 --no-d1
```
