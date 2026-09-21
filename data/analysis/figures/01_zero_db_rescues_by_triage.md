# Zero-DB rescues by triage — what the agent catches that classical surface DBs miss

Whole-genome view of the genes the **Sonnet (+ NCBI) triage agent**
flags as surface-accessible despite **none** of the five classical
surface DBs (UniProt / GO CC / HPA / SURFY / CSPA) voting "yes." Two
grouped bar panels on a shared y-axis show per-reason counts within
each verdict bucket:

* **yes** — definite surface, by triage agent's `verdict=yes`
* **contextual** — state / lineage / partner-dependent surface
  display, by triage agent's `verdict=contextual`

Beneath each panel, select gene callouts illustrate the kind of
biology the triage agent surfaces in each verdict bucket. Each
callout's reason is verified at runtime against the catalog's
`triage.reason` — mismatches raise an error.

Run:

```
uv run make_zero_db_rescues_by_triage.py
```

Source: the whole-proteome catalog TSV — [`data/processed/catalog/whole_proteome_catalog.tsv`](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/processed/catalog/whole_proteome_catalog.tsv). 19,324 protein-coding human genes; each row carries the five `*_surface_flag` fields + `n_sources_surface` + the canonical Sonnet `sonnet_verdict` and `sonnet_reason`. The rescue slice = `n_sources_surface == 0 AND sonnet_verdict ∈ {yes, contextual}`. Sourced from D1 by [`scripts/tsv-export/export_whole_proteome_catalog_to_tsv.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/tsv-export/export_whole_proteome_catalog_to_tsv.py).

Canonical in-repo generator:
[`scripts/figures/zero_db_rescues_by_triage.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/figures/zero_db_rescues_by_triage.py).
