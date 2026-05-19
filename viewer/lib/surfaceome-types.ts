/*
 * Surfaceome record types — schema v1.0.0.
 * ------------------------------------------------------------
 * Mirrors the planned v1.0.0 `SurfaceomeRecord` Pydantic schema
 * (docs/plans/2026-05-13-deep-dive-redesign-surface-accessibility.md).
 * The v1.0.0 record is split into:
 *
 *   * `deterministic_features` — orchestrator-prefetched blocks
 *     (AlphaFold DB, Ensembl Compara orthologs+paralogs, DeepTMHMM
 *     canonical+isoform topologies). Each block stamps source /
 *     license / attribution / tool_version so the viewer can build
 *     the Data Sources footer mechanically.
 *   * LLM-emitted synthesis sections (executive_summary, filters,
 *     surface_evidence, biological_context, accessibility_risks,
 *     knowledge_gaps, evidence ledger).
 *
 * Breaking change from v0.5.0: top-level fields, names, and enums
 * are entirely new. Per-gene JSONs that don't carry
 * `schema_version: "1.0.0"` won't typecheck and shouldn't be served.
 */

// ============================================================
// Identifier + cross-cutting enums
// ============================================================

export interface GeneIdentifier {
  hgnc_symbol: string;
  hgnc_id: string;
  uniprot_acc: string;
  ncbi_gene_id: number;
  ensembl_gene: string;
}

export type TriageSignal =
  | "likely_accessible"
  | "possibly_accessible"
  | "unlikely"
  | "unknown";

export type SurfaceAccessibility = "high" | "moderate" | "low" | "uncertain";
export type Confidence = "high" | "moderate" | "low";
export type StateDependence = "low" | "moderate" | "high" | "unclear";

export type Subcategory =
  | "single_pass_T1"
  | "single_pass_T2"
  | "multi_pass"
  | "GPCR"
  | "GPI_anchored"
  | "tetraspanin"
  | "ion_channel"
  | "transporter"
  | "other";

export type EvidenceGrade =
  | "direct_multi_method"
  | "direct_single_method"
  | "supportive_but_indirect"
  | "conflicting"
  | "weak";

export type EcdAccessibilityClass =
  | "large"
  | "moderate"
  | "small"
  | "minimal"
  | "none";

export type EvidenceDensity = "low" | "moderate" | "high";
export type ExpressionLevel = "high" | "moderate" | "low" | "absent";
export type ExpressionBreadth = "pan_tissue" | "broad" | "restricted" | "rare";
export type SurfaceSpecificity =
  | "surface_dominant"
  | "mixed"
  | "mostly_intracellular";

export type Severity = "high" | "moderate" | "low" | "unknown";
export type EvidenceStrength = "strong" | "moderate" | "weak" | "inferred";

export type Orientation = "extracellular" | "cytoplasmic";
export type OrthologyType = "one2one" | "one2many" | "many2many";

export type HeadlineRisk =
  | "shed_form"
  | "secreted_form"
  | "co_receptor"
  | "ecd_too_small"
  | "epitope_masked"
  | "isoform_decoy"
  | "restricted_subdomain"
  | "low_endogenous_expression"
  | "antibody_validation_weak"
  | "ligand_unknown"
  | "other";

export type TissueLevel =
  | "high"
  | "moderate"
  | "low"
  | "absent"
  | "mixed"
  | "unknown";

export type DiseaseContext =
  | "normal"
  | "tumor"
  | "tumor_adjacent"
  | "other_disease"
  | "mixed"
  | "unknown";

// ============================================================
// Executive summary + filter facets
// ============================================================

export interface ExecutiveSummary {
  one_paragraph: string;
  surface_accessibility: SurfaceAccessibility;
  evidence_grade_summary: EvidenceGrade;
  confidence: Confidence;
  state_dependence: StateDependence;
  subcategory: Subcategory;
  headline_risks: HeadlineRisk[];
  cited_evidence_ids: string[];
}

