/*
 * Surfaceome data loader + label helpers.
 * ------------------------------------------------------------
 * Read per-gene `SurfaceomeRecord` JSONs at build time from
 * `site/public/data/surfaceome/*.json`. Reading from /public lets
 * the same files serve as the static-fetch endpoint at runtime
 * (`/data/surfaceome/{SYMBOL}.json`) while also being readable
 * via `fs` during `generateStaticParams` and server-rendered
 * page bodies.
 *
 * When the public Cloudflare Worker at
 * `api.deliverome.org/surfaceome/v1/genes/{SYMBOL}` is live, the
 * loader can be swapped to `fetch()` against that URL — same
 * `SurfaceomeRecord` shape, just a different source.
 */

import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import type { BenchmarkMatrix, SurfaceomeRecord } from "./surfaceome-types";

const DATA_DIR = path.join(process.cwd(), "public", "data", "surfaceome");

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
 * The viewer's local JSON set is the source of truth for which
 * rows have a viewable deep-dive page. The public catalog's
 * ``deep_dive`` flag is currently out of sync with the v1.0.0
 * cut-over: the production D1 mirror still flags v0.x records
 * (HSPA1A, TGOLN2) that no longer have local JSONs, and doesn't
 * yet flag the v1.0.0 records that this PR introduces (e.g.
 * GPR75). Override the flag to match the local set so links resolve
 * and the "Deep-dive" filter chip stays honest.
 */
