/*
 * Surfaceome data loader + label helpers.
 * ------------------------------------------------------------
 * Per-gene `SurfaceomeRecord` data flows from the public Cloudflare
 * Worker at `api.deliverome.org/surfaceome/v1/genes/{SYMBOL}` —
 * fetched at build time, baked into the static export via
 * `cache: "force-cache"`. Same SSG lifecycle as the catalog: a
 * re-deploy of the Worker surfaces in the viewer on the next
 * `npm run build`, no per-page-load D1 hits in production.
 *
 * D1 is the SINGLE source of truth for deep-dive records. There is no
 * on-disk fallback whatsoever: deep-dive SurfaceomeRecords are written
 * direct to public D1 (`cloud.surface_annotation.publish_record`), and
 * the viewer reads them only through the Worker. The set of routes is
 * sourced the same way — `listSurfaceomeGenes` hits the Worker's
 * `/v1/genes` (the annotated-gene list backed by `surface_annotation`)
 * to decide which gene pages `generateStaticParams` emits. There used
 * to be a backstop union with `viewer/public/data/surfaceome/*.json`
 * snapshots to paper over edge-cache lag on `/v1/genes` after a fresh
 * publish; that backstop was removed when publish_record gained
 * by-URL edge-cache purge — the lag is now ~0 so the snapshot dir
 * adds no signal, only drift risk (a stale local snapshot could route
 * a gene the Worker hasn't published yet, then 500 at render time).
 *
 * Like the catalog (`loadCatalog`), the gene pages therefore
 * hard-require the live Worker in production. `SURFACEOME_API_BASE=local`
 * makes both surfaces return empty (0-row catalog, 0 gene routes) so the
 * offline CI smoke build renders the chrome without a network hit; the
 * Pages-side build runs against the real Worker and emits the full set.
 */

import { readFileSync } from "node:fs";
import path from "node:path";

// Build-time snapshot cache for the two over-2MB Worker endpoints
// (/v1/catalog ≈ 5.7 MB, /v1/benchmark/matrix ≈ 3 MB). Pre-written by
// `viewer/scripts/build-data-snapshot.mjs` BEFORE `next build` runs, so
// SSG reads from disk instead of refetching per-worker per-page (each
// fetch was a Next.js Data-Cache miss because both exceed the 2 MB cap,
// hammering D1 ~15× per build). Falls back to the live fetch path when
// the snapshot file is missing — i.e. `next dev` or any contributor who
// didn't run `npm run build:snapshot` first.
const BUILD_CACHE_DIR = path.join(process.cwd(), "build-cache");

function readBuildCache<T>(file: string): T | null {
  try {
    const p = path.join(BUILD_CACHE_DIR, file);
    const raw = readFileSync(p, "utf-8");
    return JSON.parse(raw) as T;
  } catch {
    // ENOENT (no snapshot run yet) or malformed JSON — let the caller
    // fall through to the live fetch. Deliberately swallowed: the
    // snapshot is an optimization, not a correctness gate.
    return null;
  }
}
import { pickDeepDiveFilters } from "./deep-dive-fields";
import { renumberEvidenceIds } from "./evidenceRenumber";
import type {
  BenchmarkMatrix,
  BenchmarkRow,
  Compartment,
  Confidence,
  CoreceptorDependency,
  EcdAccessibilityClass,
  EvidenceDensity,
  EvidenceGrade,
  ExpressionBreadth,
  ExpressionLevel,
  ProteinFamily,
  RestrictedSubdomainKind,
  SecretedSource,
  StateDependence,
  Subcategory,
  SurfaceAccessibility,
  SurfaceomeRecord,
  SurfaceSpecificity,
  TriageReason,
  TriageSignal,
} from "./surfaceome-types";

// Gene-name lookup is sourced directly from the NCBI triageable TSV
// in the repo (data/external/ncbi_gene_info/...). The viewer used to
// commit a pre-built JSON snapshot of this; we dropped it because the
// TSV is already in the repo and parsing it once at build (~50 ms
// for 19k rows) is cheaper than carrying a 150k-line derivative file.
const GENE_NAMES_TSV = path.join(
  process.cwd(),
  "..",
  "data",
  "external",
  "ncbi_gene_info",
  "Homo_sapiens.protein_coding.with_hgnc.triageable.tsv",
);

// HGNC complete set — authoritative symbol↔UniProt mapping. The
// candidate_universe_public table only carries `uniprot_acc` for genes
// that hit at least one DB, leaving ~13.7k non-candidate rows in the
// catalog with no accession surfaced. The HGNC TSV fills that gap and
// also gives us a second source for the full gene name (preferred over
// the NCBI description because HGNC's `name` field is the canonical
// "approved name" — the same string used by UniProt, Ensembl, etc.).
//
// ~45k rows, ~25 MB; parsing it once per build is fine and the result
// is memoized below.
const HGNC_TSV = path.join(
  process.cwd(),
  "..",
  "data",
  "external",
  "hgnc",
  "hgnc_complete_set.tsv",
);

/**
 * One row of the genome-wide catalog the index table renders. Sourced
 * from the public Worker's `/v1/catalog` endpoint (which joins
 * `candidate_universe_public` + `triage_run_public` + `surface_annotation`
 * in the `surfaceome_public` D1 mirror). The committed
 * `public/data/catalog.json` is a snapshot fallback used when the API
 * is unreachable (offline dev, Worker not yet deployed, etc.).
 */
export interface TriageCell {
  verdict: string;
  reason: string | null;
}

/**
 * Slimmed projection of `SurfaceomeRecord.filters` carried on each
 * catalog row for the deep-dive-filter section in the CatalogTable.
 * The Worker only emits this when `deep_dive=true` AND the
 * annotation_json parsed cleanly; rows without a deep-dive simply
 * omit `deep_dive_filters`.
 *
 * 21 fields: 13 enums + 8 booleans. Continuous fields
 * (max_paralog_ecd_pct_identity, ortholog identities) are excluded
 * — the catalog UI doesn't expose range filters yet, and the deep-
 * dive page already shows them in the FiltersCard. The schema
 * mirrors `DDF_KEYS` in cloudflare/workers/surfaceome_api/src/index.js
 * — extend both when adding a field.
 */
/** Coarse band an ECD %-identity is binned into for catalog/compare
 *  filtering (see deep-dive-fields.ts:ecdBand). */
export type EcdBand = "high" | "moderate" | "low" | "none";

/** Catalog-baked percentile band on `n_papers_selected` (unique-paper
 *  count behind the evidence list). Cutoffs are recomputed from the
 *  live deep-dive cohort at catalog-build time:
 *    • `low`      — n_papers_selected ≤ p10
 *    • `moderate` — p10 < n_papers_selected < p90
 *    • `high`     — n_papers_selected ≥ p90
 *  The viewer's filter UI presents these as a multi-select pill row;
 *  the exact p10 / p90 cutoffs travel on the catalog response as
 *  `n_papers_selected_cutoffs` so tooltips can render the concrete
 *  thresholds. */
