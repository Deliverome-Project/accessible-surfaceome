# CellxGene RNA enrichment

How the surfaceome viewer computes "where is this gene expressed?" from
CZI Census 2025-11-08, what the chips mean, the known limitations, and
the TODO list for the next pass.

## Pipeline at a glance

```
CZI WMG (1 GB gzip) ──▶ build_czi_enrichment_v2_1.py ──▶ per-gene JSON
                            │
                            ├─ noise gate per (cl, tissue)
                            ├─ aggregate to 5 axes (see "Axes" below)
                            ├─ τ over linear pop mean per axis
                            └─ classify by τ cutoffs
                                                │
                                                ▼
                                surfaceome_public.czi_cellxgene_enrichment (D1)
                                                │
                                                ▼
                                /v1/genes/{symbol}/cellxgene (Worker)
                                                │
                                                ▼
                                viewer CellxGeneCard + FiltersCard chips
```

Bulk-sync script + embed script keep the per-gene snapshot under
`viewer/public/data/surfaceome/{SYMBOL}.json` in lockstep with D1, so a
reader downloading the snapshot gets the same data the viewer renders.

## Inputs

| Source | What we use |
|---|---|
| `CZI_WMG_GZ` — `expression-summary-condensed-DD-MM-YY.csv.gz` | per (gene, tissue, cell_type): `nnz` (expressing cells) + `sum_log1p(CP10K)` |
| `CZI_TISSUE_COUNTS` — `(cell_type, tissue, n_cells)` TSV | per (cl, ub) cell-count denominator |
| `cl-basic.obo` — OBO Foundry CL release (3.2 MB) | cell ontology graph for compartment / family rollup |
| `uberon.obo` — OBO Foundry UBERON release (~50 MB) | tissue ontology graph for category / organ rollup |
| `Homo_sapiens.protein_coding.with_hgnc.tsv` | Ensembl ↔ symbol ↔ HGNC mapping |

## The five axes

Per-gene we emit five HPA-elevation classifications. The chip prefers the
**middle-granularity** axes (cell_family + tissue_organ) — they're the
HPA-sized entities (~150 each) where the classifier reads most cleanly.

| Axis | Entities | How it's computed | Used by |
|---|---|---|---|
| `cell_type_enrichment` | ~600 leaf CL terms | per-leaf pooled across tissues | viewer chip fallback, debug |
| `cell_family_enrichment` ← **chip primary** | ~150 family CL terms | leaf → nearest CL ancestor with 6–40 CZI cohort descendants (`cl_family.py`) | viewer chip, summary card |
| `cell_class_enrichment` | 10 compartments | leaf → ancestor in priority list (`cl_graph.py`) | viewer chip fallback |
| `tissue_enrichment` | 410 leaf UBERON terms | per-UBERON pooled across cell types | viewer chip fallback, debug |
| `tissue_organ_enrichment` ← **chip primary** | ~150 organ UBERON terms | UBERON → cohort ancestor with most cohort descendants (`uberon_organ.py`) | viewer chip, summary card |
| `tissue_category_enrichment` | 13 organ systems | UBERON → category (programmatic walk, `tissue-categories-uberon-map.generated.ts`) | viewer chip fallback |

Per-axis signal aggregation is **max-pop-mean-per-rollup** — each rollup
competes via its strongest representative leaf, not by summing or
averaging across the rollup. This avoids dilution (KLK2's prostate
luminal CL shouldn't be diluted by averaging across all Epithelial
cells genome-wide).

## τ-cutoff classification

Per axis we compute Yanai 2005's specificity score on the **linear
population mean** of eligible entities:

```
τ = Σ (1 − x_i / x_max) / (N − 1)
x_i = expm1(mean_log1p_cp10k) × pct_expressing per entity
```

τ ∈ [0, 1]: **0** = uniformly expressed across eligibles, **1** =
concentrated in one entity. The discrete class then follows HPA's
tissue-specificity nTPM convention:

| τ | Class |
|---|---|
| ≥ 0.85 | **enriched** |
| 0.5 ≤ τ < 0.85 | **enhanced** |
| < 0.5 | **low_specificity** |
| no eligibles | **not_detected** |
| 1 eligible | **enriched** (definitionally) |

Companion: `fold_change` = top-vs-next-ranked ratio (informational; not
class-determining under τ cutoffs).

### Why τ cutoffs, not HPA's 4× rule