export interface Filters {
  surface_accessibility: SurfaceAccessibility;
  confidence: Confidence;
  subcategory: Subcategory;
  evidence_grade: EvidenceGrade;
  ecd_accessibility_class: EcdAccessibilityClass;
  evidence_density: EvidenceDensity;
  expression_level: ExpressionLevel;
  expression_breadth: ExpressionBreadth;
  surface_specificity: SurfaceSpecificity;
  has_shed_form: boolean;
  has_secreted_form: boolean;
  requires_coreceptor_for_expression: boolean;
  has_epitope_masking: boolean;
  has_restricted_subdomain: boolean;
  mouse_ortholog_ecd_pct_identity: number;
  cyno_ortholog_ecd_pct_identity: number;
  /** PR23 round 10: replaces the dropped LLM
   *  `has_paralog_cross_reactivity_risk` bool. Deterministic
   *  rollup `max(deterministic_features.paralogs[].ecd_pct_identity)`;
   *  `null` when the gene has no paralogs in Compara. Catalog
   *  readers filter on raw %identity instead of an LLM verdict. */
  max_paralog_ecd_pct_identity: number | null;
  n_term_extracellular: boolean;
  c_term_extracellular: boolean;
}

// ============================================================
// Deterministic features
// ============================================================

export interface CanonicalTopology {
  tm_helix_count: number;
  n_terminal_orientation: Orientation;
  c_terminal_orientation: Orientation;
  signal_peptide_length: number;
  ecd_length_residues: number;
  icd_length_residues: number;
  per_residue_topology: string;
  tool_version: string;
  retrieved_at: string;
}

export interface IsoformTopology {
  isoform_id: string;
  uniprot_acc: string;
  tm_helix_count: number;
  n_terminal_orientation: Orientation;
  signal_peptide_length: number;
  ecd_length_residues: number;
  icd_length_residues: number;
  per_residue_topology: string;
  tool_version: string;
  retrieved_at: string;
}

export interface OrthologEntry {
  is_canonical: boolean;
  isoform_id: string;
  ensembl_id: string;
  ortholog_uniprot_acc: string;
  ortholog_symbol: string;
  type: OrthologyType;
  // ECD identity is null when the human protein has no ECD to compare against
  // (inner-leaflet, soluble, GPI-anchored without surface loops). Full-length
  // identity is always available from Ensembl Compara BioMart.
  ecd_pct_identity_to_human_canonical: number | null;
  ecd_pct_similarity_to_human_canonical: number | null;
  full_length_pct_identity_to_human_canonical: number | null;
  ecd_length_residues: number;
  tm_helix_count: number;
  compara_version: string;
  retrieved_at: string;
}

export interface OrthologSet {
  mouse: OrthologEntry[];
  cynomolgus: OrthologEntry[];
}

export interface ParalogEntry {
  paralog_symbol: string;
  paralog_uniprot_acc: string;
  ecd_pct_identity: number;
  family_id: string;
  compara_version: string;
}

export interface StructureBlock {
  afdb_id: string;
  afdb_version: string;
  ecd_mean_plddt: number;
  ecd_disordered_fraction: number;
  source: string;
  license: string;
  attribution: string;
  citations: string[];
}

export interface DeterministicFeatures {
  canonical_topology: CanonicalTopology;
  isoform_topologies: IsoformTopology[];
  orthologs: OrthologSet;
  paralogs: ParalogEntry[];
  structure: StructureBlock;
}

// ============================================================
// Surface evidence
// ============================================================

export type MethodFamily =
  | "flow_cytometry"
  | "immunofluorescence"
  | "immunohistochemistry"
  | "mass_spec"
  | "biotinylation"
  | "glycoproteomics"
  | "proximity_labeling"
  | "fractionation"
  | "other";

export type MethodSubclass =
  | "live_cell_flow"
  | "fixed_cell_flow"
  | "nonpermeabilized_IF"
  | "permeabilized_IF"
  | "IHC_membranous"
  | "surface_biotinylation"
  | "cell_surface_capture"
  | "N_glycoproteomics"
  | "plasma_membrane_fractionation"
  | "whole_cell_proteomics"
  | "unknown";

