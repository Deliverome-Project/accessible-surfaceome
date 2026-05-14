# DB ↔ Sonnet agreement on the whole proteome — bench-optimized cutoffs

Whole-genome analog of the 147-gene bench plot
`db_correctness_by_class`. On the bench, ground truth is hand-curated;
on the whole proteome (~19,324 protein-coding genes) it doesn't exist,
so we use the **Sonnet (+ NCBI) triage verdict as the reference** and
ask: for each surface DB (under its bench-optimized cutoff) and each
≥k-DB ensemble (k = 1..5), what fraction of genes does it agree with
Sonnet on, split by Sonnet's verdict bucket.

Soft-credit rule: DB "yes" matches Sonnet "yes" *or* "contextual";
DB "no" matches Sonnet "no" only.

Four buckets per caller:

* **overall** — across all genes with a rated Sonnet verdict
* **Sonnet = yes** — sensitivity-like
* **Sonnet = contextual** — DB must yes-vote for a match
* **Sonnet = no** — specificity-like (dominates overall by population)

10 callers total: 5 ensembles ≥1..≥5 (teal ramp, light = permissive) +
5 individual DBs under their optimized cutoffs (sorted descending by
overall agreement). Sonnet is the reference and does not appear as a
bar — it would be 100% by construction.

Run:

```
uv run make_db_vs_sonnet_whole_proteome.py
```

Sources (fetched live from the public repo + public catalog API):

- Whole-proteome Sonnet verdicts: [`api.deliverome.org/surfaceome/v1/catalog`](https://api.deliverome.org/surfaceome/v1/catalog) — 19,324 protein-coding genes with `triage.verdict` per gene
- Per-DB votes (GO CC / HPA / SURFY flags): [`data/processed/candidate_universe/candidate_universe.tsv`](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/processed/candidate_universe/candidate_universe.tsv)
- UniProt + CSPA optimized-cutoff accession sets: [`data/processed/triage_bench/db_optimized_cutoffs.tsv`](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/processed/triage_bench/db_optimized_cutoffs.tsv)

Canonical in-repo generator:
[`scripts/db_vs_sonnet_whole_proteome.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/db_vs_sonnet_whole_proteome.py).
