// Build "link out to the actual antibody" URLs from an AntibodyRef.
//
// Two tiers, best-first:
//   1. RRID → the Antibody Registry resolver. An RRID (e.g. "AB_2533976")
//      uniquely identifies a reagent, so this lands on the exact antibody.
//   2. No RRID → a Google search seeded with the gene symbol + whatever
//      reagent keywords we have (clone / vendor / catalog / name). Not a
//      single-record link, but it puts the reader one click from the
//      vendor page / citations instead of re-typing the clone into search.
//
// Kept as a standalone lib (no React) so it's unit-testable and reusable
// by any card that renders antibody reagents.

export interface AntibodyKeywords {
  name: string;
  clone?: string | null;
  vendor?: string | null;
  catalog?: string | null;
  rrid?: string | null;
}

export type AntibodyLinkKind = "rrid" | "search";

export interface AntibodyLink {
  href: string;
  label: string;
  kind: AntibodyLinkKind;
}

/** Normalize an RRID to its bare AB_ identifier (drop a leading "RRID:"). */
function normalizeRrid(rrid: string): string {
  return rrid.replace(/^\s*RRID:\s*/i, "").trim();
}

/** Antibody Registry deep link for an RRID — resolves to the exact reagent. */
export function antibodyRegistryUrl(rrid: string): string {
  return `https://www.antibodyregistry.org/search?q=${encodeURIComponent(
    normalizeRrid(rrid),
  )}`;
}

/** Google search seeded with the gene symbol + reagent keywords. The gene
 *  symbol anchors the search on the right target; the reagent fields
 *  (clone / vendor / catalog) disambiguate the specific antibody. */
export function antibodySearchUrl(
  geneSymbol: string,
  ab: AntibodyKeywords,
): string {
  const terms = [
    geneSymbol,
    "antibody",
    ab.clone,
    ab.vendor,
    ab.catalog,
    // Fall back to the agent's free-text name only when no structured
    // reagent keyword is available, so the query stays specific.
    ab.clone || ab.vendor || ab.catalog ? null : ab.name,
  ].filter((t): t is string => Boolean(t && t.trim()));
  return `https://www.google.com/search?q=${encodeURIComponent(terms.join(" "))}`;
}

/** Pick the best available link for an antibody: RRID resolver if we have
 *  an RRID, else a keyword Google search. Returns null only when there's
 *  nothing to search on (no gene symbol AND no reagent keywords). */
export function antibodyLink(
  geneSymbol: string,
  ab: AntibodyKeywords,
): AntibodyLink | null {
  if (ab.rrid && normalizeRrid(ab.rrid)) {
    return {
      href: antibodyRegistryUrl(ab.rrid),
      label: "Antibody Registry",
      kind: "rrid",
    };
  }
  const hasSearchTerms =
    Boolean(geneSymbol) ||
    Boolean(ab.clone || ab.vendor || ab.catalog || ab.name);
  if (!hasSearchTerms) return null;
  return {
    href: antibodySearchUrl(geneSymbol, ab),
    label: "Search ↗",
    kind: "search",
  };
}
