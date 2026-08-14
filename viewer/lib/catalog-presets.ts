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
 *
 * Evidence gate is two-part. (1) A grade FLOOR: `evidence_grade` must be
 * at least `supportive_but_indirect`; `weak` and `conflicting` are held
 * out of Canonical. A `weak`-graded gene is either genuinely non-surface
 * or has under-covered / mis-credited evidence — neither belongs on the
 * high-confidence shortlist, and when a `weak` gene is truly surface the
 * remedy is to fix its evidence (re-annotate / methods-builder), which
 * lifts it to `supportive`+ and re-admits it. (2) Above that floor the
 * real quality bar is the synthesizer's overall `confidence` ruling
 * (`high` / `moderate`), NOT the deterministic A1-only `evidence_grade` —
 * that grade scores an empty A1 (direct-method) ledger low even when the
 * surface call rests on rich A2 (biological-context) evidence, so
 * `confidence` is what certifies the call above the floor. Fixing
 * evidence_grade at source is tracked in issue #131.
 *
 * State-dependence is NOT a hard exclusion: a `state_dependence='high'`
 * gene still qualifies as long as it is at least moderately expressed
 * (`expression_level ∈ {moderate, high}`). This gates on the expression
 * LEVEL directly rather than the derived `low_endogenous_expression`
 * boolean the earlier rule used — that boolean folds in expression
 * BREADTH (it flags a `moderate`-but-tissue-restricted gene as
 * low-endogenous), which then demoted validated targets that surface on
 * a specific lineage. Breadth is a therapeutic-window property (low
 * off-target burden is *good*), not a surface-membership signal: a
 * restricted, moderately-expressed target (CTLA4, 4-1BB — moderate on a
 * specific T-cell lineage, both validated antibody targets) is exactly
 * the kind of confidently-surface protein Canonical should certify.
 * Tissue restriction is surfaced by the `cell_type_restricted` facet and
 * induction by the `induced` facet, so a Canonical gene can still carry
 * an induced/restricted chip (CTLA4 → tier `canonical`, facet `induced`).
 * Only genuinely low/absent-baseline genes (`expression_level ∈ {low,
 * absent}`) that surface only when induced are held out of Canonical.
 * Canonical certifies *is* it surface (the five evidence/verdict gates);
 * *when* and *where* are the state_dependence + breadth facets. The
 * disjunct is additive — it only admits high-state-dependence genes,
 * never drops a low/moderate one.
 */
export function passesCanonical(f: DeepDiveFilters): boolean {
  return (
    // Canonical = classical BROAD surface proteins. Tissue-restricted AND
    // lysosomal-exocytosis are non-classical surfacing → routed to Likely +
    // their facet, never the broad Canonical shortlist. (State/induced
    // facets still overlay Canonical; only these two reasons are hard
    // exclusions here.)
    f.surface_call_reason !== "tissue_restricted_surface" &&
    f.surface_call_reason !== "lysosomal_exocytosis" &&
    // Evidence FLOOR: at least `supportive_but_indirect` — `weak` and
    // `conflicting` are held out (see docstring). Gates on the SYNTHESIZER's
    // holistic grade (`effectiveEvidenceGrade`), not the deterministic
    // A1-only `evidence_grade` which under-calls genes whose surface call
    // rests on rich A2 context.
    (effectiveEvidenceGrade(f) === "direct_multi_method" ||
      effectiveEvidenceGrade(f) === "direct_single_method" ||
      effectiveEvidenceGrade(f) === "supportive_but_indirect") &&
    (f.confidence === "high" || f.confidence === "moderate") &&
    (f.surface_specificity === "surface_dominant" ||
      f.surface_specificity === "mixed") &&
    ((f.state_dependence === "low" ||
      f.state_dependence === "moderate" ||
      f.state_dependence === "unclear") ||
      f.expression_level === "moderate" ||
      f.expression_level === "high") &&
    (f.surface_accessibility === "high" ||
      f.surface_accessibility === "moderate") &&
    (f.evidence_density === "high" || f.evidence_density === "moderate")
  );
}

/**
 * The evidence grade the tiers gate on: the synthesizer's holistic
 * `evidence_grade_summary` (what the gene page displays), falling back to the
 * deterministic A1-only `evidence_grade` when the summary is absent (older
 * records / before the Worker ships the ddf field). The deterministic grade
 * under-calls genes whose surface call rests on rich A2 context (MC2R, EFNA5:
 * deterministic `weak` but summary `supportive`), so gating on the summary
 * keeps the tiers consistent with what the gene page shows.
 */
export function effectiveEvidenceGrade(f: DeepDiveFilters) {
  return f.evidence_grade_summary ?? f.evidence_grade;
}

