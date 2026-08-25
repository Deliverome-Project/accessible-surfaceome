/** Internalization sequence-prior grade — the opus-5 model prior's read of a
 *  protein's intrinsic / basal endocytic propensity from amino-acid sequence +
 *  extracellular/cytoplasmic (E/C) topology alone (5-point SeqGrade + `unknown`).
 *  Ordered high → low.
 *
 *  This module is deliberately **client-safe** (no server-only imports). It
 *  exists separately from `surfaceome.ts` so a client component — e.g. the
 *  catalog table — can value-import `INTERNALIZATION_GRADES` without dragging
 *  `surfaceome.ts`'s `node:fs` snapshot code into the browser bundle. */
export type InternalizationGrade =
  | "very_high"
  | "high"
  | "moderate"
  | "low"
  | "very_low"
  | "unknown";

/** Canonical high → low order, used for filter-chip ordering and sort ranks. */
export const INTERNALIZATION_GRADES: readonly InternalizationGrade[] = [
  "very_high",
  "high",
  "moderate",
  "low",
  "very_low",
  "unknown",
] as const;

/** Internalization LITERATURE-track grade — the PMID/DOI-anchored, span-verified
 *  read of OBSERVED internalization (per-mode basal/native-ligand/therapeutic,
 *  rolled to one overall Grade). A DIFFERENT enum from the sequence prior above:
 *  the literature Grade has no `very_high`/`very_low` and adds `no` (observed
 *  non-internalizing). Kept separate so the catalog can show the two tracks as
 *  distinct columns/filters. Ordered high → low. */
export type InternalizationLitGrade =
  | "high"
  | "moderate"
  | "low"
  | "no"
  | "unknown";

/** Canonical high → low order for the literature-track grade. */
export const INTERNALIZATION_LIT_GRADES: readonly InternalizationLitGrade[] = [
  "high",
  "moderate",
  "low",
  "no",
  "unknown",
] as const;
