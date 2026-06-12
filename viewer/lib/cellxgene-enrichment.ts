/**
 * CZI CellxGene RNA-enrichment summary — type + loader.
 *
 * Shape mirrors the JSON the Worker serves at
 * `/v1/genes/{symbol}/cellxgene`, which is sourced from the
 * `czi_cellxgene_enrichment` D1 table populated by
 * `scripts/sync_czi_enrichment_to_d1.py`.
 *
 * Mean values are WMG-scale — mean log1p(census_normalized_counts_per_10k)
 * among expressing cells, identical to what cellxgene.cziscience.com's
 * gene-expression viewer displays. `pct_expressing` is computed as
 * `n_expressing / n_total` where `n_total` is the count of CZI primary
 * cells of that cell type (from `cellxgene_census.obs.value_counts`); it
 * matches the dot-size channel of the WMG dot plot.
 *
 * v2.0: dropped the curated "enrichment targets" / "selective targets"
 * blocks (the upstream tissue_mappings.json was a moving target). The
 * tab is now a single dense ranking of top cell types overall, each
 * with the tissues it draws from.
 *
 * CZI publishes Census data under CC-BY 4.0; the summary inherits.
 */

const DEFAULT_API_BASE = "https://api.deliverome.org/surfaceome";
const RECORD_FETCH_CACHE: RequestCache =
  process.env.NODE_ENV === "production" ? "force-cache" : "no-store";
const FETCH_TIMEOUT_MS = 8_000;

export interface TissueRow {
  /** Human-readable UBERON term label, e.g. "lung". */
  tissue: string;
  /** UBERON ontology ID, e.g. "UBERON:0002048". */
  uberon_id: string;
  /** Mean log1p(CP10K) among expressing cells in this (cell_type, tissue) pair. */
  mean_log1p_cp10k: number;
  /** Number of cells of this (cell_type, tissue) where the gene is expressed. */
  n_expressing: number;
  /** Total cells of this (cell_type, tissue) in the Census primary set. */
  n_total: number;
  /** n_expressing / n_total, clamped to [0, 1]. */
  pct_expressing: number;
}

export interface CellTypeRow {
  /** Human-readable CL term label, e.g. "pulmonary alveolar type 2 cell". */
  cell_type: string;
  /** Cell Ontology ID, e.g. "CL:0002063". */
  cl_id: string;
  /** Mean log1p(CP10K) pooled across the tissues this cell type appears in. */
  mean_log1p_cp10k: number;
  /** Number of expressing cells, pooled across tissues. */
  n_expressing: number;
  /** Total Census-primary cells of this cell type, pooled across tissues. */
  n_total: number;
  /** Pooled n_expressing / n_total. */
  pct_expressing: number;
  /** True when n_total < 10,000 — rendered after common cell types in
   *  the same chart, so a rare high-expressor doesn't dominate the
   *  ranking but stays visible for comparison. */
  is_rare: boolean;
  /** True when the cell type fails the noise filter (n_expressing < 10
   *  OR pct < 1%). v2.1.1+. Trace rows render muted with a badge. */
  is_trace?: boolean;
  /** Top tissues for this cell type, ranked by n_expressing DESC (≤ 3). */
  tissues: TissueRow[];
}

/**
 * τ-cutoff classification (v2.1.5+). Computed per-gene from the
 * eligible-entity distribution's Yanai 2005 τ score on linear
 * population mean (mean × pct, ≈ HPA nTPM):
 *
 * - enriched      → τ ≥ 0.85 (or single eligible — definitionally
 *                   enriched since there's no other entity to spread
 *                   expression over)
 * - enhanced      → 0.5 ≤ τ < 0.85
 * - low_specificity → τ < 0.5
 * - not_detected  → zero eligibles (no entity meets the CZI noise
 *                   threshold: n_expressing ≥ 10 AND pct ≥ 1%, or
 *                   ≥ 5% for the broad-class axis). Distinct from
 *                   low_specificity — "couldn't measure above
 *                   background" vs "broadly expressed."
 *
 * Cutoffs follow HPA's tissue-specificity nTPM convention:
 * https://www.proteinatlas.org/humanproteome/tissue/tissue+specific
 *
 * group_enriched dropped from the active set — under τ cutoffs a
 * 1-tissue and a 3-tissue concentration both register as enriched;
 * the chip's entity list (top 3 by pop mean) conveys "how many"
 * without a separate class. Kept in the legacy union below so older
 * D1 rows still render correctly during the schema transition.
 */
