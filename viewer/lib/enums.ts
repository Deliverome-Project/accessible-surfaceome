// Enum display helpers — a deliberately dependency-free leaf module.
//
// These live here (not in `lib/surfaceome.ts`) so that CLIENT components
// can import `prettyEnum` / `titleCase` / `tissueLabel` without dragging
// `lib/surfaceome.ts`'s top-level `node:fs` / `node:path` imports (its
// SSG/build-time record loaders) into the client bundle. Webpack can't
// tree-shake a `node:*` import out across a `"use client"` boundary, so
// importing anything from `surfaceome.ts` in a client component fails the
// browser build with `UnhandledSchemeError: Reading from "node:fs"`.
//
// `lib/surfaceome.ts` re-exports these for back-compat, so existing
// server-side importers keep working; client components should import
// from THIS module directly.

// Pretty labels for v1.0.0 enums. Keys must stay in sync with the
// string-literal unions in `surfaceome-types.ts`. Anything missing
// here falls through to `titleCase` (snake_case → Title Case), which
// is correct for most plain values.
const ENUM_MAP: Record<string, string> = {
  // Triage / accessibility
  likely_accessible: "Likely accessible",
  possibly_accessible: "Possibly accessible",
  unlikely: "Unlikely",
  unknown: "Unknown",
  high: "High",
  moderate: "Moderate",
  low: "Low",
  uncertain: "Uncertain",
  unclear: "Unclear",
  none: "None",
  negligible: "Negligible",

  // Subcategory
  single_pass_T1: "Single-pass type I",
  single_pass_T2: "Single-pass type II",
  multi_pass: "Multi-pass",
  GPCR: "GPCR",
  GPI_anchored: "GPI-anchored",
  tetraspanin: "Tetraspanin",
  ion_channel: "Ion channel",
  transporter: "Transporter",
  other: "Other",

  // Surface call reason (TriageReason in models.py — same 19-value
  // taxonomy used by surface_triage AND surfaceome_synthesizer for
  // surface_call_reason). titleCase fallback mangles a few of these
  // ("Pmhc Only Intracellular", "Gpi Anchored"); spell those out so
  // any future caller of prettyEnum(...) on a reason value gets the
  // right casing without each call site having to bring its own map.
  // Catalog chips override these via DD_ENUM_FIELDS.valueLabels for
  // its own tighter labels; this map is the global fallback. Five
  // CONTEXTUAL values + secreted_only already appear elsewhere in
  // this map (Modulation / Contradiction-types blocks below) so we
  // don't re-declare them here — TS rejects duplicate keys.
  classical_surface_receptor: "Classical surface receptor",
  gpi_anchored: "GPI-anchored",
  multipass_with_exposed_loops: "Multipass, exposed loops",
  extracellular_face_protein: "Extracellular-face protein",
  stable_complex_partner: "Stable complex partner",
  mitochondrial_internal: "Mitochondrial (internal)",
  endomembrane_resident: "Endomembrane-resident",
  nuclear_envelope: "Nuclear envelope",
  inner_leaflet_anchored: "Inner-leaflet anchored",
  pmhc_only_intracellular: "pMHC (intracellular only)",

  // Evidence grade / strength / density
  direct_multi_method: "Direct, multi-method",
  direct_single_method: "Direct, single method",
  supportive_but_indirect: "Supportive but indirect",
  conflicting: "Conflicting",
  weak: "Weak",
  strong: "Strong",
  inferred: "Inferred",

  // ECD class
  large: "Large",
  small: "Small",
  minimal: "Minimal",

  // Expression
  absent: "Absent",
  pan_tissue: "Pan-tissue",
  broad: "Broad",
  restricted: "Restricted",
  rare: "Rare",
  surface_dominant: "Surface-dominant",
  mixed: "Mixed",
  mostly_intracellular: "Mostly intracellular",

  // Topology
  extracellular: "Extracellular",
  cytoplasmic: "Cytoplasmic",
  one2one: "One-to-one",
  one2many: "One-to-many",
  many2many: "Many-to-many",

  // Methods
  flow_cytometry: "Flow cytometry",
  immunofluorescence: "Immunofluorescence",
  immunohistochemistry: "IHC",
  mass_spec: "Mass spec",
  biotinylation: "Biotinylation",
  glycoproteomics: "Glycoproteomics",
  proximity_labeling: "Proximity labeling",
  fractionation: "Fractionation",
  live_cell_flow: "Live-cell flow",
  fixed_cell_flow: "Fixed-cell flow",
  nonpermeabilized_IF: "Non-permeabilized IF",
  permeabilized_IF: "Permeabilized IF",
  IHC_membranous: "IHC (membranous)",
  surface_biotinylation: "Surface biotinylation",
  cell_surface_capture: "Cell-surface capture",
  N_glycoproteomics: "N-glycoproteomics",
  plasma_membrane_fractionation: "PM fractionation",
  whole_cell_proteomics: "Whole-cell proteomics",
  live_cell: "Live cell",
  nonpermeabilized: "Non-permeabilized",
  permeabilized: "Permeabilized",
  fixed_unknown: "Fixed (unknown)",

  // Antibody fields
  monoclonal: "Monoclonal",
  polyclonal: "Polyclonal",
  recombinant: "Recombinant",
  conformational: "Conformational",
  isoform_specific: "Isoform-specific",
  intracellular: "Intracellular",
  genetic_KO: "Genetic KO",
  siRNA_knockdown: "siRNA knockdown",
  CRISPR_KO: "CRISPR KO",
  orthogonal_method: "Orthogonal method",
  ip_ms_pulldown: "IP-MS pulldown",
  isoform_specific_KO: "Isoform-specific KO",
  overexpression_reference: "Overexpression reference",
  vendor_claim_only: "Vendor claim only",
  endogenous: "Endogenous",
  overexpression: "Overexpression",
  knock_in_tag: "Knock-in tag",

  // Accessibility relevance + claim type
  direct_surface_accessibility: "Direct surface accessibility",
  supports_surface_localization: "Supports surface localization",
  supports_membrane_association: "Supports membrane association",
  expression_only: "Expression only",
  weak_or_ambiguous: "Weak or ambiguous",
  surface_accessible: "Surface-accessible",
  plasma_membrane_localized: "Plasma membrane",
  membrane_fraction_enriched: "Membrane-fraction enriched",
  cell_junction_localized: "Cell junction",
  apical_or_luminal: "Apical / luminal",
  secreted_or_shed: "Secreted / shed",
  intracellular_pool: "Intracellular pool",

  // Sample types
  primary_human_tissue: "Primary tissue",
  primary_human_cell: "Primary cell",
  patient_sample: "Patient sample",
  patient_derived_organoid: "Patient-derived organoid",
  iPSC_derived: "iPSC-derived",
  established_cell_line: "Cell line",
  xenograft: "Xenograft",
  ex_vivo: "Ex vivo",

  // Compartments
  plasma_membrane: "Plasma membrane",
  endosome: "Endosome",
  lysosome: "Lysosome",
  ER: "ER",
  Golgi: "Golgi",
  mitochondrion: "Mitochondrion",
  nucleus: "Nucleus",
  cytosol: "Cytosol",
  secreted: "Secreted",
  secretory_vesicle: "Secretory vesicle",

  // Anatomical orientation
  blood_interstitial_facing: "Blood / interstitial-facing",
  luminal_facing: "Luminal-facing",
  apical: "Apical",
  basolateral: "Basolateral",
  lateral: "Lateral",
  junction_restricted: "Junction-restricted",
  ciliary: "Ciliary",
  synaptic: "Synaptic",
  matrix_facing: "Matrix-facing",
  favorable: "Favorable",
  context_dependent: "Context-dependent",

  // Modulation
  cell_state_induced: "Cell-state induced",
  tissue_restricted_surface: "Tissue-restricted surface",
  lysosomal_exocytosis: "Lysosomal exocytosis",
  dual_localization: "Dual localization",
  stable_surface_attachment: "Stable surface attachment",
  activation_induced: "Activation-induced",
  stress_induced: "Stress-induced",
  disease_state_induced: "Disease-state induced",
  polarization_dependent: "Polarization-dependent",
  post_translational_dependent: "Post-translational dependent",
  developmental_stage: "Developmental stage",
  ER_stress: "ER stress",
  heat_shock: "Heat shock",
  oxidative_stress: "Oxidative stress",
  DNA_damage_response: "DNA damage response",
  apoptosis: "Apoptosis",
  necroptosis: "Necroptosis",
  oncogenic_transformation: "Oncogenic transformation",
  infection_viral: "Viral infection",
  infection_bacterial: "Bacterial infection",
  immune_activation: "Immune activation",
  antigen_stimulation: "Antigen stimulation",
  cytokine_stimulation: "Cytokine stimulation",
  hypoxia: "Hypoxia",
  nutrient_deprivation: "Nutrient deprivation",
  hyperthermia: "Hyperthermia",
  mechanical_stress: "Mechanical stress",

  // Restricted lineage
  germline_reproductive: "Germline / reproductive",
  embryonic_developmental: "Embryonic / developmental",
  hematopoietic: "Hematopoietic",
  neural: "Neural",
  epithelial: "Epithelial",
  endothelial: "Endothelial",
  muscle: "Muscle",
  endocrine: "Endocrine",
  specialized_somatic_other: "Specialized somatic (other)",

  // Restricted subdomain / risks
  junctional: "Junctional",
  raft: "Lipid raft",

  // Co-receptor
  required: "Required",
  modulatory: "Modulatory",
  co_expression_only: "Co-expression only",
  trafficking: "Trafficking",
  knockout: "Knockout",

  // Headline-risk shorthand
  shed_form: "Shed form",
  secreted_form: "Secreted form",
  co_receptor: "Co-receptor",
  paralog_cross_reactivity: "Paralog cross-reactivity",
  ecd_too_small: "ECD too small",
  epitope_masked: "Epitope masked",
  isoform_decoy: "Isoform decoy",
  restricted_subdomain: "Restricted subdomain",
  low_endogenous_expression: "Low endogenous expression",
  antibody_validation_weak: "Weak Ab validation",
  ligand_unknown: "Ligand unknown",

  // Therapeutic stage
  approved_drug: "Approved drug",
  in_clinical_trials: "In clinical trials",
  preclinical_in_vivo: "Preclinical (in vivo)",
  none_documented: "None documented",

  // Contradiction types
  alternative_localization: "Alternative localization",
  secreted_only: "Secreted only",
  cell_line_specific_absence: "Cell-line-specific absence",
  antibody_conflict: "Antibody conflict",
  proteomics_conflict: "Proteomics conflict",
  isoform_conflict: "Isoform conflict",

  // Knowledge gaps
  no_literature: "No literature",
  outside_scope: "Outside scope",

  // Evidence tier
  primary: "Primary",
  secondary: "Secondary",
  tertiary: "Tertiary",

  // Secreted-form source
  alternative_splicing: "Alternative splicing",
  proteolytic: "Proteolytic",
  both: "Both",

  // Epitope masking mechanism
  glycan: "Glycan",
  partner: "Partner",
  cleaved: "Cleaved",
};

export function titleCase(s: string | null | undefined): string {
  return String(s ?? "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function prettyEnum(s: string | null | undefined): string {
  if (!s) return "—";
  return ENUM_MAP[s] ?? titleCase(s);
}

export function tissueLabel(t: string): string {
  return titleCase(t);
}
