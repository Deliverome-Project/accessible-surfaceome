# figures — canonical project figures + reproduction gists

Curated set of headline figures for the accessible-surfaceome project,
each paired with a standalone `make_<slug>.py` reproduction script.
Expected to stay small (~10 figures total).

A figure earns a slot here only when:

1. Its data lineage is canonical (D1, or a flat TSV exported from D1,
   or a public-repo TSV) — never the gitignored runner-output JSON tree.
2. The figure has stabilised — re-running the generator produces a
   visually-equivalent output across two consecutive runs.
3. A `make_<slug>.py` + `01_<slug>.md` pair exists alongside the
   PDF + PNG.

In-progress / scratch plots live in `data/analysis/triage_bench/` and
similar working folders. Promote to `figures/` only when the three
conditions hold.

## Current figures

There are 21 published figures. The canonical list — figure number, slug,
reproduction gist, and Software Heritage identifier — is generated, so it
never drifts:

- [`paper/figure_index.md`](../../../paper/figure_index.md) — the manuscript-facing index
- [`gist_map.json`](gist_map.json) — slug to gist id
- [`swhid_map.json`](swhid_map.json) / [`figure_swhids.json`](figure_swhids.json) — slug to SWHID

Regenerate the index with `uv run python scripts/build_figure_index.py`.

Each PDF + PNG also carries its gist URL in file metadata (PDF
`dc:source` XMP field, PNG `Source` tEXt chunk). Refresh with
`scripts/figures/embed_figure_gist_metadata.py` after any regeneration.

## Data sources used by the reproduction scripts

Predictions and truth labels are read from the public API (see
`CLAUDE.md` "Final figures must read from the public API"). The
per-DB universe table and cutoff-tradeoff points are still
committed TSVs — they don't have API endpoints yet.

- `https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=mainbench_canonical_v1&replicate=1`
  — 1,470 per-cell predictions (gene × model × variant), with
  cost_usd + token counts, **plus** per-source DB votes
  (uniprot/go/surfy/cspa/hpa) + uniprot_acc joined in server-side
  (21 cols total). Source-of-truth replacement for the former
  `data/processed/triage_bench/mainbench_canonical_v1.tsv`.
- `https://api.deliverome.org/surfaceome/v1/benchmark/export.tsv`
  — 147-gene bench-restricted multi-model sweep with truth labels
  + DB votes joined in (24 cols, one row per gene × model × variant).
  For truth labels only (the historical 7-column shape), use
  `/v1/benchmark` JSON instead.
- [`data/processed/triage_bench/db_cutoff_tradeoff_points.tsv`](../../processed/triage_bench/db_cutoff_tradeoff_points.tsv)
  — precomputed cutoff-variant accuracy points; dumped as a side
  effect of `scripts/figures/triage_bench_db_barplot.py::make_db_tradeoff_plot`.
- [`data/processed/candidate_universe/candidate_universe.tsv`](../../processed/candidate_universe/candidate_universe.tsv)
  — 5-DB surface-vote table (also drives the Venn).
- [`data/eval/triage_benchmark_v1.tsv`](../../eval/triage_benchmark_v1.tsv)
  — 147-gene ground-truth source (input to the D1 sync; the truth
  columns become the `truth_*` fields in `/v1/benchmark/export.tsv`
  + the `/v1/benchmark` JSON endpoint. Figures read the API, not
  this file.

## Gist-publishing workflow

Per the CLAUDE.md "Final-Figure Gist Convention":

1. Edit `make_<slug>.py` until it produces the figure you want.
2. Confirm `uv run make_<slug>.py` produces a clean output against
   the canonical data sources.
3. Create the gist **as public** — figure-reproduction gists are linked
   from Substack / blog posts so discoverability is the right default:
   ```
   gh gist create --public 01_<slug>.md make_<slug>.py -d "<short description>"
   ```
   GitHub does NOT allow flipping visibility after creation — pick
   public on first creation. Before publishing a new gist for an
   existing figure, check the slug → gist-ID map in the saved-memory
   `figure_gists.md` to avoid duplicates.
4. Record the gist URL in the canonical generator script's module
   docstring under a `# Reproduction:` line so readers can find it
   from the source. Also set the `GIST_URL` constant in
   `make_<slug>.py` so the URL embeds in PNG `Source` / PDF `Subject`
   metadata on next regeneration.

The on-repo `make_<slug>.py` is the source of truth; the gist is the
readers' minimal-dependency mirror.