/**
 * Discovery-corpus size below which the deep dive rarely reaches a confident
 * (canonical) call — so a below-canonical verdict may be an evidence gap, not
 * biology. Empirical (PR #130, 5,130 cohort): canonical rate ~1-5% below 75
 * papers, 18% in 75-100, vs 47% at 150-200 and ~60% above 200 — inflection at
 * ~100 (≈ bottom 20% of the discovery distribution; median ≈ 220).
 */
export const LOW_LIT_PAPERS_MAX = 100;

/**
 * Badge — NOT a tier preset (kept out of PRESETS). Flags a NON-canonical gene
 * whose below-canonical verdict is plausibly evidence-limited: thin discovery
 * corpus (`n_papers_found < LOW_LIT_PAPERS_MAX`) AND an external surface-DB call
 * predicts it surface — an under-studied surface candidate worth a re-dive.
 *
 * `dbSurfacePositive` is wired to **UniProt** (`catalogRow.db.uniprot`): for the
 * low-lit population UniProt beats SURFY — it catches the understudied
 * olfactory/taste-GPCR class SURFY blind-spots, and its unique low-lit adds read
 * more surface-leaning by the deep dive's own accessibility/specificity.
 * (UniProt localization is itself a hybrid: curated evidence + similarity +
 * sequence-feature prediction, so not purely knowledge-based.) Passed as an
 * argument because the DB call is a candidate-universe flag in the 5-DB strip,
 * NOT part of the deep-dive `filters` — which is why it isn't a `(filters) =>
 * bool` preset. Scoped to non-canonical genes. Missing `n_papers_found` → not
 * flagged. Mirror of catalog_presets.is_low_literature_surface.
 */
