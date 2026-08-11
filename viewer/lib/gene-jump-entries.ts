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
