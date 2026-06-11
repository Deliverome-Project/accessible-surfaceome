/**
 * CZI CellxGene RNA-enrichment summary — type + loader.
 *
 * Shape mirrors the JSON the Worker serves at
 * `/v1/genes/{symbol}/cellxgene`, which is sourced from the
 * `czi_cellxgene_enrichment` D1 table populated by
 * `scripts/sync_czi_enrichment_to_d1.py`.
 *
 * The values are WMG-scale: mean log1p(census_normalized_counts_per_10k)
 * among expressing cells, identical to what cellxgene.cziscience.com's
 * gene-expression viewer displays. The "summary" shape (top-N cell types,
 * per-target aggregates, top-N selective targets) is intentionally narrow
 * — a typical gene page renders ~10 + ~10 rows, not the ~600 cell types
 * the CZI viewer's dot plot can show.
 *
 * CZI publishes Census data under CC-BY 4.0; the summary inherits.
 */

const DEFAULT_API_BASE = "https://api.deliverome.org/surfaceome";
const RECORD_FETCH_CACHE: RequestCache =
  process.env.NODE_ENV === "production" ? "force-cache" : "no-store";
const FETCH_TIMEOUT_MS = 8_000;

export interface CellTypeRow {
  /** Human-readable CL term label, e.g. "pulmonary alveolar type 2 cell". */
  cell_type: string;
  /** Cell Ontology ID, e.g. "CL:0002063". */
  cl_id: string;
  /** Mean log1p(CP10K) among expressing cells. WMG viewer scale. */
  mean_log1p_cp10k: number;
  /** Number of expressing cells pooled across all tissues in the Census. */
  n_expressing: number;
}

export interface EnrichmentTargetRow {
  /** tissue_mappings.json key, e.g. "alveolar_type_2". */
  target_key: string;
  /** Human-readable label, e.g. "Alveolar Type 2 Cells". */
  label: string;
  /** Coarse group, e.g. "lung", "cns_cell_types". */
  category: string;
  /** "high" / "medium" / "low" / "unknown" — from tissue_mappings.json. */
  priority?: string;
  /** Mean log1p(CP10K) pooled across the CL IDs that make up this target. */
  mean_log1p_cp10k: number;
  n_expressing: number;
  /** The CL IDs underlying this target (1-N). */
  cl_ids: string[];
}

export interface SelectiveTargetRow extends EnrichmentTargetRow {
  /** mean_log1p_cp10k − lymphoid_baseline.mean_log1p_cp10k. */
  delta_vs_lymphoid: number;
}

export interface LymphoidBaseline {
  mean_log1p_cp10k: number;
  n_expressing: number;
  cl_ids: string[];
}

export interface CellxGeneEnrichment {
  schema_version: string;
  census_version: string;
  gene_symbol: string;
  hgnc_id: string | null;
  ensembl_gene: string | null;
  top_cell_types: CellTypeRow[];
  enrichment_targets: EnrichmentTargetRow[];
  lymphoid_baseline: LymphoidBaseline;
  top_selective_targets: SelectiveTargetRow[];
  computed_at?: string;
}

/**
 * Fetch the per-gene CZI CellxGene enrichment summary from the public
 * Worker. Returns `null` on any error or under `SURFACEOME_API_BASE=local`.
 *
 * This is a separate fetch from `loadSurfaceomeRecord` so a gene without
 * a deep-dive record can still get a CellxGene tab (every protein-coding
 * gene is in the Census).
 */
export async function loadCellxGeneEnrichment(
  symbol: string,
): Promise<CellxGeneEnrichment | null> {
  const base = (process.env.SURFACEOME_API_BASE ?? DEFAULT_API_BASE).trim();
  if (base === "local" || !base) return null;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(`${base}/v1/genes/${symbol}/cellxgene`, {
      cache: RECORD_FETCH_CACHE,
      signal: controller.signal,
    });
    if (!res.ok) return null;
    return (await res.json()) as CellxGeneEnrichment;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
