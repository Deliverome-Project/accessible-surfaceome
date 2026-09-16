# Figure 1 — Five surface protein databases agree on only 188 proteins

UpSet over the five source surface-protein databases (UniProt, GO CC, HPA,
SURFY, CSPA). Each bar counts the proteins found in that database *or
combination of databases and no others*; columns are grouped by how many
databases list the protein, running from all five on the left to a single
database on the right. The left panel gives each database's total size
against the five-database average.

This figure replaces a 5-way Venn. The Venn is not area-proportional and
cannot be made so: all 31 regions are non-empty and span 3–1,063 proteins,
and a least-squares fit of five ellipses to those areas draws the
188-protein five-way core at 305 (+62%) while collapsing the 252-protein
UniProt∩SURFY∩CSPA region to 9. Every bar in an UpSet is a true count.

## Reproduce

```bash
uv run make_db_overlap_upset.py
```

The script declares its own dependencies via PyPA inline script metadata,
so `uv` resolves them; no `pip install` step. It reads the bundled
`db_overlap_venn.tsv` (same five flags, one row per accession) if present
next to it, and otherwise falls back to the copy in the repository.

## Canonical sources

- Figure generator:
  [`scripts/figures/db_overlap_upset.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/figures/db_overlap_upset.py)
- Data:
  [`data/processed/figures/db_overlap_venn.tsv`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/data/processed/figures/db_overlap_venn.tsv)
