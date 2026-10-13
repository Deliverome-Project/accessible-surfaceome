# Deep-dive run-to-run concordance (Supplementary Figure 15)

Frozen record sets for a reproducibility check of the deep-dive pipeline: 50
genes drawn at random from the deep-dive cohort, each annotated three ways.

| File | What it is | Run |
|---|---|---|
| `published.jsonl.gz` | The public record as served by `api.deliverome.org/surfaceome/v1/genes/{SYMBOL}` (+ `/evidence`) on 2026-09-27 | `cu_v3_sonnet_2026_06` (June–July 2026; a few records re-generated in August, e.g. by the A1-recovery backfill) |
| `full_rerun.jsonl.gz` | A from-scratch re-annotation — literature discovery, abstract triage, paper selection, section builders and synthesizer all re-executed | `deep_dive_concordance_v1` (2026-09-27; private D1 only, never published) |
| `fixed_evidence_replay.jsonl.gz` | Builders + synthesizer re-run on each published run's own evidence ledger (discovery and selection held fixed) | replay of `cu_v3_sonnet_2026_06` intermediates (2026-09-27) |
| `sample_genes.tsv` | The 50 genes and their batch | — |

**Sampling.** Two disjoint batches of 25 genes, drawn uniformly at random from
the 5,332 deep-dive records (`random.seed(20260927)` for batch 1, then
`random.seed(20260928)` over the remaining genes for batch 2).

**Same prompts.** Every published record, the full re-run and the replay used
the same prompt SHA (`8e6605494dbc`) and prompt-corpus version (2.50.2); the
record schema moved from 2.14.2 to 2.14.4 between the June run and the re-run.
The full re-run is therefore a *conservative* test: it also absorbs three
months of literature and cache drift.

**Format.** One JSON object per line: `{"hgnc_symbol", "sample_batch",
"record"}`, where `record` is a full `SurfaceomeRecord` (the published set
carries its evidence ledger under `evidence`, as the Worker serves it).

**Rebuild the figure inputs.**

```bash
uv run python scripts/build/build_deep_dive_concordance_tsvs.py
uv run python scripts/figures/deep_dive_replicate_kappa.py
```

**Cost.** Full re-run $80.19 (50 genes), fixed-evidence replay $35.15.
