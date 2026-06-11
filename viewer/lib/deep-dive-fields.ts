/**
 * Deep-dive filter taxonomy — shared by the catalog filter panel
 * (`components/CatalogTable/CatalogTable.tsx`) and the upload-compare
 * tool (`components/CompareTool/CompareTool.tsx`).
 *
 * 13 enum-valued fields + 8 boolean fields. Keys mirror `DeepDiveFilters`
 * in `lib/surfaceome.ts` and `DDF_KEYS` in the Worker
 * (`cloudflare/workers/surfaceome_api/src/index.js`); the enum value
 * lists come from the Python Literal definitions in
 * `src/accessible_surfaceome/tools/_shared/models.py`.
 *
 * `tooltipKey` indexes the `tooltips` map in `lib/tooltips.tsx` — the
 * same text bank the gene-page FiltersCard reads — so the language stays
 * consistent across the catalog chips, the gene-page pills, and the
 * compare tool's expandable detail.
 *
 * Extracted from CatalogTable in the compare-tool change so both
 * surfaces share one source of truth; extend here (and the Pydantic /
 * Worker / `DeepDiveFilters` shapes) when adding a field.
 */

export type DdEnumKey =
  | "surface_accessibility"
  | "confidence"
  | "state_dependence"
  | "surface_call_reason"
  | "subcategory"
  | "llm_family"
  | "primary_compartment"
  | "restricted_subdomain_kind"
  | "secreted_form_source"
  | "evidence_grade"
  | "evidence_density"
  | "ecd_accessibility_class"
  | "expression_level"
  | "expression_breadth"
  | "surface_specificity"
  | "co_receptor_dependency"
  // Derived ECD-identity bands (binned from the numeric *_ecd_pct_identity
  // record fields in pickDeepDiveFilters / the Worker).
  | "cyno_ortholog_ecd"
  | "mouse_ortholog_ecd"
  | "max_paralog_ecd"
  | "induction_trigger";

export type DdBoolKey =
  | "has_known_ligand"
  | "low_endogenous_expression"
  | "overexpression_surface_localization_observed"
  | "has_shed_form"
  | "has_secreted_form"
  | "has_epitope_masking"
  | "has_restricted_subdomain"
  | "n_term_extracellular"
  | "c_term_extracellular"
  | "tumor_associated"
  | "has_live_cell_surface_evidence";

/**
 * Provenance bucket used by the catalog filter panel to partition
 * deep-dive fields under the Deep Dive group.
 *
 * **The contract — what makes a field `deterministic`:** the value is
 * derived purely from tool output on the protein sequence (DeepTMHMM
 * topology, AlphaFold pLDDT, Compara %-identity, SURFACE-Bind MaSIF
 * patch scoring). Re-running the same tool on the same sequence gives
 * the same value, regardless of which deep-dive agent ran. No LLM
 * inclusion judgement enters the chain.
 *
 * **What is NOT `deterministic`, even when the final transform is
 * mechanical:** a field whose input depends on what the LLM chose to
 * include. Example: `evidence_density` buckets `len(evidence_rows)`
 * with fixed thresholds, but the agent's pick of which rows to include
 * is LLM-driven, so the bucket value reflects that judgement. That's
 * `llm` provenance even though the bucketing itself is a one-liner.
 *
 * - `llm` — synthesizer rollups (re-derived from the merged A1+A2
 *   evidence ledger but still an LLM judgement), and any mechanical
 *   downstream transforms of LLM-pulled inputs.
 * - `deterministic` — tool-derived readouts on the sequence only.
 *
 * The catalog filter panel renders three collapsible subsections:
 * "Surface call" (`provenance === "llm" && !isRisk`), "Risks"
 * (`isRisk`, orthogonal to provenance), and "Deterministic"
 * (`provenance === "deterministic"`). `isRisk` is a topical tag, not a
 * provenance value — the risk fields keep their `llm` provenance.
 *
 * The same provenance split is used by the gene-page FiltersCard at
 * `viewer/components/surfaceome/FiltersCard/FiltersCard.tsx`.
 */