export type PapersSelectedBand = "low" | "moderate" | "high";

/** Cohort percentile cutoffs surfaced as catalog metadata so the
 *  viewer can display "low ≤ 8 papers · high ≥ 47 papers" in the
 *  filter tooltip rather than just band names. Null on cold catalogs
 *  with fewer than 3 deep-dive records (cutoffs aren't meaningful). */
export interface PapersSelectedCutoffs {
  p10: number;
  p90: number;
  /** Population size the cutoffs were computed over. */
  n: number;
}

/** Dominant induction-trigger bucket (mirrors models.py InductionTrigger). */
export type InductionTrigger =
  | "none"
  | "oncogenic"
  | "immune"
  | "stress_hypoxia"
  | "cell_death"
  | "infection"
  | "other";

export interface DeepDiveFilters {
  surface_accessibility: SurfaceAccessibility;
  confidence: Confidence;
  state_dependence: StateDependence;
  surface_call_reason: TriageReason;
  subcategory: Subcategory;
  llm_family: ProteinFamily;
  evidence_grade: EvidenceGrade;
  evidence_density: EvidenceDensity;
  /** Raw unique-paper count behind the evidence list (schema 2.14.0).
   *  Optional because records annotated before 2.14.0 lack the field. */
  n_papers_selected?: number;
  /** Pre-trim discovery corpus size — display-only context for the
   *  filter. Optional + nullable: records annotated before 2.14.0
   *  lack it AND the backfill for it requires a discover-only rerun
   *  (not yet done for the 14 already-published genes). */
  n_papers_found?: number | null;
  /** Catalog-baked percentile band keyed off `n_papers_selected`.
   *  Cohort cutoffs travel as the top-level
   *  `n_papers_selected_cutoffs` field on the catalog response. */
  n_papers_selected_band?: PapersSelectedBand;
  ecd_accessibility_class: EcdAccessibilityClass;
  expression_level: ExpressionLevel;
  expression_breadth: ExpressionBreadth;
  surface_specificity: SurfaceSpecificity;
  co_receptor_dependency: CoreceptorDependency;
  has_known_ligand: boolean;
  low_endogenous_expression: boolean;
  overexpression_surface_localization_observed: boolean;
  has_shed_form: boolean;
  has_secreted_form: boolean;
  has_epitope_masking: boolean;
  n_term_extracellular: boolean;
  c_term_extracellular: boolean;
  // Newer fields — optional so older records (which omit them) still type.
  has_restricted_subdomain?: boolean;
  cyno_ortholog_ecd?: EcdBand;
  mouse_ortholog_ecd?: EcdBand;
  max_paralog_ecd?: EcdBand;
  tumor_associated?: boolean;
  induction_trigger?: InductionTrigger;
  has_live_cell_surface_evidence?: boolean;
  /** Sourced from `biological_context.subcellular_localization.primary_compartment`,
   *  not the top-level `filters` block. Optional so older catalog payloads
   *  (pre-rollup) still type. */
  primary_compartment?: Compartment;
  /** Sourced from `accessibility_risks.restricted_subdomain.domain`, but
   *  ONLY when `restricted_subdomain.present === true`. Tells you the
   *  *kind* of polarized localization (apical / ciliary / junctional /
   *  …); use alongside `has_restricted_subdomain` which is the bool
   *  presence flag. Optional so non-restricted genes simply omit it. */
  restricted_subdomain_kind?: RestrictedSubdomainKind;
  /** Sourced from `accessibility_risks.secreted_form.source`, but ONLY
   *  when `secreted_form.present === true`. Tells you how the soluble
   *  form is generated (alternative splicing / proteolytic / both /
   *  unknown). `alternative_splicing` covers soluble splice isoforms.
   *  Use alongside `has_secreted_form` which is the bool presence flag. */
  secreted_form_source?: SecretedSource;
  /** Sourced from `deterministic_features.surface_bind` (Balbi 2026,
   *  PMID 41604262). 4-way bucket of `n_sites` × `has_data`. */
  surface_bind_targetability?:
    | "high"
    | "moderate"
    | "none"
    | "not_scored";
  /** SURFACE-Bind's native family axis. Only set when `has_data=true`. */
  surface_bind_main_class?:
    | "Receptors"
    | "Enzymes"
    | "Transporters"
    | "Miscellaneous";
  /** Schweke 2024 AF2 homo-oligomer prediction (PMID 38325366). Schweke
   *  is positives-only — `false` (or absent in the record) means "not
   *  in the predicted homomer refset", NOT "AF2 disagrees". Use as a
   *  lower-bound structural prior on homo-oligomerization risk. */
  is_homo_oligomer?: boolean;
}

export interface CatalogRow {
  symbol: string;
  uniprot: string;
  name?: string;
  synonyms?: string[];
  n_sources: number;
  db: {
    uniprot: number;
    go: number;
    surfy: number;
    cspa: number;
    hpa: number;
  };
  /** Per-model NCBI-variant verdict in the order matrix.models
   *  exposes. Today: [Haiku 4.5, Sonnet 4.6, Opus 4.8]. Each slot is
   *  null when no run exists for that model on that gene (most non-
   *  bench genes have only the Sonnet slot populated). */
  triage_by_model: (TriageCell | null)[];
  deep_dive: boolean;
  /** SURFACE-Bind scored-patch count (Balbi et al 2026, PMID 41604262). Three-
   *  state semantics:
   *   - ``undefined`` → UniProt not in SURFACE-Bind's dataset at
   *     all (filtered out at structural QC).
   *   - ``0`` → scored, but no patches cleared the MaSIF threshold.
   *   - ``N > 0`` → number of scored targetable patches.
   *  Populated by the Worker via D1 join on ``surface_bind_protein``;
   *  ``undefined`` here also covers the pre-Worker-deploy interim
   *  where the field hasn't shipped yet. */
  surface_bind_sites?: number;
  /** Slimmed deep-dive `filters` projection — present only when
   *  `deep_dive=true` AND the annotation_json parsed. See the
   *  DeepDiveFilters docstring for the field set; the catalog
   *  filter panel reads this for the "Deep Dive" filter group. */
  deep_dive_filters?: DeepDiveFilters;
}

export interface Catalog {
  /** Always ``"api"`` — the committed snapshot path was dropped when
   *  the public Worker stabilized. */
  source: "api";
  generated_at?: string;
  universe_version?: string;
  bench_version?: string | null;
  /** Model order for `CatalogRow.triage_by_model`. The viewer pins
   *  this to a known [Haiku, Sonnet, Opus] but reads from the
   *  response so a future Worker-side reorder doesn't silently swap
   *  columns. */
  models: string[];
  n_rows: number;
  n_with_triage: number;
  n_with_deep_dive: number;
  /** Cohort percentile cutoffs for `n_papers_selected`, baked at
   *  catalog-build time by the Worker (`row_schema ≥ 6`). Null on
   *  responses from older Workers OR when fewer than 3 deep-dive
   *  records carry the count — in that case the per-row
   *  `n_papers_selected_band` will be absent too and the filter UI
   *  should fall back to "any" only. */
  n_papers_selected_cutoffs?: PapersSelectedCutoffs | null;
  rows: CatalogRow[];
}

