# Supplementary Figure 11 — Papers found vs papers selected as evidence — MOCK / placeholder

**MOCK figure.** Per-gene scatter of two corpus axes the deep-dive
literature pipeline returns, colored by the agent's `evidence_grade`
verdict. Points are synthesized from the production-pipeline
distributional shape pending the full v2 deep-dive sweep — the layout,
verdict-color encoding, and reference selection-rate diagonals (5 %,
10 %) will not change between MOCK and real.

## What each axis would measure (once the full sweep completes)

- **x-axis — Papers found per gene (discovery corpus).** The size of
  the per-gene candidate corpus from the discovery stage (EuropePMC +
  PubTator NER + gene2pubmed union). Methods-section 100-gene audit:
  median 234.5 papers/gene, range ~50 papers for orphan genes to ~400
  for well-studied receptors. **Cannot be backfilled from existing
  records** — the discovery count was never persisted on the agent
  record, only the post-trim selection. Requires a discover-only
  rerun (free, no LLM cost — only the EuropePMC + PubTator + gene2pubmed
  HTTP fetches) to populate from `PlanTrimSelectResult.n_papers_discovered`
  (`len(cumulative_discovered)`), then plumbed through to
  `Filters.n_papers_found` per the CLAUDE.md schema 2.14.1+ contract.
- **y-axis — Papers selected as evidence.** The subset the deep-dive's
  `plan_trim_select` step ranks high-enough to feed into the block
  builders for full-text claim extraction. **Already computable from
  existing records** as `len({source.source_id for ev in evidence for
  span in ev.spans})` — see `scripts/backfill_n_papers_selected.py`.
- **Color — agent `evidence_grade` verdict** ∈ closed enum:
  - `direct_multi_method` — multiple independent assay types
  - `direct_single_method` — direct surface evidence from one assay
  - `supportive_but_indirect` — circumstantial / topology-based
  - `weak` — sparse or low-quality evidence

The two reference diagonals (5 %, 10 %) mark canonical selection
rates — well-evidenced surface targets sit above the 10 % line in the
upper-right (rich corpus + rich selection → `direct_multi_method`
verdict), weak-evidence calls cluster below the 5 % line in the
lower-left.

## How the MOCK draws are generated

Hand-synthesized with `numpy.random.default_rng(seed=42)` so the
placeholder figure doesn't drift between renders:

- `papers_found_mock` ~ Lognormal(μ=ln 234, σ=0.6), clipped to [25, 550]
- selection_rate = 0.12 × ln(75) / ln(found) + Gaussian(0, 0.025),
  clipped to [0.01, 0.30] (a 75-paper gene keeps ~12 %, a 400-paper
  gene selects ~6 %)
- `papers_selected_mock` = round(found × selection_rate), clipped to [2, 50]
- `evidence_grade` assigned categorically as a function of
  ln1p(selected) + 1.5 × selection_rate + Gaussian(0, 0.22), with
  thresholds tuned to land ~30 / 25 / 25 / 20 across the four buckets

## Reproducibility

```bash
uv run make_evidence_corpus_vs_selected.py
```

The script reads only the bundled `evidence_corpus_vs_selected.tsv`
next to it — no network fetch, no external joins. The TSV is one row
per synthesized gene with columns `gene_symbol`, `papers_found_mock`,
`papers_selected_mock`, `evidence_grade`.

## Canonical generator

[`scripts/evidence_corpus_vs_selected.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/evidence_corpus_vs_selected.py)
in the project repo. The mock-synthesis recipe lives in that script's
`_synthesize_mock_data()`; once the v2 deep-dive sweep populates
`deep_dive_run.evidence_grade` genome-wide, that helper will be
replaced with a public-D1 SELECT (sketched in the docstring) that
returns the same three-column shape.

## Data lineage

- Per-figure TSV (bundled here): [`data/processed/figures/evidence_corpus_vs_selected.tsv`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/data/processed/figures/evidence_corpus_vs_selected.tsv)
- TSV builder:
  [`scripts/build_figure_tsvs.py:build_evidence_corpus_vs_selected`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/build_figure_tsvs.py)
  — deterministic synthesis with `numpy.random.default_rng(seed=42)`;
  no real D1 read until the discover-only rerun populates
  `n_papers_found` on the records.
- Schema source (closed enum for `evidence_grade`):
  [`src/accessible_surfaceome/tools/_shared/models.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/src/accessible_surfaceome/tools/_shared/models.py)
- Paper-count semantics:
  `Filters.n_papers_selected` + `Filters.n_papers_found` (schema
  2.14.1+; see CLAUDE.md "Paper-count signals on Filters").
