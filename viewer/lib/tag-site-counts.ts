// viewer/lib/tag-site-counts.ts
/*
 * Per-gene tag-site category counts for the catalog filters. Parsed shape of
 * public/data/tag-site-counts.json (built by scripts/build-tag-site-counts.mjs
 * from the committed public/tag-sites/{SYMBOL}.json files).
 *
 * MUST stay free of node:fs — value-imported by the client CatalogTable. The
 * build-time loader (lib/surfaceome.ts) reads the JSON and overlays the counts
 * onto each catalog row keyed by symbol (like the fg-library overlay).
 */

export interface TagSiteCounts {
  /** Deterministic extracellular N-terminal tag sites. */
  nterm_ec: number;
  /** Deterministic extracellular C-terminal tag sites. */
  cterm_ec: number;
  /** Deterministic internal surface-loop sites. */
  internal: number;
  /** Deterministic disordered-loop sites. */
  disorder: number;
  /** Surface-accessible literature-validated sites. */
  lit_ec: number;
}

export type TagSiteCountsMap = Record<string, TagSiteCounts>;

export const EMPTY_TAG_SITE_COUNTS: TagSiteCounts = {
  nterm_ec: 0,
  cterm_ec: 0,
  internal: 0,
  disorder: 0,
  lit_ec: 0,
};

/** Narrow an unknown payload (the parsed JSON) to a TagSiteCountsMap. Skips
 *  malformed entries; returns {} on a non-object so the overlay is a no-op. */
export function parseTagSiteCounts(raw: unknown): TagSiteCountsMap {
  if (!raw || typeof raw !== "object") return {};
  const out: TagSiteCountsMap = {};
  for (const [sym, v] of Object.entries(raw as Record<string, unknown>)) {
    if (!v || typeof v !== "object") continue;
    const o = v as Record<string, unknown>;
    const num = (k: string) => (typeof o[k] === "number" ? (o[k] as number) : 0);
    out[sym] = {
      nterm_ec: num("nterm_ec"),
      cterm_ec: num("cterm_ec"),
      internal: num("internal"),
      disorder: num("disorder"),
      lit_ec: num("lit_ec"),
    };
  }
  return out;
}
