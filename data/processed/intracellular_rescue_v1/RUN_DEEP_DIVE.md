# Staged — deep dive over the 148 rescues

**Not yet run.** This file is the launch runbook; nothing here executes
on its own.

`deep_dive_cohort.tsv` is the 147-gene cohort: the 148 rescues from
`genome_intracellular_pubmed_ncbi_v1` **minus NPM1**, which was already
deep-dived ad hoc (`run_id=npm1_adhoc_probe_2026_09_19`, private D1).

## Launch

```bash
SP=<scratch dir>
cut -f2 data/processed/intracellular_rescue_v1/deep_dive_cohort.tsv \
  | tail -n +2 > "$SP/ids.txt"

cat > "$SP/run_one.sh" <<'SH'
#!/usr/bin/env bash
SP="$1"; GID="$2"
uv run python scripts/annotate_gene.py "$GID" \
  --publish --persist \
  --cohort-run-id intracellular_rescue_v1_sonnet_2026_09 \
  > "$SP/dd_logs/${GID//:/_}.log" 2>&1
echo "$GID exit=$?"
SH
chmod +x "$SP/run_one.sh"; mkdir -p "$SP/dd_logs"

xargs -P 8 -I{} "$SP/run_one.sh" "$SP" {} < "$SP/ids.txt"
```

Genes are addressed by `hgnc_id`, per the gene-identifier-resolution rule.

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
* Wall clock at `-P 8`: **~3 hours**

`resolve_gene_concurrency()` returns 66 for the Modal environment; 8 is the
conservative local figure. Raise only with rate-limit headroom.
