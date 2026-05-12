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
const CATALOG_PATH = path.join(process.cwd(), "public", "data", "catalog.json");

/**
 * One row of the genome-wide catalog the index table renders. Generated
 * by `scripts/build_viewer_catalog.py` in the upstream repo by joining
 * the candidate-universe TSV with `data/triage/` and the deep-dive
 * record set. Catalog is the deploy artifact; the script is the source
 * of truth.
 */
export interface CatalogRow {
  symbol: string;
  uniprot: string;
  n_sources: number;
  db: {
    uniprot: number;
    go: number;
    surfy: number;
    cspa: number;
    hpa: number;
    deeptmhmm: number;
    compartments: number;
  };
  triage: { verdict: string; reason: string | null } | null;
  deep_dive: boolean;
}

export interface Catalog {
  generated_at: string;
  n_rows: number;
  n_with_triage: number;
  n_with_deep_dive: number;
  rows: CatalogRow[];
}

export function loadCatalog(): Catalog {
  const raw = readFileSync(CATALOG_PATH, "utf-8");
  return JSON.parse(raw) as Catalog;
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

const ENUM_MAP: Record<string, string> = {
  tcr_mimic: "TCR-mimic mAb",
  tcr_t: "TCR-T",
  bispecific: "Bispecific (ImmTAC-style)",
  not_recommended: "Not recommended",
  edge_case: "Edge case",
  validated: "Validated",
  preclinical: "Preclinical",
  discovery: "Discovery",
  pan_tumor: "Pan-tumor",
  not_pm_associated: "Not PM-associated",
  mhc_presented_peptide: "MHC-presented peptide",
  absent: "Absent",
  present: "Present",
  rare_surface: "Rare surface",
  conditional_surface: "Conditional surface",
  constitutive_surface: "Constitutive surface",
  unknown: "Unknown",
  high: "High",
  medium: "Medium",
  low: "Low",
  blocking: "Blocking",
  non_internalizing: "Non-internalizing",
  outer_leaflet_peripheral: "Outer-leaflet peripheral",
  type_i: "Type I",
  type_ii: "Type II",
  type_iii: "Type III",
  multi_pass: "Multi-pass",
  gpi: "GPI-anchored",
  peripheral: "Peripheral",
  lipidated: "Lipidated",
  exposed_ecd: "Exposed ECD",
  cell_state_stress: "Cell-state stress",
  oncogenic_state: "Oncogenic state",
  immunogenic_cell_death: "Immunogenic cell death",
  likely_accessible: "Likely accessible",
  possibly_accessible: "Possibly accessible",
  supports_surface: "Supports",
  refutes_surface: "Refutes",
  ambiguous: "Ambiguous",
  strong: "Strong",
  moderate: "Moderate",
  weak: "Weak",
  flow_cytometry: "Flow cytometry",
  surface_biotinylation: "Surface biotinylation",
  mass_spec_surfaceome: "Mass-spec surfaceome",
  immunofluorescence_intact_cells: "IF (intact cells)",
  immunohistochemistry: "IHC",
  crystal_structure_with_ecd: "Crystal structure (ECD)",
  antibody_on_live_cells: "Ab on live cells",
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
