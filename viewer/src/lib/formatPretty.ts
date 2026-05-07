export const titleCase = (s: string | null | undefined): string =>
  String(s || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

const ENUM_MAP: Record<string, string> = {
  tcr_mimic: "TCR-mimic mAb",
  tcr_t: "TCR-T",
  bispecific: "Bispecific (ImmTAC-style)",
  not_recommended: "Not recommended",
  edge_case: "Edge case",
  validated: "Validated",
  pan_tumor: "Pan-tumor",
  not_pm_associated: "Not PM-associated",
  mhc_presented_peptide: "MHC-presented peptide",
  absent: "Absent",
  present: "Present",
  rare_surface: "Rare surface",
  unknown: "Unknown",
  high: "High",
  medium: "Medium",
  low: "Low",
  blocking: "Blocking",
  non_internalizing: "Non-internalizing",
};

export const prettyEnum = (s: string | null | undefined): string => {
  if (!s) return "—";
  return ENUM_MAP[s] || titleCase(s);
};

export const tissueLabel = (t: string): string => titleCase(t);
