/*
 * Surfaceome record types.
 * ------------------------------------------------------------
 * Mirrors the `SurfaceomeRecord` Pydantic schema in the
 * `accessible-surfaceome` repo
 * (`src/accessible_surfaceome/tools/_shared/models.py`). Loose where
 * the source schema is open-ended (enum-other_label fields).
 *
 * v0.4.0 dropped these legacy v0.3.2 fields and renamed
 * `therapeutic_landscape` → `surface_engagement_validation`:
 *   * approved_drugs, clinical_trials, patent_disclosures
 *   * targetability.recommended_modalities
 *   * adc_properties, expression
 *   * deeptmhmm topology on IsoformAccessibility / OrthologRecord
 *
 * Legacy fields stay as `?` so a v0.3.2 record still parses; v0.4.0
 * records simply omit them. UI cards guard each access with `?.` and
 * fall back to empty / "—".
 */

export type Tier =
  | "validated"
  | "edge_case"
  | "not_recommended"
  | "preclinical"
  | "discovery";
export type Confidence = "high" | "medium" | "low";
export type Severity = "blocking" | "high" | "medium" | "low";
export type Direction = "supports" | "refutes" | "ambiguous";
export type TriageSignal =
  | "likely_accessible"
  | "possibly_accessible"
  | "unlikely"
  | "unknown";

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
  recommended_modalities?: Modality[];
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
  exposure_class?: string;
  extracellular_domain: {
    size_aa: number | null;
    domains: unknown[];
    accessibility: string;
    notes: string | null;
  };
  induced_presentation?: InducedPresentation[];
  surface_localization_assays?: SurfaceLocalizationAssay[];
  glycosylation?: unknown;
  shedding_documented?: unknown;
  db_comparison: DBComparison;
  cited_evidence_ids: string[];
}

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

export interface CoreceptorRequirement {
  partner_symbol: string;
  partner_uniprot_acc?: string | null;
  requirement_kind: string;
  requirement_kind_other_label?: string | null;
  description: string;
  cited_evidence_ids?: string[];
}

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

export interface PreclinicalEvidence {
  citation: string;
  modality?: string;
  modality_other_label?: string | null;
  finding_summary: string;
  cited_evidence_ids: string[];
}

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

export interface TherapeuticLandscape {
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
  cited_evidence_ids?: string[];
  confidence: Confidence;
  confidence_reasoning: string;
  contradiction_flag: boolean;
  rationale: string;
  model_path: string;

  expression?: Expression;
  adc_properties?: {
    internalization: string;
    estimated_copies_per_cell: number | null;
    expression_homogeneity: string;
    payload_compatibility_notes: string;
  };
  therapeutic_landscape?: TherapeuticLandscape;

  protein_features?: ProteinFeatures;
  surface_engagement_validation?: SurfaceEngagementValidation;
  isoform_accessibility?: IsoformAccessibility[];
  coreceptor_requirements?: CoreceptorRequirement[];
  orthology?: OrthologRecord[];
  triage_signal?: TriageSignal;

  evidence?: unknown[];
}
