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
population mean** over the **full measured universe** (eligibles plus
ineligibles floored at a 1e-3 noise level):

```
τ = Σ (1 − x_i / x_max) / (N − 1)
x_i = expm1(mean_log1p_cp10k) × pct_expressing per eligible entity
x_i = 1e-3                             per ineligible entity (universe-stable floor)
```

τ ∈ [0, 1]: **0** = uniformly expressed across the universe, **1** =
concentrated in one entity. The class follows τ cutoffs from
Kryuchkova-Mostacci & Robinson-Rechavi 2017 (PMID 26891983, τ
best-in-class benchmark with τ ≥ 0.8 as "specific") and Lüleci &
Yılmaz 2022 (the τ ≥ 0.85 idiom):

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
cellxgene's 410 UBERONs or ~600 leaf CLs, it reads `low_specificity`
for genes that are clearly elevated in a small set — none of the
eligible siblings dominates each other 4×. τ doesn't care about
pair-wise ratios; it asks "how concentrated is the overall
distribution?" which scales gracefully across axis sizes.
Kryuchkova-Mostacci 2017 and Karbalaei 2024 (single-cell benchmark)
both crown τ as the most robust specificity metric for high-dimension
tissue/cell-type axes.

### Why the τ universe is the full measured set (not eligibles-only)

Yanai 2005, Kryuchkova-Mostacci 2017, HPA's published tissue-specific
proteome (37-tissue universe, nTPM ≥ 1 floor), and Tabula Sapiens 2.0
(fixed N = 175 cell types) all keep `N` fixed by **flooring** low
values rather than dropping below-threshold entities. Eligibles-only τ
collapses to "concentration among entities that express the gene" —
not the same question as specificity, and not cross-gene comparable.
Our floor of 1e-3 linear pop mean is at the noise level (≈ a gene at
mean log1p(CP10K)≈0.1 in 1% of cells); below the eligibility gate but
not zero, so τ stays in a meaningful range when many entities sit at
sub-noise levels.

### Why population mean, not mean-among-expressors

`mean_log1p(CP10K)` in CZI's WMG is the mean *among expressing cells*. A
gene with 1 cell at CP10K=20 in a 10,000-cell tissue (pct=0.01%) looks
identical to a gene at 100% prevalence with the same intensity. HPA /
GTEx / Tabula Sapiens / Karbalaei 2024 all run on the population mean
(intensity × prevalence — algebraically equal to mean across ALL cells
including non-expressors). Multiplying by `pct_expressing` collapses
both axes into one number.

### Why DE / Wilcoxon backstop isn't required

A common question: shouldn't an "enriched" call carry a per-call
significance test? Field practice on τ-based specificity work doesn't
do this — τ is itself the discriminator, and the cutoffs (0.5 / 0.85)
already encode an effect-size threshold. Kryuchkova-Mostacci 2017's
benchmark and the τ-using HPA / Tabula Sapiens publications all
classify by τ cutoffs without an accompanying Wilcoxon. We *could*
layer a DE backstop on the chip-displayed entity (per-call p-value
that the top entity is statistically higher than the rest), and might
do so eventually for the leaf-CL axis where N=600+ inflates the
false-discovery surface — but it's not required to ship the current
τ-cutoff calls.

### Per-entity τ contributions (v2.1.7+)

