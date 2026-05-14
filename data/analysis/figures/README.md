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

## Current figures (5)

| Figure | Reproduction gist (public) | Generator |
|--------|---------------------------|-----------|
| `db_overlap_venn` | [d655abfc…](https://gist.github.com/beccajcarlson/d655abfc9c7deeaff1cfbe584de96ffa) | `scripts/triage_bench_db_venn.py::make_plot` |
| `db_correctness_by_class` | [2bb4f7aa…](https://gist.github.com/beccajcarlson/2bb4f7aac629535982c142bc2032e04d) | `scripts/triage_bench_db_barplot.py::make_by_class_plot` |
| `db_cutoff_tradeoff` | [f9319af8…](https://gist.github.com/beccajcarlson/f9319af882e372194bd30640c0cbf2ed) | `scripts/triage_bench_db_barplot.py::make_db_tradeoff_plot` |
| `db_correctness_overall` | [9c765ed9…](https://gist.github.com/beccajcarlson/9c765ed9673d7bd845c3ac091ad2204d) | `scripts/triage_bench_db_barplot.py::make_overall_plot` |
| `benchmark_cost_vs_accuracy` | [d7f764d2…](https://gist.github.com/beccajcarlson/d7f764d2de288ae31cf44173bc396d41) | `scripts/triage_bench_db_barplot.py::make_cost_vs_accuracy_plot` |

Each PDF + PNG also carries its gist URL in file metadata (PDF
`dc:source` XMP field, PNG `Source` tEXt chunk). Refresh with
`scripts/embed_figure_gist_metadata.py` after any regeneration.

## Data sources used by the reproduction scripts

All published as plain-git TSVs in the repo (LFS-exempted in
`.gitattributes`) so the gist scripts can fetch them via
`raw.githubusercontent.com`:

- [`data/processed/triage_bench/mainbench_canonical_v1.tsv`](../../processed/triage_bench/mainbench_canonical_v1.tsv)
  — 1,470 per-cell predictions exported from D1 by
  [`scripts/export_mainbench_to_tsv.py`](../../../scripts/export_mainbench_to_tsv.py).
- [`data/processed/triage_bench/db_cutoff_tradeoff_points.tsv`](../../processed/triage_bench/db_cutoff_tradeoff_points.tsv)
  — precomputed cutoff-variant accuracy points; dumped as a side
  effect of `scripts/triage_bench_db_barplot.py::make_db_tradeoff_plot`.
- [`data/processed/candidate_universe/candidate_universe.tsv`](../../processed/candidate_universe/candidate_universe.tsv)
  — 5-DB surface-vote table (also drives the Venn).
- [`data/eval/triage_benchmark_v1.tsv`](../../eval/triage_benchmark_v1.tsv)
  — 147-gene ground-truth labels.

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