export type Permeabilization =
  | "live_cell"
  | "nonpermeabilized"
  | "permeabilized"
  | "fixed_unknown"
  | "unknown";

export type ExpressionSystem =
  | "endogenous"
  | "overexpression"
  | "knock_in_tag"
  | "mixed"
  | "unknown";

export type AntibodyKind =
  | "monoclonal"
  | "polyclonal"
  | "recombinant"
  | "unknown";

export type AntibodyEpitopeRegion =
  | "extracellular"
  | "intracellular"
  | "conformational"
  | "isoform_specific"
  | "unknown";

export type ValidationStrategy =
  | "genetic_KO"
  | "siRNA_knockdown"
  | "CRISPR_KO"
  | "orthogonal_method"
  | "ip_ms_pulldown"
  | "isoform_specific_KO"
  | "overexpression_reference"
  | "vendor_claim_only"
  | "none"
  | "unknown";

export type ValidationStrength =
  | "strong"
  | "moderate"
  | "weak"
  | "none"
  | "unknown";

export type AccessibilityRelevance =
  | "direct_surface_accessibility"
  | "supports_surface_localization"
  | "supports_membrane_association"
  | "expression_only"
  | "weak_or_ambiguous";

export type SurfaceClaimType =
  | "surface_accessible"
  | "plasma_membrane_localized"
  | "membrane_fraction_enriched"
  | "cell_junction_localized"
  | "apical_or_luminal"
  | "secreted_or_shed"
  | "intracellular_pool"
  | "unclear";

export type SampleType =
  | "primary_human_tissue"
  | "primary_human_cell"
  | "patient_sample"
  | "patient_derived_organoid"
  | "iPSC_derived"
  | "established_cell_line"
  | "xenograft"
  | "ex_vivo"
  | "unknown";

export type MeasurementType =
  | "RNA"
  | "bulk_protein"
  | "IHC_protein"
  | "single_cell_RNA"
  | "unknown";

export type TherapeuticStage =
  | "approved_drug"
  | "in_clinical_trials"
  | "preclinical_in_vivo"
  | "none_documented"
  | "unknown";

export type ContradictionType =
  | "intracellular_pool"
  | "alternative_localization"
  | "secreted_only"
  | "cell_line_specific_absence"
  | "antibody_conflict"
  | "proteomics_conflict"
  | "isoform_conflict"
  | "other";

export type ContradictionSeverity = "high" | "moderate" | "low" | "unclear";

export interface AntibodyRef {
  name: string;
  clone: string | null;
  vendor: string | null;
  catalog: string | null;
  rrid: string | null;
  monoclonal_or_polyclonal: AntibodyKind;
  antibody_epitope_region: AntibodyEpitopeRegion;
  validation_strategy: ValidationStrategy;
  validation_strength: ValidationStrength;
  cross_reactivity_notes: string | null;
}

export interface ExpressionObservation {
  context: string;
  sample_type: SampleType;
  level: ExpressionLevel;
  cited_evidence_ids: string[];
}

export interface MethodObservation {
  method_family: MethodFamily;
  method_subclass: MethodSubclass;
  permeabilization: Permeabilization;
  expression_system: ExpressionSystem;
  antibodies: AntibodyRef[];
  accessibility_relevance: AccessibilityRelevance;
  surface_claim_type: SurfaceClaimType;
  expression_observations: ExpressionObservation[];
  cited_evidence_ids: string[];
}

export interface NonSurfaceExpression {
  context: string;
  sample_type: SampleType;
  measurement_type: MeasurementType;
  level: ExpressionLevel;
  cited_evidence_ids: string[];
}

export interface TherapeuticEngagement {
  highest_stage: TherapeuticStage;
  description: string;
  surface_form_rationale: string;
  cited_evidence_ids: string[];
}

export interface Contradiction {
  claim: string;
  contradiction_type: ContradictionType;
  severity_for_surface_accessibility: ContradictionSeverity;
  likely_explanation: string | null;
  cited_evidence_ids: string[];
}