export type EnrichmentClass =
  | "enriched"
  | "enhanced"
  | "low_specificity"
  | "not_detected"
  // Legacy strings still present in older D1 rows; the viewer
  // accepts them so the page doesn't crash mid-rebuild. The labels
  // map normalizes them onto the same chip text. group_enriched was
  // dropped in v2.1.5 when we switched to τ cutoffs — τ doesn't
  // distinguish single vs. few enriched entities, so we collapsed
  // it into "enriched."
  | "tissue_enriched"
  | "tissue_enhanced"
  | "group_enriched";

export interface CellTypeEnrichment {
  class: EnrichmentClass;
  /** CL IDs the elevation applies to (1 for enriched/enhanced,
   *  2-5 for group_enriched, empty for low_specificity). */
  cl_ids: string[];
  /** Linear fold change at the elevation boundary. Null for low_specificity. */
  fold_change: number | null;
  /** Yanai et al. 2005 specificity τ over the eligible set ∈ [0, 1].
   *  Null when fewer than 2 entities clear the noise gate. v2.1.2+. */
  tau?: number | null;
}

/**
 * v2.1.1+ broad-class rollup of leaf CL terms (Epithelial / Immune /
 * Neural / Endothelial / Stromal / Muscle / Reproductive / Stem /
 * Tumor / Other). HPA's 4× test works at this granularity —
 * `cell_type_enrichment` at the leaf CL level often returns
 * low_specificity because sibling CL terms expressing at similar
 * levels can't dominate each other 4×. The chip on the gene page
 * reads from THIS field first.
 */
export interface CellClassEnrichment {
  class: EnrichmentClass;
  /** Broad-class names ("Epithelial", "Immune", …) the elevation
   *  applies to. Same shape as `class_labels` — both arrays are
   *  populated with the human-readable class names. */
  class_ids: string[];
  class_labels: string[];
  fold_change: number | null;
  fold_change_infinite?: boolean;
  /** Yanai et al. 2005 specificity τ over the eligible compartment
   *  set ∈ [0, 1]. Null when fewer than 2 compartments are above
   *  noise. v2.1.2+. */
  tau?: number | null;
}

export interface TissueEnrichment {
  class: EnrichmentClass;
  /** UBERON IDs the elevation applies to. */
  uberon_ids: string[];
  /** Human labels parallel to uberon_ids ("lung", "brain", …). */
  tissue_labels: string[];
  fold_change: number | null;
  /** Yanai et al. 2005 specificity τ over the eligible tissue set
   *  ∈ [0, 1]. Null when fewer than 2 tissues are above noise.
   *  v2.1.2+. */
  tau?: number | null;
}

/**
 * v2.1.3+ organ-system category rollup of the 410 fine-grained UBERON
 * terms via the programmatic ontology walk (see
 * viewer/lib/tissue-categories-uberon-map.generated.ts and
 * scripts/build_tissue_category_mapping.py). 14 categories (CNS,
 * Head & sensory, Respiratory, ...). Per-category signal is the
 * max-UBERON pop mean within the category (same approach as
 * CellClassEnrichment for cells). GPR75 → CNS via brain;
 * KLK2 → Reproductive via prostate gland.
 */
export interface TissueCategoryEnrichment {
  class: EnrichmentClass;
  category_ids: string[];
  category_labels: string[];
  /** The UBERON tissue each category's signal rests on (the
   *  max-pop-mean UBERON within that category). Parallel to
   *  category_ids. */
  top_tissues?: string[];
  fold_change: number | null;
  fold_change_infinite?: boolean;
  tau?: number | null;
}

export interface TissueAggregateRow {
  tissue: string;
  uberon_id: string;
  mean_log1p_cp10k: number;
  n_expressing: number;
  n_total: number;
  pct_expressing: number;
  /** True when the tissue passes n_total ≥ 1000 but fails the noise
   *  filter (n_expressing < 10 OR pct < 1%). Trace rows render muted
   *  with a "trace" badge — useful for low-expression genes whose
   *  qualified tissues alone don't tell the story (GPR75: only brain
   *  and embryo qualify, but pleura/forelimb/intestine carry signal). */
  is_trace?: boolean;
}

export interface CellxGeneEnrichment {
  schema_version: string;
  census_version: string;
  gene_symbol: string;
  hgnc_id: string | null;
  ensembl_gene: string | null;

