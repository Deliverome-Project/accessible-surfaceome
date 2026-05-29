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
  | "protein_family"
  | "evidence_grade"
  | "evidence_density"
  | "ecd_accessibility_class"
  | "expression_level"
  | "expression_breadth"
  | "surface_specificity"
  | "co_receptor_dependency";

export type DdBoolKey =
  | "has_known_ligand"
  | "low_endogenous_expression"
  | "overexpression_surface_localization_observed"
  | "has_shed_form"
  | "has_secreted_form"
  | "has_epitope_masking"
  | "n_term_extracellular"
  | "c_term_extracellular";

/**
 * Provenance bucket used by the catalog filter panel to partition
 * deep-dive fields under the Deep Dive group:
 *
 * - `llm` — rollups the deep-dive *synthesizer* emits as its own
 *   classification (re-derived from the merged A1+A2 evidence ledger
 *   but still an LLM judgement).
 * - `deterministic` — tool-derived readouts (DeepTMHMM topology,
 *   ledger-count buckets, SURFACE-Bind MaSIF patch scoring). No LLM
 *   involvement; values are reproducible by re-running the tool.
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
    key: "surface_accessibility",
    label: "Accessibility",
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
    tooltipKey: "catalog_subcategory",
    provenance: "llm",
  },
  {
    key: "protein_family",
    label: "Family",
    values: ["receptor", "enzyme", "transporter", "miscellaneous"],
    tooltipKey: "catalog_protein_family",
    provenance: "llm",
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
    key: "evidence_density",
    label: "Evidence density",
    values: ["low", "moderate", "high"],
    tooltipKey: "catalog_evidence_density",
    provenance: "deterministic",
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
];

export const DD_BOOL_FIELDS: readonly DdBoolSpec[] = [
  {
    key: "has_known_ligand",
    label: "Known ligand",
    tooltipKey: "headline_risks",
    provenance: "llm",
  },
  {
    key: "low_endogenous_expression",
    label: "Low endogenous expression",
    tooltipKey: "headline_risks",
    provenance: "llm",
  },
  {
    key: "overexpression_surface_localization_observed",
    label: "OE + surface precedent",
    tooltipKey: "headline_risks",
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
];
