/**
 * Client-side matching for the /compare upload tool.
 *
 * Parses a pasted / uploaded list of gene symbols or UniProt accessions
 * and resolves each token against the baked catalog rows. Matching is
 * case-insensitive and tries, in order: exact HGNC symbol → UniProt
 * accession → synonym / previous symbol (from `CatalogRow.synonyms`,
 * which the build-time NCBI/HGNC merge populates). Nothing leaves the
 * browser — this is a pure in-memory join.
 */

import type { CatalogRow } from "./surfaceome";

export type MatchedBy =
  | "symbol"
  | "uniprot"
  | "synonym"
  | "ambiguous"
  | "none";

export interface ParsedToken {
  /** Original token as typed (trimmed, quote/prefix-stripped). */
  raw: string;
  /** Uppercased lookup key (also the dedupe key). */
  key: string;
}

export interface ParseResult {
  /** Deduped tokens, in first-seen order. */
  tokens: ParsedToken[];
  /** How many tokens were dropped as case-insensitive duplicates. */
  duplicateCount: number;
}

export interface ResolvedEntry {
  /** Original token as typed. */
  input: string;
  matchedBy: MatchedBy;
  /** The matched catalog row, or null for ambiguous / not-found. */
  row: CatalogRow | null;
}

export interface CompareIndex {
  bySymbol: Map<string, CatalogRow>;
  byUniprot: Map<string, CatalogRow>;
  bySynonym: Map<string, CatalogRow>;
  /** Synonym keys that map to >1 gene — not auto-resolved. */
  ambiguousSynonyms: Set<string>;
}

// UniProt accession shape (the 6- and 10-char forms from the UniProtKB
// regex). Only used to keep `isUniprotAccession` available to callers;
// `resolveToken` tries both maps regardless of shape, so a mis-shaped
// token still resolves.
const UNIPROT_RE =
  /^[OPQ][0-9][A-Z0-9]{3}[0-9]$|^[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}$/;

export function isUniprotAccession(token: string): boolean {
  return UNIPROT_RE.test(token.trim().toUpperCase());
}

/**
 * Split on whitespace / commas / semicolons / tabs, trim, strip
 * surrounding quotes and a leading `uniprot:` / `UniProtKB:` prefix,
 * drop empties, and dedupe case-insensitively (preserving the first
 * original spelling for display).
 */
export function parseInput(text: string): ParseResult {
  const seen = new Set<string>();
  const tokens: ParsedToken[] = [];
  let duplicateCount = 0;
  for (const piece of text.split(/[\s,;]+/)) {
    let raw = piece.trim();
    if (!raw) continue;
    raw = raw.replace(/^["']+/, "").replace(/["']+$/, "");
    raw = raw.replace(/^uniprotkb:/i, "").replace(/^uniprot:/i, "");
    raw = raw.trim();
    if (!raw) continue;
    const key = raw.toUpperCase();
    if (seen.has(key)) {
      duplicateCount += 1;
      continue;
    }
    seen.add(key);
    tokens.push({ raw, key });
  }
  return { tokens, duplicateCount };
}

/**
 * Build the lookup maps once from the catalog rows. A real symbol always
 * wins over a synonym key (the synonym pass skips keys already present in
 * `bySymbol`), and a synonym shared by two genes is recorded as ambiguous
 * rather than silently resolving to whichever row was seen last.
 */
export function buildIndex(rows: CatalogRow[]): CompareIndex {
  const bySymbol = new Map<string, CatalogRow>();
  const byUniprot = new Map<string, CatalogRow>();
  const bySynonym = new Map<string, CatalogRow>();
  const ambiguousSynonyms = new Set<string>();

  for (const r of rows) {
    if (r.symbol) bySymbol.set(r.symbol.toUpperCase(), r);
    if (r.uniprot) byUniprot.set(r.uniprot.toUpperCase(), r);
  }
  // Second pass so a synonym never shadows a canonical symbol.
  for (const r of rows) {
    for (const s of r.synonyms ?? []) {
      const key = s.trim().toUpperCase();
      if (!key || bySymbol.has(key)) continue;
      const existing = bySynonym.get(key);
      if (existing && existing !== r) {
        ambiguousSynonyms.add(key);
      } else if (!existing) {
        bySynonym.set(key, r);
      }
    }
  }
  return { bySymbol, byUniprot, bySynonym, ambiguousSynonyms };
}

/** Resolve one parsed token. Precedence: symbol → uniprot → synonym. */
export function resolveToken(
  token: ParsedToken,
  index: CompareIndex,
): ResolvedEntry {
  const { key, raw } = token;
  const sym = index.bySymbol.get(key);
  if (sym) return { input: raw, matchedBy: "symbol", row: sym };
  const up = index.byUniprot.get(key);
  if (up) return { input: raw, matchedBy: "uniprot", row: up };
  if (index.ambiguousSynonyms.has(key)) {
    return { input: raw, matchedBy: "ambiguous", row: null };
  }
  const syn = index.bySynonym.get(key);
  if (syn) return { input: raw, matchedBy: "synonym", row: syn };
  return { input: raw, matchedBy: "none", row: null };
}

/** Parse + resolve a whole pasted list against the catalog index. */
export function resolveList(
  text: string,
  index: CompareIndex,
): { entries: ResolvedEntry[]; duplicateCount: number } {
  const { tokens, duplicateCount } = parseInput(text);
  return { entries: tokens.map((t) => resolveToken(t, index)), duplicateCount };
}
