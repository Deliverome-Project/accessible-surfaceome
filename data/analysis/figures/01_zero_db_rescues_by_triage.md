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

Source: the catalog endpoint is fetched live —
[`api.deliverome.org/surfaceome/v1/catalog`](https://api.deliverome.org/surfaceome/v1/catalog).
19,324 protein-coding human genes; each row carries `db` (the
classical-DB yes-vote count) plus a `triage` block with `verdict`
and `reason`. The rescue slice = `db == 0 AND verdict ∈ {yes, contextual}`.

Canonical in-repo generator:
[`data/analysis/triage_bench_exploration/zero_db_rescues_by_triage.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/data/analysis/triage_bench_exploration/zero_db_rescues_by_triage.py).