Every axis's emitted record carries `top_entity_contribs` — the top
1–3 entities by linear pop mean, each with its own per-entity τ
contribution `1 − x / x_max`. The chip tooltip renders them so a
reader can see *which* entities the call rests on and how strongly
each one carries the τ score. The top entity always contributes 0
(it's `x_max`); runners-up contribute proportionally to how far below
the top they sit. For an `enriched` call where 3 entities are close
in pop mean, the second and third contributions stay near 0 — the
gene is concentrated in a small group. For `enriched · {one entity}`
where only one stands out, the second contribution is large.

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

The "fixed in v2.1.7" entries below were live concerns through v2.1.6
and are noted here so a reader catching the doc pre-rebuild knows
they're addressed; they'll move to a changelog section after the next
doc pass.

1. **`pct_expressing` overcount on the tissue axis — FIXED in v2.1.7.**
   Per-UBERON `n_total` previously summed `pair_counts[(cl, ub)]` over
   all CL terms. When CZI's WMG annotates the same cells under
   parent + child CL (`naive T cell` AND `T cell`), the cell was
   counted in both pairs, inflating both numerator and denominator
   (CD63 pancreas → raw pct=154%). Fix: aggregate only over **cohort-
   leaf CL terms** (CL terms in the cohort with no cohort descendants)
   plus a **per-(cl, ub) WMG-nnz fallback** at aggregation time
   (`n_total_pair = max(cache_n_total, nnz)`), so per-pair pct is ≤
   1.0 by construction and the per-UBERON weighted sum stays ≤ 1.0.
   No clipping needed.

2. **Stale cell-count cache vs WMG export — MITIGATED in v2.1.7.** The
   cache at `/tmp/czi_cell_tissue_counts.tsv` was generated from an
   earlier `obs.value_counts()` snapshot than the 2025-11-08 WMG it
   joins against. EGFR-embryo: cache has 4 CL terms profiled, WMG
   sees 36 with 28k expressing cells. The per-(cl, ub) WMG-nnz
   fallback handles the gap (cells dropped from the cache float
   back in via WMG). Long-term fix: regenerate the cell-count cache
   from the 2025-11-08 Census snapshot.

3. **Cell-family fallback — FIXED in v2.1.7.** Previously: when a
   leaf CL had no graph ancestor with 6–40 cohort descendants (KLK2's
   prostate luminal CL has few CZI siblings), the family axis fell
   back to the broad compartment ("Epithelial"), losing precision in
   the chip label. Fix: the leaf IS its own family — the chip now
   reads `enriched · luminal cell of prostate epithelium` instead of
   `enriched · Epithelial`. See [src/accessible_surfaceome/audit/cl_family.py:113](src/accessible_surfaceome/audit/cl_family.py:113).

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
   passing the gate doesn't always promote its family.

6. **No multiple-testing correction.** When the classifier picks
   "enriched" at the leaf-CL axis (~600 entities) for a gene, that
   choice has 600× the false-discovery surface of an HPA call on 40
   tissues. We don't BH-correct. Field-standard would, especially at
   the leaf-CL granularity. Lower priority for the middle-granularity
   axes (~150 each) where false-discovery surface is closer to HPA's
   scale.

7. **No statistical-significance gate.** Noise thresholds (nnz ≥ 10,
   pct ≥ 1%) but no Wilcoxon / permutation test. Per the "Why DE
   backstop isn't required" section above, field practice on τ-based
   specificity doesn't require one; the τ cutoff (0.5/0.85) IS the
   effect-size threshold. Optional layer for a later pass on the
   leaf-CL axis where the multiple-testing surface is highest.

8. **The leaf-CL classification is published but mostly returns
   `enriched` (because τ on ~600 noisy entities almost always finds
   one peak).** Power users can read it from the JSON for inspection,
   but exposing it in the chip would be noise. The viewer chip
   defaults to `cell_family_enrichment` for this reason. Worth
   deciding pre-6500-rollout: drop `cell_type_enrichment` from the
   emitted record (saves ~1KB per gene), or keep as a power-user
   debug field?

9. **Eye / tongue / vasculature dominance isn't a bug, but it IS
   counterintuitive.** A reader expecting "tissue specificity" might
   be surprised KLK2's tissue-organ axis says `enriched · prostate
   gland` (right) but EGFR's says `enriched · heart` or `enriched ·
   tongue` (right per the population-mean metric, but EGFR is
   biologically broadly epithelial). The cell-family axis is more
   interpretable for broadly-expressed genes. Worth documenting in a
   per-gene help bubble or surfacing the top-3 contributors so the
   reader sees the runner-up tissues are close.

10. **No per-axis effect-size lower bound.** A gene can register
    `enriched` at the cell-family axis with a top entity at pop_mean
    = 0.05 (just above the 1e-3 noise floor — its τ shape is still
    concentrated) if every other family is below noise. This reads
    correctly under τ semantics ("concentrated where it's detected at
    all"), but a reader might expect "enriched" to imply an
    absolute-magnitude floor too. Could add a `confidence` field that
    flags when the top entity's pop_mean is below e.g. 1.0.

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

**Key design decision: the cellxgene layer is independent of the
deep-dive layer.** The 6500-gene catalog will first be built and
served WITHOUT cellxgene enrichment (just `candidate_universe_public`
+ `surface_annotation` deep-dive records as they're written). Once
the catalog is live, we layer cellxgene on top via a D1 LEFT JOIN —
the Worker query becomes "give me the catalog row plus its cellxgene
chip columns if present." This decoupling means:

1. The cellxgene build runs on its own schedule (rebuild whenever the
   CZI Census refreshes; the WMG stream is the constant cost).
2. The cellxgene build doesn't have to wait for deep-dives, and a
   gene without a deep-dive still gets a cellxgene chip in the
   catalog table.
3. Schema migrations on `czi_cellxgene_enrichment` don't touch the
   deep-dive tables.

The build-script side scales linearly with the gene set (the WMG
stream is the constant cost, ~60s; per-gene per-axis math is
microseconds). The question is **how D1 serves the result**:

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

#### Option B (DONE in v2.1.7): denormalize chip-facing columns into `czi_cellxgene_enrichment`

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

- [x] Land the Option B schema migration in `cloudflare/d1_schema.sql`
      and `cloudflare/d1_public_schema.sql`. *(v2.1.7)*
- [x] Add the column-write path to `sync_czi_enrichment_to_d1.py`.
      *(v2.1.7)*
- [x] Update the Worker's `/v1/catalog` to LEFT JOIN
      `czi_cellxgene_enrichment` and emit the compact `cxg_cf` / `cxg_to`
      short-key fields. *(deployed)*
- [x] Wire viewer `CatalogTable` to render the chips + filter chips +
      entity-dropdown for cell_family + tissue_organ. *(v2.1.7)*
- [ ] Decide: keep leaf-CL classification (currently mostly
      `enriched` because τ on ~600 noisy entities almost always finds
      one peak — see weakness #8) or drop it from the emitted record?
      Saves ~1KB per gene.
- [ ] Regenerate `/tmp/czi_cell_tissue_counts.tsv` from the 2025-11-08
      Census so the WMG-nnz fallback isn't needed (mitigation is in
      place; this is a clean-up, not a blocker).
- [ ] Smoke-test the join with a subset first (run for 100 genes,
      verify viewer chip + catalog filter work end-to-end).
- [ ] Full 6500-gene rebuild + sync.

### What the 6500-gene rollout looks like operationally

The deep-dive cohort grows independently — at 14 genes today,
targeting 6500 once `surface_annotator` is running at full cohort
scale. The cellxgene layer doesn't need to wait. Concretely:

1. Run `build_czi_enrichment_v2_1.py` over the full ~19k
   protein-coding cohort (no `--genes-file`; the WMG stream is
   read once for everything). ETA ~5–10 minutes for the WMG + per-gene
   record build; D1 push dominates at ~3–5 minutes via
   `ThreadPoolExecutor` parallelism.
2. The catalog page already serves `cxg_cf` / `cxg_to` via the
   Worker's LEFT JOIN — every gene with a cellxgene row gets its
   chip, every gene without (≈ 0 at full coverage) gets a blank chip
   gracefully.
3. The catalog filter chips (cell_family enriched/enhanced + entity
   dropdown, same for tissue_organ) work over the full 6500 without
   schema changes — the indexes on `cell_family_class` and
   `tissue_organ_class` are pre-existing from the v2.1.7 migration.
4. Per-gene pages without a deep-dive will still get the chart +
   classification chips, because `loadCellxGeneEnrichment` is a
   separate fetch from `loadSurfaceomeRecord` and gracefully reads
   from `/v1/genes/{symbol}/cellxgene` directly.

## References

- Yanai et al. 2005, *Bioinformatics* (PMID [15388519](https://pubmed.ncbi.nlm.nih.gov/15388519/)) — original τ definition; uses fixed N with noise floor.
- Kryuchkova-Mostacci & Robinson-Rechavi 2017, *Brief. Bioinformatics* (PMID [26891983](https://pubmed.ncbi.nlm.nih.gov/26891983/)) — τ benchmarked most robust across specificity metrics; < 1 RPKM floor.
- Lüleci & Yılmaz 2022, *BioData Mining* — τ ≥ 0.85 cutoff for "specific" expression.
- Karbalaei et al. 2024, *Brief. Bioinformatics* — single-cell extension benchmark; pseudobulk / population-mean input.
- Tabula Sapiens 2.0, bioRxiv 2024.12.03.626516 — fixed N = 175 cell types + τ > 0.85 cutoff.
- HPA tissue-specificity definitions (4× nTPM rule — context, not what we use): https://www.proteinatlas.org/humanproteome/tissue/tissue+specific
- CZI Census: https://chanzuckerberg.github.io/cellxgene-census/ (CC-BY 4.0).
- Cell Ontology (cl-basic.obo): https://purl.obolibrary.org/obo/cl/cl-basic.obo
- UBERON ontology: https://purl.obolibrary.org/obo/uberon.obo