export interface SurfaceEvidence {
  evidence_grade: EvidenceGrade;
  grade_rationale: string;
  methods: MethodObservation[];
  non_surface_expression: NonSurfaceExpression[];
  therapeutic_engagement: TherapeuticEngagement | null;
  contradicting_evidence: Contradiction[];
}

// ============================================================
// Biological context
// ============================================================

export type Compartment =
  | "plasma_membrane"
  | "endosome"
  | "lysosome"
  | "ER"
  | "Golgi"
  | "mitochondrion"
  | "nucleus"
  | "cytosol"
  | "secreted"
  | "other";

export type AnatomicalOrientation =
  | "blood_interstitial_facing"
  | "luminal_facing"
  | "apical"
  | "basolateral"
  | "lateral"
  | "junction_restricted"
  | "ciliary"
  | "synaptic"
  | "matrix_facing"
  | "unknown";

export type AccessibilityImplication =
  | "favorable"
  | "restricted"
  | "context_dependent"
  | "unclear";

export type ModulationCategory =
  | "cell_state_induced"
  | "tissue_restricted_surface"
  | "lysosomal_exocytosis"
  | "dual_localization"
  | "stable_surface_attachment"
  | "activation_induced"
  | "stress_induced"
  | "disease_state_induced"
  | "polarization_dependent"
  | "post_translational_dependent"
  | "developmental_stage"
  | "none"
  | "other"
  | "unknown";

export type CellStateTrigger =
  | "ER_stress"
  | "heat_shock"
  | "oxidative_stress"
  | "DNA_damage_response"
  | "apoptosis"
  | "necroptosis"
  | "oncogenic_transformation"
  | "infection_viral"
  | "infection_bacterial"
  | "immune_activation"
  | "antigen_stimulation"
  | "cytokine_stimulation"
  | "hypoxia"
  | "nutrient_deprivation"
  | "hyperthermia"
  | "mechanical_stress"
  | "other"
  | "unknown";

export type RestrictedLineage =
  | "germline_reproductive"
  | "embryonic_developmental"
  | "hematopoietic"
  | "neural"
  | "epithelial"
  | "endothelial"
  | "muscle"
  | "endocrine"
  | "specialized_somatic_other"
  | "other"
  | "unknown";

export type DualLocPartnerCompartment =
  | "ER"
  | "Golgi"
  | "endosome"
  | "lysosome"
  | "mitochondrion"
  | "nucleus"
  | "cytosol"
  | "secretory_vesicle"
  | "other"
  | "unknown";

export interface TissueContext {
  tissue: string;
  /** Six-level expression-level enum (upgraded from boolean in
   *  PR23 round 5 — `mixed` covers tissues with heterogeneous
   *  per-cell-type levels, `unknown` is the default when no
   *  evidence speaks to it). */
  present: TissueLevel;
  /** New disease-context axis — same tissue can appear twice
   *  (normal vs tumor) with different `present` levels. Obesity
   *  / inflammation / etc. fall under `other_disease`. */
  disease_context: DiseaseContext;
  cell_types: string[];
  cell_states: string[];
  cited_evidence_ids: string[];
}

export interface CellTypeContext {
  cell_type: string;
  ontology_id: string;
  present_in_tissues: string[];
  cited_evidence_ids: string[];
}

export interface StateContext {
  state: string;
  descriptor: string;
  cited_evidence_ids: string[];
}

export interface DualLocalization {
  compartment: Compartment;
  fraction_estimate: number | null;
  condition: string | null;
  cited_evidence_ids: string[];
}

export interface MembraneSubdomain {
  subdomain: string;
  cited_evidence_ids: string[];
}

export interface SubcellularLocalization {
  primary_compartment: Compartment;
  dual_localization: DualLocalization[];
  membrane_subdomains: MembraneSubdomain[];
}

export interface AnatomicalAccessibilityObservation {
  context: string;
  orientation: AnatomicalOrientation;
  accessibility_implication: AccessibilityImplication;
  rationale: string;
  cited_evidence_ids: string[];
}

