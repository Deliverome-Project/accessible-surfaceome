import type { PaperMetadata } from "./surfaceome-types";

/** "Bock et al. · Sci Rep 2018" — whichever parts NCBI actually had.
 *
 *  Returns null when none of them are known, so a caller can fall back to
 *  the bare accession rather than render an empty line.
 *
 *  Shared by the EvidenceDrawer and the EvidenceLedgerCard: the same paper
 *  appears in both, one directly above the other in the reading flow, so a
 *  second copy of this formatting would be visible the moment the two
 *  drifted.
 */
export function bylineOf(meta: PaperMetadata): string | null {
  const journalYear = [meta.journal, meta.year].filter(Boolean).join(" ");
  const parts = [meta.authors_short, journalYear].filter(Boolean);
  return parts.length ? parts.join(" · ") : null;
}
