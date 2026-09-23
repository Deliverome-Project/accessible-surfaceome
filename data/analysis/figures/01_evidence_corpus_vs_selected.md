# Supplementary Figure 12 — Papers found vs papers selected as evidence

Per-gene scatter of two corpus axes the deep-dive literature pipeline
returns, colored by the agent's `evidence_grade` verdict. Every point is
a real published deep-dive record: **n = 5,313 genes**, the deep-dive
cohort (5,332) minus 19 legacy records written before schema 2.14.0 that
carry a null `n_papers_found` — both axes must be present to plot a
point. Median 219 papers found/gene, median 10 selected.

The two dotted diagonals are **constant selection rates** (papers
selected ÷ papers found), drawn at 5 % and 10 %. They are reference
lines, not fits: a gene sitting on the 10 % line had one paper in ten
promoted from the discovery corpus into the evidence ledger.

## What each axis measures

- **x-axis — Papers found per gene (discovery corpus).** The size of
  the per-gene candidate corpus from the discovery stage (EuropePMC +
  PubTator NER + gene2pubmed union). Populated from
  `PlanTrimSelectResult.n_papers_discovered` (`len(cumulative_discovered)`)
  and plumbed onto `Filters.n_papers_found` per the CLAUDE.md schema
  2.14.1+ contract. It **cannot be recomputed from a finished record** —
  the discovery count was never persisted before 2.14.0, only the
  post-trim selection — so the 19 legacy records lacking it are the rows
  dropped above. (An earlier 100-gene methods audit put the median at
  234.5; the full cohort's is 219.)
- **y-axis — Papers selected as evidence.** The subset the deep-dive's
  `plan_trim_select` step ranks high-enough to feed into the block
  builders for full-text claim extraction. **Already computable from
  existing records** as `len({source.source_id for ev in evidence for
  span in ev.spans})` — see `scripts/build/backfill_n_papers_selected.py`.
- **Color — agent `evidence_grade` verdict** ∈ closed enum:
  - `direct_multi_method` — multiple independent assay types
  - `direct_single_method` — direct surface evidence from one assay
  - `supportive_but_indirect` — circumstantial / topology-based
  - `conflicting` — direct evidence on both sides
  - `weak` — sparse or low-quality evidence

Reading the diagonals: well-evidenced surface targets sit above the
10 % line in the upper-right (rich corpus *and* rich selection →
`direct_multi_method`), while weak-evidence calls cluster below the 5 %
line in the lower-left.

## Reproducibility

```bash
uv run make_evidence_corpus_vs_selected.py
```

The script reads only the bundled `evidence_corpus_vs_selected.tsv` next
to it — no network fetch, no external joins. One row per published
deep-dive record, with columns `gene_symbol`, `uniprot_acc`,
`papers_found`, `papers_selected`, `evidence_grade`, `tier`.

## Canonical generator

[`scripts/figures/evidence_corpus_vs_selected.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/figures/evidence_corpus_vs_selected.py)
in the project repo.

> **Note on earlier versions.** Before the v2 sweep produced records, this
> figure was a placeholder drawn from a synthesized lognormal
> (`numpy.random.default_rng(seed=42)`, columns `papers_found_mock` /
> `papers_selected_mock`). That synthesis is gone — the generator no
> longer contains a `_synthesize_mock_data()` helper and the TSV carries
> real gene symbols and real counts. This README described the mock
> recipe for longer than the figure used it; if you have a copy of this
> gist that still documents mock draws, it predates the sweep.

## Data lineage

- Per-figure TSV (bundled here): [`data/processed/figures/evidence_corpus_vs_selected.tsv`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/data/processed/figures/evidence_corpus_vs_selected.tsv)
- TSV builder:
  [`scripts/build_figure_tsvs.py:build_evidence_corpus_vs_selected`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/build_figure_tsvs.py)
  — one row per published deep-dive record, read from public D1.
- Schema source (closed enum for `evidence_grade`):
  [`src/accessible_surfaceome/tools/_shared/models.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/src/accessible_surfaceome/tools/_shared/models.py)
- Paper-count semantics:
  `Filters.n_papers_selected` + `Filters.n_papers_found` (schema
  2.14.1+; see CLAUDE.md "Paper-count signals on Filters").
