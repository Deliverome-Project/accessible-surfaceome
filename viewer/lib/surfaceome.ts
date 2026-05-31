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
 * on-disk fallback: deep-dive SurfaceomeRecords are written direct to
 * public D1 (`cloud.surface_annotation.publish_record`), and the
 * viewer reads them only through the Worker. The set of routes is
 * sourced the same way — `listSurfaceomeGenes` hits the Worker's
 * `/v1/genes` (the annotated-gene list backed by `surface_annotation`)
 * to decide which gene pages `generateStaticParams` emits. The old
 * committed `viewer/public/data/surfaceome/*.json` snapshots (and the
 * fs-readback fallback they powered) were removed deliberately so a
 * stale on-disk copy can never mask the authoritative D1 record.
 *
 * Like the catalog (`loadCatalog`), the gene pages therefore
 * hard-require the live Worker in production. `SURFACEOME_API_BASE=local`
 * makes both surfaces return empty (0-row catalog, 0 gene routes) so the
 * offline CI smoke build renders the chrome without a network hit; the
 * Pages-side build runs against the real Worker and emits the full set.
 */

import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import type {
  BenchmarkMatrix,
  BenchmarkRow,
  Confidence,
  CoreceptorDependency,
  EcdAccessibilityClass,
  EvidenceDensity,
  EvidenceGrade,
  ExpressionBreadth,
  ExpressionLevel,
  ProteinFamily,
  StateDependence,
  Subcategory,
  SurfaceAccessibility,
  SurfaceomeRecord,
  SurfaceSpecificity,
  TriageReason,
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

// In-tree per-gene record snapshots (`publish_record` writes these on
// every annotate run). Used to backfill the `generateStaticParams` route
// list when the Worker's edge-cached `/v1/genes` lags a fresh publish.
const SURFACEOME_SNAPSHOT_DIR = path.join(
  process.cwd(),
  "public",
  "data",
  "surfaceome",
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
   *  exposes. Today: [Haiku 4.5, Sonnet 4.6, Opus 4.7]. Each slot is
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
  rows: CatalogRow[];
}

const DEFAULT_API_BASE = "https://api.deliverome.org/surfaceome";
const FETCH_TIMEOUT_MS = 8_000;

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
      models: ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-7"],
      n_rows: 0,
      n_with_triage: 0,
      n_with_deep_dive: 0,
      rows: [],
    };
  }
  // Retry-on-5xx loop. The /v1/catalog response is ~4.5 MB and the
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
        // `force-cache` makes the response part of the static build
        // artifact under `output: "export"`. A re-deploy of the Worker
        // surfaces in the viewer on the next `npm run build` — exactly
        // the SSG lifecycle we want for a research catalogue (no
        // per-page-load D1 hits in production).
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
  const payload = (await res.json()) as Omit<Catalog, "source" | "rows"> & {
    rows: unknown[];
  };
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
        "claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5",
      ],
      variants: ["naive", "ncbi", "web_ncbi", "pubmed_ncbi"],
      headline_variant: "ncbi",
      n_genes: 0,
      rows: [],
    };
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
let _geneListPromise: Promise<string[]> | null = null;

export async function listSurfaceomeGenes(): Promise<string[]> {
  if (_geneListPromise) return _geneListPromise;
  _geneListPromise = _listSurfaceomeGenesImpl();
  return _geneListPromise;
}

