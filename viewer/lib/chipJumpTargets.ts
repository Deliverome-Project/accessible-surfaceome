/*
 * Central destination-id map for §01 Summary metrics chip jumps.
 *
 * Both producers (the destination elements on the Biology / Expression
 * / Risks / Evidence tabs) and consumers (the ChipJumpButton wrappers
 * in FiltersCard + FeatureChips) import from this file. Hard-coding
 * the same id in two places would silently drift; one source of truth
 * is the whole point.
 *
 * See docs/superpowers/specs/2026-07-01-clickable-summary-chip-jump-design.md.
 */

/** SectionTabs section id → the string that follows "#section-" in the
 *  URL hash. Matches keys in FeatureChips.tsx's FEATURE_CATEGORIES. */
export type ChipJumpTab = "biology" | "expression" | "risks" | "evidence";

export const chipJumpTargets = {
  /** FeatureRationales row for chip `key` in `category`. */
  featureRationale: (category: "biology" | "expression" | "risks", key: string): string =>
    `chip-jump-${category}-${key}`,
  /** Subcellular-localization block on the Biology tab. */
  primaryCompartment: "chip-jump-primary-compartment",
  /** Contradicting-evidence block on the Evidence tab. */
  contradictingEvidence: "chip-jump-contradicting-evidence",
  /** First row (in currently-sorted order) matching `category` in the
   *  accessibility-modulation table on the Biology tab. */
  modulationCategory: (category: string): string => `chip-jump-modulation-${category}`,
} as const;