export interface AccessibilityModulationObservation {
  category: ModulationCategory;
  category_other_label: string | null;
  cell_state_trigger: CellStateTrigger | null;
  restricted_lineage: RestrictedLineage | null;
  dual_loc_partner_compartment: DualLocPartnerCompartment | null;
  baseline_context: string;
  modulating_state: string;
  change: string;
  accessibility_implication: string;
  cited_evidence_ids: string[];
}

export interface BiologicalContext {
  tissues: TissueContext[];
  cell_types: CellTypeContext[];
  cell_states: StateContext[];
  subcellular_localization: SubcellularLocalization;
  anatomical_accessibility: AnatomicalAccessibilityObservation[];
  accessibility_modulation: AccessibilityModulationObservation[];
}

// ============================================================
// Accessibility risks
// ------------------------------------------------------------
// PR23 round 10 dropped the LLM `paralog_assessment: list[ParalogRisk]`
// block entirely. Per-antibody cross-reactivity behavior is captured
// in `AntibodyRef.cross_reactivity_notes` (§1 surface evidence);
// the gene-family prior is captured by the deterministic
// `filters.max_paralog_ecd_pct_identity` rollup. The §4 Paralogs
// card now renders the Compara table only.
// ============================================================

export interface ShedForm {
  present: boolean;
  severity: Severity;
  evidence_strength: EvidenceStrength;
  mechanism: string | null;
  sheddase_if_known: string | null;
  cited_evidence_ids: string[];
}

export type SecretedSource =
  | "alternative_splicing"
  | "proteolytic"
  | "both"
  | "unknown";

export interface SecretedForm {
  present: boolean;
  severity: Severity;
  evidence_strength: EvidenceStrength;
  ratio_to_membrane: number | null;
  source: SecretedSource | null;
  cited_evidence_ids: string[];
}

export type RestrictedSubdomainKind =
  | "apical"
  | "junctional"
  | "ciliary"
  | "synaptic"
  | "raft"
  | "basolateral"
  | "other"
  | "unknown";

export interface RestrictedSubdomain {
  present: boolean;
  domain: RestrictedSubdomainKind;
  severity: Severity;
  evidence_strength: EvidenceStrength;
  rationale: string;
  cited_evidence_ids: string[];
}

export type CoReceptorDependency = "required" | "modulatory" | "none" | "unknown";
export type CoReceptorEvidenceBasis =
  | "co_expression_only"
  | "trafficking"
  | "knockout"
  | "mixed";

export interface CoReceptorRequirements {
  surface_expression_dependency: CoReceptorDependency;
  partners: string[];
  evidence_basis: CoReceptorEvidenceBasis;
  rationale: string;
  cited_evidence_ids: string[];
}

export interface EcdSizeAssessment {
  ecd_accessibility_class: EcdAccessibilityClass;
  rationale: string;
  cited_evidence_ids: string[];
}

export type EpitopeMaskingMechanism =
  | "glycan"
  | "partner"
  | "conformational"
  | "cleaved"
  | "none";

export type EpitopeMaskingSeverity = "high" | "moderate" | "low" | "none";

export interface EpitopeMasking {
  /** PR23 round 6: upgraded from a single value to a list so
   *  multi-mechanism cases (GRP78: glycan + partner; GPR75:
   *  glycan + conformational) don't collapse to one value. Empty
   *  list means no mechanism documented; `["none"]` is the
   *  explicit "no masking" call. */
  mechanism: EpitopeMaskingMechanism[];
  severity: EpitopeMaskingSeverity;
  evidence_strength: EvidenceStrength;
  rationale: string;
  cited_evidence_ids: string[];
}

export interface AccessibilityRisks {
  shed_form: ShedForm;
  secreted_form: SecretedForm;
  restricted_subdomain: RestrictedSubdomain;
  co_receptor_requirements: CoReceptorRequirements;
  ecd_size_assessment: EcdSizeAssessment;
  epitope_masking: EpitopeMasking;
}