  /** Per-broad-class HPA elevation. v2.1.1+. The chip on the gene
   *  page reads from this field first, falling back to
   *  cell_type_enrichment for older records. */
  cell_class_enrichment?: CellClassEnrichment;
  /** Per-leaf-CL HPA elevation class. v2.1+. */
  cell_type_enrichment?: CellTypeEnrichment;
  /** Per-tissue HPA elevation class. v2.1+. */
  tissue_enrichment?: TissueEnrichment;
  /** Per-tissue-category HPA elevation. v2.1.3+. Same role for the
   *  tissue axis that cell_class_enrichment plays for cells — 14
   *  organ-system rollup vs the fine-grained UBERON axis. */
  tissue_category_enrichment?: TissueCategoryEnrichment;

  /** Legacy back-compat fields. In v2.0 these were the only classification
   *  surface; v2.1 keeps them populated mirroring cell_type_enrichment.* so
   *  the viewer's older readers continue to work during transitions. */
  enrichment_class?: EnrichmentClass;
  enrichment_cl_ids?: string[];
  fold_change?: number | null;

  /** Top cell types overall, ranked by mean_log1p_cp10k DESC. v2.1 caps
   *  at 30: up to 20 common (n_total ≥ 10,000) + up to 10 rare. */
  top_cell_types: CellTypeRow[];
  /** Top tissues overall, ranked by mean_log1p_cp10k DESC. v2.1+. */
  top_tissues?: TissueAggregateRow[];
  /** Reverse map: UBERON ID → cell types that express the gene in
   *  that tissue, ranked by n_expressing DESC, capped at 20. v2.1.2+.
   *  Lets the viewer's tissue cross-filter find cell types that the
   *  global top_cell_types cap drops (e.g. fibroblast in vasculature
   *  for GPR75 — small per-tissue cell count, pooled mean too low
   *  to rank in top 50 cell types overall). */
  cells_by_tissue?: Record<string, CellInTissue[]>;
  computed_at?: string;
}

/** One row inside cells_by_tissue[uberon_id]. */
export interface CellInTissue {
  cl_id: string;
  cell_type: string;
  mean_log1p_cp10k: number;
  n_expressing: number;
  n_total: number;
  pct_expressing: number;
  is_trace?: boolean;
}

/**
 * Fetch the per-gene CZI CellxGene enrichment summary from the public
 * Worker. Returns `null` on any error or under `SURFACEOME_API_BASE=local`.
 *
 * This is a separate fetch from `loadSurfaceomeRecord` so a gene without
 * a deep-dive record can still get a CellxGene tab (every protein-coding
 * gene is in the Census).
 *
 * **Dev fallback** — in development mode, if the Worker returns null (e.g.
 * the new `/cellxgene` route hasn't been deployed yet to the live
 * Worker), we fall back to reading the per-gene snapshot off the local
 * filesystem at `CELLXGENE_DEV_SNAPSHOT_DIR` (default: `/tmp/czi_enrichment`).
 * Gated on `NODE_ENV !== "production"` so the prod bundle never imports
 * `node:fs`. The path is the same one `scripts/sync_czi_enrichment_to_d1.py`
 * reads from, so a local CZI build feeds both the D1 push and the dev
 * server without an extra hop.
 */
export async function loadCellxGeneEnrichment(
  symbol: string,
): Promise<CellxGeneEnrichment | null> {
  const base = (process.env.SURFACEOME_API_BASE ?? DEFAULT_API_BASE).trim();
  if (base !== "local" && base) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    try {
      const res = await fetch(`${base}/v1/genes/${symbol}/cellxgene`, {
        cache: RECORD_FETCH_CACHE,
        signal: controller.signal,
      });
      if (res.ok) return (await res.json()) as CellxGeneEnrichment;
    } catch {
      // fall through to dev fs fallback
    } finally {
      clearTimeout(timer);
    }
  }
  if (process.env.NODE_ENV !== "production") {
    return _loadFromDevSnapshot(symbol);
  }
  return null;
}

async function _loadFromDevSnapshot(
  symbol: string,
): Promise<CellxGeneEnrichment | null> {
  try {
    // Dynamic import keeps `node:fs` out of any client/edge bundle —
    // server components and route handlers can resolve it at runtime.
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    const dir = process.env.CELLXGENE_DEV_SNAPSHOT_DIR ?? "/tmp/czi_enrichment";
    const file = path.join(dir, `${symbol.toUpperCase()}.json`);
    const text = await fs.readFile(file, "utf8");
    return JSON.parse(text) as CellxGeneEnrichment;
  } catch {
    return null;
  }
}
