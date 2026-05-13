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
import type { SurfaceomeRecord } from "./surfaceome-types";

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

/**
 * One row of the genome-wide catalog the index table renders. Sourced
 * from the public Worker's `/v1/catalog` endpoint (which joins
 * `candidate_universe_public` + `triage_run_public` + `surface_annotation`
 * in the `surfaceome_public` D1 mirror). The committed
 * `public/data/catalog.json` is a snapshot fallback used when the API
 * is unreachable (offline dev, Worker not yet deployed, etc.).
 */
export interface CatalogRow {
  symbol: string;
  uniprot: string;
  /** Descriptive gene name from NCBI gene_info (e.g. ``transferrin``).
   *  Merged in by ``loadCatalog`` from
   *  ``public/data/gene_names.json``; empty / missing when the symbol
   *  isn't in the NCBI snapshot. */
  name?: string;
  /** Pipe-separated synonyms from NCBI gene_info (e.g.
   *  ``["HEL-S-71p", "PRO1557", ...]`` for TF). Same provenance as
   *  ``name``. */
  synonyms?: string[];
  n_sources: number;
  // Five gating DBs (uniprot, go, surfy, cspa, hpa). DeepTMHMM +
  // COMPARTMENTS are demoted to auxiliary signals upstream
  // (src/accessible_surfaceome/merge/__init__.py) and don't appear in
  // the public catalog table — the database row still carries them
  // for fidelity, but the Worker filters them out of /v1/catalog.
  db: {
    uniprot: number;
    go: number;
    surfy: number;
    cspa: number;
    hpa: number;
  };
  triage: { verdict: string; reason: string | null } | null;
  deep_dive: boolean;
}

export interface Catalog {
  /** Always ``"api"`` — the committed snapshot path was dropped when
   *  the public Worker stabilized. Kept for forward-compat / explicit
   *  semantics; the field tells consumers what built the catalog. */
  source: "api";
  generated_at?: string;
  universe_version?: string;
  bench_version?: string | null;
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
}

// Module-level memo. The TSV is ~3.5 MB / 19,325 rows; parsing it
// once per build (or once per request in dev) is fine, but
// `loadGeneName` is called for every gene-detail page (potentially
// thousands at SSG time), so we cache after the first parse.
let _geneNamesCache: Record<string, GeneNameEntry> | null = null;

function loadGeneNamesMap(): Record<string, GeneNameEntry> {
  if (_geneNamesCache) return _geneNamesCache;
  try {
    const raw = readFileSync(GENE_NAMES_TSV, "utf-8");
    const lines = raw.split(/\r?\n/);
    if (lines.length < 2) {
      _geneNamesCache = {};
      return _geneNamesCache;
    }
    const header = lines[0].split("\t");
    const symIdx = header.indexOf("gene_symbol");
    const nameIdx = header.indexOf("description");
    const synIdx = header.indexOf("synonyms");
    if (symIdx < 0 || nameIdx < 0 || synIdx < 0) {
      _geneNamesCache = {};
      return _geneNamesCache;
    }
    const out: Record<string, GeneNameEntry> = {};
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
    _geneNamesCache = out;
    return out;
  } catch {
    _geneNamesCache = {};
    return _geneNamesCache;
  }
}

function enrichRowsWithNames(
  rows: CatalogRow[],
  names: Record<string, GeneNameEntry>,
): CatalogRow[] {
  if (Object.keys(names).length === 0) return rows;
  return rows.map((r) => {
    const entry = names[r.symbol];
    if (!entry) return r;
    return { ...r, name: entry.name, synonyms: entry.synonyms };
  });
}

/**
 * The Worker (`row_schema: 2`) packs the 5 surface-DB flags into a
 * 5-bit integer to keep payloads compact:
 *   bit 0 = uniprot, 1 = go, 2 = surfy, 3 = cspa, 4 = hpa.
 * The committed snapshot still uses the object form. Decode the
 * bitmask into the object shape so the CatalogTable can index by
 * key. No-op when `row.db` is already an object (snapshot fallback).
 */
function decodeDbBitmask(rows: CatalogRow[]): CatalogRow[] {
  return rows.map((r) => {
    const dbValue = r.db as unknown;
    if (typeof dbValue !== "number") return r;
    const bits = dbValue;
    return {
      ...r,
      db: {
        uniprot: bits & 1 ? 1 : 0,
        go: bits & 2 ? 1 : 0,
        surfy: bits & 4 ? 1 : 0,
        cspa: bits & 8 ? 1 : 0,
        hpa: bits & 16 ? 1 : 0,
      },
    };
  });
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

export async function loadCatalog(): Promise<Catalog> {
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
  const payload = (await res.json()) as Omit<Catalog, "source">;
  if (!payload.rows || payload.rows.length === 0) {
    throw new Error(
      `${base}/v1/catalog returned an empty catalog — the Worker is ` +
        "reachable but no candidate-universe data has been loaded into D1 yet.",
    );
  }
  return {
    source: "api",
    ...payload,
    rows: enrichRowsWithNames(decodeDbBitmask(payload.rows), names),
  };
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
