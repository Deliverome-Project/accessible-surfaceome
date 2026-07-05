# Main Figure 6 — Deep-dive record richness across five axes

A 5-panel violin showing the **real** per-gene distribution along five axes
that characterise *how much information* a single deep dive captures for a
gene. Every panel is faceted by the **deep-dive tier** (`canonical` / `likely`
/ `low` / `no`) — the top-level verdict from the deep-dive bucket logic — so a
reader can see how record richness scales with confidence rather than a coarse
surface-vs-non-surface split. Each violin is the real distribution of that
tier's genes; there is no synthesised fan.

## What's plotted

Five small per-panel violins (one Y axis each, because the scales range from
feature counts 0–24 to papers in the hundreds — a shared Y would compress the
small axes into the baseline). A faint point strip overlays the real per-gene
values so the actual per-tier `n` is visible. Panels a/b keep the `no` tier;
panels c–e drop it (non-surface proteins carry little extracellular evidence by
definition). The `uncertain` tier (n=9) is dropped everywhere as too small to
plot.

- **a. Papers found** — discovery-corpus size (EuropePMC + PubTator NER +
  gene2pubmed union, deduped by PMID). Tiers: canonical, likely, low, no.
- **b. Papers selected** — unique papers read full-text into the evidence list.
  Tiers: canonical, likely, low, no.
- **c. Papers with extracellular evidence** — selected papers carrying a
  *primary*-tier experimental surface-method tag (flow cytometry,
  immunofluorescence, IHC, mass-spec surfaceome, live-cell surface labelling).
  Tiers: canonical, likely, low.
- **d. LLM filters with a positive finding** — how many of the viewer's 24
  `provenance:"llm"` filter facets carry a *positive / substantive*
  determination. Definitive negatives and `unknown` do **not** count, so this
  reads record **richness** (what the agent found), not schema completeness —
  the LLM-side analogue of panel e. Counting *any* call instead saturates near
  24 for every gene (the agent almost always makes some call), so the
  positive-finding count is what separates the tiers: canonical ~19 → likely
  ~17 → low ~15 (median of 24). Tiers: canonical, likely, low.
- **e. Deterministic features (derived, 0–7)** — how many of the seven derived
  `deterministic_features` sub-blocks carry data (canonical_topology,
  isoform_topologies, structure, orthologs, paralogs, surface_bind,
  homo_oligomerization). Tiers: canonical, likely, low.

## Reproducibility

```bash
uv run make_deep_dive_record_richness.py
```

The script reads only the bundled `deep_dive_record_richness.tsv` next to it —
no network fetch, no external joins. The TSV carries one row per deep-dived
gene with its `tier` plus the five real per-gene richness axes.

## Canonical generator (full version)

The in-repo figure at
[`data/analysis/figures/deep_dive_record_richness.pdf`](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/analysis/figures/deep_dive_record_richness.pdf)
is produced by
[`scripts/deep_dive_record_richness.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/deep_dive_record_richness.py)
in the project repo. This gist mirror reads the pre-aggregated per-figure TSV
instead so it stays self-contained.

## Data lineage

- Public D1 `surface_annotation.annotation_json` — one row per published
  deep-dive record.
- Facet export: [`scripts/export_deep_dive_figure_source.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/export_deep_dive_figure_source.py)
  — server-side `json_extract` pulls the per-gene axes (including the
  positive-finding `n_llm_evidence` count over the 24 filter facets and the
  `n_det_features` count over the 7 deterministic-feature blocks) into
  `data/processed/deep_dive/deep_dive_records.tsv`.
- Pre-joined per-figure TSV (bundled here): [`data/processed/figures/deep_dive_record_richness.tsv`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/data/processed/figures/deep_dive_record_richness.tsv)
  — [`scripts/build_figure_tsvs.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/build_figure_tsvs.py)
  folds the export into the tier-faceted rows the figure draws (one row per
  deep-dived gene: the five axes + the deep-dive `tier`).
- Filter / deterministic-feature enums:
  [`src/accessible_surfaceome/tools/_shared/models.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/src/accessible_surfaceome/tools/_shared/models.py)
  + [`viewer/lib/deep-dive-fields.ts`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/viewer/lib/deep-dive-fields.ts).
