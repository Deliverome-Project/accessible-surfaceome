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
  /** Top tissues for this cell type, ranked by n_expressing DESC (≤ 3). */
  tissues: TissueRow[];
}

export interface CellxGeneEnrichment {
  schema_version: string;
  census_version: string;
  gene_symbol: string;
  hgnc_id: string | null;
  ensembl_gene: string | null;
  /** Top cell types overall, ranked by mean_log1p_cp10k DESC. */
  top_cell_types: CellTypeRow[];
  computed_at?: string;
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
