# Deep dive over the 148 rescues

Launched 2026-09-20 under `--cohort-run-id intracellular_rescue_v1_sonnet_2026_09`
at concurrency 28, publishing to public D1.

`deep_dive_cohort.tsv` is the 147-gene cohort: the 148 rescues from
`genome_intracellular_pubmed_ncbi_v1` **minus NPM1**, which was already
deep-dived ad hoc (`run_id=npm1_adhoc_probe_2026_09_19`, private D1).

## Launch

```bash
uv run python scripts/run_deep_dive_sweep.py \
    --gene-list data/processed/intracellular_rescue_v1/deep_dive_cohort.tsv \
    --cohort-run-id intracellular_rescue_v1_sonnet_2026_09 \
    --concurrency 28 --publish --max-total-cost-usd 400
```

`--dry-run` resolves the cohort without calling the API; `--resume` (default on)
skips genes already in `deep_dive_run` under this run_id, so an interrupted
sweep restarts cleanly.

### Why a driver and not `xargs -P N`

`xargs -P N` over `scripts/annotate_gene.py` spawns N **processes**, each with
its own in-process `RateLimiter` — so the per-host courtesy interval against
NCBI / Europe PMC / PubTator is violated N-fold. `ratelimit.py` says the
limiter "is intentionally in-process by default" and that "local scripts leave
[the cross-process gate] unset"; Modal solves this with a single-container
gate, and the local equivalent is to keep every gene in **one** process.
`run_deep_dive_sweep.py` is a ThreadPoolExecutor for exactly that reason.

It also decouples the private-D1 sinks from `--publish`, which
`annotate_gene.py` conflates — a failed annotate is the highest-value case for
the diagnostic trail, and there it is silently dropped.

## Sizing

| Source | Number |
|---|---|
| OTPM-safe ceiling (`resolve_gene_concurrency()`) | 66 concurrent |
| Production sweep realized (423 genes/hr ÷ 597 s avg) | ~70 concurrent |
| Latency tail, 5,130-gene sweep | p50 556 s · p90 1,025 s · p99 1,428 s · max 2,549 s |
| NCBI budget (4 keys × 9 qps) vs. demand (18 calls/gene over ~600 s) | 36 qps vs. 0.03 qps/gene |

OTPM and NCBI are both non-binding at any concurrency this cohort will use
(28 genes ≈ 504k OTPM against a 1.2M headroom target). The **latency tail** is
the real ceiling: with only 147 genes, past ~24–30 concurrent the wall clock
converges on the single slowest gene and stops improving.

## Before you launch — three things

1. **`--publish` goes live.** It writes `viewer/public/data/surfaceome/{SYM}.json`
   **and** public D1, then purges the edge cache. All 147 genes appear on
   surfaceome.deliverome.org and in the catalog's Likely/induced filter chips
   immediately. Drop `--publish` for a private-only dry run.
2. **ALDOC already published.** A first attempt at this sweep was stopped
   after one gene; `ALDOC` reached public D1 (catalog `n_with_deep_dive`
   5,130 → 5,131). Re-running it is idempotent — `publish_record` is
   `INSERT OR REPLACE` on `(gene_symbol, schema_version)`.
3. **Topology is a placeholder for every gene here.** None of these
   accessions are in the topology sweep cohort, so each record carries
   `canonical_topology.tool_version = "placeholder-no-d1-row"` with
   `tm_helix_count` / `ecd_length_residues` / `signal_peptide_length`
   reading 0 — "not measured", not "measured as zero". Backfilling
   topology first (`scripts/build/run_topology_sweep.py`, adapted to an
   arbitrary accession list) would avoid publishing 147 pages with
   placeholder topology bars.

## Cost + wall clock

Measured on NPM1: **$2.00/gene**, 413 s. Cohort mean for the 5,130-gene
sweep was **$1.44/gene**, 597 s.

* Projected cost: **~$210–290**
* Wall clock at concurrency 28: **~60-90 min** (tail-bounded)