HPA's 4× rule was sized for their ~40 broad tissues. Reapplied to
cellxgene's 410 UBERONs or 600 leaf CLs, it reads `low_specificity` for
genes that are clearly elevated in a small set — none of the eligible
siblings dominates each other 4×. τ doesn't care about pair-wise
ratios; it asks "how concentrated is the overall distribution?" which
scales gracefully across axis sizes. Karbalaei 2024 (single-cell
benchmark) reaffirms τ as the most robust specificity metric in
single-cell contexts.

### Why population mean, not mean-among-expressors

`mean_log1p(CP10K)` in CZI's WMG is the mean *among expressing cells*. A
gene with 1 cell at CP10K=20 in a 10,000-cell tissue (pct=0.01%) looks
identical to a gene at 100% prevalence with the same intensity. HPA /
GTEx / Tabula Sapiens / Karbalaei 2024 all run on the population mean
(intensity × prevalence — algebraically equal to mean across ALL cells
including non-expressors). Multiplying by `pct_expressing` collapses
both axes into one number.

### Why "enhanced" doesn't include zero baseline

The enriched / not_detected tests count below-noise entities as 0 in
the universe (so GPR75 signal in 4 of 56 tissues classifies as
enriched, not low_specificity). The `enhanced` test *doesn't* include
the zero baseline — including 50+ zeros drags `mean(rest)` to ~0.5 and
EVERY moderately-expressed gene reads as enhanced over its
most-prevalent tissue. The cutoff is asymmetric by design.

## Why eye / tongue / vasculature appear high for many genes

This is **biological, not a sampling artifact**. CZI samples eye
(retina), tongue (buccal / lingual epithelium), and vasculature
(endothelium) using cell types that biologically express many surface
receptors at high prevalence and intensity. The population mean lands
high because the underlying biology of those cell types is
surface-protein-rich, not because of how many cells were profiled.

Sampling density affects `n_total` (statistical power for the noise
gate) but NOT `pct_expressing` — `pct` is a normalized fraction.

## Known weaknesses

1. **`pct_expressing` overcount on the tissue axis.** Per-UBERON
   `n_total` comes from summing `pair_counts[(cl, ub)]` over CL. When
   CZI's WMG has parent + child CL annotations for the same cells
   ("naive T cell" and "T cell" both annotated), the cell is counted
   in both pairs, inflating both numerator and denominator. Usually
   they cancel, but for tissues with deep CL hierarchies it doesn't —
   CD63 pancreas yielded raw pct=154%. Clamp to ≤100% so the chart
   doesn't render nonsense; long-term fix is a per-UBERON cell-union
   count from `cellxgene_census.obs.value_counts(['tissue_ontology_term_id'])`
   instead of summed pair counts.

2. **Stale cell-count cache vs WMG export.** The cell-count cache at
   `/tmp/czi_cell_tissue_counts.tsv` was generated by an older
   `obs.value_counts()` snapshot than the 2025-11-08 WMG it's joined
   against. EGFR-embryo: cache has 4 CL terms profiled, WMG sees 36
   with 28k expressing cells. Mitigation: WMG-nnz fallback (set
   `n_total = max(cache_n_total, nnz)` and flag `is_uncertain=True`).
   Long-term fix: regenerate the cell-count cache from the same Census
   snapshot.

3. **Cell-family fallback to compartment.** When a leaf CL has no CL
   graph ancestor with 6–40 cohort descendants (KLK2's prostate
   luminal CL has very few CZI siblings), the family axis falls back
   to the broad compartment ("Epithelial"). The chip then reads
   `enriched · Epithelial` instead of `enriched · luminal prostate
   epithelial cell`. Fine for ranking but loses precision in the
   label. Could be improved by widening the descendant range or by a
   secondary fallback to the leaf CL itself.

4. **Tissue-organ "single leaf is its own organ" heuristic.** Each
   UBERON's organ is the most-ancestral cohort UBERON above it (per
   `uberon_organ._build_organ_map`). For UBERONs without any cohort
   ancestor (prostate gland — no finer prostate subdivisions in CZI),
   the leaf IS its own organ. Works for prostate; might give
   surprising results when CZI starts sampling finer subdivisions of
   other organs.