export type DdProvenance = "llm" | "deterministic";

export interface DdEnumSpec {
  key: DdEnumKey;
  label: string;
  values: readonly string[];
  /** Key into the `tooltips` map for the InfoTip body. */
  tooltipKey: string;
  /** LLM-rollup vs deterministic-tool readout. */
  provenance: DdProvenance;
  /** Accessibility-risk topical tag. Orthogonal to `provenance` — a
   *  risk field keeps its `llm`/`deterministic` provenance but is
   *  surfaced under the catalog's "Risks" subsection rather than the
   *  "Surface call" one. Undefined = not a risk. */
  isRisk?: boolean;
  /** Optional per-value display label override. When a value isn't in
   *  the map (or the map is absent), the renderer falls back to
   *  `prettyEnum(value)`. Used where the raw snake_case value
   *  prettifies poorly — e.g. `pmhc_only_intracellular` →
   *  "Pmhc Only Intracellular" — so the reader sees a human-facing
   *  label instead of a mangled token. */
  valueLabels?: Readonly<Record<string, string>>;
}

export interface DdBoolSpec {
  key: DdBoolKey;
  label: string;
  tooltipKey: string;
  /** LLM-rollup vs deterministic-tool readout. */
  provenance: DdProvenance;
  /** Accessibility-risk topical tag (see `DdEnumSpec.isRisk`). */
  isRisk?: boolean;
}

