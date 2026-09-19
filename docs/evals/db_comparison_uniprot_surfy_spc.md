# Single-DB vs SurfaceGenie SPC on the triage benchmark (2026-09-19)

Head-to-head comparison of the individual surface-annotation databases and the SurfaceGenie
**SPC** consensus score (0-4), scored as binary surface classifiers on the curated triage
benchmark. Question this answers: *is SPC a better surface classifier than any single database
we already use, and are SPC's three legacy predictors worth adding as library sources?*

Reproduce with
[`scripts/audit/db_vs_spc_comparison.py`](../../scripts/audit/db_vs_spc_comparison.py):

```
uv run python scripts/audit/db_vs_spc_comparison.py
```

## Result (v1 benchmark, drop-contextual, n = 116: 68 `yes` / 48 `no`)

| predictor | accuracy | balanced-acc | precision | recall | F1 |
|---|---:|---:|---:|---:|---:|
| **UniProt (optimized)** | **0.974** | **0.969** | 0.958 | 1.000 | **0.978** |
| SURFY | 0.905 | 0.904 | 0.925 | 0.912 | 0.919 |
| UniProt (baseline flag) | 0.879 | 0.891 | 0.966 | 0.824 | 0.889 |
| SPC >= 2 | 0.853 | 0.854 | 0.892 | 0.853 | 0.872 |
| SPC >= 1 | 0.828 | 0.792 | 0.773 | 1.000 | 0.872 |
| SPC >= 3 | 0.819 | 0.843 | 0.980 | 0.706 | 0.821 |
| SPC >= 4 | 0.552 | 0.618 | 1.000 | 0.235 | 0.381 |
| CSPA | 0.483 | 0.510 | 0.600 | 0.353 | 0.444 |
| GO-CC | 0.448 | 0.456 | 0.538 | 0.412 | 0.467 |
| HPA | 0.440 | 0.479 | 0.548 | 0.250 | 0.343 |
| SPC graded (AUROC) | - | 0.941 | - | - | - |

**Ranking: UniProt (optimized) > SURFY > UniProt (baseline) > SPC (best cutoff, >= 2) > CSPA / GO-CC / HPA.**

## Takeaways

- **UniProt's *optimized* config** (TM-or-signal-or-strict-location topology proxy — the
  recommended cut in `data/processed/triage_bench/db_cutoff_tradeoff_points.tsv`) is the best
  single database (acc 0.974); SURFY is second (0.905). The plain **baseline**
  `uniprot_surface_flag` (0.879) trails SURFY, so comparisons must state which UniProt cut they
  use. UniProt is the highest-**precision** source (0.958-0.966); SURFY trades a little
  precision for higher recall.
- **No SPC hard cutoff beats UniProt-optimized or SURFY.** SPC's best hard call (>= 2) is
  0.853 acc; its most flattering number, the graded AUROC 0.941, is still below
  UniProt-optimized's balanced accuracy (0.969) and SURFY's (0.904). SPC cutoffs behave as a
  precision/recall dial (>= 4: precision 1.00, recall 0.235; >= 1: recall 1.00, precision 0.77).
- **SPC does beat GO-CC / CSPA / HPA**, which all fall below 0.5 accuracy on this
  disagreement-enriched hard set — but those are already the weakest three sources, so this is
  a low bar.
- **SPC = SurfaceGenie consensus of 4 *in-silico* predictors**: SURFY (Bausch-Fluck 2018),
  da Cunha 2009, Diaz-Ramos 2011, Town 2016 - none experimental. SPC already contains SURFY,
  and **SURFY alone (0.905) beats SPC's best cutoff (0.853)**, so the three legacy lists add no
  discriminative value here. **No reason to add da Cunha / Diaz-Ramos / Town as library
  sources** - legacy predictions subsumed by SURFY.

## Scoring convention (and how it differs from the paper Figure 2 DB barplot)

This table is a **clean head-to-head classifier** comparison, so every predictor is scored on
the same set under the same rule:

- Positives/negatives are `ground_truth_verdict` with **`contextual` dropped**, leaving the
  binary yes-vs-no set (116 of 147). The paper's Figure-2 DB barplot
  (`scripts/figures/triage_bench_db_barplot.py`) instead keeps all 147, counts `contextual` as
  a correct surface call, and is **coverage-aware** (a source is not penalised where it
  abstains). That convention answers "how good is each DB where it has an opinion"; this one
  answers "is SPC a better classifier head-to-head." **The two tables are not directly
  comparable by construction** - do not cross-read a number from one into the other.
- Baseline DB flags come from `data/processed/triage_bench/mainbench_canonical_v2.tsv` (the
  true per-protein flag for all 116). The **optimized** UniProt cut comes from
  `data/processed/triage_bench/db_optimized_cutoffs.tsv`; a benchmark protein absent from that
  file did not pass the optimized rule, so its optimized flag is 0 (every absent benchmark
  protein is `no`/`contextual`, never `yes`, so 0 is the correct call, not an artifact).
- SPC (0-4) is the per-accession SurfaceGenie score in
  `data/external/surfacegenie/SPC_by_Source_sprot.csv` (Waas et al. 2020, Bioinformatics
  36:3447); all 116 benchmark accessions are covered.

## Benchmark-set note

The v1 benchmark (`data/eval/triage_benchmark_v1.tsv`, 147 proteins) is **68 `yes` / 31
`contextual` / 48 `no`**; dropping `contextual` gives the 116-protein yes/no set scored above.
`data/processed/triage_bench/mainbench_canonical_v2.tsv` is the LLM-run table over the same
147-gene benchmark (1,617 model x variant x replicate rows across Haiku 4.5 / Sonnet 4.6 /
Sonnet 5 / Opus 4.8), carrying the ground-truth verdict and the five baseline DB flags per
protein.

> **Stale doc, flagged separately:** `docs/evals/triage_benchmark_v1.md` still states
> `71 yes / 27 contextual / 49 no` in its header, section titles, and per-section protein
> lists, which no longer matches the TSV (`68 / 31 / 48`) - three proteins moved from `yes` to
> `contextual`. Reconciling it properly means regenerating the section membership from the TSV,
> not just editing the counts (a header-only edit would make the doc self-contradictory), so it
> is left to a dedicated follow-up rather than this note.