5. **Cell-family universe inflation.** The cell-family axis's
   zero-baseline universe sums `n_total` across all leaf CLs assigned
   to each family. Some families (e.g. "ON-bipolar cell" — 10
   descendants in the cohort, each ~10k cells) have universe ~100k;
   others (T cell — 24 descendants, millions of cells) have universe
   ~10M. The τ math is universe-insensitive (it normalizes by N) but
   the noise gate compares pct against MIN_PCT_FOR_CLASS, so a leaf
   passing the gate doesn't always promote its family. Mitigation:
   the family-axis classifier uses leaf-pct eligibility (any-leaf
   pass at MIN_PCT_FOR_BROAD_CLASS) the same way the broad-class axis
   does, but the universe size still affects τ.

6. **No multiple-testing correction.** When the classifier picks
   "enriched" at the leaf-CL axis (600+ entities) for a gene, that
   choice has 600× the false-discovery surface of an HPA call on 40
   tissues. We don't BH-correct. Field-standard would.

7. **No statistical-significance gate.** We use noise thresholds
   (nnz ≥ 10, pct ≥ 1%) but no Wilcoxon / permutation test. A
   marker-style test (like `rank_genes_groups` in scanpy) would give
   per-call p-values.

8. **No Wilcoxon / DE backstop on the chip-displayed entity.** When
   `enriched · kidney loop of Henle` shows for GPR75, we report the
   max-pop-mean leaf. Field-standard would be a Wilcoxon test "is
   this gene significantly higher in this CL term than the rest?"
   The chip just claims the rank.

9. **The leaf-CL classification is published but mostly returns
   low_specificity.** Power users can read it from the JSON, but
   exposing it in the chip would be noise. Worth deciding: drop
   `cell_type_enrichment` from the emitted record, or keep as a
   power-user field?

10. **Eye / tongue / vasculature dominance isn't a bug, but it IS
    counterintuitive.** A reader expecting "tissue specificity" might
    be surprised KLK2's tissue-organ axis says `enriched · prostate
    gland` (right) but EGFR's says `enriched · tongue` (right per the
    metric, but EGFR is biologically broadly epithelial). The
    cell-family axis is more interpretable for broadly-expressed
    genes. Worth documenting in a per-gene help bubble.

## TODOs (next pass)

| Priority | Task |
|---|---|
| High | Regenerate the cell-count cache (`/tmp/czi_cell_tissue_counts.tsv`) from the 2025-11-08 Census snapshot so the WMG-nnz fallback isn't needed. |
| High | Run the full 6500+ gene build over WMG once D1 schema + Worker join are finalized (see "Scalability" below). |
| Medium | Per-UBERON cell-union count via `obs.value_counts(['tissue_ontology_term_id'])` to fix the pct overcount. |
| Medium | Wilcoxon DE backstop on the chip-displayed entity (per-call p-value). |
| Medium | BH-FDR correction on the leaf-CL axis. |
| Low | Drop `cell_type_enrichment` from the emitted record (or keep gated behind a debug flag). |
| Low | Per-axis tooltip variant explaining what `enriched · {entity}` actually means in surfaceome targeting terms. |

## Scalability plan for the full 6500+ gene cohort

This isn't yet run — it's the next deliberate decision. The
build-script side scales linearly with the gene set (the WMG stream is
the constant cost, ~60s; per-gene per-axis math is microseconds). The
question is **how D1 serves the result**:

### D1 schema options

#### Option A: keep `czi_cellxgene_enrichment.enrichment_json` as the single source

Pros:
- No schema migration; everything's already in the v2.1.5 JSON blob.
- The Worker's `/v1/genes/{symbol}/cellxgene` endpoint returns the
  whole blob; viewer renders chip + chart from it.

Cons:
- Catalog filters (`is tissue enriched · {organ}`) can't query JSON
  efficiently in D1. The Worker would need to fetch every gene's blob
  and filter in-app — expensive at 6500-gene scale.
- The `surface_annotation` endpoint can't easily JOIN — the cellxgene
  data isn't column-indexed.

#### Option B: denormalize chip-facing columns into `czi_cellxgene_enrichment`

Add columns:

```sql
ALTER TABLE czi_cellxgene_enrichment ADD COLUMN
    cell_family_class TEXT,        -- enriched | enhanced | low_specificity | not_detected
    cell_family_top   TEXT,        -- pipe-separated top entity labels
    cell_family_tau   REAL,
    tissue_organ_class TEXT,
    tissue_organ_top   TEXT,
    tissue_organ_tau   REAL;
