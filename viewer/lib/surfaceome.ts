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
  source: "api" | "snapshot";
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
 * Build-time catalog fetch. Tries the public Worker first; falls back
 * to the committed snapshot so an offline build (or a build before the
 * Worker is deployed) still produces a working page.
 *
 * The base URL is overridable via `SURFACEOME_API_BASE` for staging
 * environments. Set `SURFACEOME_API_BASE=local` to skip the fetch
 * entirely and read straight from the snapshot — useful in CI where
 * outbound HTTP is sandboxed.
 */
export async function loadCatalog(): Promise<Catalog> {
  const base = (process.env.SURFACEOME_API_BASE ?? DEFAULT_API_BASE).trim();
  if (base && base !== "local") {
    try {
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
      if (!res.ok) throw new Error(`status ${res.status}`);
      const payload = (await res.json()) as Omit<Catalog, "source">;
      // Treat an empty payload (Worker reachable but no universe loaded
      // yet) as a soft miss — fall through to the snapshot so the page
      // isn't blank during initial bring-up.
      if (!payload.rows || payload.rows.length === 0) {
        throw new Error("empty catalog payload");
      }
      return { source: "api", ...payload };
    } catch (err) {
      console.warn(
        `[surfaceome] /v1/catalog fetch failed (${(err as Error).message}); ` +
          `falling back to public/data/catalog.json snapshot`,
      );
    }
  }

  // Snapshot fallback.
  const raw = readFileSync(CATALOG_PATH, "utf-8");
  const snap = JSON.parse(raw) as Omit<Catalog, "source">;
  return { source: "snapshot", ...snap };
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
