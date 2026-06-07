# DB correctness by class — optimized cutoffs vs Sonnet+NCBI on the 147-gene bench

5 surface DBs (UniProt, GO CC, HPA, SURFY, CSPA) + Sonnet+NCBI,
grouped bars showing accuracy per ground-truth class (overall / yes /
contextual / no). DB cutoffs are the **trade-off-audit optimized**
versions, not canonical baselines:

* **UniProt — TM+signal**: admit any accession with a TM domain, a
  signal peptide, OR a strict surface subcellular term (looser than
  canonical; rescues more bench positives without hurting the
  no-class).
* **CSPA — HC-only**: admit only the high-confidence flag (drops
  `putative` + `unspecific`; stricter than canonical, lifts
  precision against the no-class).
* **GO CC / HPA / SURFY**: canonical baselines (audit didn't surface
  a better cutoff).

See the companion `db_cutoff_tradeoff` figure for the audit that
recommends these cutoffs.

Run:

```
uv run make_db_correctness_by_class.py
```

Sources (fetched live from the public API):

- Bench predictions: `https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=mainbench_canonical_v1&replicate=1`
- Whole-proteome catalog (DB flags + Sonnet verdicts): [`data/processed/catalog/whole_proteome_catalog.tsv`](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/processed/catalog/whole_proteome_catalog.tsv)
- Bench truth labels: [`data/eval/triage_benchmark_v1.tsv`](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/eval/triage_benchmark_v1.tsv)
- Optimized-cutoff accessions: [`data/processed/triage_bench/db_optimized_cutoffs.tsv`](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/processed/triage_bench/db_optimized_cutoffs.tsv)
  (one row per accession admitted by either optimized rule; columns
  `uniprot_optimized` + `cspa_optimized` mark which).

Canonical in-repo generator:
[`scripts/triage_bench_db_barplot.py::make_by_class_plot`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/triage_bench_db_barplot.py)
with `_USE_OPTIMIZED_CUTOFFS = True`. The optimized accession TSV
above is dumped as a side effect of the same function via
`_dump_db_optimized_cutoffs`.