CREATE INDEX idx_cellxgene_cell_family_class ON czi_cellxgene_enrichment(cell_family_class);
CREATE INDEX idx_cellxgene_tissue_organ_class ON czi_cellxgene_enrichment(tissue_organ_class);
```

Pros:
- Catalog filter queries are O(log n) on the index.
- The Worker `/v1/catalog` can JOIN this table on `gene_symbol` and
  include the τ-class chips in its response without parsing JSON.
- The detailed `enrichment_json` blob stays for the chart's full data.

Cons:
- 6 new columns × 6500 rows ≈ 40 KB extra (negligible).
- Sync script (`sync_czi_enrichment_to_d1.py`) needs to write the
  denormalized columns alongside the JSON. One-line change in
  `Row.from_snapshot`.

**Recommendation: Option B.** Cheap on storage, fast for filters, keeps
the blob as the source of truth.

#### Option C (longer term): separate `czi_cellxgene_chip` and `czi_cellxgene_detail` tables

Pros: cleaner separation. Cons: more migration; no real win over B.

### Worker route shape

For the catalog filter use case, add to `/v1/catalog` query params:

```
GET /v1/catalog?cellxgene_cell_family=enriched&cellxgene_cell_family_top=hepatocyte
GET /v1/catalog?cellxgene_tissue_organ=enriched&cellxgene_tissue_organ_top=prostate%20gland
```

Worker SQL:

```sql
SELECT cu.*, cxg.cell_family_class, cxg.cell_family_top,
       cxg.tissue_organ_class, cxg.tissue_organ_top
  FROM candidate_universe_public cu
  LEFT JOIN czi_cellxgene_enrichment cxg
    ON cu.gene_symbol = cxg.gene_symbol
   AND cxg.census_version = '2025-11-08'  -- pin to current Census
 WHERE 1=1
   AND (?cellxgene_cell_family IS NULL OR cxg.cell_family_class = ?cellxgene_cell_family)
   AND (?cellxgene_tissue_organ IS NULL OR cxg.tissue_organ_class = ?cellxgene_tissue_organ)
   ...
```

D1 plans this as an indexed nested-loop join → milliseconds for full
catalog queries.

### Build orchestration for 6500 genes

The WMG stream is read once (~60s) regardless of gene count. Per-gene
record build is microseconds. For 6500 genes total per-gene time is
~5-10 minutes — single-shot run is fine.

D1 push is the bottleneck — 6500 rows × 2 databases × ~300ms per HTTP
round-trip × 16-way parallelism = ~3-5 minutes. Already handled by
`sync_czi_enrichment_to_d1.py`'s `ThreadPoolExecutor`.

### Pre-flight checklist before the 6500-gene run

- [ ] Decide: keep leaf-CL classification (currently mostly
      low_specificity, JSON only) or drop it from the emitted record?
- [ ] Regenerate `/tmp/czi_cell_tissue_counts.tsv` from the 2025-11-08
      Census so WMG-nnz fallback isn't needed (or keep the fallback if
      cache regeneration is expensive).
- [ ] Land the Option B schema migration in `cloudflare/d1_schema.sql`
      and `cloudflare/d1_public_schema.sql`.
- [ ] Add the column-write path to `sync_czi_enrichment_to_d1.py`.
- [ ] Update the Worker's `/v1/catalog` to JOIN + accept the new
      query params.
- [ ] Smoke-test the join with a subset first (run for 100 genes,
      verify viewer chip + catalog filter work end-to-end).
- [ ] Full 6500-gene rebuild + sync.

## References

- Yanai et al. 2005, *Bioinformatics* — original τ definition.
- Kryuchkova-Mostacci & Robinson-Rechavi 2017, *Brief. Bioinformatics* — τ benchmarked most robust.
- Karbalaei et al. 2024, *Brief. Bioinformatics* — single-cell extension benchmark; pseudobulk / population-mean input.
- HPA tissue-specificity definitions: https://www.proteinatlas.org/humanproteome/tissue/tissue+specific
- CZI Census: https://chanzuckerberg.github.io/cellxgene-census/ (CC-BY 4.0).
- Cell Ontology (cl-basic.obo): https://purl.obolibrary.org/obo/cl/cl-basic.obo
- UBERON ontology: https://purl.obolibrary.org/obo/uberon.obo