const DEFAULT_API_BASE = "https://api.deliverome.org/surfaceome";
const FETCH_TIMEOUT_MS = 8_000;

/**
 * Cache mode for the live Worker fetches (/v1/genes index + per-gene
 * record + triage reasoning). Production keeps `force-cache` so each
 * fetched payload is baked into the static export (SSG,
 * citation-stable). In dev / any non-production build we use
 * `no-store` so the page always reflects the LATEST published D1
 * record immediately — no stale Next-dev fetch-cache to fight while
 * iterating on annotations. Flip is driven by NODE_ENV (Next sets it:
 * `development` under `next dev`, `production` under `next build`).
 *
 * Applies to BOTH `/v1/genes` (the freshness-dot auto-derive reads
 * cohort schema_versions off this) and per-gene record fetches.
 * Skipping this for `/v1/genes` lets the freshness signal go stale
 * after a re-annotation lands — symptom: a gene republished at a new
 * schema_version still reads amber because the cached payload only
 * has the pre-republish version.
 */
const RECORD_FETCH_CACHE: RequestCache =
  process.env.NODE_ENV === "production" ? "force-cache" : "no-store";

/**
 * Build-time catalog fetch. The committed
 * ``viewer/public/data/catalog.json`` snapshot fallback was dropped
 * once the public Worker stabilized — the snapshot's 270k-line
 * formatted JSON dominated the PR diff for ~zero runtime benefit.
 * In production, the `surfaceome-viewer` Pages project depends on
 * `api.deliverome.org/surfaceome/v1/catalog` being live.
 *
 * Two non-production paths:
 *   * ``SURFACEOME_API_BASE=local`` — return an empty stub catalog
 *     without hitting the network. Used by the GitHub-Actions
 *     viewer-build workflow (the runner's IPs hit Cloudflare's WAF
 *     and get 403'd, so the workflow runs an offline build smoke
 *     and lets the Pages-side build do the live fetch).
 *   * Custom URL — point at a staging Worker for previews.
 *
 * If the live fetch fails, the build fails loudly with the Worker
 * response status.
 */
interface GeneNameEntry {
  name: string;
  synonyms: string[];
  /** UniProt accession for this gene symbol, sourced from HGNC's
   *  authoritative symbol→uniprot mapping. Used to fill in the
   *  catalog rows where `candidate_universe_public.uniprot_acc` is
   *  empty (most non-surface genes). Empty when HGNC has no mapping
   *  (rare — non-protein-coding loci, withdrawn symbols). */
  uniprot?: string;
}

// Module-level memo. The TSV is ~3.5 MB / 19,325 rows; parsing it
// once per build (or once per request in dev) is fine, but
// `loadGeneName` is called for every gene-detail page (potentially
// thousands at SSG time), so we cache after the first parse.
let _geneNamesCache: Record<string, GeneNameEntry> | null = null;

function loadGeneNamesMap(): Record<string, GeneNameEntry> {
  if (_geneNamesCache) return _geneNamesCache;
  const out: Record<string, GeneNameEntry> = {};
  // Pass 1 — NCBI gene_info. Source of synonyms (canonical pipe-
  // delimited list) and a fallback gene description when HGNC
  // doesn't carry one.
  try {
    const raw = readFileSync(GENE_NAMES_TSV, "utf-8");
    const lines = raw.split(/\r?\n/);
    if (lines.length >= 2) {
      const header = lines[0].split("\t");
      const symIdx = header.indexOf("gene_symbol");
      const nameIdx = header.indexOf("description");
      const synIdx = header.indexOf("synonyms");
      if (symIdx >= 0 && nameIdx >= 0 && synIdx >= 0) {
        for (let i = 1; i < lines.length; i++) {
          const row = lines[i];
          if (!row) continue;
          const cols = row.split("\t");
          const sym = cols[symIdx]?.trim();
          if (!sym) continue;
          const name = cols[nameIdx]?.trim() ?? "";
          const rawSyn = cols[synIdx]?.trim() ?? "";
          const synonyms =
            rawSyn && rawSyn !== "-"
              ? rawSyn.split("|").filter((s) => s && s !== "-")
              : [];
          out[sym] = { name, synonyms };
        }
      }
    }
  } catch {
    /* fall through with whatever we got so far */
  }
  // Pass 2 — HGNC. Authoritative symbol→uniprot mapping; HGNC's
  // `name` overrides NCBI's `description` when both are present so
  // every gene gets the canonical "approved name" used by UniProt /
  // Ensembl downstream. Entries seen only in HGNC (not NCBI) get
  // created here, so the merged map covers any gene with an HGNC
  // record even if NCBI's protein-coding triageable filter dropped it.
  try {
    const raw = readFileSync(HGNC_TSV, "utf-8");
    const lines = raw.split(/\r?\n/);
    if (lines.length >= 2) {
      const header = lines[0].split("\t");
      const symIdx = header.indexOf("symbol");
      const nameIdx = header.indexOf("name");
      const uniprotIdx = header.indexOf("uniprot_ids");
      if (symIdx >= 0 && uniprotIdx >= 0) {
        for (let i = 1; i < lines.length; i++) {
          const row = lines[i];
          if (!row) continue;
          const cols = row.split("\t");
          const sym = cols[symIdx]?.trim();
          if (!sym) continue;
          const hgncName = nameIdx >= 0 ? (cols[nameIdx]?.trim() ?? "") : "";
          // HGNC's uniprot_ids is a pipe-separated list when a symbol
          // maps to multiple reviewed Swiss-Prot entries (rare —
          // mostly genuine 1-to-1). Take the first so the rendered
          // value is unambiguous; downstream consumers wanting the
          // full list can hit the API for the deep-dive record.
          const rawUni = cols[uniprotIdx]?.trim() ?? "";
          const uniprot = rawUni ? rawUni.split("|")[0]?.trim() : "";
          const prior = out[sym];
          out[sym] = {
            name: hgncName || prior?.name || "",
            synonyms: prior?.synonyms ?? [],
            uniprot: uniprot || prior?.uniprot,
          };
        }
      }
    }
  } catch {
    /* fall through */
  }
  _geneNamesCache = out;
  return out;
}

function enrichRowsWithNames(
  rows: CatalogRow[],
  names: Record<string, GeneNameEntry>,
): CatalogRow[] {
  if (Object.keys(names).length === 0) return rows;
  return rows.map((r) => {
    const entry = names[r.symbol];
    if (!entry) return r;
    // Backfill `uniprot` from HGNC when the row arrived from
    // `candidate_universe_public` with an empty accession (currently
    // ~71% of universe rows — every non-surface gene). Existing
    // accessions take priority because the catalog row may be more
    // specific (e.g. an isoform-aware mapping the universe builder
    // pinned to).
    return {
      ...r,
      name: entry.name,
      synonyms: entry.synonyms,
      uniprot: r.uniprot || entry.uniprot || "",
    };
  });
}

