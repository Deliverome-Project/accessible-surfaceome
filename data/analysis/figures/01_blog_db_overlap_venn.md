# Blog figure — five surface-protein databases barely agree

Five-way Venn over UniProt, SURFY, CSPA, GO CC and HPA, with two
redundant encodings of magnitude:

- **Label type size** scales with each region's protein count, using a
  constrained search that shrinks the scale until no two labels collide
  while keeping every label inside its own region.
- **Ellipse opacity** scales with each database's total set size, so a
  bigger source reads as a heavier wash.

**The counts are exact.** Only the type size and the wash are
exaggerated — no geometry is redrawn, and every printed number is the
real region count from the bundled TSV.

## This is not a numbered paper figure

Figure 1 is now an **UpSet** ([gist](https://gist.github.com/beccajcarlson/d655abfc9c7deeaff1cfbe584de96ffa)).
A five-set Venn cannot be drawn area-proportionally: all 31 regions are
non-empty and span 3–1,063 proteins, and the best least-squares fit of
five ellipses draws the 188-protein five-way core at 305 while
collapsing a 252-protein region to 9. That is a property of five-set
geometry, not of the render.

It keeps its place as a blog / talk visual, where "these five databases
barely agree" has to land in one glance rather than survive re-analysis.

## Reproduce

```bash
uv run make_blog_db_overlap_venn.py
```

Dependencies are declared inline (PyPA inline script metadata), so `uv`
resolves them — no `pip install` step. The script reads the bundled
`blog_db_overlap_venn.tsv` sitting next to it.

## Canonical sources

- Figure generator:
  [`scripts/figures/blog_db_overlap_venn.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/figures/blog_db_overlap_venn.py)
- Data:
  [`data/processed/figures/blog_db_overlap_venn.tsv`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/data/processed/figures/blog_db_overlap_venn.tsv)

## Credit

The count-scaled label treatment and the collision-avoiding placement
search are Nirmit Damania's, from PR #217.
