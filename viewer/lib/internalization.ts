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

export type InternalizationLitConfidence = "high" | "moderate" | "low";
export const INTERNALIZATION_LIT_CONFIDENCES: readonly InternalizationLitConfidence[] = [
  "high",
  "moderate",
  "low",
] as const;

export type InternalizationModeKey = "basal" | "native" | "therapeutic" | "pathogen";
export const INTERNALIZATION_MODES: readonly {
  key: InternalizationModeKey;
  label: string;
}[] = [
  { key: "basal", label: "Basal (constitutive)" },
  { key: "native", label: "Native ligand" },
  { key: "therapeutic", label: "Therapeutic / Ab / ADC" },
  { key: "pathogen", label: "Pathogen entry" },
] as const;

export const INTERNALIZATION_LIT_MODE_GRADES: readonly InternalizationLitGrade[] = [
  "high",
  "moderate",
  "low",
  "no",
] as const;

export type InternalizationFate =
  | "degrades_lysosome"
  | "recycles"
  | "transcytoses"
  | "retained_intracellular"
  | "mixed"
  | "unknown";

export const INTERNALIZATION_FATES: readonly {
  key: Exclude<InternalizationFate, "unknown">;
  label: string;
}[] = [
  { key: "degrades_lysosome", label: "lysosomal degradation" },
  { key: "recycles", label: "recycling" },
  { key: "transcytoses", label: "transcytosis" },
  { key: "retained_intracellular", label: "intracellular retention" },
  { key: "mixed", label: "mixed" },
] as const;

export const INTERNALIZATION_FATE_LABELS: Record<string, string> = {
  degrades_lysosome: "lysosomal degradation",
  recycles: "recycling",
  transcytoses: "transcytosis",
  retained_intracellular: "intracellular retention",
  mixed: "mixed",
  unknown: "unknown",
};

export const INTERNALIZATION_BINDER_TYPES: readonly {
  key: string;
  label: string;
}[] = [
  { key: "antibody", label: "antibody" },
  { key: "adc", label: "ADC" },
  { key: "nanobody_or_fab", label: "nanobody / Fab" },
  { key: "bispecific_or_biparatopic", label: "bispecific / biparatopic" },
  { key: "nanoparticle_or_lnp", label: "LNP / nanoparticle" },
  { key: "native_ligand", label: "native ligand" },
  { key: "none_constitutive", label: "constitutive (no binder)" },
  { key: "small_molecule", label: "small molecule" },
  { key: "peptide", label: "peptide" },
  { key: "viral_or_toxin", label: "viral / toxin" },
] as const;

export const INTERNALIZATION_MECHANISMS: readonly {
  key: string;
  label: string;
}[] = [
  { key: "clathrin", label: "clathrin" },
  { key: "clathrin_independent", label: "clathrin-independent" },
  { key: "caveolin", label: "caveolin" },
  { key: "macropinocytosis", label: "macropinocytosis" },
] as const;

/** Slim catalog-level projection of the schema 0.3.0 literature internalization
 *  facets (Worker row_schema v12 `row.intl`). Optional keys are omitted on the
 *  wire when unknown / empty / false to keep /v1/catalog compact. */
export interface InternalizationLitFacets {
  conf?: InternalizationLitConfidence;
  basal?: InternalizationLitGrade;
  native?: InternalizationLitGrade;
  therapeutic?: InternalizationLitGrade;
  pathogen?: InternalizationLitGrade;
  fate?: InternalizationFate;
  primary?: boolean;
  quant?: boolean;
  fitted?: boolean;
  binders?: string[];
  mechs?: string[];
}