/**
 * The Worker (`row_schema: 3`) packs each row's per-model NCBI
 * verdicts into a 3-slot tuple at `r.tr` — `[haiku?, sonnet?, opus?]`
 * where each slot is either `null` or `[verdict, reason]`. Plus the
 * 5 DB flags as a 5-bit integer at `r.db` (LSB → MSB: uniprot, go,
 * surfy, cspa, hpa).
 *
 * Inflate both into the object/array shape the CatalogTable consumes.
 * No-op if a snapshot fallback already has the inflated form.
 */
function inflateCatalogRow(raw: unknown): CatalogRow {
  const r = raw as Record<string, unknown>;
  let db: CatalogRow["db"];
  if (typeof r.db === "number") {
    const bits = r.db as number;
    db = {
      uniprot: bits & 1 ? 1 : 0,
      go: bits & 2 ? 1 : 0,
      surfy: bits & 4 ? 1 : 0,
      cspa: bits & 8 ? 1 : 0,
      hpa: bits & 16 ? 1 : 0,
    };
  } else {
    db = r.db as CatalogRow["db"];
  }
  const tr = (r.tr ?? r.triage_by_model) as
    | Array<[string, string | null] | null>
    | undefined;
  const triage_by_model: (TriageCell | null)[] = (tr ?? [null, null, null]).map(
    (slot) => (slot ? { verdict: slot[0], reason: slot[1] } : null),
  );
  // Worker row_schema v4+ ships an optional ``sb`` field — number of
  // SURFACE-Bind targetable patches. Undefined on rows whose UniProt
  // isn't in SURFACE-Bind at all (the "not in dataset" state); 0
  // means scored-but-no-patches. Decoder passes the value through
  // unchanged so the table filter can distinguish the three states.
  const sb = r.sb as number | undefined;
  // Worker row_schema v5+ ships an optional ``ddf`` field — slim
  // projection of SurfaceomeRecord.filters. Snapshot fallbacks may
  // carry the inflated `deep_dive_filters` shape instead, so accept
  // either. Type-cast pass-through; the field is fully optional and
  // the catalog filter pass guards `r.deep_dive_filters` before reading.
  const ddf = (r.ddf ?? r.deep_dive_filters) as DeepDiveFilters | undefined;
  return {
    symbol: r.symbol as string,
    uniprot: (r.uniprot as string | undefined) ?? "",
    name: r.name as string | undefined,
    synonyms: r.synonyms as string[] | undefined,
    n_sources: r.n_sources as number,
    db,
    triage_by_model,
    deep_dive: Boolean(r.deep_dive),
    surface_bind_sites: typeof sb === "number" ? sb : undefined,
    deep_dive_filters: ddf,
  };
}

/** Look up the descriptive gene name for a symbol. Used by the gene
 *  viewer page header so the page renders e.g. ``transferrin`` under
 *  ``TF``. Returns ``null`` when the symbol isn't in the lookup. */
export function loadGeneName(
  symbol: string,
): { name: string; synonyms: string[] } | null {
  const names = loadGeneNamesMap();
  const entry = names[symbol];
  if (!entry) return null;
  return entry;
}

// Module-level memo. SSG builds call loadCatalog once per home/benchmark
// build, plus once per gene page if we ask for the row by symbol. Memo
// avoids re-inflating 19k rows on every per-gene lookup.
let _catalogPromise: Promise<Catalog> | null = null;
let _catalogRowIndex: Map<string, CatalogRow> | null = null;

/**
 * Server-side lookup for a single gene's catalog row — gives the per-
 * gene page access to the 5 source-DB votes (`r.db`) and `n_sources`
 * count that the catalog + benchmark tables surface. Returns `null`
 * when the symbol is absent from the universe (rare; resolver-failure
 * outliers). Builds an index on first call; subsequent lookups are
 * O(1).
 */
export async function loadCatalogRow(symbol: string): Promise<CatalogRow | null> {
  if (!_catalogRowIndex) {
    const cat = await loadCatalog();
    _catalogRowIndex = new Map(cat.rows.map((r) => [r.symbol, r]));
  }
  return _catalogRowIndex.get(symbol) ?? null;
}

export async function loadCatalog(): Promise<Catalog> {
  if (_catalogPromise) return _catalogPromise;
  _catalogPromise = _loadCatalogImpl();
  return _catalogPromise;
}

