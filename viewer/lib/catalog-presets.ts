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
 * low / moderate / unclear state-dependence. The reader's "default
 * shortlist of high-confidence surface targets."
 *
 * Drops the ECD filter that earlier versions imposed — the small-vs-
 * large-ECD distinction is an antibody-design refinement, not a
 * surface-membership signal, and was burying claudins-class proteins
 * (CLDN18.2) whose small ECD loops are legitimately surface and
 * legitimately targetable (zolbetuximab is approved against
 * Claudin-18.2). State-dependence accepts `unclear` because the
 * synthesizer's contract is "unclear ≠ excluded"; the value lands
 * when the deep-dive can't confidently call low vs high.
 */
export function passesCanonical(f: DeepDiveFilters): boolean {
  return (
    (f.evidence_grade === "direct_multi_method" ||
      f.evidence_grade === "direct_single_method") &&
    (f.confidence === "high" || f.confidence === "moderate") &&
    (f.surface_specificity === "surface_dominant" ||
      f.surface_specificity === "mixed") &&
    (f.state_dependence === "low" ||
      f.state_dependence === "moderate" ||
      f.state_dependence === "unclear") &&
    (f.surface_accessibility === "high" ||
      f.surface_accessibility === "moderate") &&
    (f.evidence_density === "high" || f.evidence_density === "moderate")
  );
}

/**
 * Likely = broader shortlist. Adds `supportive_but_indirect` evidence,
 * `mostly_intracellular` specificity (proteins like SRC that surface
 * via lysosomal-exocytosis or HMGB1 via DAMP-release), and
 * `high` / `unclear` / null state-dep.
 *
 * Drops the ECD filter for the same reason Canonical did — ECD-size is
 * a downstream antibody-design refinement, not a surface-membership
 * signal. Inner-leaflet false positives (LYN, BAX) are still excluded
 * here because they fail OTHER filters: LYN has `evidence_grade=weak`
 * AND `surface_accessibility=no`; BAX has `evidence_grade=weak` AND
 * `surface_accessibility=no`. IZUMO4 (secreted-only) fails the same
 * way. So the ECD gate was load-bearing only for biology, never for
 * defending against the inner-leaflet bucket — removing it doesn't
 * leak SRC-class-but-actually-intracellular calls.
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
  return true;
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

/** Induction sub-axes — only meaningful when Induced is active.
 *  Cancer is its own bucket (induction_trigger=oncogenic) so it
 *  doesn't drown the Disease bucket; Disease is non-oncogenic
 *  disease state (cell death / infection). */
