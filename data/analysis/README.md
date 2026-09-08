# data/analysis

Outputs of analyses run against the processed data. Two kinds of thing live
here, and the distinction is what decides where a new file belongs.

## `figures/` — the published figures

Everything the manuscript cites. Each figure keeps its generator, its input
TSV, its rendered PDF/PNG, and its caption together in this one directory:

- `make_<slug>.py` — the standalone gist mirror of the canonical generator,
  which lives at `scripts/figures/<slug>.py`. Guard tests fail if the pair
  drifts apart, so edit both.
- `01_<slug>.md` — the analysis note behind the figure.
- `<slug>.caption.md`, `<slug>.pdf`, `<slug>.png` — caption and renders.
- `by_paper_number/` — symlinks mapping the manuscript's figure numbering onto
  those files, so renumbering a figure never moves the real artifact.
- `gist_map.json`, `swhid_map.json`, `figure_swhids.json` — the reproduction
  gist and Software Heritage identifier for each figure.

There are 19 `make_*.py` generators for 21 figures: `deep_dive_flow` and
`web_preview` are hand-authored SVG schematics with no data pipeline, so they
have a caption and an `.svg` but no generator.

## Topic directories — exploratory analyses

`candidate_universe_agreement/`, `db_vs_sonnet_inclusion/`, `paywall_bot_block/`,
`cross_source_uniprot_audit/`, `topology_reaudit/`, `v2_deterministic_coverage/`,
`a1_recovery/`, `blog/`.

Each holds one investigation's own outputs — tables, notes, and sometimes a
plot. **None of these plots appear in the manuscript.** They are working
figures and, in `blog/`, a post asset. A few directories are the provenance
record of a completed remediation rather than an ongoing analysis:
`a1_recovery/` holds the manifest and rescue plan for the A1 evidence-ledger
recovery, which `modal/a1_recovery_app.py` still reads.

## Where a new file goes

If the manuscript will cite it, it belongs in `figures/` with a generator, a
caption, and a gist. If it is an investigation whose conclusion matters more
than its plot, give it a topic directory.
