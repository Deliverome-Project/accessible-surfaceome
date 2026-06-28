# DB overlap Venn — 5-way agreement across the M1 surface databases

Topologically-correct 5-ellipse Venn of the M1 candidate universe.
Each ellipse is one surface-prediction DB (UniProt subcellular,
GO cellular component, HPA, SURFY, CSPA). Cell labels are protein
counts in each of the 31 non-empty regions.

Note: 5-set Venns can't be drawn area-proportional in 2D (open
geometry problem). For an area-proportional view of the same data,
see the companion UpSet plot.

Run:

```
uv run make_db_overlap_venn.py
```

Source (fetched live from the public repo):

- DB votes (whole-proteome catalog): [`data/processed/catalog/whole_proteome_catalog.tsv`](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/processed/catalog/whole_proteome_catalog.tsv)

Canonical in-repo generator:
[`scripts/figures/triage_bench_db_venn.py::make_plot`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/figures/triage_bench_db_venn.py).