async function _loadCatalogImpl(): Promise<Catalog> {
  const names = loadGeneNamesMap();
  const base = (process.env.SURFACEOME_API_BASE ?? DEFAULT_API_BASE).trim();
  if (!base) {
    throw new Error(
      "SURFACEOME_API_BASE is empty — set it to the public Worker (e.g. " +
        "https://api.deliverome.org/surfaceome), to `local` for an empty " +
        "stub, or to a staging endpoint.",
    );
  }
  if (base === "local") {
    // Offline-build stub. Used by the GitHub-Actions viewer-build
    // smoke; the rendered page shows the chrome but a 0-row catalog.
    // Pages-side builds run with the real Worker URL and emit the
    // populated page.
    return {
      source: "api",
      generated_at: undefined,
      universe_version: "local-stub",
      bench_version: null,
      models: ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-8"],
      n_rows: 0,
      n_with_triage: 0,
      n_with_deep_dive: 0,
      rows: [],
    };
  }
  // Try the build-time snapshot first (written by
  // `viewer/scripts/build-data-snapshot.mjs` before `next build`). When
  // present this saves us a ~5.7 MB Worker fetch × every SSG worker —
  // and avoids the Next.js Data-Cache miss that the 2MB cap forces.
  type CatalogPayload = Omit<Catalog, "source" | "rows"> & {
    rows: unknown[];
  };
  let payload = readBuildCache<CatalogPayload>("catalog.json");
  if (!payload) {
    // Retry-on-5xx loop. The /v1/catalog response is ~5.7 MB and the
    // Worker brushes Cloudflare's per-request CPU cap when D1 is cold,
    // so intermittent 503s are normal — they almost always recover on
    // the next call. Three attempts at 1.5s / 3s / 6s backoff. After
    // that, fall through to the throw so build failures stay loud
    // (we don't want to ship a viewer built against a wedged Worker).
    let res: Response | null = null;
    let lastStatus: number | null = null;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
      try {
        res = await fetch(`${base}/v1/catalog`, {
          // `force-cache` is still set on the fallback path so dev / no-
          // snapshot builds at least share the response across pages,
          // even though Next.js will warn that the payload exceeds 2MB.
          cache: "force-cache",
          signal: controller.signal,
        });
      } finally {
        clearTimeout(timer);
      }
      if (res.ok) break;
      lastStatus = res.status;
      // Don't retry on 4xx — those are deterministic.
      if (res.status < 500) break;
      // 503 / 502 / 504 — usually transient; back off and retry.
      if (attempt < 2) {
        const delay = [1500, 3000][attempt] ?? 3000;
        await new Promise((r) => setTimeout(r, delay));
      }
    }
    if (!res || !res.ok) {
      throw new Error(
        `${base}/v1/catalog returned ${lastStatus ?? "no-response"} ` +
          `after 3 attempts`,
      );
    }
    payload = (await res.json()) as CatalogPayload;
  }
  if (!payload.rows || payload.rows.length === 0) {
    throw new Error(
      `${base}/v1/catalog returned an empty catalog — the Worker is ` +
        "reachable but no candidate-universe data has been loaded into D1 yet.",
    );
  }
  // Sonnet 4.6 (slot 1 in triage_by_model) is the catalog's headline
  // verdict — every page surface reads from that slot. Rows where it
  // didn't run on file are the universe's resolver-failure outliers
  // (e.g. CTXN1 as of 2026-05; SEA was healed by PR #30). Drop them
  // from the catalog so the visible universe matches `n_with_triage`
  // and the verdict filter doesn't need a "no call" bucket.
  const inflated = payload.rows
    .map(inflateCatalogRow)
    .filter((r) => Boolean(r.triage_by_model[1]));
  // Reconcile the per-row `deep_dive` flag against the exact set of genes
  // `generateStaticParams` will emit pages for — the Worker's `/v1/genes`
  // list (memoized, so both call sites share one build-cached fetch).
  // CatalogTable renders a `/[symbol]` link only for `deep_dive` rows, and
  // under `output: export` a link to a gene without a generated page is a
  // hard build error ("missing param … in generateStaticParams"). Deriving
  // both the link set and the page set from `/v1/genes` makes them
  // consistent by construction, even if `/v1/catalog`'s own `deep_dive`
  // column momentarily disagrees while D1 is mid-write (e.g. a deep-dive
  // landing between the two endpoint fetches).
  const deepDiveGenes = new Set(await listSurfaceomeGenes());
  const reconciled = inflated.map((r) =>
    r.deep_dive === deepDiveGenes.has(r.symbol)
      ? r
      : { ...r, deep_dive: deepDiveGenes.has(r.symbol) },
  );
  const rows = enrichRowsWithNames(reconciled, names);
  const n_with_deep_dive = rows.reduce(
    (n, r) => n + (r.deep_dive ? 1 : 0),
    0,
  );
  return {
    source: "api",
    ...payload,
    // Override the Worker's header counts so they match what we
    // actually shipped to the page (after dropping null-triage rows).
    n_rows: rows.length,
    n_with_triage: rows.length,
    rows,
    n_with_deep_dive,
  };
}

/**
 * Build-time fetch for the 147-gene benchmark matrix. Same pattern as
 * `loadCatalog`: hit the public Worker with `cache: "force-cache"` so the
 * response gets baked into the `output: "export"` artifact. Returns an
 * empty stub under `SURFACEOME_API_BASE=local` so the GitHub-Actions
 * smoke build (whose IPs hit the Cloudflare WAF) doesn't 403.
 */
