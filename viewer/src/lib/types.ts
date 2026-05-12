// Mirrors src/accessible_surfaceome/tools/_shared/models.py:SurfaceomeRecord.
// Loose where the Pydantic schema is open-ended (e.g. enum-other_label fields).
//
// v0.4.0 schema refocus dropped several fields from the legacy v0.3.2 record:
//   * approved_drugs, clinical_trials, patent_disclosures
//   * targetability.recommended_modalities
//   * adc_properties bucket
//   * expression bucket
//   * deeptmhmm topology fields on IsoformAccessibility / OrthologRecord
// and renamed therapeutic_landscape → surface_engagement_validation.
//
// These types keep the LEGACY fields as `?` optionals so v0.3.2 records still
// validate, and add the NEW v0.4.0 fields. The viewer components guard each
// access with `?.` + `??` fallbacks so a v0.4.0 record renders without
// reaching for fields that no longer exist.

export type Tier = "validated" | "edge_case" | "not_recommended";
export type Confidence = "high" | "medium" | "low";
export type Severity = "blocking" | "high" | "medium" | "low";
export type Direction = "supports" | "refutes" | "ambiguous";
export type TriageSignal =
  | "likely_accessible" | "possibly_accessible" | "unlikely" | "unknown";

export interface Gene {
  hgnc_symbol: string;
  hgnc_id: string;
  uniprot_acc: string;
  ncbi_gene_id: number;
  ensembl_gene: string;
}

export interface Modality {
  kind: string;
  kind_other_label: string | null;
  rationale: string;
}

export interface Targetability {
  tier: Tier;
  recommended_modalities?: Modality[];  // dropped in v0.4.0
  tldr: string;
  cited_evidence_ids: string[];
}

export interface DBComparison {
  surfy: boolean;
  cspa: boolean;
  uniprot_query: boolean;
  go: boolean;
  hpa: boolean;
  deeptmhmm: boolean;
  compartments: boolean;
  patent_handle: boolean;
  n_sources_voting_surface: number;
}

export interface SurfaceLocalizationAssay {
  assay_type: string;
  assay_type_other_label?: string | null;
  species: string;
  cell_type_or_line: string;
  direction: "supports_surface" | "refutes_surface" | "ambiguous";
  strength: "strong" | "moderate" | "weak";
  cited_evidence_ids: string[];
}

export interface InducedPresentation {
  context_kind: string;
  context_kind_other_label?: string | null;
  description: string;
  cited_evidence_ids: string[];
}

export interface SurfaceBiology {
  surface_status: string;
  topology: string;
  anchor_type: string;
  exposure_class?: string;  // v0.4.0
  extracellular_domain: {
    size_aa: number | null;
    domains: unknown[];
    accessibility: string;
    notes: string | null;
  };
  induced_presentation?: InducedPresentation[];  // v0.4.0
  surface_localization_assays?: SurfaceLocalizationAssay[];  // v0.4.0
  glycosylation: unknown;
  shedding_documented: unknown;
  db_comparison: DBComparison;
  cited_evidence_ids: string[];
}

// v0.4.0: per-gene structured biology features pre-injected by the orchestrator.
export interface ProteinFeatures {
  protein_length_aa?: number | null;
  tm_domain_count?: number | null;
  signal_peptide?: boolean | null;
  topology_string?: string | null;
  topology_source?: string;
  almen_main_class?: string | null;
  almen_sub_class?: string | null;
  cd_designation?: string | null;
  uniprot_keywords?: string[];
  pdb_ids?: string[];
  cspa_peptide_count?: number | null;
  hpa_antibody_available?: boolean | null;
  drugbank_ids?: string[];
  surfy_ml_score?: number | null;
  surfy_label_source?: string | null;
  provenance?: string | null;
}

