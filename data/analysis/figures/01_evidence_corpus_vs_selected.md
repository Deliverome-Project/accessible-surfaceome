# `evidence_corpus_vs_selected` — MOCK / placeholder

**MOCK figure.** Appendix Figure 12. Papers found vs papers selected
as evidence per gene, colored by agent `evidence_grade` verdict. For
each gene in the deep-dive cohort, the literature pipeline returns:

- **Papers found** — the size of the per-gene candidate corpus from
  discovery (EuropePMC + PubTator NER + gene2pubmed; median ~234
  papers per gene on the 100-gene audit, range ~50 for orphan genes
  to ~400 for well-studied receptors).
- **Papers selected as evidence** — the subset the deep-dive's
  `plan_trim_select` step ranks high-enough to feed into the block
  builders for full-text claim extraction. The selection ratio
  decreases with corpus size — more candidate papers means more
  noise, not proportionally more relevant evidence.

The agent then assigns each gene's evidence base an `evidence_grade`
verdict from the closed enum:

- `direct_multi_method` — multiple independent assay types
- `direct_single_method` — direct surface evidence from one assay
- `supportive_but_indirect` — circumstantial / topology-based
- `weak` — sparse or low-quality evidence

The figure shows how the verdict tracks the two corpus axes — well-
evidenced surface targets pile up in the upper-right (rich corpus +
rich selection → multi-method verdict), while weak-evidence calls
cluster in the lower-left.

Counts are **synthesized** from the production-pipeline distributional
shape pending the full v2 deep-dive sweep. The mock parameters are:

- 220 genes; reproducible via `np.random.default_rng(42)`
- `papers_found ~ Lognormal(μ=ln 234, σ=0.6)`, clipped to [25, 550]
- selection rate decreases with `log(papers_found)`; baseline 12% scaled by
  `ln(75)/ln(found)` so a 75-paper gene keeps ~12%, a 400-paper gene
  selects ~6%
- verdict assigned by thresholds on a latent quality score that is
  mostly `log(papers_selected)` + a small contribution from selection rate

Replace `_synthesize_mock_data()` with a public-D1 SELECT once
`deep_dive_run.evidence_grade` is populated genome-wide:

```sql
SELECT gene_symbol,
       json_extract(annotation_json, '$.evidence_count')         AS papers_found,
       json_extract(annotation_json, '$.primary_evidence_count') AS papers_selected,
       json_extract(annotation_json, '$.filters.evidence_grade') AS verdict
FROM surface_annotation;
```

## Run

```sh
uv run make_evidence_corpus_vs_selected.py
```

Schema source (closed enum for the verdict assignment):
[`src/accessible_surfaceome/tools/_shared/models.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/src/accessible_surfaceome/tools/_shared/models.py)
(`EvidenceGrade`).

Canonical in-repo generator:
[`scripts/evidence_corpus_vs_selected.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/evidence_corpus_vs_selected.py).
