# `bench_topology_vs_universe` — reproduction

Appendix Figure 8. Side-by-side grouped barplot over the same 9
topology categories the
[`topology_coverage_by_source`](../figures/01_topology_coverage_by_source.md)
3×3 figure breaks out, with two hues:

- **any-yes universe** (n=6,588) — the full "≥1 source voted yes"
  cohort the per-protein-features TSV materialises.
- **SurfaceBench** (n=146 of 147 that join into the features TSV) —
  the 147-protein hand-curated benchmark deliberately enriched for
  cases where the five gating databases disagree.

The figure surfaces the **bench enrichment bias**: the bench is *not*
a random topological sample of the surfaceome. DB-confusing classes
(GPI-anchored, single-pass TM with ambiguous orientation,
inner-leaflet lipidated, glycosylation-positive) are over-represented;
the DBs-agree-easily class (multi-pass TM) is under-represented.
SurfaceBench accuracy is therefore a **lower bound** on expected
full-proteome accuracy, not a representative point estimate.

Bench bars carry **Wilson 95% binomial confidence intervals** so the
small-n classes (likely secreted n=4, no-TM/no-signal n=6) read as
noisier than they would as bare bars. Significance stars are
2-tailed exact binomial test of bench vs universe proportion,
**Bonferroni-corrected across 9 classes**.

## Run

```sh
uv run https://gist.githubusercontent.com/beccajcarlson/676b9e5ab9112191a96560ca6fdb17d6/raw/make_bench_topology_vs_universe.py
```

Or after cloning the gist:

```sh
uv run make_bench_topology_vs_universe.py
```

`uv` reads the [PyPA inline script metadata](https://packaging.python.org/en/latest/specifications/inline-script-metadata/)
header (`# /// script ... # ///`), installs matplotlib / numpy /
pandas / seaborn in a one-shot env, and emits
`bench_topology_vs_universe.{pdf,png}` in the current directory.

## Data + canonical generator

- **SurfaceBench TSV** (~50 KB, plain TSV):
  [`data/eval/triage_benchmark_v1.tsv`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/data/eval/triage_benchmark_v1.tsv).
  147 hand-curated benchmark genes with ground-truth verdict + UniProt
  accession.
- **Per-protein feature table** (~2.8 MB, plain TSV):
  [`data/analysis/db_vs_sonnet_inclusion/per_protein_features.tsv`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/data/analysis/db_vs_sonnet_inclusion/per_protein_features.tsv).
  One row per universe protein with the 6 source-inclusion flags,
  topology-class one-hots, UniProt feature counts, DeepTMHMM
  classification.
- **Canonical in-repo generator** (uses the project's `_plotting_config`):
  [`scripts/bench_topology_vs_universe.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/bench_topology_vs_universe.py).

## Method (brief)

For each topology feature, the script computes:

- `100 × |universe-rows where feature == 1| / |universe-rows|`
- `100 × |bench-rows where feature == 1| / |bench-rows|`

The bench-rows are the universe-rows whose `uniprot_accession` matches
a row in the SurfaceBench TSV.

The Δ between bench% and universe% is annotated above each pair, with
significance stars from a 2-tailed exact binomial test (H₀: bench
n_pos ~ Binomial(n_bench, p_universe)), Bonferroni-corrected across
the 9 topology classes (* p<0.05, ** p<0.01, *** p<0.001).

Wilson 95% binomial confidence intervals on the bench bars are
robust at small n; the universe is treated as a population (no CI).
