/**
 * Catalog preset predicates.
 *
 * Each preset is a pure predicate over a `CatalogRow.deep_dive_filters`
 * payload — runs entirely client-side, no extra fetch. Rows without a
 * deep_dive_filters payload (the ~19k non-deep-dive genes) never match
 * any preset and are excluded when a non-"all" preset is active.
 *
 * The predicates mirror the Python audit logic at the same names
 * (v6 contract documented in the conversation thread):
 *   - canonical:        strictest tier, antibody/ADC gold-standard
 *   - likely:           same shape, broader on evidence + topology
 *   - induced:          sub-bucket of likely — state-induced surface
 *                       (HSPA5-class)
 *   - cell_type_restricted: sub-bucket of likely — tissue-restricted
 *                       constitutive surface (KLK2-class)
 *
 * "Induced" further sub-splits by `induction_trigger`:
 *   - disease (oncogenic / cell_death / infection)
 *   - stress  (stress_hypoxia)
 *   - immune  (immune)
 * These sub-axes are NOT mutually exclusive with each other; a gene
 * with `induction_trigger=oncogenic` lands in `disease` only.
 */
import type { DeepDiveFilters } from "./surfaceome";
import type { TriageReason } from "./surfaceome-types";

/** Reasons in the YES + CONTEXTUAL buckets (real surface call). */
const POSITIVE_REASONS = new Set<TriageReason>([
  // YES bucket
  "classical_surface_receptor",
  "gpi_anchored",
  "multipass_with_exposed_loops",
  "extracellular_face_protein",
  "stable_complex_partner",
  // CONTEXTUAL bucket
  "cell_state_induced",
  "tissue_restricted_surface",
  "lysosomal_exocytosis",
  "dual_localization",
  "stable_surface_attachment",
]);

const INDUCTION_NON_NONE = new Set([
  "oncogenic",
  "immune",
  "stress_hypoxia",
  "cell_death",
  "infection",
]);

/**
 * Canonical = strictest tier. Direct evidence, high or moderate
 * confidence, surface-dominant or mixed (not mostly intracellular),
 * low or moderate state-dependence, real ECD. The reader's "default
 * shortlist of high-confidence surface targets."
 */
export function passesCanonical(f: DeepDiveFilters): boolean {
  return (
    (f.evidence_grade === "direct_multi_method" ||
      f.evidence_grade === "direct_single_method") &&
    (f.confidence === "high" || f.confidence === "moderate") &&
    (f.surface_specificity === "surface_dominant" ||
      f.surface_specificity === "mixed") &&
    (f.state_dependence === "low" || f.state_dependence === "moderate") &&
    (f.surface_accessibility === "high" ||
      f.surface_accessibility === "moderate") &&
    (f.evidence_density === "high" || f.evidence_density === "moderate") &&
    (f.ecd_accessibility_class === "large" ||
      f.ecd_accessibility_class === "moderate" ||
      f.ecd_accessibility_class === "small")
  );
}

/**
 * Likely = broader shortlist. Adds `supportive_but_indirect` evidence,
 * `mostly_intracellular` specificity (proteins like SRC that surface
 * via lysosomal-exocytosis), `high` / `unclear` / null state-dep, and
 * relaxes ECD=none/minimal IFF the synthesizer's `surface_call_reason`
 * is a positive (yes / contextual) call. The ECD bypass lets HMGB1
 * (cell_state_induced, ecd=none) and SRC (lysosomal_exocytosis,
 * ecd=none) through while still excluding LYN (inner_leaflet_anchored,
 * a NEGATIVE reason) and IZUMO4 (secreted_only).
 */
export function passesLikely(f: DeepDiveFilters): boolean {
  if (
    f.evidence_grade !== "direct_multi_method" &&
    f.evidence_grade !== "direct_single_method" &&
    f.evidence_grade !== "supportive_but_indirect"
  ) {
    return false;
  }
  if (
    f.surface_specificity !== "surface_dominant" &&
    f.surface_specificity !== "mixed" &&
    f.surface_specificity !== "mostly_intracellular"
  ) {
    return false;
  }
  if (
    f.surface_accessibility !== "high" &&
    f.surface_accessibility !== "moderate" &&
    f.surface_accessibility !== "low"
  ) {
    return false;
  }
  // state_dependence allows null (older 1.1.0 records that didn't
  // populate the field) — keep permissive.
  const sd = f.state_dependence;
  if (
    sd !== null &&
    sd !== undefined &&
    sd !== "low" &&
    sd !== "moderate" &&
    sd !== "high" &&
    sd !== "unclear"
  ) {
    return false;
  }
  // ECD gate with bypass.
  const ecd = f.ecd_accessibility_class;
  const ecdOk =
    ecd === "large" || ecd === "moderate" || ecd === "small"
      ? true
      : (ecd === "minimal" || ecd === "none") &&
        POSITIVE_REASONS.has(f.surface_call_reason);
  return Boolean(ecdOk);
}

