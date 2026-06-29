/**
 * Static list of gene symbols that are queued for a deep-dive run
 * but haven't yet been processed by the agent. Used by the viewer to
 * mark them visually (orange left-edge in BenchmarkTable, "queued"
 * pill on CatalogTable) so we can see at a glance what's pending
 * without paying the $/gene Sonnet cost yet.
 *
 * To run a queued gene's deep dive::
 *
 *     uv run accessible-surfaceome agents annotate IGF2R
 *     uv run python scripts/upload/sync_public_d1.py --only surface_annotation
 *
 * Then remove the gene from QUEUED_DEEP_DIVES below (or leave it —
 * the orange marker only fires when the gene is in this list AND has
 * no `surface_annotation` row yet; once a record lands the catalog's
 * deep_dive flag takes over).
 */

export const QUEUED_DEEP_DIVES: ReadonlySet<string> = new Set([
  "IGF2R",   // cation-independent mannose-6-phosphate receptor / CD222
  "SCARB2",  // scavenger receptor class B member 2 / LAMP2-family
  "LY6G6D",  // lymphocyte antigen 6 family member G6D
]);

/** True iff the symbol is queued and doesn't yet have a deep-dive record. */
export function isQueuedDeepDive(
  symbol: string,
  hasExistingRecord: boolean,
): boolean {
  return QUEUED_DEEP_DIVES.has(symbol) && !hasExistingRecord;
}
