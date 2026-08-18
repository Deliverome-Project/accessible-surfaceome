/*
 * Deliverome FG surface-protein library membership — client-safe overlay.
 * ----------------------------------------------------------------------
 * The parsed shape of `public/data/fg-library.json` (generated from the
 * deliverome-analysis library, s1e3) plus the tiny helper set both the
 * server build and the client components read through.
 *
 * IMPORTANT: this module MUST stay free of `node:fs` (and any other
 * server-only import). It is value-imported by client components
 * (`app/gene/page.tsx`, `GeneDetail`, `GeneHeader`, `IsoformsCard`) AND by
 * the build-time loader (`lib/surfaceome.ts`, which itself imports
 * `node:fs`). The client fetches the JSON at runtime and hands it to
 * `parseFgLibrary`; the server reads the same file via fs and hands the
 * parsed object here — same helpers, one source of truth. The 2,346-gene
 * data itself is never inlined into this module; it lives only in the JSON.
 */

/** Library tier a gene lands in. Mirrors `library_membership.tsv` (final_library.py):
 *  T1/T2/T3 graded confidence, LL low-lit/UniProt, SV screen-validated (Willow
 *  GPCR screen), OE overexpression-rescue. */
export type FgTier = "T1" | "T2" | "T3" | "LL" | "SV" | "OE";

/** A surface-competent ortholog of a library gene. `species` is the source
 *  key from the analysis ("mouse" | "cyno"); `symbol` is that species'
 *  gene symbol (e.g. mouse "Abcb11", cyno "ABCB11"). */
export interface FgOrtholog {
  symbol: string;
  species: string;
}

/** Per-gene membership entry: tier + the precomputed surface-competent
 *  isoform accessions and orthologs from the analysis. */
export interface FgGeneEntry {
  tier: FgTier;
  /** UniProt isoform accessions (e.g. "P00533-2") flagged surface-competent. */
  surface_isoform_ids: string[];
  surface_orthologs: FgOrtholog[];
}

/** Parsed `fg-library.json`. A gene is "in the FG library" iff its symbol
 *  is a key in `genes`. */
export interface FgLibraryData {
  genes: Record<string, FgGeneEntry>;
}

const KNOWN_TIERS: ReadonlySet<string> = new Set([
  "T1",
  "T2",
  "T3",
  "LL",
  "SV",
  "OE",
]);

function asStringArray(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.filter((x): x is string => typeof x === "string");
}

function parseOrthologs(v: unknown): FgOrtholog[] {
  if (!Array.isArray(v)) return [];
  const out: FgOrtholog[] = [];
  for (const item of v) {
    if (!item || typeof item !== "object") continue;
    const o = item as Record<string, unknown>;
    if (typeof o.symbol === "string" && typeof o.species === "string") {
      out.push({ symbol: o.symbol, species: o.species });
    }
  }
  return out;
}

/**
 * Parse/normalize an unknown JSON blob (fetched over HTTP, or read from
 * disk via fs) into the {@link FgLibraryData} shape. Deliberately tolerant:
 * anything malformed degrades to `{ genes: {} }` (→ nothing is "in the
 * library"), the same graceful-miss contract the gene page's other overlays
 * use. `null`/`undefined` in → empty out.
 */
export function parseFgLibrary(raw: unknown): FgLibraryData {
  const out: FgLibraryData = { genes: {} };
  if (!raw || typeof raw !== "object") return out;
  const root = raw as Record<string, unknown>;
  const genes = root.genes;
  if (!genes || typeof genes !== "object") return out;
  for (const [symbol, entryRaw] of Object.entries(
    genes as Record<string, unknown>,
  )) {
    if (!entryRaw || typeof entryRaw !== "object") continue;
    const e = entryRaw as Record<string, unknown>;
    const tier =
      typeof e.tier === "string" && KNOWN_TIERS.has(e.tier)
        ? (e.tier as FgTier)
        : "T1";
    out.genes[symbol] = {
      tier,
      surface_isoform_ids: asStringArray(e.surface_isoform_ids),
      surface_orthologs: parseOrthologs(e.surface_orthologs),
    };
  }
  return out;
}

/** True when `symbol` is a member of the FG library (a key in `genes`). */
export function inFgLibrary(
  data: FgLibraryData | null | undefined,
  symbol: string,
): boolean {
  if (!data) return false;
  return Object.prototype.hasOwnProperty.call(data.genes, symbol);
}

/** The set of every library-member symbol — used to filter an alphabetical
 *  gene list down to library members (the catalog overlay + the deep-dive
 *  prev/next navigation). */
export function fgLibrarySymbolSet(
  data: FgLibraryData | null | undefined,
): Set<string> {
  return new Set(data ? Object.keys(data.genes) : []);
}

/** The precomputed surface-competent isoform accessions for `symbol`
 *  (empty set when the gene isn't in the library or has none). Match
 *  against `IsoformTopology.isoform_id`. */
export function surfaceIsoformIds(
  data: FgLibraryData | null | undefined,
  symbol: string,
): Set<string> {
  const entry = data?.genes[symbol];
  return new Set(entry?.surface_isoform_ids ?? []);
}

/** Stable key for an ortholog: `${SYMBOL}|${species}`, both case-folded so
 *  the analysis JSON's casing (mouse "Abcb11", species "cyno") matches the
 *  record's ortholog symbol + the display species handed to `orthologRow`
 *  ("Mouse"/"Cyno"). */
export function orthologKey(symbol: string, species: string): string {
  return `${symbol.toUpperCase()}|${species.toLowerCase()}`;
}

/** The set of surface-competent ortholog keys for `symbol` (see
 *  {@link orthologKey}). Empty when the gene isn't in the library. */
export function surfaceOrthologKeys(
  data: FgLibraryData | null | undefined,
  symbol: string,
): Set<string> {
  const entry = data?.genes[symbol];
  const out = new Set<string>();
  for (const o of entry?.surface_orthologs ?? []) {
    out.add(orthologKey(o.symbol, o.species));
  }
  return out;
}
