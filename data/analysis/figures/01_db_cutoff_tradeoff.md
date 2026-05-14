# DB cutoff tradeoff — universe size vs benchmark accuracy per source

For each of the 5 M1 surface DBs (UniProt, GO CC, HPA, SURFY, CSPA),
a small panel plotting how the choice of "surface-vote" cutoff
trades universe size (proteins this filter admits, log-scale x) for
benchmark accuracy on the 147-gene bench (y, %). Lower-x = stricter.

Markers:
* Circle — alternative cutoff option, not currently used in the
  M1 merge rules.
* Diamond — canonical baseline currently configured in the loaders
  (cross-checked against `candidate_universe.tsv` flag counts).
* Star — recommended cutoff after the trade-off audit, shown only
  when it differs from canonical (currently: UniProt "TM+signal"
  and CSPA "HC-only").

Per-point annotation: variant short label, universe size,
`+pos% / -neg%` recall on the bench.

Run:

```
uv run make_db_cutoff_tradeoff.py
```

Source (fetched live from the public repo):

- Pre-computed trade-off points (small TSV): [`data/processed/triage_bench/db_cutoff_tradeoff_points.tsv`](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/processed/triage_bench/db_cutoff_tradeoff_points.tsv).
  Dumped by the canonical generator when it runs, so re-running
  the canonical script keeps this TSV (and therefore the gist plot)
  in sync.

Canonical in-repo generator:
[`scripts/triage_bench_db_barplot.py::make_db_tradeoff_plot`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/triage_bench_db_barplot.py).
The accuracy math runs over the raw DB source dumps; this gist
script reads the precomputed points table instead so it stays small
and self-contained.
