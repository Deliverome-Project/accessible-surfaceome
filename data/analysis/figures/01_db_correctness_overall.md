# LLM overall accuracy — Claude triage on the 147-gene bench

Bars showing overall verdict accuracy for each (model, prompt-variant)
Claude triage cell on the 147-gene bench. Grouped by model
(Haiku 4.5 / Sonnet 4.6 / Opus 4.7); within each group, four bars
encode the prompt variants via hatch:

* solid — naive (gene symbol only)
* `//` — + NCBI resolver context
* `xx` — + NCBI + web_search
* `..` — + NCBI + PubMed evidence

Accuracy uses the project's soft-credit rule: yes ≡ contextual on
the positive side; `no` matches `no` only.

Run:

```
uv run make_db_correctness_overall.py
```

Sources (fetched live from the public repo):

- Bench predictions: [`data/processed/triage_bench/mainbench_canonical_v1.tsv`](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/processed/triage_bench/mainbench_canonical_v1.tsv)
- Bench truth labels: [`data/eval/triage_benchmark_v1.tsv`](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/eval/triage_benchmark_v1.tsv)

Canonical in-repo generator:
[`scripts/triage_bench_db_barplot.py::make_overall_plot`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/triage_bench_db_barplot.py).
