# Sonnet vs best DB vs ≥k-DB ensembles — overall accuracy on 147-gene bench

Six-bar comparison of overall verdict accuracy on the 147-gene
triage benchmark:

* **Sonnet (+ NCBI)** — Claude Sonnet 4.6 triage agent on its
  canonical NCBI-resolver prompt variant
* **UniProt (TM+signal)** — best single classical DB under its
  bench-optimized cutoff (TM OR signal-peptide positive)
* **≥2 / ≥3 / ≥4 / ≥5 DB** — ensemble callers: "yes" iff at least
  k of the 5 surface DBs (UniProt, GO CC, HPA, SURFY, CSPA, each
  under its own optimized cutoff) vote yes. k=2 is the lightest
  ensemble; k=5 is the strict intersection of all 5.

Accuracy uses the project's soft-credit rule: yes ≡ contextual on
the positive side; `no` matches `no` only. Per-bucket breakdown
(yes / contextual / no) lives in the sibling `combined_db_correctness_by_class`
figure.

Run:

```
uv run make_ensemble_vs_best_db_vs_sonnet.py
```

Sources (fetched live from the public repo):

- Bench truth labels: [`data/eval/triage_benchmark_v1.tsv`](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/eval/triage_benchmark_v1.tsv)
- Sonnet predictions: [`data/processed/triage_bench/mainbench_canonical_v1.tsv`](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/processed/triage_bench/mainbench_canonical_v1.tsv)
- Candidate-universe DB flags: [`data/processed/candidate_universe/candidate_universe.tsv`](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/processed/candidate_universe/candidate_universe.tsv)
- DB-optimized cutoffs: [`data/processed/triage_bench/db_optimized_cutoffs.tsv`](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/processed/triage_bench/db_optimized_cutoffs.tsv)

Canonical in-repo generator:
[`scripts/ensemble_vs_best_db_vs_sonnet.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/ensemble_vs_best_db_vs_sonnet.py).