export function passesInductionCancer(f: DeepDiveFilters): boolean {
  return f.induction_trigger === "oncogenic";
}
export function passesInductionDisease(f: DeepDiveFilters): boolean {
  return (
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
export type InductionSubKey = "cancer" | "disease" | "stress" | "immune";

/** Standard advisory line appended (visually, via the InfoTip) to
 *  every preset description so the reader sees, without scrolling
 *  to the API page, that these shortlists only apply to genes that
 *  carry a deep-dive record. Non-deep-dive rows auto-drop on any
 *  non-"All" preset because there's no `deep_dive_filters` to
 *  evaluate — the count badge on a preset chip is therefore the
 *  population of (deep-dive ∩ predicate), never a subset of the
 *  full 6.5k-row universe. */
export const DEEP_DIVE_ONLY_NOTE =
  "Applies only to genes with a deep-dive record. " +
  "Non-deep-dive rows auto-exclude because the predicate reads " +
  "fields the catalog row doesn't carry.";

/** Per-preset map of deep-dive filter chips the preset's predicate
 *  REQUIRES to be set. Drives the "preset-implied" visual state on
 *  the More-filters chips so the reader can see which facet values
 *  are already in play before they refine. Keyed by the enum field
 *  key on `DeepDiveFilters`; the value is the set of allowed values.
 *
 *  Conditional rules (Likely's `ecd=none + positive reason` bypass)
 *  surface as the dominant set only — the bypass is documented in
 *  the preset description rather than visualized as an implied chip.
 *  Trying to encode it visually would require an OR-pill, which
 *  would clutter the row for marginal payoff. */
export const PRESET_IMPLIED_FILTERS: Record<
  PresetKey,
  Partial<Record<string, ReadonlySet<string>>>
> = {
  all: {},
  canonical: {
    evidence_grade: new Set(["direct_multi_method", "direct_single_method"]),
    confidence: new Set(["high", "moderate"]),
    surface_specificity: new Set(["surface_dominant", "mixed"]),
    state_dependence: new Set(["low", "moderate", "unclear"]),
    surface_accessibility: new Set(["high", "moderate"]),
    evidence_density: new Set(["high", "moderate"]),
    // ecd_accessibility_class intentionally dropped — see
    // passesCanonical docstring.
  },
  likely: {
    evidence_grade: new Set([
      "direct_multi_method",
      "direct_single_method",
      "supportive_but_indirect",
    ]),
    surface_specificity: new Set([
      "surface_dominant",
      "mixed",
      "mostly_intracellular",
    ]),
    state_dependence: new Set(["low", "moderate", "high", "unclear"]),
    surface_accessibility: new Set(["high", "moderate", "low"]),
  },
  induced: {
    evidence_grade: new Set([
      "direct_multi_method",
      "direct_single_method",
      "supportive_but_indirect",
    ]),
    surface_specificity: new Set([
      "surface_dominant",
      "mixed",
      "mostly_intracellular",
    ]),
    state_dependence: new Set(["high"]),
    surface_accessibility: new Set(["high", "moderate", "low"]),
  },
  cell_type_restricted: {
    evidence_grade: new Set([
      "direct_multi_method",
      "direct_single_method",
      "supportive_but_indirect",
    ]),
    surface_specificity: new Set([
      "surface_dominant",
      "mixed",
      "mostly_intracellular",
    ]),
    state_dependence: new Set(["moderate", "high"]),
    surface_accessibility: new Set(["high", "moderate", "low"]),
    surface_call_reason: new Set(["tissue_restricted_surface"]),
  },
};

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
      "high/moderate confidence, surface-dominant or mixed, low / " +
      "moderate / unclear state-dependence, high/moderate surface " +
      "accessibility, high/moderate evidence density. The high-" +
      "confidence surface shortlist. ECD-size is intentionally NOT " +
      "filtered — that's an antibody-design refinement, not a " +
      "surface-membership signal (Claudin-18.2 has tiny ECD loops " +
      "and a landed therapeutic anyway).",
    predicate: passesCanonical,
  },
  {
    key: "likely",
    label: "Likely",
    description:
      "Broader shortlist — adds supportive-but-indirect evidence, " +
      "mostly-intracellular surface fractions (e.g. SRC via lysosomal " +
      "exocytosis, HMGB1 via DAMP release), and high / unclear / null " +
      "state-dependence. ECD-size is intentionally NOT filtered for " +
      "the same reason as Canonical; inner-leaflet false positives " +
      "(LYN, BAX) are still excluded because they fail on evidence_" +
      "grade=weak + surface_accessibility=no.",
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
    key: "cancer",
    label: "Cancer",
    description:
      "induction_trigger = oncogenic — surface form is induced by " +
      "oncogenic transformation specifically (TROP2-class cancer " +
      "overexpression, eSrc-class lysosomal-exocytosis pool). Split " +
      "off from Disease because oncogenic is the largest single " +
      "trigger in the cohort and conflating it with infection / cell-" +
      "death buries those rarer buckets.",
    predicate: passesInductionCancer,
  },
  {
    key: "disease",
    label: "Other disease",
    description:
      "induction_trigger ∈ {cell_death, infection} — non-oncogenic " +
      "disease state (pyroptosis / necroptosis / immune-cell-death; " +
      "viral or bacterial infection). HMGB1-class DAMP release lives " +
      "here rather than under Cancer.",
    predicate: passesInductionDisease,
  },
  {
    key: "stress",
    label: "Stress",
    description:
      "induction_trigger = stress_hypoxia — surface form responds to " +
      "hypoxia / ER stress / metabolic stress. Independent of " +
      "tumor / inflammation context.",
    predicate: passesInductionStress,
  },
  {
    key: "immune",
    label: "Immune",
    description:
      "induction_trigger = immune — surface form responds to immune " +
      "activation. Coarse umbrella for both constitutive-surface-with-" +
      "immune-modulation (KIR2DL1-class) and release-by-immune-" +
      "activation (HMGB1 DAMP-release pool); the prose distinguishes.",
    predicate: passesInductionImmune,
  },
];