export const DD_ENUM_FIELDS: readonly DdEnumSpec[] = [
  {
    // Wire/storage name stays `surface_accessibility` everywhere (Pydantic,
    // records on disk, D1, Worker, /v1/* API consumers). Only the DISPLAY
    // LABEL changes — the field reads as a verdict graded by evidence
    // strength (best-case-state, capped by THE BRACKET in
    // surfaceome_synthesizer/prompts/system.md), not a steady-state
    // magnitude. "Accessibility" misled readers into expecting % surface;
    // "Surface verdict" is what it actually is. Pair with
    // `surface_specificity` for the proportion axis.
    key: "surface_accessibility",
    label: "Surface verdict",
    values: ["high", "moderate", "low", "uncertain", "no"],
    tooltipKey: "surface_accessibility",
    provenance: "llm",
  },
  {
    key: "confidence",
    label: "Confidence",
    values: ["high", "moderate", "low"],
    tooltipKey: "confidence",
    provenance: "llm",
  },
  {
    key: "state_dependence",
    label: "State dependence",
    values: ["low", "moderate", "high", "unclear"],
    tooltipKey: "state_dependence",
    provenance: "llm",
  },
  {
    key: "surface_call_reason",
    label: "Surface reason",
    values: [
      "classical_surface_receptor",
      "gpi_anchored",
      "multipass_with_exposed_loops",
      "extracellular_face_protein",
      "stable_complex_partner",
      "cell_state_induced",
      "tissue_restricted_surface",
      "lysosomal_exocytosis",
      "dual_localization",
      "stable_surface_attachment",
      "cytoplasmic",
      "nuclear",
      "mitochondrial_internal",
      "endomembrane_resident",
      "nuclear_envelope",
      "inner_leaflet_anchored",
      "secreted_only",
      "pmhc_only_intracellular",
      "other",
    ],
    // User-facing display labels — plain biology language, not the
    // snake_case enum token. prettyEnum mangles a few of these
    // ("Pmhc Only Intracellular", "Gpi Anchored"), so spell them out.
    valueLabels: {
      classical_surface_receptor: "Classical surface receptor",
      gpi_anchored: "GPI-anchored",
      multipass_with_exposed_loops: "Multipass, exposed loops",
      extracellular_face_protein: "Extracellular-face protein",
      stable_complex_partner: "Stable complex partner",
      cell_state_induced: "Cell-state induced",
      tissue_restricted_surface: "Tissue-restricted surface",
      lysosomal_exocytosis: "Lysosomal exocytosis",
      dual_localization: "Dual localization",
      stable_surface_attachment: "Stable surface attachment",
      cytoplasmic: "Cytoplasmic",
      nuclear: "Nuclear",
      mitochondrial_internal: "Mitochondrial (internal)",
      endomembrane_resident: "Endomembrane-resident",
      nuclear_envelope: "Nuclear envelope",
      inner_leaflet_anchored: "Inner-leaflet anchored",
      secreted_only: "Secreted only",
      pmhc_only_intracellular: "pMHC (intracellular only)",
      other: "Other",
    },
    tooltipKey: "catalog_surface_call_reason",
    provenance: "llm",
  },
  {
    key: "subcategory",
    label: "Architecture",
    values: [
      "single_pass_T1",
      "single_pass_T2",
      "multi_pass",
      "GPCR",
      "GPI_anchored",
      "tetraspanin",
      "other",
    ],
    // Cap the acronyms — sentence-casing would mangle these to
    // "Gpcr" / "Gpi anchored" / "Single pass t1".
    valueLabels: {
      single_pass_T1: "Single-pass (type I)",
      single_pass_T2: "Single-pass (type II)",
      multi_pass: "Multi-pass",
      GPCR: "GPCR",
      GPI_anchored: "GPI-anchored",
      tetraspanin: "Tetraspanin",
      other: "Other",
    },
    tooltipKey: "catalog_subcategory",
    provenance: "llm",
  },
  {
    key: "llm_family",
    label: "Family (LLM)",
    values: ["receptor", "enzyme", "transporter", "miscellaneous"],
    tooltipKey: "catalog_llm_family",
    provenance: "llm",
  },
  {
    // Mirrors `biological_context.subcellular_localization.primary_compartment`
    // (the `Compartment` enum in `viewer/lib/surfaceome-types.ts`, sourced from
    // `PrimaryCompartment` in `src/accessible_surfaceome/tools/_shared/models.py`).
    // Note: sourced from the biological-context block, NOT the top-level
    // `filters` block — see `pickDeepDiveFilters` in this file + the Worker's
    // `projectDeepDiveFilters`.
    key: "primary_compartment",
    label: "Primary localization",
    values: [
      "plasma_membrane",
      "endosome",
      "lysosome",
      "ER",
      "Golgi",
      "mitochondrion",
      "nucleus",
      "cytosol",
      "secreted",
      "other",
    ],
    valueLabels: {
      plasma_membrane: "Plasma membrane",
      endosome: "Endosome",
      lysosome: "Lysosome",
      ER: "ER",
      Golgi: "Golgi",
      mitochondrion: "Mitochondrion",
      nucleus: "Nucleus",
      cytosol: "Cytosol",
      secreted: "Secreted",
      other: "Other",
    },
    tooltipKey: "catalog_primary_compartment",
    provenance: "llm",
  },
  {
    // Sourced from `accessibility_risks.restricted_subdomain.domain`
    // ONLY when `restricted_subdomain.present === true`. The schema
    // requires `domain` to always be set (with "unknown" as the
    // not-applicable sentinel); projecting unconditionally would pile
    // every non-restricted gene into "unknown" and drown the signal.
    // The bool `has_restricted_subdomain` says whether the protein has
    // a polarized localization at all; this enum says what kind of
    // domain.
    key: "restricted_subdomain_kind",
    label: "Restricted subdomain",
    values: [
      "apical",
      "junctional",
      "ciliary",
      "synaptic",
      "raft",
      "basolateral",
      "other",
      "unknown",
    ],
    valueLabels: {
      apical: "Apical",
      junctional: "Junctional",
      ciliary: "Ciliary",
      synaptic: "Synaptic",
      raft: "Lipid raft",
      basolateral: "Basolateral",
      other: "Other",
      unknown: "Unknown",
    },
    tooltipKey: "catalog_restricted_subdomain_kind",
    provenance: "llm",
    isRisk: true,
  },
  {
    // Sourced from `accessibility_risks.secreted_form.source` ONLY when
    // `secreted_form.present === true` — same project-when-present
    // pattern as restricted_subdomain_kind. The bool
    // `has_secreted_form` says whether a non-membrane-anchored form
    // exists; this enum says how it's made. `alternative_splicing`
    // covers soluble splice isoforms (per the Pydantic SecretedForm
    // rationale field's own docstring: "alternative splicing producing
    // a TM-less isoform"). Useful to find decoys with a specific
    // sheddability profile (e.g. proteolytic-only shed targets that
    // antibody campaigns must compete with).
    key: "secreted_form_source",
    label: "Secreted-form source",
    values: ["alternative_splicing", "proteolytic", "both", "unknown"],
    valueLabels: {
      alternative_splicing: "Alt. splicing (incl. soluble isoform)",
      proteolytic: "Proteolytic shedding",
      both: "Both (splicing + proteolysis)",
      unknown: "Unknown",
    },
    tooltipKey: "catalog_secreted_form_source",
    provenance: "llm",
    isRisk: true,
  },
  {
    key: "evidence_grade",
    label: "Evidence grade",
    values: [
      "direct_multi_method",
      "direct_single_method",
      "supportive_but_indirect",
      "conflicting",
      "weak",
    ],
    tooltipKey: "experimental_surface_evidence",
    provenance: "llm",
  },
  {
    // Provenance is `llm`, NOT `deterministic`: the buckets (≥30 / ≥10
    // / else) are mechanical, but the INPUT count is the number of
    // evidence rows the synthesizer chose to include from the merged
    // A1+A2 ledger. That inclusion judgement is an LLM rollup, so the
    // final value depends on the LLM. The `deterministic` bucket is
    // reserved for fields derived purely from tool output on the
    // protein sequence — DeepTMHMM topology, AlphaFold pLDDT, Compara
    // identity — where rerunning the same tool on the same sequence
    // gives the same value regardless of the agent.
    key: "evidence_density",
    label: "Evidence density",
    values: ["low", "moderate", "high"],
    tooltipKey: "catalog_evidence_density",
    provenance: "llm",
  },
  {
    key: "ecd_accessibility_class",
    label: "ECD class",
    values: ["large", "moderate", "small", "minimal", "none"],
    tooltipKey: "catalog_ecd_class",
    provenance: "deterministic",
  },
  {
    key: "expression_level",
    label: "Expression level",
    values: ["high", "moderate", "low", "absent"],
    tooltipKey: "expression_level",
    provenance: "llm",
  },
  {
    key: "expression_breadth",
    label: "Expression breadth",
    values: ["pan_tissue", "broad", "restricted", "rare"],
    tooltipKey: "expression_breadth",
    provenance: "llm",
  },
  {
    key: "surface_specificity",
    label: "Surface specificity",
    values: ["surface_dominant", "mixed", "mostly_intracellular"],
    tooltipKey: "surface_specificity",
    provenance: "llm",
  },
  {
    key: "co_receptor_dependency",
    label: "Co-receptor",
    values: ["required", "modulatory", "none", "unknown"],
    tooltipKey: "co_receptor_dependency",
    provenance: "llm",
    isRisk: true,
  },
  // Cross-species + paralog ECD %-identity bands. The numeric source fields
  // aren't catalog facets; the binned band is (derived in
  // `pickDeepDiveFilters` / the Worker via `ecdBand`).
  {
    key: "cyno_ortholog_ecd",
    label: "Cyno ECD identity",
    values: ["high", "moderate", "low", "none"],
    valueLabels: {
      high: "≥90% (cross-reactive)",
      moderate: "70–90%",
      low: "<70%",
      none: "No cyno ortholog",
    },
    tooltipKey: "catalog_cyno_ecd",
    provenance: "deterministic",
  },
  {
    key: "mouse_ortholog_ecd",
    label: "Mouse ECD identity",
    values: ["high", "moderate", "low", "none"],
    valueLabels: {
      high: "≥90% (cross-reactive)",
      moderate: "70–90%",
      low: "<70%",
      none: "No mouse ortholog",
    },
    tooltipKey: "catalog_mouse_ecd",
    provenance: "deterministic",
  },
  {
    key: "max_paralog_ecd",
    label: "Paralog ECD identity",
    values: ["high", "moderate", "low", "none"],
    valueLabels: {
      high: "≥70% (cross-reactivity risk)",
      moderate: "40–70%",
      low: "<40%",
      none: "No paralog",
    },
    tooltipKey: "catalog_paralog_ecd",
    provenance: "deterministic",
  },
  // Dominant induction trigger (deep-block rollup from
  // accessibility_modulation.cell_state_trigger). surface_call_reason is
  // the mechanism; this is the stimulus that surfaces it.
  {
    key: "induction_trigger",
    label: "Induction trigger",
    values: [
      "none",
      "oncogenic",
      "immune",
      "stress_hypoxia",
      "cell_death",
      "infection",
      "other",
    ],
    valueLabels: {
      none: "Not induced",
      oncogenic: "Oncogenic transformation",
      immune: "Immune activation",
      stress_hypoxia: "Stress / hypoxia",
      cell_death: "Cell death (apoptosis/necroptosis)",
      infection: "Infection",
      other: "Other",
    },
    tooltipKey: "catalog_induction_trigger",
    provenance: "llm",
  },
];