export function isLowLiteratureSurface(
  f: DeepDiveFilters,
  dbSurfacePositive: boolean,
): boolean {
  if (passesCanonical(f)) return false;
  const n = f.n_papers_found;
  if (n == null) return false;
  return dbSurfacePositive && n < LOW_LIT_PAPERS_MAX;
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
  const g = effectiveEvidenceGrade(f);
  if (
    g !== "direct_multi_method" &&
    g !== "direct_single_method" &&
    g !== "supportive_but_indirect"
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
  // Accessibility FLOOR: moderate+ (same as Canonical). A `low`
  // surface-accessibility call — the "Surface likelihood: Low" pill on the
  // gene page — means the deep dive judged the accessible epitope hard to
  // reach; those genes drop to the below-Likely `low` tier rather than the
  // Likely shortlist. `uncertain` / `no` are likewise excluded.
  if (
    f.surface_accessibility !== "high" &&
    f.surface_accessibility !== "moderate"
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
 * Likely-ONLY = the Likely tier MINUS Canonical. This is what the "Likely"
 * catalog preset chip filters to, so that under multi-select the Canonical and
 * Likely chips are DISJOINT selectable bands whose union is the full Likely
 * tier (Canonical ⊂ Likely by construction — every canonical gene also passes
 * passesLikely). Select both chips to reconstitute the whole tier.
 *
 * Deliberately NOT the same as `passesLikely`: the tier-assignment helper
 * `deepDiveTier` and the Figure-5 buckets still use the full `passesLikely`
 * (they assign canonical genes tier=canonical by precedence, so no double
 * count). Only the preset chip narrows to the exclusive band.
 */
export function passesLikelyOnly(f: DeepDiveFilters): boolean {
  return passesLikely(f) && !passesCanonical(f);
}

/**
 * Cell-state induced = surface presentation depends on cell state
 * (stress, activation, oncogenic transformation, etc.). Matches via
 * EITHER `surface_call_reason ∈ {cell_state_induced,
 * lysosomal_exocytosis}` (the v2 schema's explicit induced-surface
 * signals) OR `induction_trigger != "none"` (the field schema-1.1.0
 * records like HSPA5 actually populate — the surface_call_reason
 * field is null on the older schema).
 *
 * State-dep accepts `moderate` (not high-only): moderate state-
 * dependence still indicates state-modulation; the TROP2-class
 * cancer-overexpression records that the synthesizer rates "moderate"
 * legitimately belong here. Accepts null + unclear too so older
 * records / undecided calls don't drop out.
 *
 * `dual_localization` is intentionally NOT in the reason set — it
 * just means "found in two compartments concurrently," not "the
 * surface fraction is state-induced." A constitutively dual-
 * localized protein (cell-surface AND Golgi at steady state, no
 * state-driven shuttle) would false-positive into Induced. The
 * induced semantic comes from state_dep + induction_trigger; if a
 * dual-localized record IS state-driven, those two gates already
 * catch it (TGOLN2 lands via `induction_trigger=infection`, not
 * via its `dual_localization` reason).
 */
export function passesInduced(f: DeepDiveFilters): boolean {
  if (!passesLikely(f)) return false;
  const sd = f.state_dependence;
  if (
    sd !== null &&
    sd !== undefined &&
    sd !== "moderate" &&
    sd !== "high" &&
    sd !== "unclear"
  ) {
    return false;
  }
  // PRIMARY (and only) gate: the surface_call_reason must itself say the
  // surface pool is state-gained. The old `induction_trigger` disjunct
  // over-counted 5x (2,127) because 'oncogenic' ≈ tumor_associated (99%
  // overlap), sweeping in constitutively-surface receptors that merely
  // correlate with cancer. Restricting to the reason code drops it to ~407
  // genuinely state-induced genes. The trigger axis remains as the sub-chips.
  return (
    f.surface_call_reason === "cell_state_induced" ||
    f.surface_call_reason === "lysosomal_exocytosis"
  );
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

export type DeepDiveTier = "canonical" | "likely" | "low" | "uncertain" | "no";
export type DeepDiveFacet = "induced" | "cell_type_restricted" | null;

/**
 * Resolve a record's single deep-dive tier + optional sub-facet — the same
 * five-tier spectrum the catalog and Figure 5 use, so the gene page reads the
 * same classification. Mirrors the precedence in build_figure_tsvs
 * `_dd_assign_bucket`: canonical (strictest) first; then the below-likely lean
 * split by the tentative surface_accessibility call; then likely with its
 * cell-type / cell-state sub-facet.
 *
 * The facet (Cell-state induced / Cell-type restricted) is surfaced whenever
 * its predicate holds — including on canonical genes (the figures bucket
 * canonical separately, but on the detail page it's useful to show that a
 * canonical target is also state-induced, e.g. TMEM123).
 */
export function deepDiveTier(f: DeepDiveFilters): {
  tier: DeepDiveTier;
  facet: DeepDiveFacet;
} {
  const facet: DeepDiveFacet = passesCellTypeRestricted(f)
    ? "cell_type_restricted"
    : passesInduced(f)
      ? "induced"
      : null;
  if (passesCanonical(f)) return { tier: "canonical", facet };
  if (passesLikely(f)) return { tier: "likely", facet };
  const acc = f.surface_accessibility;
  if (acc === "uncertain") return { tier: "uncertain", facet: null };
  if (acc === "low" || acc === "moderate") return { tier: "low", facet: null };
  return { tier: "no", facet: null };
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
    surface_accessibility: new Set(["high", "moderate"]),
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
    state_dependence: new Set(["moderate", "high", "unclear"]),
    surface_accessibility: new Set(["high", "moderate"]),
    // surface_call_reason values implied by the predicate's OR clause.
    // Not strictly required (the predicate also matches on
    // induction_trigger), but worth highlighting in More filters so
    // the reader sees which reasons land here. The induction_trigger
    // chip set is computed dynamically from the active sub-axes — see
    // resolveImpliedTriggerSet() in CatalogTable.tsx.
    surface_call_reason: new Set([
      "cell_state_induced",
      "lysosomal_exocytosis",
    ]),
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
    surface_accessibility: new Set(["high", "moderate"]),
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
      "Strictest tier — at least supportive-but-indirect evidence " +
      "(weak and conflicting excluded), high/moderate confidence, " +
      "surface-dominant or mixed localization, state-dependence low/" +
      "moderate/unclear (or, if high, at least moderate expression), " +
      "high/moderate surface accessibility, high/moderate evidence " +
      "density. The high-confidence surface shortlist.",
    predicate: passesCanonical,
  },
  {
    key: "likely",
    label: "Likely",
    description:
      "Likely-ONLY band — clears the same supportive-or-stronger evidence " +
      "floor AND the same moderate+ surface-accessibility floor as Canonical, " +
      "but falls short of Canonical elsewhere: admits mostly-intracellular " +
      "surface fractions (e.g. SRC via lysosomal exocytosis, HMGB1 via DAMP " +
      "release) and high / unclear / null state-dependence. Genes the deep " +
      "dive rates low surface-accessibility drop to the below-Likely `low` " +
      "tier. Canonical genes are EXCLUDED here — select the Canonical chip " +
      "alongside this one to see the full Likely tier (Canonical ⊂ Likely).",
    predicate: passesLikelyOnly,
  },
  {
    key: "induced",
    label: "Cell-state induced",
    description:
      "Subset of Likely where the surface pool is GAINED on a cell state. " +
      "Membership is set by the deep-dive surface_call_reason itself — " +
      "cell_state_induced or lysosomal_exocytosis — the reason codes that " +
      "mean the protein reaches the surface because of a state change, not " +
      "constitutively (SRC, CD63, HMGB1, C3 land here). This is deliberately " +
      "NOT keyed off induction_trigger: 'oncogenic' is assigned to nearly " +
      "every tumour-associated gene (~99% overlap), which would sweep in " +
      "constitutively-surface receptors that merely correlate with cancer. " +
      "The oncogenic / immune / stress / infection trigger is instead exposed " +
      "as the sub-chips within this set.",
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