function syncDeepDiveToLocal(
  rows: CatalogRow[],
  localSymbols: Set<string>,
): CatalogRow[] {
  return rows.map((r) => {
    const hasLocal = localSymbols.has(r.symbol);
    if (hasLocal === r.deep_dive) return r;
    return { ...r, deep_dive: hasLocal };
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
  return {
    symbol: r.symbol as string,
    uniprot: (r.uniprot as string | undefined) ?? "",
    name: r.name as string | undefined,
    synonyms: r.synonyms as string[] | undefined,
    n_sources: r.n_sources as number,
    db,
    triage_by_model,
    deep_dive: Boolean(r.deep_dive),
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
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  const res = await fetch(`${base}/v1/catalog`, {
    // `force-cache` makes the response part of the static build
    // artifact under `output: "export"`. A re-deploy of the Worker
    // surfaces in the viewer on the next `npm run build` — exactly
    // the SSG lifecycle we want for a research catalogue (no
    // per-page-load D1 hits in production).
    cache: "force-cache",
    signal: controller.signal,
  }).finally(() => clearTimeout(timer));
  if (!res.ok) {
    throw new Error(`${base}/v1/catalog returned ${res.status}`);
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
  const localSymbols = new Set(listSurfaceomeGenes());
  // Sonnet 4.6 (slot 1 in triage_by_model) is the catalog's headline
  // verdict — every page surface reads from that slot. Rows where it
  // didn't run on file are the universe's resolver-failure outliers
  // (e.g. CTXN1 as of 2026-05; SEA was healed by PR #30). Drop them
  // from the catalog so the visible universe matches `n_with_triage`
  // and the verdict filter doesn't need a "no call" bucket.
  const inflated = payload.rows
    .map(inflateCatalogRow)
    .filter((r) => Boolean(r.triage_by_model[1]));
  const rows = syncDeepDiveToLocal(enrichRowsWithNames(inflated, names), localSymbols);
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

export function listSurfaceomeGenes(): string[] {
  let entries: string[];
  try {
    entries = readdirSync(DATA_DIR);
  } catch {
    return [];
  }
  return entries
    .filter((name) => name.endsWith(".json"))
    .map((name) => name.replace(/\.json$/, ""))
    .sort();
}

export function loadSurfaceomeRecord(symbol: string): SurfaceomeRecord | null {
  const file = path.join(DATA_DIR, `${symbol}.json`);
  try {
    const raw = readFileSync(file, "utf-8");
    return JSON.parse(raw) as SurfaceomeRecord;
  } catch {
    return null;
  }
}

export function loadAllSurfaceomeRecords(): SurfaceomeRecord[] {
  return listSurfaceomeGenes()
    .map((sym) => loadSurfaceomeRecord(sym))
    .filter((r): r is SurfaceomeRecord => r != null);
}

// Pretty labels for v1.0.0 enums. Keys must stay in sync with the
// string-literal unions in `surfaceome-types.ts`. Anything missing
// here falls through to `titleCase` (snake_case → Title Case), which
// is correct for most plain values.
const ENUM_MAP: Record<string, string> = {
  // Triage / accessibility
  likely_accessible: "Likely accessible",
  possibly_accessible: "Possibly accessible",
  unlikely: "Unlikely",
  unknown: "Unknown",
  high: "High",
  moderate: "Moderate",
  low: "Low",
  uncertain: "Uncertain",
  unclear: "Unclear",
  none: "None",
  negligible: "Negligible",

  // Subcategory
  single_pass_T1: "Single-pass type I",
  single_pass_T2: "Single-pass type II",
  multi_pass: "Multi-pass",
  GPCR: "GPCR",
  GPI_anchored: "GPI-anchored",
  tetraspanin: "Tetraspanin",
  ion_channel: "Ion channel",
  transporter: "Transporter",
  other: "Other",

  // Evidence grade / strength / density
  direct_multi_method: "Direct, multi-method",
  direct_single_method: "Direct, single method",
  supportive_but_indirect: "Supportive but indirect",
  conflicting: "Conflicting",
  weak: "Weak",
  strong: "Strong",
  inferred: "Inferred",

  // ECD class
  large: "Large",
  small: "Small",
  minimal: "Minimal",

  // Expression
  absent: "Absent",
  pan_tissue: "Pan-tissue",
  broad: "Broad",
  restricted: "Restricted",
  rare: "Rare",
  surface_dominant: "Surface-dominant",
  mixed: "Mixed",
  mostly_intracellular: "Mostly intracellular",

  // Topology
  extracellular: "Extracellular",
  cytoplasmic: "Cytoplasmic",
  one2one: "One-to-one",
  one2many: "One-to-many",
  many2many: "Many-to-many",

  // Methods
  flow_cytometry: "Flow cytometry",
  immunofluorescence: "Immunofluorescence",
  immunohistochemistry: "IHC",
  mass_spec: "Mass spec",
  biotinylation: "Biotinylation",
  glycoproteomics: "Glycoproteomics",
  proximity_labeling: "Proximity labeling",
  fractionation: "Fractionation",
  live_cell_flow: "Live-cell flow",
  fixed_cell_flow: "Fixed-cell flow",
  nonpermeabilized_IF: "Non-permeabilized IF",
  permeabilized_IF: "Permeabilized IF",
  IHC_membranous: "IHC (membranous)",
  surface_biotinylation: "Surface biotinylation",
  cell_surface_capture: "Cell-surface capture",
  N_glycoproteomics: "N-glycoproteomics",
  plasma_membrane_fractionation: "PM fractionation",
  whole_cell_proteomics: "Whole-cell proteomics",
  live_cell: "Live cell",
  nonpermeabilized: "Non-permeabilized",
  permeabilized: "Permeabilized",
  fixed_unknown: "Fixed (unknown)",

  // Antibody fields
  monoclonal: "Monoclonal",
  polyclonal: "Polyclonal",
  recombinant: "Recombinant",
  conformational: "Conformational",
  isoform_specific: "Isoform-specific",
  intracellular: "Intracellular",
  genetic_KO: "Genetic KO",
  siRNA_knockdown: "siRNA knockdown",
  CRISPR_KO: "CRISPR KO",
  orthogonal_method: "Orthogonal method",
  ip_ms_pulldown: "IP-MS pulldown",
  isoform_specific_KO: "Isoform-specific KO",
  overexpression_reference: "Overexpression reference",
  vendor_claim_only: "Vendor claim only",
  endogenous: "Endogenous",
  overexpression: "Overexpression",
  knock_in_tag: "Knock-in tag",

  // Accessibility relevance + claim type
  direct_surface_accessibility: "Direct surface accessibility",
  supports_surface_localization: "Supports surface localization",
  supports_membrane_association: "Supports membrane association",
  expression_only: "Expression only",
  weak_or_ambiguous: "Weak or ambiguous",
  surface_accessible: "Surface-accessible",
  plasma_membrane_localized: "Plasma membrane",
  membrane_fraction_enriched: "Membrane-fraction enriched",
  cell_junction_localized: "Cell junction",
  apical_or_luminal: "Apical / luminal",
  secreted_or_shed: "Secreted / shed",
  intracellular_pool: "Intracellular pool",

  // Sample types
  primary_human_tissue: "Primary tissue",
  primary_human_cell: "Primary cell",
  patient_sample: "Patient sample",
  patient_derived_organoid: "Patient-derived organoid",
  iPSC_derived: "iPSC-derived",
  established_cell_line: "Cell line",
  xenograft: "Xenograft",
  ex_vivo: "Ex vivo",

  // Compartments
  plasma_membrane: "Plasma membrane",
  endosome: "Endosome",
  lysosome: "Lysosome",
  ER: "ER",
  Golgi: "Golgi",
  mitochondrion: "Mitochondrion",
  nucleus: "Nucleus",
  cytosol: "Cytosol",
  secreted: "Secreted",
  secretory_vesicle: "Secretory vesicle",

  // Anatomical orientation
  blood_interstitial_facing: "Blood / interstitial-facing",
  luminal_facing: "Luminal-facing",
  apical: "Apical",
  basolateral: "Basolateral",
  lateral: "Lateral",
  junction_restricted: "Junction-restricted",
  ciliary: "Ciliary",
  synaptic: "Synaptic",
  matrix_facing: "Matrix-facing",
  favorable: "Favorable",
  context_dependent: "Context-dependent",

  // Modulation
  cell_state_induced: "Cell-state induced",
  tissue_restricted_surface: "Tissue-restricted surface",
  lysosomal_exocytosis: "Lysosomal exocytosis",
  dual_localization: "Dual localization",
  stable_surface_attachment: "Stable surface attachment",
  activation_induced: "Activation-induced",
  stress_induced: "Stress-induced",
  disease_state_induced: "Disease-state induced",
  polarization_dependent: "Polarization-dependent",
  post_translational_dependent: "Post-translational dependent",
  developmental_stage: "Developmental stage",
  ER_stress: "ER stress",
  heat_shock: "Heat shock",
  oxidative_stress: "Oxidative stress",
  DNA_damage_response: "DNA damage response",
  apoptosis: "Apoptosis",
  necroptosis: "Necroptosis",
  oncogenic_transformation: "Oncogenic transformation",
  infection_viral: "Viral infection",
  infection_bacterial: "Bacterial infection",
  immune_activation: "Immune activation",
  antigen_stimulation: "Antigen stimulation",
  cytokine_stimulation: "Cytokine stimulation",
  hypoxia: "Hypoxia",
  nutrient_deprivation: "Nutrient deprivation",
  hyperthermia: "Hyperthermia",
  mechanical_stress: "Mechanical stress",

  // Restricted lineage
  germline_reproductive: "Germline / reproductive",
  embryonic_developmental: "Embryonic / developmental",
  hematopoietic: "Hematopoietic",
  neural: "Neural",
  epithelial: "Epithelial",
  endothelial: "Endothelial",
  muscle: "Muscle",
  endocrine: "Endocrine",
  specialized_somatic_other: "Specialized somatic (other)",

  // Restricted subdomain / risks
  junctional: "Junctional",
  raft: "Lipid raft",

  // Co-receptor
  required: "Required",
  modulatory: "Modulatory",
  co_expression_only: "Co-expression only",
  trafficking: "Trafficking",
  knockout: "Knockout",

  // Headline-risk shorthand
  shed_form: "Shed form",
  secreted_form: "Secreted form",
  co_receptor: "Co-receptor",
  paralog_cross_reactivity: "Paralog cross-reactivity",
  ecd_too_small: "ECD too small",
  epitope_masked: "Epitope masked",
  isoform_decoy: "Isoform decoy",
  restricted_subdomain: "Restricted subdomain",
  low_endogenous_expression: "Low endogenous expression",
  antibody_validation_weak: "Weak Ab validation",
  ligand_unknown: "Ligand unknown",

  // Therapeutic stage
  approved_drug: "Approved drug",
  in_clinical_trials: "In clinical trials",
  preclinical_in_vivo: "Preclinical (in vivo)",
  none_documented: "None documented",

  // Contradiction types
  alternative_localization: "Alternative localization",
  secreted_only: "Secreted only",
  cell_line_specific_absence: "Cell-line-specific absence",
  antibody_conflict: "Antibody conflict",
  proteomics_conflict: "Proteomics conflict",
  isoform_conflict: "Isoform conflict",

  // Knowledge gaps
  no_literature: "No literature",
  outside_scope: "Outside scope",

  // Evidence tier
  primary: "Primary",
  secondary: "Secondary",
  tertiary: "Tertiary",

  // Secreted-form source
  alternative_splicing: "Alternative splicing",
  proteolytic: "Proteolytic",
  both: "Both",

  // Epitope masking mechanism
  glycan: "Glycan",
  partner: "Partner",
  cleaved: "Cleaved",
};

export function titleCase(s: string | null | undefined): string {
  return String(s ?? "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function prettyEnum(s: string | null | undefined): string {
  if (!s) return "—";
  return ENUM_MAP[s] ?? titleCase(s);
}

export function tissueLabel(t: string): string {
  return titleCase(t);
}