async function _listSurfaceomeGenesImpl(): Promise<string[]> {
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
      res = await fetch(`${base}/v1/genes`, {
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
    genes?: Array<{ gene_symbol?: string }>;
  };
  const fromWorker = (data.genes ?? [])
    .map((g) => g.gene_symbol)
    .filter((s): s is string => Boolean(s));
  // Union with locally-published snapshots. `publish_record` writes
  // `public/data/surfaceome/{SYMBOL}.json` on every annotate run, but the
  // Worker's `/v1/genes` list is fronted by Cloudflare's edge cache and
  // can lag a freshly-published gene by minutes — long enough that under
  // `output: export` the just-generated route 500s ("missing param in
  // generateStaticParams") even though the record is already live in D1.
  // The snapshots are the in-tree source of truth, so any gene with one
  // gets a route regardless of edge-cache state; its record data still
  // comes from the Worker at render time. Best-effort — a missing dir
  // (clean checkout / CI smoke build) just leaves the Worker list as-is.
  const merged = new Set(fromWorker);
  for (const sym of _localSnapshotGenes()) merged.add(sym);
  return Array.from(merged).sort();
}

/** Gene symbols with a committed `public/data/surfaceome/{SYMBOL}.json`
 *  snapshot. Best-effort: returns `[]` if the directory is absent. */
function _localSnapshotGenes(): string[] {
  try {
    return readdirSync(SURFACEOME_SNAPSHOT_DIR)
      .filter((f) => f.endsWith(".json"))
      .map((f) => f.slice(0, -".json".length));
  } catch {
    return [];
  }
}

/**
 * Worker fetch for one gene's full SurfaceomeRecord. Returns `null` on
 * any Worker error (network, 404, non-2xx, malformed JSON). Uses
 * `cache: "force-cache"` so each gene's record is fetched once per
 * build and baked into the static export. D1 is the only source — there
 * is no on-disk fallback.
 */
async function _fetchRecordFromWorker(
  symbol: string,
  base: string,
): Promise<SurfaceomeRecord | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(`${base}/v1/genes/${symbol}`, {
      cache: "force-cache",
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

/**
 * Pull the triage agent's free-text reasoning from `/v1/triage/{symbol}`
 * (the `triage_run` store), picking the latest headline run — Sonnet 4.6
 * with the `ncbi` context variant — that carries a non-empty
 * `verdict_reasoning`. Returns `null` on any miss.
 *
 * Used to backfill a deep-dive record whose own `triage_reasoning` is
 * empty. The catalog's rationale drawer already reads this endpoint (see
 * `CatalogRationaleDrawer`); sourcing the gene-page triage drawer from
 * the same place keeps the two surfaces in sync without re-publishing
 * the record into D1.
 */
async function _fetchTriageReasoningFromWorker(
  symbol: string,
  base: string,
): Promise<string | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(`${base}/v1/triage/${symbol}`, {
      cache: "force-cache",
      signal: controller.signal,
    });
    if (!res.ok) return null;
    const data = (await res.json()) as {
      runs?: Array<{
        created_at: string;
        model: string;
        prompt_variant: string | null;
        verdict_reasoning: string | null;
      }>;
    };
    let latest: { created_at: string; verdict_reasoning: string } | null = null;
    for (const r of data.runs ?? []) {
      // Headline triage cell = Sonnet 4.6 + the NCBI context block — the
      // same (model, variant) the catalog rationale drawer surfaces.
      if (r.model !== "claude-sonnet-4-6") continue;
      if (r.prompt_variant !== "ncbi") continue;
      const reasoning = r.verdict_reasoning?.trim();
      if (!reasoning) continue;
      if (!latest || latest.created_at < r.created_at) {
        latest = { created_at: r.created_at, verdict_reasoning: reasoning };
      }
    }
    return latest?.verdict_reasoning ?? null;
  } catch {
    return null;
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
 * Triage-reasoning backfill: when the resolved record's own
 * `triage_reasoning` field is empty, pull it from the `triage_run` store
 * via `/v1/triage/{symbol}`. Older D1 records (published before the field
 * existed) serve it as `null` even though the triage prose lives in
 * `triage_run` and renders in the catalog drawer — so the gene-page
 * triage drawer would otherwise self-hide. Sourcing from the same place
 * keeps both surfaces in sync without re-publishing the record.
 */
export async function loadSurfaceomeRecord(
  symbol: string,
): Promise<SurfaceomeRecord | null> {
  const base = (process.env.SURFACEOME_API_BASE ?? DEFAULT_API_BASE).trim();
  if (base === "local" || !base) {
    return null;
  }
  const record = await _fetchRecordFromWorker(symbol, base);
  if (record && !record.triage_reasoning?.trim()) {
    const reasoning = await _fetchTriageReasoningFromWorker(symbol, base);
    if (reasoning) return { ...record, triage_reasoning: reasoning };
  }
  return record;
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