// ============================================================
// Evidence ledger
// ------------------------------------------------------------
// PR23 round 5: the standalone `knowledge_gaps` block was
// dropped. Uncertainty signal now flows through
// `contradicting_evidence` (literature conflicts),
// `confidence` + `confidence_reasoning` (overall uncertainty,
// max 600 chars), `evidence_grade` + `grade_rationale`
// (evidence quality), and per-section `rationale` fields.
// ============================================================

export type EvidenceTier = "primary" | "secondary" | "tertiary";

export interface SourceRef {
  pmid?: string | null;
  doi?: string | null;
  pmcid?: string | null;
  url?: string | null;
  journal?: string | null;
  title?: string | null;
  authors?: string | null;
  year?: number | null;
}

export interface EvidenceSpan {
  text: string;
  start?: number | null;
  end?: number | null;
}

export interface Evidence {
  evidence_id: string;
  claim: string;
  claim_type: string;
  evidence_tier: EvidenceTier;
  confidence: number;
  source: SourceRef;
  spans: EvidenceSpan[];
  entailment_verified: boolean;
}

export interface SearchEntry {
  query: string;
  count?: number;
  notes?: string | null;
}

// ============================================================
// Top-level record
// ============================================================

export interface SurfaceomeRecord {
  schema_version: "1.0.0";
  gene: GeneIdentifier;
  triage_signal: TriageSignal;
  executive_summary: ExecutiveSummary;
  filters: Filters;
  deterministic_features: DeterministicFeatures;
  surface_evidence: SurfaceEvidence;
  biological_context: BiologicalContext;
  accessibility_risks: AccessibilityRisks;
  evidence: Evidence[];
  search_log: SearchEntry[];
  confidence: number;
  /** Free-text justification for the top-level confidence value.
   *  PR23 round 9 constraint: max 600 chars; required when
   *  confidence != "high" (validator-enforced). */
  confidence_reasoning: string;
  /** Record-assembly time (renamed from `generated_at` in
   *  PR23 round 9 for explicit contrast with the nested
   *  `retrieved_at` fields on each deterministic-feature block,
   *  which capture tool-fetch time). */
  record_generated_at: string;
  model_path: string;
}


// ---------------------------------------------------------------------------
// Benchmark matrix — shape of /v1/benchmark/matrix from the public Worker.
// Renders at /benchmark/ as the 147-gene table with all four prompt
// variants per model laid out flat (one column per model × variant cell),
// the same five DB columns the homepage CatalogTable shows, and a
// row-expand reveal of each cell's verdict reasoning.
// ---------------------------------------------------------------------------

export type BenchmarkSource =
  | "uniprot"
  | "go"
  | "surfy"
  | "cspa"
  | "hpa";

export interface BenchmarkVariantResult {
  verdict: string | null;
  reason: string | null;
  confidence: string | null;
  key_uncertainty: string | null;
  /** Per-call free-text reasoning the agent emitted alongside the
   *  verdict. Shown in the row-expand reveal so readers can audit
   *  any specific (gene, model, variant) call's logic. */
  reasoning: string | null;
  correct: number | null;
  latency_s: number | null;
  n_web_searches: number | null;
  created_at: string | null;
  error: string | null;
  cost_usd?: number | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  cache_creation_tokens?: number | null;
  cache_read_tokens?: number | null;
}

export interface BenchmarkRow {
  gene_symbol: string;
  uniprot_acc: string;
  class: string;
  truth_verdict: "yes" | "contextual" | "no" | string;
  truth_signal: string;
  truth_reason: string;
  db: Record<BenchmarkSource, 0 | 1> | null;
  n_db_surface: number;
  /** model-id → variant-name → run result (or null for a missing cell). */
  verdicts: Record<string, Record<string, BenchmarkVariantResult | null>>;
}

export interface BenchmarkMatrix {
  bench_version: string | null;
  universe_version: string | null;
  generated_at?: string;
  sources: BenchmarkSource[];
  models: string[];
  /** All prompt variants in display order — every one renders as its
   *  own column on the page. */
  variants: string[];
  /** Optional hint for consumers that want to highlight one variant
   *  visually (e.g. emboss the column header). */
  headline_variant: string;
  n_genes: number;
  rows: BenchmarkRow[];
}