// v0.4.0: per-isoform accessibility.
export interface IsoformAccessibility {
  isoform_id: string;
  name?: string | null;
  is_canonical?: boolean;
  length_aa?: number | null;
  surface_status?: string | null;
  exposure_class?: string;
  uniprot_isoform_specific_locations?: string[];
  differential_from_canonical?: boolean;
  rationale?: string;
  cited_evidence_ids?: string[];
}

// v0.4.0: surface-delivery co-receptor partner requirement.
export interface CoreceptorRequirement {
  partner_symbol: string;
  partner_uniprot_acc?: string | null;
  requirement_kind: string;
  requirement_kind_other_label?: string | null;
  description: string;
  cited_evidence_ids?: string[];
}

// v0.4.0: mouse / cyno ortholog identity + concordance.
export interface OrthologRecord {
  species: "mouse" | "cynomolgus";
  ortholog_uniprot_acc?: string | null;
  ortholog_gene_symbol?: string | null;
  ensembl_gene_id?: string | null;
  orthology_type?: string;
  percent_identity?: number | null;
  surface_status?: string | null;
  surface_concordant_with_human?: boolean | null;
  notes?: string;
  cited_evidence_ids?: string[];
}

// v0.4.0: surface_engagement_validation replaces therapeutic_landscape.
export interface SurfaceEngagementValidation {
  preclinical_evidence: PreclinicalEvidence[];
}

export interface Expression {
  tumor_indications: string[];
  tumor_specificity: string;
  normal_tissue_top: string[];
  normal_tissue_concerns: string[];
  summary: string;
  cited_evidence_ids: string[];
}

export interface PatentDisclosure {
  wo_number: string;
  title: string;
  applicant: string;
  modality: string;
  modality_other_label: string | null;
  priority_year: number;
  summary: string;
  cited_evidence_ids: string[];
}

export interface PreclinicalEvidence {
  citation: string;
  modality?: string;  // dropped in v0.4.0 — kept optional for legacy records
  modality_other_label?: string | null;
  finding_summary: string;
  cited_evidence_ids: string[];
}

export interface TherapeuticLandscape {  // legacy v0.3.2; v0.4.0 uses SurfaceEngagementValidation
  approved_drugs?: unknown[];
  clinical_trials?: unknown[];
  patent_disclosures?: PatentDisclosure[];
  preclinical_evidence?: PreclinicalEvidence[];
}

export interface RiskFlag {
  kind: string;
  kind_other_label: string | null;
  severity: Severity;
  description: string;
  cited_evidence_ids: string[];
}

export interface SurfaceomeRecord {
  schema_version: string;
  gene: Gene;
  canonical_isoform: string | null;
  isoform_flattened: boolean;
  targetability: Targetability;
  surface_biology: SurfaceBiology;
  risk_flags: RiskFlag[];
  primary_evidence_count: number;
  secondary_evidence_count: number;
  evidence_count: number;
  cited_evidence_ids?: string[];   // v0.3.2 carried this at top level
  confidence: Confidence;
  confidence_reasoning: string;
  contradiction_flag: boolean;
  rationale: string;
  model_path: string;

  // Legacy v0.3.2 fields — optional so v0.4.0 records still parse.
  expression?: Expression;
  adc_properties?: {
    internalization: string;
    estimated_copies_per_cell: number | null;
    expression_homogeneity: string;
    payload_compatibility_notes: string;
  };
  therapeutic_landscape?: TherapeuticLandscape;

  // v0.4.0 additions.
  protein_features?: ProteinFeatures;
  surface_engagement_validation?: SurfaceEngagementValidation;
  isoform_accessibility?: IsoformAccessibility[];
  coreceptor_requirements?: CoreceptorRequirement[];
  orthology?: OrthologRecord[];
  triage_signal?: TriageSignal;

  // The orchestrator persists the full evidence chain on the
  // SurfaceomeRecord (not just on EvidenceClaim drafts). Treat as
  // unknown blobs for now — render via the raw-record tab.
  evidence?: unknown[];
}
