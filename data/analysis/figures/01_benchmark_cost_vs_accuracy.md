# Benchmark cost vs accuracy — Claude triage agents on the 147-gene bench

Each point is one (model, prompt-variant) cell of the triage agent
benchmark: x = $/whole-genome (cost projected to a 1-replicate-per-gene
sweep over 19,324 protein-coding genes), y = verdict accuracy on the
147-gene labelled bench. Ten Claude cells: Haiku 4.5 × {naive, +NCBI,
+NCBI+PubMed, +NCBI+web}, Sonnet 4.6 × same 4 variants, and Opus
4.7 × {naive, +NCBI}. Cost amortises prompt-caching using the
observed cache-hit rate per cell.

The y-axis floor is set at ~78% to spread the LLM-cell range; DB
baselines are intentionally absent (they'd compress the LLM cluster
against the bottom of the chart). For the DB-vs-LLM comparison, see
`db_correctness_overall` and `db_correctness_by_class`.

Run:

```
uv run make_benchmark_cost_vs_accuracy.py
```

Sources (fetched live from the public repo):

- Bench predictions: [`data/processed/triage_bench/mainbench_canonical_v1.tsv`](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/processed/triage_bench/mainbench_canonical_v1.tsv)
- Bench truth labels: [`data/eval/triage_benchmark_v1.tsv`](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/eval/triage_benchmark_v1.tsv)

Canonical in-repo generator:
[`scripts/triage_bench_db_barplot.py::make_cost_vs_accuracy_plot`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/triage_bench_db_barplot.py).
