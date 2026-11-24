// Type-only import → erased at compile, so importing this helper never pulls
// in lib/surfaceome.ts (which imports node:fs) — safe for the client shell.
import type { GeneEntry } from "./surfaceome";

/** The build-baked `{SYMBOL: synonyms[]}` overlay (see
 *  `scripts/build-data-snapshot.mjs` → `public/data/gene-synonyms.json`). */
export type SynonymOverlay = Record<string, string[]>;

/**
 * Build the GeneJump typeahead set from the `/v1/genes` index, overlaying
 * per-gene synonyms so alias queries match (e.g. "Nav1.7" → SCN9A) — the
 * SAME behaviour the homepage catalog search gets from `loadGeneNamesMap`.
 *
 * Why the overlay exists: the gene page is a client shell
 * (`app/gene/page.tsx`), so it can't read the NCBI gene-name TSV that
 * `loadGeneNamesMap` uses (node:fs is server-only), and the `/v1/genes`
 * index carries no synonyms. The build bakes a slim symbol→synonyms map
 * from that same TSV to `public/data/gene-synonyms.json`; the shell fetches
 * it and passes it here. A null/absent map degrades to symbol-only matching
 * (the pre-fix behaviour) rather than breaking the dropdown.
 *
 * `stale` is always false: the freshness dot is off on the gene page.
 */
export function buildGeneJumpEntries(
  genesJson: unknown,
  synonyms?: SynonymOverlay | null,
): GeneEntry[] {
  const data = genesJson as { genes?: Array<{ gene_symbol?: string }> } | null;
  const out: GeneEntry[] = [];
  for (const g of data?.genes ?? []) {
    if (!g.gene_symbol) continue;
    const syn = synonyms?.[g.gene_symbol];
    out.push(
      syn && syn.length > 0
        ? { symbol: g.gene_symbol, stale: false, synonyms: syn }
        : { symbol: g.gene_symbol, stale: false },
    );
  }
  return out;
}

/** Rank a gene + its aliases against an uppercased query (0 = best, 6 = no match).
 *  Shared by `GeneJump` on the main viewer and the L1 review search box so alias
 *  queries like "CD20" → MS4A1 or "Nav1.7" → SCN9A behave identically. */
export function geneSynonymRank(
  symbol: string,
  synonyms: readonly string[] | undefined,
  qUpper: string,
): number {
  const sym = symbol.toUpperCase();
  const aliases = (synonyms ?? []).map((s) => s.toUpperCase());
  if (sym === qUpper) return 0;
  if (aliases.some((a) => a === qUpper)) return 1;
  if (sym.startsWith(qUpper)) return 2;
  if (aliases.some((a) => a.startsWith(qUpper))) return 3;
  if (sym.includes(qUpper)) return 4;
  if (aliases.some((a) => a.includes(qUpper))) return 5;
  return 6;
}

/** Return the best-matching synonym for `qUpper` (exact > prefix > substring), or null. */
export function matchingSynonym(
  synonyms: readonly string[] | undefined,
  qUpper: string,
): string | null {
  if (!synonyms?.length || !qUpper) return null;
  return (
    synonyms.find((s) => s.toUpperCase() === qUpper) ??
    synonyms.find((s) => s.toUpperCase().startsWith(qUpper)) ??
    synonyms.find((s) => s.toUpperCase().includes(qUpper)) ??
    null
  );
}

let cachedSynonyms: Promise<SynonymOverlay> | null = null;

/** Fetch the build-baked `/data/gene-synonyms.json` overlay once per session. */
export function fetchGeneSynonyms(): Promise<SynonymOverlay> {
  if (!cachedSynonyms) {
    cachedSynonyms = fetch("/data/gene-synonyms.json")
      .then((res) => (res.ok ? (res.json() as Promise<SynonymOverlay>) : {}))
      .catch(() => ({}));
  }
  return cachedSynonyms;
}
