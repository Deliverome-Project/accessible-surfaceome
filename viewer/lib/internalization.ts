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