export async function loadBenchmarkMatrix(): Promise<BenchmarkMatrix> {
  const base = (process.env.SURFACEOME_API_BASE ?? DEFAULT_API_BASE).trim();
  if (!base) {
    throw new Error(
      "SURFACEOME_API_BASE is empty — set it to the public Worker (e.g. " +
        "https://api.deliverome.org/surfaceome), to `local` for an empty " +
        "stub, or to a staging endpoint.",
    );
  }
  if (base === "local") {
    return {
      bench_version: null,
      universe_version: null,
      sources: ["uniprot", "go", "surfy", "cspa", "hpa"],
      models: [
        "claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5",
      ],
      variants: ["naive", "ncbi", "web_ncbi", "pubmed_ncbi"],
      headline_variant: "ncbi",
      n_genes: 0,
      rows: [],
    };
  }
  // Build-time snapshot first (same rationale as loadCatalog: matrix is
  // ~3 MB, exceeds the Next.js Data-Cache 2 MB cap, refetched per page
  // without the snapshot).
  const cached = readBuildCache<BenchmarkMatrix>("benchmark-matrix.json");
  if (cached) {
    return cached;
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  const res = await fetch(`${base}/v1/benchmark/matrix`, {
    cache: "force-cache",
    signal: controller.signal,
  }).finally(() => clearTimeout(timer));
  if (!res.ok) {
    throw new Error(`${base}/v1/benchmark/matrix returned ${res.status}`);
  }
  const payload = (await res.json()) as BenchmarkMatrix;
  return payload;
}

// Module-level memo for per-gene benchmark-row lookups. The benchmark
// matrix is ~147 rows; index it once so every gene page that asks "is
// this gene in SurfaceBench?" is an O(1) Map hit rather than a re-fetch.
let _benchmarkRowIndex: Map<string, BenchmarkRow> | null = null;

/**
 * Server-side lookup for a single gene's benchmark row — gives the per-
 * gene page the curated ground-truth verdict (`truth_verdict`) when the
 * gene is one of the ~147 SurfaceBench members. Returns `null` for the
 * ~19k genes NOT in the benchmark (the common case), so the caller can
 * conditionally render the benchmark call only for bench members.
 *
 * Builds the index off `loadBenchmarkMatrix()` on first call; under
 * `SURFACEOME_API_BASE=local` that matrix is the empty stub, so every
 * lookup returns `null` and the benchmark row simply doesn't render.
 */
export async function loadBenchmarkRow(
  symbol: string,
): Promise<BenchmarkRow | null> {
  if (!_benchmarkRowIndex) {
    const matrix = await loadBenchmarkMatrix();
    _benchmarkRowIndex = new Map(matrix.rows.map((r) => [r.gene_symbol, r]));
  }
  return _benchmarkRowIndex.get(symbol) ?? null;
}

/**
 * The set of genes that have a viewable deep-dive page. Sourced from the
 * Worker's `/v1/genes` endpoint, which lists the `surface_annotation`
 * rows in public D1 — the authoritative deep-dive store. Drives which
 * gene pages `generateStaticParams` emits.
 *
 * Returns `[]` ONLY under `SURFACEOME_API_BASE=local` (or empty) so the
 * offline CI smoke build emits no gene routes; the Pages-side build runs
 * against the real Worker and emits the full set.
 *
 * On a real Worker error it now THROWS (retry-on-5xx, mirroring
 * `loadCatalog`) rather than returning `[]`. An empty list is not a
 * benign "no extra routes" state: `loadCatalog` reconciles every catalog
 * row's `deep_dive` flag against this set, so a silent `[]` would drop
 * all gene routes AND mark every row non-deep-dive — shipping a viewer
 * with no gene pages and no error. The build must fail loudly instead,
 * exactly like the catalog fetch.
 */
/** One deep-dive gene in the index: its symbol plus whether its published
 *  record is `stale` — i.e. its declared `schema_version` lags the current
 *  observed target (the highest `schema_version` seen across the cohort,
 *  computed per-fetch by :func:`maxSchemaVersion`). The per-gene
 *  `schema_version` is read straight off the Worker's `/v1/genes` index
 *  (D1 column `surface_annotation.schema_version`), so the freshness
 *  signal updates the moment a re-annotated record lands in D1 — no
 *  manifest to regenerate, no constant to bump. The GeneJump dropdown
 *  colors each entry's freshness dot from this flag (amber = stale,
 *  green = current). */
export interface GeneEntry {
  symbol: string;
  stale: boolean;
  synonyms?: string[];
}

/** Hard-coded fallback when `/v1/genes` returns zero entries with a
 *  `schema_version` field (offline-stub build, malformed payload, very
 *  early bring-up). The cohort-observed max is preferred whenever it's
 *  computable; this only fires as a safety net.
 *
 *  Update this string if the Pydantic `SurfaceomeRecord.schema_version`
 *  default moves AND the entire cohort is empty (unlikely after bring-up).
 *  In normal operation it has no effect on the freshness dot — the
 *  observed-max wins. */
const FALLBACK_SCHEMA_VERSION = "2.9.0";

/** Cohort-wide current `schema_version` — derived from `/v1/genes` on
 *  the most recent call to :func:`listSurfaceomeGeneEntries`. Initialized
 *  to the fallback so the first import has a sensible value before the
 *  Worker fetch runs; replaced with the observed max after each fetch.
 *  Exported for any caller that wants to display "current schema
 *  version: X" (none today; reserved for future use). */
export let CURRENT_RECORD_SCHEMA_VERSION: string = FALLBACK_SCHEMA_VERSION;

/** Compare two semver-shaped `"major.minor.patch"` strings numerically.
 *  Returns negative / 0 / positive in the standard sort order. Falls
 *  back to lexical comparison for non-numeric components so it doesn't
 *  throw on a malformed value (just sorts it conservatively). */
function _semverCmp(a: string, b: string): number {
  const pa = a.split(".");
  const pb = b.split(".");
  const len = Math.max(pa.length, pb.length);
  for (let i = 0; i < len; i++) {
    const na = parseInt(pa[i] ?? "0", 10);
    const nb = parseInt(pb[i] ?? "0", 10);
    if (Number.isNaN(na) || Number.isNaN(nb)) {
      return (pa[i] ?? "").localeCompare(pb[i] ?? "");
    }
    if (na !== nb) return na - nb;
  }
  return 0;
}

/** Pick the highest `schema_version` from an iterable of strings (skipping
 *  `null` / `undefined` / empty). Returns `null` when no real version is
 *  present so the caller can fall back to its preferred default. */
export function maxSchemaVersion(
  versions: Iterable<string | undefined | null>,
): string | null {
  let best: string | null = null;
  for (const v of versions) {
    if (!v) continue;
    if (best === null || _semverCmp(v, best) > 0) best = v;
  }
  return best;
}

let _geneEntriesPromise: Promise<GeneEntry[]> | null = null;

/**
 * Deep-dive genes WITH each gene's declared `schema_version`. This is the
 * single primitive behind the gene list: `listSurfaceomeGenes()` projects
 * it to symbols, so the Worker's `/v1/genes` index is fetched at most once
 * per build (the result is memoized).
 */
export async function listSurfaceomeGeneEntries(): Promise<GeneEntry[]> {
  if (_geneEntriesPromise) return _geneEntriesPromise;
  _geneEntriesPromise = _listSurfaceomeGeneEntriesImpl();
  return _geneEntriesPromise;
}

export async function listSurfaceomeGenes(): Promise<string[]> {
  return (await listSurfaceomeGeneEntries()).map((e) => e.symbol);
}

async function _listSurfaceomeGeneEntriesImpl(): Promise<GeneEntry[]> {
  const base = (process.env.SURFACEOME_API_BASE ?? DEFAULT_API_BASE).trim();
  // Offline-build stub stays a benign empty list: the GitHub-Actions
  // viewer-build smoke sets SURFACEOME_API_BASE=local and expects zero
  // gene routes (the Pages-side build does the real fetch).
  if (base === "local" || !base) return [];
  // Retry-on-5xx loop mirroring loadCatalog. /v1/genes is a small
  // payload, but the Worker brushes Cloudflare's per-request CPU cap when
  // D1 is cold, so intermittent 503s are normal and recover on the next
  // call. Three attempts at 1.5s / 3s backoff; 4xx is deterministic so we
  // break and surface it without retrying.
  let res: Response | null = null;
  let lastStatus: number | null = null;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    try {
      // Same dev/prod pattern as RECORD_FETCH_CACHE: force-cache in prod
      // so the static export bakes the gene list, no-store in dev so the
      // freshness-dot auto-derive sees the live cohort. Without this,
      // Next dev's fetch-cache persists across restarts and the
      // auto-derived current-schema-version reads off a frozen cohort
      // (the symptom: gene republished at 2.9.0 still reads amber because
      // the cached /v1/genes payload only has the pre-republish 1.1.0).
      res = await fetch(`${base}/v1/genes`, {
        cache: RECORD_FETCH_CACHE,
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timer);
    }
    if (res.ok) break;
    lastStatus = res.status;
    // Don't retry on 4xx — those are deterministic.
    if (res.status < 500) break;
    if (attempt < 2) {
      const delay = [1500, 3000][attempt] ?? 3000;
      await new Promise((r) => setTimeout(r, delay));
    }
  }
  if (!res || !res.ok) {
    throw new Error(
      `${base}/v1/genes returned ${lastStatus ?? "no-response"} ` +
        `after 3 attempts`,
    );
  }
  const data = (await res.json()) as {
    genes?: Array<{
      gene_symbol?: string;
      schema_version?: string;
      prompt_corpus_version?: string;
    }>;
  };
  // Map symbol → (schema_version, prompt_corpus_version) straight off
  // the Worker payload. ``prompt_corpus_version`` joined the
  // ``surface_annotation`` row in 2026-06: the freshness dot now
  // tracks BOTH coordinates so a re-annotation under the same schema
  // but a newer prompt_corpus surfaces as fresh. Pre-corpus rows
  // (missing column) fall back to '0.0.0' so they don't masquerade as
  // newer than corpus-tagged rows. The /v1/genes index runs through
  // `COALESCE(prompt_corpus_version, '0.0.0')` on the Worker side, so
  // this fallback is symmetric.
  const schemaBySymbol = new Map<string, string | undefined>();
  const promptCorpusBySymbol = new Map<string, string | undefined>();
  for (const g of data.genes ?? []) {
    if (g.gene_symbol) {
      schemaBySymbol.set(g.gene_symbol, g.schema_version);
      promptCorpusBySymbol.set(g.gene_symbol, g.prompt_corpus_version);
    }
  }
  // Derive the current target from observation: the highest
  // schema_version present across the cohort. This makes the freshness
  // dot auto-update when a re-annotated record lands at a new schema
  // version — no constant to bump in lock-step with the Pydantic
  // default. Empty cohort → keep the fallback (so an early bring-up
  // / stub build still has a sensible target).
  const observed = maxSchemaVersion(schemaBySymbol.values());
  if (observed !== null) CURRENT_RECORD_SCHEMA_VERSION = observed;
  const target = CURRENT_RECORD_SCHEMA_VERSION;
  // The current prompt_corpus target is the highest one observed
  // across the cohort, computed the same way the schema_version
  // target is. Both axes default-stale when missing — a row whose
  // schema is current but whose corpus lags the observed max still
  // reads stale.
  const observedCorpus = maxSchemaVersion(promptCorpusBySymbol.values());
  const targetCorpus = observedCorpus ?? "0.0.0";
  const names = loadGeneNamesMap();
  return Array.from(schemaBySymbol.keys())
    .sort((a, b) => a.localeCompare(b))
    .map((symbol) => ({
      symbol,
      stale:
        schemaBySymbol.get(symbol) !== target ||
        (promptCorpusBySymbol.get(symbol) ?? "0.0.0") !== targetCorpus,
      synonyms: names[symbol]?.synonyms,
    }));
}

/**
 * Worker fetch for one gene's full SurfaceomeRecord. Returns `null` on
 * any Worker error (network, 404, non-2xx, malformed JSON). Cache mode is
 * `RECORD_FETCH_CACHE` (force-cache in prod for SSG, no-store in dev for
 * always-fresh). D1 is the only source — there is no on-disk fallback.
 */
async function _fetchRecordFromWorker(
  symbol: string,
  base: string,
): Promise<SurfaceomeRecord | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(`${base}/v1/genes/${symbol}`, {
      cache: RECORD_FETCH_CACHE,
      signal: controller.signal,
    });
    if (!res.ok) return null;
    return (await res.json()) as SurfaceomeRecord;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

interface TriageMeta {
  reasoning: string | null;
  reason: string | null;
  confidence: string | null;
}

/**
 * Pull the triage agent's headline call (reasoning + reason code +
 * confidence) from `/v1/triage/{symbol}` (the `triage_run` store),
 * picking the latest Sonnet 4.6 + `ncbi` variant run — the same (model,
 * variant) the catalog rationale drawer surfaces.
 *
 * Used to backfill deep-dive records that pre-date one or more of these
 * fields. `verdict_reasoning` is selected from the latest run that has
 * non-empty prose (older runs sometimes have an empty body); the reason
 * + confidence come from that same latest-with-reasoning run so the
 * three fields stay consistent. Returns ``{null, null, null}`` on any
 * miss so the caller can do a single shallow merge.
 */
/** Most-positive triage call (yes > contextual > unclear > no) from
 *  /v1/triage/{symbol}, with latest `created_at` as the tiebreak.
 *  Matches the picker the catalog drawer uses — see
 *  CatalogRationaleDrawer.pickSonnetHeadlineAndSecondary. The
 *  bundled `rec.triage_signal` on a SurfaceomeRecord is a SPECIFIC
 *  triage call (the one that triggered the deep-dive); this helper
 *  surfaces the latest positive consensus, which the catalog row
 *  also shows. KLK2 is the smoking gun: bundled signal='unlikely'
 *  (2026-06-01 sonnet-ncbi), headline='possibly_accessible'
 *  (2026-06-23 sonnet-pubmed_ncbi). */
export interface TriageHeadlinePayload {
  signal: TriageSignal;
  reason: string | null;
  reasoning: string;
  confidence: string | null;
  /** ISO timestamp of the picked run (newest with the most-positive
   *  verdict). Surfaced on the gene page so a reader can spot a
   *  stale 3-week-old "no" being overridden by a fresh "contextual". */
  createdAt: string | null;
  /** prompt_variant of the picked run (e.g. "pubmed_ncbi"). Surfaced
   *  alongside the verdict so the reader knows which triage variant
   *  the headline call came from. */
  promptVariant: string | null;
  /** Other variants' latest runs that disagree with the headline,
   *  sorted positive→negative, capped at 3. Same shape the catalog
   *  drawer surfaces under "Other triage variants disagree". Empty
   *  when all variants agree. */
  secondary: ReadonlyArray<TriageHeadlineSecondaryEntry>;
}

export interface TriageHeadlineSecondaryEntry {
  signal: TriageSignal;
  /** Raw verdict ("yes" | "contextual" | "no" | …) for the
   *  verdict-tone class lookup; mirrors what the catalog drawer
   *  renders so the two surfaces tone the same chip. */
  verdict: string;
  reason: string | null;
  createdAt: string;
  promptVariant: string | null;
}

const _VERDICT_RANK: Record<string, number> = {
  yes: 3,
  contextual: 2,
  unclear: 1,
  no: 0,
};

function _verdictToSignal(v: string | null | undefined): TriageSignal {
  if (v === "yes") return "likely_accessible";
  if (v === "contextual") return "possibly_accessible";
  if (v === "no") return "unlikely";
  return "unknown";
}

export async function loadTriageHeadline(
  symbol: string,
): Promise<TriageHeadlinePayload | null> {
  const base = (process.env.SURFACEOME_API_BASE ?? DEFAULT_API_BASE).trim();
  if (!base || base === "local") return null;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(`${base}/v1/triage/${symbol}`, {
      cache: RECORD_FETCH_CACHE,
      signal: controller.signal,
    });
    if (!res.ok) return null;
    const data = (await res.json()) as {
      runs?: Array<{
        created_at: string;
        model: string;
        prompt_variant: string | null;
        predicted_verdict: string;
        predicted_reason: string | null;
        predicted_confidence: string | null;
        verdict_reasoning: string | null;
      }>;
    };
    // Collapse to one row per (model × variant), keeping the latest.
    // Scoped to Sonnet 4.6 to match the drawer (the catalog's
    // canonical headline model); cross-model runs are useful in the
    // benchmark page but would noise the deep-dive's triage row.
    const latestByVariant = new Map<string, NonNullable<typeof data.runs>[number]>();
    for (const r of data.runs ?? []) {
      if (r.model !== "claude-sonnet-4-6") continue;
      const key = r.prompt_variant ?? "";
      const prev = latestByVariant.get(key);
      if (!prev || prev.created_at < r.created_at) {
        latestByVariant.set(key, r);
      }
    }
    const ranked = [...latestByVariant.values()].sort((a, b) => {
      const dr =
        (_VERDICT_RANK[b.predicted_verdict] ?? -1) -
        (_VERDICT_RANK[a.predicted_verdict] ?? -1);
      if (dr !== 0) return dr;
      return a.created_at < b.created_at ? 1 : -1;
    });
    if (ranked.length === 0) return null;
    const headline = ranked[0];
    const secondary: TriageHeadlineSecondaryEntry[] = ranked
      .slice(1)
      .filter((r) => r.predicted_verdict !== headline.predicted_verdict)
      .slice(0, 3)
      .map((r) => ({
        signal: _verdictToSignal(r.predicted_verdict),
        verdict: r.predicted_verdict,
        reason: r.predicted_reason?.trim() || null,
        createdAt: r.created_at,
        promptVariant: r.prompt_variant ?? null,
      }));
    return {
      signal: _verdictToSignal(headline.predicted_verdict),
      reason: headline.predicted_reason?.trim() || null,
      reasoning: headline.verdict_reasoning?.trim() ?? "",
      confidence: headline.predicted_confidence?.trim() || null,
      createdAt: headline.created_at,
      promptVariant: headline.prompt_variant ?? null,
      secondary,
    };
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

async function _fetchTriageMetaFromWorker(
  symbol: string,
  base: string,
): Promise<TriageMeta> {
  const empty: TriageMeta = { reasoning: null, reason: null, confidence: null };
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(`${base}/v1/triage/${symbol}`, {
      cache: RECORD_FETCH_CACHE,
      signal: controller.signal,
    });
    if (!res.ok) return empty;
    const data = (await res.json()) as {
      runs?: Array<{
        created_at: string;
        model: string;
        prompt_variant: string | null;
        verdict_reasoning: string | null;
        predicted_reason?: string | null;
        predicted_confidence?: string | null;
      }>;
    };
    let latest:
      | {
          created_at: string;
          verdict_reasoning: string;
          predicted_reason: string | null;
          predicted_confidence: string | null;
        }
      | null = null;
    for (const r of data.runs ?? []) {
      if (r.model !== "claude-sonnet-4-6") continue;
      if (r.prompt_variant !== "ncbi") continue;
      const reasoning = r.verdict_reasoning?.trim();
      if (!reasoning) continue;
      if (!latest || latest.created_at < r.created_at) {
        latest = {
          created_at: r.created_at,
          verdict_reasoning: reasoning,
          predicted_reason: r.predicted_reason?.trim() || null,
          predicted_confidence: r.predicted_confidence?.trim() || null,
        };
      }
    }
    if (!latest) return empty;
    return {
      reasoning: latest.verdict_reasoning,
      reason: latest.predicted_reason,
      confidence: latest.predicted_confidence,
    };
  } catch {
    return empty;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Load one gene's full SurfaceomeRecord from public D1 via the Worker.
 *
 * D1 is the only source — there is no fs fallback. Returns `null` under
 * `SURFACEOME_API_BASE=local` (or empty), which the offline CI smoke
 * build uses, and on any Worker error.
 *
 * Triage-meta backfill: when any of ``triage_reasoning`` /
 * ``triage_reason`` / ``triage_confidence`` is missing on the resolved
 * record, pull the headline (Sonnet 4.6 + NCBI variant) run from
 * ``/v1/triage/{symbol}`` and overlay each field that the record itself
 * doesn't carry. Records published before these fields existed serve
 * them as ``null`` / ``undefined`` even though the values live in
 * ``triage_run`` and render in the catalog drawer — sourcing from the
 * same place keeps the two surfaces in sync without re-publishing the
 * record into D1.
 */
export async function loadSurfaceomeRecord(
  symbol: string,
): Promise<SurfaceomeRecord | null> {
  const base = (process.env.SURFACEOME_API_BASE ?? DEFAULT_API_BASE).trim();
  if (base === "local" || !base) {
    return null;
  }
  let record = await _fetchRecordFromWorker(symbol, base);
  if (
    record &&
    (!record.triage_reasoning?.trim() ||
      !record.triage_reason ||
      !record.triage_confidence)
  ) {
    const meta = await _fetchTriageMetaFromWorker(symbol, base);
    record = {
      ...record,
      triage_reasoning:
        record.triage_reasoning?.trim() ? record.triage_reasoning : meta.reasoning,
      triage_reason: record.triage_reason ?? meta.reason,
      triage_confidence: record.triage_confidence ?? meta.confidence,
    };
  }
  // Renumber the `aN_evi_NN` ids into a single per-record `evi_N`
  // sequence so chip labels are unambiguous across the merged ledger.
  // See `renumberEvidenceIds` docstring — collisions are real (13/14
  // sample records had them), so this is on by default rather than gated.
  return record ? renumberEvidenceIds(record) : null;
}

/**
 * Rebuild each deep-dived row's `deep_dive_filters` from its per-gene
 * record, replacing whatever the Worker's `/v1/catalog` shipped. The Worker
 * projection lags the in-tree filter taxonomy until it's redeployed, so
 * deriving ddf from records here means a NEW filter field works the moment
 * it lands — no Worker deploy, no "inert until deploy" window. Both the
 * catalog index and `/compare` call this. Build-time only;
 * `loadSurfaceomeRecord` is memoized, so the per-gene reads dedup across the
 * build.
 */
export async function withDeepDiveFilters(
  rows: CatalogRow[],
): Promise<CatalogRow[]> {
  const ddSymbols = rows.filter((r) => r.deep_dive).map((r) => r.symbol);
  if (ddSymbols.length === 0) return rows;
  const records = await Promise.all(
    ddSymbols.map((s) => loadSurfaceomeRecord(s)),
  );
  const ddfBySymbol = new Map<string, DeepDiveFilters>();
  ddSymbols.forEach((sym, i) => {
    const ddf = pickDeepDiveFilters(
      records[i]?.filters as Record<string, unknown> | undefined,
      records[i]?.biological_context as Record<string, unknown> | undefined,
      records[i]?.accessibility_risks as Record<string, unknown> | undefined,
      records[i]?.deterministic_features as Record<string, unknown> | undefined,
    );
    // Partial DeepDiveFilters (older records omit newer fields); every
    // reader accesses fields optionally, so route the cast through unknown.
    if (ddf) ddfBySymbol.set(sym, ddf as unknown as DeepDiveFilters);
  });
  if (ddfBySymbol.size === 0) return rows;
  return rows.map((r) =>
    r.deep_dive && ddfBySymbol.has(r.symbol)
      ? { ...r, deep_dive_filters: ddfBySymbol.get(r.symbol) }
      : r,
  );
}

export async function loadAllSurfaceomeRecords(): Promise<SurfaceomeRecord[]> {
  const symbols = await listSurfaceomeGenes();
  // Concurrent fetch — each gene hits the Worker independently;
  // `cache: "force-cache"` dedups across the same build.
  const records = await Promise.all(
    symbols.map((sym) => loadSurfaceomeRecord(sym)),
  );
  return records.filter((r): r is SurfaceomeRecord => r != null);
}

// Enum display helpers (`titleCase` / `prettyEnum` / `tissueLabel` +
// the curated `ENUM_MAP` behind them) live in the dependency-free
// `./enums` leaf module so CLIENT components can import them without
// dragging this file's top-level `node:fs` / `node:path` imports into
// the browser bundle (webpack can't tree-shake a `node:*` import across
// a `"use client"` boundary). Re-exported here for back-compat so the
// existing server-side importers keep working unchanged.
export { titleCase, prettyEnum, tissueLabel } from "./enums";