/**
 * Cell-state induced = surface presentation depends on cell state
 * (stress, activation, oncogenic transformation, etc.). Matches via
 * EITHER `surface_call_reason ∈ {cell_state_induced,
 * lysosomal_exocytosis}` (the v2 schema's explicit signal) OR
 * `induction_trigger != "none"` (the field schema-1.1.0 records like
 * HSPA5 actually populate — `surface_call_reason` is null there).
 * Requires state_dep=high (or unknown, for older records).
 */
export function passesInduced(f: DeepDiveFilters): boolean {
  if (!passesLikely(f)) return false;
  const sd = f.state_dependence;
  if (sd !== null && sd !== undefined && sd !== "high") return false;
  if (
    f.surface_call_reason === "cell_state_induced" ||
    f.surface_call_reason === "lysosomal_exocytosis"
  ) {
    return true;
  }
  if (f.induction_trigger && INDUCTION_NON_NONE.has(f.induction_trigger)) {
    return true;
  }
  return false;
}

/**
 * Cell-type restricted = constitutively surface on specific cell types,
 * absent on others (KLK2 in prostate; PRSS family in pancreatic).
 * Distinct from cell-state-induced: different cell types vs same cell
 * across states.
 */
export function passesCellTypeRestricted(f: DeepDiveFilters): boolean {
  if (!passesLikely(f)) return false;
  if (f.state_dependence !== "moderate" && f.state_dependence !== "high") {
    return false;
  }
  return f.surface_call_reason === "tissue_restricted_surface";
}

/** Induction sub-axes — only meaningful when Induced is active. */
export function passesInductionDisease(f: DeepDiveFilters): boolean {
  return (
    f.induction_trigger === "oncogenic" ||
    f.induction_trigger === "cell_death" ||
    f.induction_trigger === "infection"
  );
}
export function passesInductionStress(f: DeepDiveFilters): boolean {
  return f.induction_trigger === "stress_hypoxia";
}
export function passesInductionImmune(f: DeepDiveFilters): boolean {
  return f.induction_trigger === "immune";
}

export type PresetKey =
  | "all"
  | "canonical"
  | "likely"
  | "induced"
  | "cell_type_restricted";
export type InductionSubKey = "disease" | "stress" | "immune";

/** Single-source-of-truth registry consumed by the toolbar. Ordered the
 *  way the chips render — strictest tier first. */
export const PRESETS: ReadonlyArray<{
  key: PresetKey;
  label: string;
  description: string;
  predicate: (f: DeepDiveFilters) => boolean;
}> = [
  {
    key: "all",
    label: "All",
    description: "Every catalog row, no preset filter.",
    predicate: () => true,
  },
  {
    key: "canonical",
    label: "Canonical",
    description:
      "Strictest tier — direct evidence (single or multi-method), " +
      "high/moderate confidence, surface-dominant or mixed, low/moderate " +
      "state-dependence, real ECD. The high-confidence surface shortlist.",
    predicate: passesCanonical,
  },
  {
    key: "likely",
    label: "Likely",
    description:
      "Broader shortlist — adds supportive-but-indirect evidence, mostly-" +
      "intracellular surface fractions (e.g. SRC via lysosomal exocytosis), " +
      "and ECD=none for proteins whose surface call rests on a positive " +
      "surface_call_reason rather than a TM-anchored ECD (HMGB1).",
    predicate: passesLikely,
  },
  {
    key: "induced",
    label: "Cell-state induced",
    description:
      "Subset of Likely where surface presentation is induced by cell " +
      "state (oncogenic transformation, stress, infection, immune " +
      "activation). HSPA5, SRC, CD63, HMGB1, C3 land here.",
    predicate: passesInduced,
  },
  {
    key: "cell_type_restricted",
    label: "Cell-type restricted",
    description:
      "Subset of Likely with constitutive surface in specific cell types " +
      "only (KLK2 in prostate, etc.). Different cell types — not same cell " +
      "across states.",
    predicate: passesCellTypeRestricted,
  },
];

export const INDUCTION_SUBS: ReadonlyArray<{
  key: InductionSubKey;
  label: string;
  description: string;
  predicate: (f: DeepDiveFilters) => boolean;
}> = [
  {
    key: "disease",
    label: "Disease",
    description:
      "induction_trigger ∈ {oncogenic, cell_death, infection} — the " +
      "surface form goes up under disease state. Most of the cohort's " +
      "induced hits land here (TROP2-class cancer overexpression).",
    predicate: passesInductionDisease,
  },
  {
    key: "stress",
    label: "Stress",
    description:
      "induction_trigger = stress_hypoxia — surface form responds to " +
      "hypoxia / ER stress / metabolic stress.",
    predicate: passesInductionStress,
  },
  {
    key: "immune",
    label: "Immune",
    description:
      "induction_trigger = immune — surface form responds to immune " +
      "activation / TME modulation.",
    predicate: passesInductionImmune,
  },
];
