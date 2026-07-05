# Main Figure 6 — Deep-dive record richness across five axes

**MOCK figure** — a 5-panel violin showing the per-record distribution
along the axes that characterise *how much information* a single deep
dive captures for a gene. A reader clicking any gene on the viewer
should expect roughly this much per axis. Panels are split or filtered
by surface verdict so the reader can see which dimensions genuinely
separate calls from non-calls vs. which look similar across the cohort.

The bucket label, `surface_verdict_bucket`, comes from each record's
`executive_summary.surface_accessibility`:

- **`no`** — agent's verdict is `"no"` (not a surface protein).
- **`surface_yes`** — any non-`no` verdict (`high` / `moderate` /
  `low` / `uncertain`). "Surface yes, even weak" — the union of all
  positive calls.

## What's plotted

Five small per-panel violins (one Y axis each, because the scales
range from boolean-counts ≤ 24 to papers in the hundreds — a shared Y
would compress the small axes into the baseline):

- **a. Papers found** — discovery-corpus size (EuropePMC + PubTator NER
  + gene2pubmed union, deduped by PMID). **Two violins** (no vs
  surface-yes-even-weak). **Fully synthesised**: the `n_papers_found`
  field landed in schema 2.14.0 *after* the published records were
  annotated, so every record's value is null pending a discover-only
  rerun. Each bucket's fan draws from a lognormal anchored on the
  methods-section stats (median 234.5, range ~50–400 for surface-yes;
  offset down to 140 for the "no" bucket so the two violins are
  visually distinguishable while staying within the documented range).
- **b. Papers selected** — unique papers in the evidence list
  (`len({span.source.source_id for ev in evidence})`). **Two violins**
  (no vs surface-yes-even-weak). **Real per-gene values**; each
  bucket's violin fan is synthesised around its own real mean / std.
- **c. Papers with extracellular evidence** — subset of (b) where the
  agent extracted *primary*-tier evidence with an experimental
  surface-method tag (flow cytometry, immunofluorescence,
  immunohistochemistry, mass-spec surfaceome, live-cell surface
  labeling). **Single violin, surface-yes only** — the "no" bucket is
  filtered out because non-surface proteins have no extracellular
  evidence by definition. **Real values.**
- **d. Filters carrying evidence** — count of populated catalog filter
  fields out of 24 (14 enums + 10 booleans the catalog UI surfaces).
  **Single violin, surface-yes only.** **Real, near-saturated** (~22
  of 24) because most filter values are mandatory in the schema; the
  under-24 cases are genes where an optional facet (e.g.,
  `primary_compartment`) wasn't confidently set.
- **e. Deterministic features populated** — count of non-null
  `deterministic_features` sub-blocks out of 7 (canonical_topology,
  isoform_topologies, structure, orthologs, paralogs, surface_bind,
  homo_oligomerization). **Single violin, surface-yes only.** **Real
  values**; missing entries fall out of genes outside SURFACE-Bind
  coverage or without a Schweke homomer prediction.

Dark dots = real values from the 20 published deep dives (6 in the
`no` bucket; 14 in the `surface_yes` bucket). The violin shape + IQR
box is a synthesised 5,000-draw fan that communicates the *shape* a
full-cohort distribution would have. Panels (b)–(e) draw their synth
from `Gaussian(empirical_mean, max(empirical_std, 0.15·mean))` clipped
to a sensible domain; panel (a) draws from the methods-section stats
since no real records yet carry the field. MOCK badges sit at the
upper-right of each mocked panel so a reviewer never confuses
synthesis with measurement.

## Reproducibility

```bash
uv run make_deep_dive_record_richness.py
```

The script reads only the bundled `deep_dive_record_richness.tsv` next
to it — no network fetch, no external joins. The TSV carries one row
per published deep-dive record with `surface_verdict_bucket` ∈ {`no`,
`surface_yes`} plus four real per-gene axes (`papers_selected`,
`papers_with_ec`, `n_filters_evidence`, `n_det_features`). Panel (a)'s
`papers_found` axis is excluded from the TSV because every record's
value is null pending the discover-only backfill — the mirror
synthesises the fan from the methods-section stats directly.

## Canonical generator (full version)

The in-repo figure at
[`data/analysis/figures/deep_dive_record_richness.pdf`](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/analysis/figures/deep_dive_record_richness.pdf)
is produced by
[`scripts/deep_dive_record_richness.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/deep_dive_record_richness.py)
in the project repo. The canonical script walks
`viewer/public/data/surfaceome/*.json` inline; this gist mirror reads
the pre-aggregated per-figure TSV instead so it stays self-contained.

## Data lineage

- Per-gene viewer snapshots: [`viewer/public/data/surfaceome/*.json`](https://github.com/Deliverome-Project/accessible-surfaceome/tree/main/viewer/public/data/surfaceome)
- Verdict bucket source: `executive_summary.surface_accessibility` on
  each snapshot (`no` → `no`; any other value → `surface_yes`).
- Pre-joined per-figure TSV (bundled here): [`data/processed/figures/deep_dive_record_richness.tsv`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/data/processed/figures/deep_dive_record_richness.tsv)
- TSV builder: [`scripts/build_figure_tsvs.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/build_figure_tsvs.py)
  — walks the snapshots and extracts the four per-gene richness axes +
  the bucket label (excludes `papers_found` since the field is null on
  every record pending the discover-only backfill).
- Catalog filter / evidence-type / deterministic-feature enums:
  [`src/accessible_surfaceome/tools/_shared/models.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/src/accessible_surfaceome/tools/_shared/models.py)
  + [`viewer/lib/deep-dive-fields.ts`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/viewer/lib/deep-dive-fields.ts).