export const DD_BOOL_FIELDS: readonly DdBoolSpec[] = [
  {
    key: "has_known_ligand",
    label: "Known ligand",
    tooltipKey: "catalog_has_known_ligand",
    provenance: "llm",
  },
  {
    key: "low_endogenous_expression",
    label: "Low endogenous expression",
    tooltipKey: "catalog_low_endogenous_expression",
    provenance: "llm",
    isRisk: true,
  },
  {
    key: "overexpression_surface_localization_observed",
    label: "Overexpression precedent",
    tooltipKey: "catalog_overexpression_precedent",
    provenance: "llm",
  },
  {
    key: "has_shed_form",
    label: "Shed form",
    tooltipKey: "catalog_shed_form",
    provenance: "llm",
    isRisk: true,
  },
  {
    key: "has_secreted_form",
    label: "Secreted form",
    tooltipKey: "catalog_secreted_form",
    provenance: "llm",
    isRisk: true,
  },
  {
    key: "has_epitope_masking",
    label: "Epitope masking",
    tooltipKey: "catalog_epitope_masking",
    provenance: "llm",
    isRisk: true,
  },
  {
    key: "has_restricted_subdomain",
    label: "Restricted subdomain",
    tooltipKey: "catalog_restricted_subdomain",
    provenance: "llm",
    isRisk: true,
  },
  {
    key: "n_term_extracellular",
    label: "N-term extracellular",
    tooltipKey: "catalog_n_term_extracellular",
    provenance: "deterministic",
  },
  {
    key: "c_term_extracellular",
    label: "C-term extracellular",
    tooltipKey: "catalog_c_term_extracellular",
    provenance: "deterministic",
  },
  // Deep-block rollups (from biological_context.tissues /
  // surface_evidence.methods).
  {
    key: "tumor_associated",
    label: "Tumor-associated",
    tooltipKey: "catalog_tumor_associated",
    provenance: "llm",
  },
  {
    key: "has_live_cell_surface_evidence",
    label: "Live-cell surface evidence",
    tooltipKey: "catalog_live_cell_evidence",
    provenance: "llm",
  },
];

