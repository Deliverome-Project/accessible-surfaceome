# scripts/archive/

Completed one-shot scripts kept for provenance. **None of these run in the
current pipeline.** They are kept so a future archaeologist can trace how
past D1 schema migrations, resolver fixes, and one-time corrections were
applied.

| Subdir | What's here |
|---|---|
| `backfills/` | One-shot column / row backfills against D1 + on-disk records |
| `fixes/` | Targeted corrections to past states (resolver collisions, isoform metadata, ortholog metadata) |
| `reruns/` | Replays for specific cohorts / record subsets after a fix or upstream change |
| `renderers/` | HTML renderers for one-off evaluation pages (deep-dive previews, paragraph-clip probes) |
| `probes-research/` | Research probes — paywall bot-block analysis, Haiku paraphrase repair, paragraph-clipping |
| `builders-oneshot/` | Cohort/catalog builders run once (whole-genome-minus-M1, reconfirm-zero-DB gene list, structure-viewer data) |
| `d1-migrations/` | Schema migrations + one-time D1 transforms |

If a script here is needed again, prefer rewriting against the current
codebase to running this copy unmodified — paths and schemas have moved.
