# Deep-dive vs Sonnet+NCBI accuracy on SurfaceBench (Supp. Fig. S12)

On the SurfaceBench benchmark genes deep-dived so far (**n = 27 of 147**,
the intersection), the evidence-anchored deep dive matches the
Sonnet+NCBI triage's soft-credit accuracy, and its confidence tier
tracks ground-truth difficulty. Each protein's deep-dive surface call
and the Sonnet+NCBI triage call are scored against the curated
ground-truth verdict under the **soft-credit rule** — a
contextually-surface protein counts correct when called surface.

- **(a)** Overall soft-credit accuracy — deep dive vs Sonnet+NCBI.
- **(b)** Accuracy split by ground-truth bucket (yes / contextual / no).
  The deep-dive bar is **stacked by the tier** it assigned to the
  correctly-classified genes — canonical / likely / low (green shades)
  and uncertain / no (grey), the same five-tier palette as Figure 5a —
  so its confidence composition is visible. Sonnet+NCBI accuracy is the
  **mean of three mainbench replicates** (one dot per replicate; error
  bar = SEM across replicates); the deep dive runs once per gene.

Deep dive and Sonnet are near-identical overall (**96% vs 96%**), and
Sonnet's SEM overlaps the deep-dive bar in every bucket.

> **PRELIMINARY** — n = 27 is small (the 'no' bucket is only 2 genes),
> so read these as an early signal; the estimates firm up as the sweep
> covers more benchmark genes.

## Reproduce

```bash
uv run make_deep_dive_vs_sonnet_benchmark.py
```

The script reads the bundled `deep_dive_vs_sonnet_benchmark.tsv` (one row
per deep-dived bench gene, carrying both predictors' soft-credit
correctness, the deep-dive tier, and the three Sonnet replicate flags)
and writes `deep_dive_vs_sonnet_benchmark.{pdf,png}`. No network access —
the data is bundled in this gist.

## Canonical sources

- **Data** — [`data/processed/figures/deep_dive_vs_sonnet_benchmark.tsv`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/data/processed/figures/deep_dive_vs_sonnet_benchmark.tsv),
  built by [`scripts/build_figure_tsvs.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/build_figure_tsvs.py)
  (`build_deep_dive_vs_sonnet_benchmark`), which joins the SurfaceBench
  ground truth, the per-gene deep-dive tier, and the three-replicate
  Sonnet+NCBI mainbench triage.
- **Canonical generator** — [`scripts/deep_dive_vs_sonnet_benchmark.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/deep_dive_vs_sonnet_benchmark.py)
  (this file is its standalone mirror).