/**
 * Project a deep-dive record's `filters` block onto the `DeepDiveFilters`
 * field set (the 13 enum + 8 bool keys above). The deployed public Worker
 * doesn't ship the catalog `ddf` field yet, so the compare page rebuilds
 * it at BUILD time from the bundled per-gene records — whose `filters`
 * block carries the same field names. Older records omit some of the
 * newer fields; those are left out and read as `undefined` by the
 * enrichment (so their groups simply don't render). Returns `undefined`
 * when nothing maps, so the caller can skip attaching an empty object.
 */
/** Bin an ECD %-identity into a coarse band. `null` (no ortholog / paralog
 *  in Compara) → "none". MUST stay in sync with the Worker's
 *  `projectDeepDiveFilters` (cloudflare/workers/surfaceome_api/src/index.js). */
export function ecdBand(
  pct: number | null | undefined,
  hi: number,
  mid: number,
): "high" | "moderate" | "low" | "none" {
  if (pct == null) return "none";
  if (pct >= hi) return "high";
  if (pct >= mid) return "moderate";
  return "low";
}

/** Derived ECD-band fields and the numeric record field each bins from.
 *  Cross-species use 90/70 (preclinical-model cross-reactivity); paralog
 *  uses 70/40 (off-target cross-reactivity risk). */
