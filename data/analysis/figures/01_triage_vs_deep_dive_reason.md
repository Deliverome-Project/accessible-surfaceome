# Supplementary Figure 12 — `triage_vs_deep_dive_reason`

**MOCK figure** — placeholder counts pending the v2 deep-dive sweep
joining onto the triage_run table; only ~20 deep-dive records exist
as of this draft.

19×19 confusion matrix between the triage agent's first-pass
`surface_call_reason` (rows) and the deep-dive synthesizer's
re-derived `surface_call_reason` (columns) on the genes that have
both a triage record AND a published deep-dive record. Both axes
draw from the same closed `TriageReason` enum in `models.py`, so the
diagonal (red cell outlines) is exact-reason agreement; off-diagonal
cells split into within-bucket reassignments (same Yes / Contextual /
No bucket, different reason) and cross-bucket flips (the rarer
cells that flag verdict-level drift between the two agents).

Tick labels are colored by bucket (yes = green / contextual = orange
/ no = grey) and thick black lines mark the bucket boundaries on each
axis, so the reader can see at a glance whether an off-diagonal cell
is a within-bucket reassignment or a cross-bucket flip. The expected
real-data pattern (once the full sweep lands) is heavy diagonal
density, moderate off-diagonal within-bucket reassignments, and rare
cross-bucket flips — the latter are the cells worth opening for
paper-level review.

## Reproduce

```bash
uv run make_triage_vs_deep_dive_reason.py
```

The bundled `triage_vs_deep_dive_reason.tsv` is the single data
source — one row per gene with `gene_symbol`, `uniprot_acc`,
`triage_reason`, `deep_dive_reason`. No other URLs, no other
TSVs. Produced from
[`scripts/build_figure_tsvs.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/build_figure_tsvs.py)
in the project repo, which joins the production triage records
(public D1 `triage_run_public` Sonnet/ncbi hits) against the
published deep-dive records (Worker `/v1/genes/{SYMBOL}` index).

## Canonical generator

The in-repo canonical figure at
[`data/analysis/figures/triage_vs_deep_dive_reason.pdf`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/data/analysis/figures/triage_vs_deep_dive_reason.pdf)
is rendered by
[`scripts/triage_vs_deep_dive_reason.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/triage_vs_deep_dive_reason.py)
in the project repo. This gist mirror ships an equivalent
single-panel render from the same bundled TSV.
