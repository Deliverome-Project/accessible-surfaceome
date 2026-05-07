// Mirrors src/accessible_surfaceome/tools/_shared/models.py:SurfaceomeRecord.
// Loose where the Pydantic schema is open-ended (e.g. enum-other_label fields).

export type Tier = "validated" | "edge_case" | "not_recommended";
export type Confidence = "high" | "medium" | "low";
export type Severity = "blocking" | "high" | "medium" | "low";
export type Direction = "supports" | "refutes" | "ambiguous";

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
  recommended_modalities: Modality[];
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

export interface SurfaceBiology {
  surface_status: string;
  topology: string;
  anchor_type: string;
  extracellular_domain: {
    size_aa: number | null;
    domains: unknown[];
    accessibility: string;
    notes: string;
  };
  glycosylation: unknown;
  shedding_documented: unknown;
  db_comparison: DBComparison;
  cited_evidence_ids: string[];
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
  modality: string;
  modality_other_label: string | null;
  finding_summary: string;
  cited_evidence_ids: string[];
}

export interface TherapeuticLandscape {
  approved_drugs: unknown[];
  clinical_trials: unknown[];
  patent_disclosures: PatentDisclosure[];
  preclinical_evidence: PreclinicalEvidence[];
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
  expression: Expression;
  adc_properties: {
    internalization: string;
    estimated_copies_per_cell: number | null;
    expression_homogeneity: string;
    payload_compatibility_notes: string;
  };
  therapeutic_landscape: TherapeuticLandscape;
  risk_flags: RiskFlag[];
  primary_evidence_count: number;
  secondary_evidence_count: number;
  evidence_count: number;
  cited_evidence_ids: string[];
  confidence: Confidence;
  confidence_reasoning: string;
  contradiction_flag: boolean;
  rationale: string;
  model_path: string;
}