const ECD_BAND_SOURCES: readonly {
  key: DdEnumKey;
  source: string;
  hi: number;
  mid: number;
}[] = [
  { key: "cyno_ortholog_ecd", source: "cyno_ortholog_ecd_pct_identity", hi: 90, mid: 70 },
  { key: "mouse_ortholog_ecd", source: "mouse_ortholog_ecd_pct_identity", hi: 90, mid: 70 },
  { key: "max_paralog_ecd", source: "max_paralog_ecd_pct_identity", hi: 70, mid: 40 },
];

export function pickDeepDiveFilters(
  filters: Record<string, unknown> | null | undefined,
  biologicalContext?: Record<string, unknown> | null,
  accessibilityRisks?: Record<string, unknown> | null,
): Record<string, unknown> | undefined {
  if (!filters) return undefined;
  const out: Record<string, unknown> = {};
  for (const f of DD_ENUM_FIELDS) {
    if (filters[f.key] != null) out[f.key] = filters[f.key];
  }
  for (const f of DD_BOOL_FIELDS) {
    if (typeof filters[f.key] === "boolean") out[f.key] = filters[f.key];
  }
  // Derived ECD bands — the numeric source lives in the record's filters
  // block; the band (not the float) is the catalog/compare facet.
  for (const b of ECD_BAND_SOURCES) {
    if (b.source in filters) {
      out[b.key] = ecdBand(filters[b.source] as number | null, b.hi, b.mid);
    }
  }
  // Sourced from biological_context, not filters — the record schema
  // keeps the localization in the biology block. MUST stay in sync with
  // the Worker's `projectDeepDiveFilters` (which performs the same
  // pull on the server side).
  const sl =
    (biologicalContext?.subcellular_localization as
      | { primary_compartment?: unknown }
      | undefined) ?? undefined;
  if (sl && typeof sl.primary_compartment === "string") {
    out.primary_compartment = sl.primary_compartment;
  }
  // Sourced from accessibility_risks.restricted_subdomain.domain ONLY
  // when present === true. The schema requires `domain` to always be
  // set (with "unknown" as the not-applicable sentinel); projecting it
  // unconditionally would pile every non-restricted gene into the
  // "unknown" bucket and drown the signal. MUST stay in sync with the
  // Worker's `projectDeepDiveFilters`.
  const rs =
    (accessibilityRisks?.restricted_subdomain as
      | { present?: unknown; domain?: unknown }
      | undefined) ?? undefined;
  if (rs && rs.present === true && typeof rs.domain === "string") {
    out.restricted_subdomain_kind = rs.domain;
  }
  // Same project-when-present pattern for secreted_form.source — only
  // surface the source when there's a secreted form to attribute it to.
  // Empty/null source on a present-true secreted form is allowed by the
  // schema (`source: SecretedFormSource | None`); skip silently.
  const sf =
    (accessibilityRisks?.secreted_form as
      | { present?: unknown; source?: unknown }
      | undefined) ?? undefined;
  if (sf && sf.present === true && typeof sf.source === "string") {
    out.secreted_form_source = sf.source;
  }
  return Object.keys(out).length > 0 ? out : undefined;
}
