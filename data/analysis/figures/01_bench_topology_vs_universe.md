# Supplementary Figure 8 — SurfaceBench topology composition vs the Sonnet 2-tier yes/contextual universe

**97-of-147 SurfaceBench genes that join the per-protein features
TSV, plotted against the 4,426-gene Sonnet 2-tier yes/contextual
universe.** Grouped bars over the same 9 topology categories the
`topology_coverage_by_source` 3x3 figure breaks out, with two hues:

- **Sonnet 2-tier yes/contextual universe** (teal) — the genes the
  production pipeline calls accessible after the Sonnet+NCBI sweep
  plus the Sonnet+PubMed rescue lane (NCBI=no → PubMed=yes/contextual
  flips). This is what the catalog *actually ships*, NOT the broader
  "any-DB-voted-yes" union.
- **SurfaceBench** (maroon) — the 97 bench-member genes that survive
  the join into the per-protein features TSV (out of the 147 curated
  bench rows).

Bench bars carry Wilson 95% binomial confidence intervals; the
universe is a population, not a sample, so no CI on the teal bars.
Above each pair sits the bench-minus-universe delta in percentage
points and Bonferroni-corrected exact 2-tailed binomial significance
stars (`*` p<0.05, `**` p<0.01, `***` p<0.001 after 9-test
correction).

**Headline**: **3 of 9 topology classes reach significance** after
Bonferroni correction.

- **Glyc. site** +20.1 pp `***` — the bench is enriched for
  N/O-glycosylated proteins (a strong surface signal that biases
  toward "easy" cases).
- **GPI-anchored** +14.5 pp `***` — the bench oversamples GPI
  anchors precisely because the DBs disagree on them most.
- **Multi-pass TM** −11.0 pp `*` — the bench *under*-samples
  multi-pass TM, the class the DBs agree easily on.

This is the **bench enrichment bias** the methods section flags:
SurfaceBench is deliberately enriched for DB-disagreement cases, so
bench-derived accuracy is a *lower bound* on expected full-proteome
accuracy, not a representative point estimate.

## Reproducibility

```bash
uv run make_bench_topology_vs_universe.py
```

The script reads only the bundled `bench_topology_vs_universe.tsv`
next to it — no network fetch, no external joins. The TSV is one
row per gene in the Sonnet 2-tier yes/contextual universe with
`is_bench` (true for 97 bench-member genes) and 9 topology boolean
flag columns denormalized in. Wilson 95% binomial CIs and
Bonferroni-corrected exact 2-tailed binomial p-values are computed
inline (no scipy dep — manual PMF loop reliable at small n).

## Canonical generator

The canonical generator that produces both this gist mirror's
inputs and the in-repo
[`data/analysis/figures/bench_topology_vs_universe.pdf`](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/analysis/figures/bench_topology_vs_universe.pdf)
lives at
[`scripts/bench_topology_vs_universe.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/bench_topology_vs_universe.py)
in the project repo. It pulls
[`data/analysis/db_vs_sonnet_inclusion/per_protein_features.tsv`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/data/analysis/db_vs_sonnet_inclusion/per_protein_features.tsv)
from raw.githubusercontent.com, filters to Sonnet 2-tier
yes/contextual via the `_is_sonnet_2tier_yc` rule (NCBI sweep
verdict ∈ {yes, contextual} OR (NCBI=no AND PubMed-rescue verdict
∈ {yes, contextual})), restricts to bench-member rows via
`uniprot_acc` join against
[`data/eval/triage_benchmark_v1.tsv`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/data/eval/triage_benchmark_v1.tsv),
and renders the same chart.

## Data lineage

- Per-protein topology features: [`data/analysis/db_vs_sonnet_inclusion/per_protein_features.tsv`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/data/analysis/db_vs_sonnet_inclusion/per_protein_features.tsv)
- Bench truth (uniprot_acc list): [`data/eval/triage_benchmark_v1.tsv`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/data/eval/triage_benchmark_v1.tsv)
- Pre-joined per-figure TSV (bundled here): [`data/processed/figures/bench_topology_vs_universe.tsv`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/data/processed/figures/bench_topology_vs_universe.tsv)

## Paste-able figure caption

> **Figure caption.** Topology composition of SurfaceBench (n = 97
> of 147 that join into the per-protein features TSV) compared
> against the Sonnet 2-tier yes/contextual universe (n = 4,426),
> the genes the production pipeline ships as accessible after the
> NCBI sweep + PubMed rescue lane. Bars show the % of each subset
> that carries the topological feature; error bars on SurfaceBench
> are Wilson 95% binomial confidence intervals (the universe is a
> population, not a sample, so no CI). Per-class p-values are
> computed by an exact 2-tailed binomial test of the bench count
> against the universe proportion under H₀, Bonferroni-corrected
> across the 9 topology classes (\* p < 0.05, \*\* p < 0.01,
> \*\*\* p < 0.001); 3 of 9 classes reach significance. The bench
> is enriched for Glyc. site (+20.1 pp\*), GPI-anchored (+14.5
> pp\*), Single-pass TM (+11.6 pp) and depleted for Inner-leaflet
> lipidated (−0.3 pp), No TM / no signal (−0.6 pp), Multi-pass TM
> (−11.0 pp\*); this reflects its deliberate selection for
> DB-disagreement cases, so bench-derived accuracy estimates are a
> lower bound on expected full-universe accuracy.
