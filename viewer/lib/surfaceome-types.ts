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

export type SurfaceAccessibility =
  | "high"
  | "moderate"
  | "low"
  | "uncertain"
  /** Confident negative call — the deep-dive evidence says this
   *  protein is NOT meaningfully at the surface. Mirrors the triage
   *  ``verdict="no"`` end of the scale. */
  | "no";
export type Confidence = "high" | "moderate" | "low";
export type StateDependence = "low" | "moderate" | "high" | "unclear";

/**
 * Co-receptor surface-expression dependency. Mirrors the Python
 * ``CoreceptorDependency`` Literal at
 * ``src/accessible_surfaceome/tools/_shared/models.py``.
 */
export type CoreceptorDependency =
  | "required"
  | "modulatory"
  | "none"
  | "unknown";

/**
 * Reason taxonomy emitted by both the triage agent and the deep-dive
 * synthesizer. The synthesizer re-derives this from A1+A2 evidence
 * (not blindly copied from the triage). Mirrors the Python
 * ``TriageReason`` Literal at
 * ``src/accessible_surfaceome/tools/_shared/models.py``.
 */
export type TriageReason =
  | "classical_surface_receptor"
  | "gpi_anchored"
  | "multipass_with_exposed_loops"
  | "extracellular_face_protein"
  | "stable_complex_partner"
  | "cell_state_induced"
  | "tissue_restricted_surface"
  | "lysosomal_exocytosis"
  | "dual_localization"
  | "stable_surface_attachment"
  | "cytoplasmic"
  | "nuclear"
  | "mitochondrial_internal"
  | "endomembrane_resident"
  | "nuclear_envelope"
  | "inner_leaflet_anchored"
  | "secreted_only"
  | "pmhc_only_intracellular"
  | "other";

/**
 * Architecture (how the protein sits in the membrane). Orthogonal
 * to the new ``ProteinFamily`` axis (function). The previous
 * ``ion_channel`` and ``transporter`` values were dropped in the
 * SURFACE-Bind alignment (Marchand 2026 PNAS) — those are now
 * ``ProteinFamily="transporter"`` paired with
 * ``Subcategory="multi_pass"``.
 */
export type Subcategory =
  | "single_pass_T1"
  | "single_pass_T2"
  | "multi_pass"
  | "GPCR"
  | "GPI_anchored"
  | "tetraspanin"
  | "other";

/**
 * Functional family. Mirrors SURFACE-Bind's four main classes
 * (Marchand et al. 2026 PNAS, doi:10.1073/pnas.2506269123). Dropped
 * their bookkeeping ``unclassified`` / ``unmatched`` because those
 * reflect their mapping-pipeline state, not biology.
 */
export type ProteinFamily =
  | "receptor"
  | "enzyme"
  | "transporter"
  | "miscellaneous";

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

/**
 * Headline risks — slimmed from 11 → 5 after the post-design
 * redundancy audit. Each remaining value names a load-bearing risk
 * that isn't easily reconstructed from another structured field.
 *
 * Removed values + where their signal lives now:
 *   * ``ecd_too_small`` → ``filters.ecd_accessibility_class``
 *   * ``restricted_subdomain`` → ``accessibility_risks.restricted_subdomain.present``
 *   * ``antibody_validation_weak`` → ``surface_evidence.evidence_grade`` +
 *     per-row ``AntibodyRef.validation_strength``
 *   * ``low_endogenous_expression`` → derived
 *     ``filters.low_endogenous_expression``
 *   * ``ligand_unknown`` → ``filters.has_known_ligand`` (it's an
 *     orphan-receptor status, not a risk)
 *   * ``other`` → forbidden; raise the risk in
 *     ``executive_summary.one_paragraph`` instead
 */
export type HeadlineRisk =
  | "shed_form"
  | "secreted_form"
  | "co_receptor"
  | "epitope_masked"
  | "isoform_decoy";

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
  /** Architecture axis (how the protein sits in the membrane). */
  subcategory: Subcategory;
  /** Function axis (SURFACE-Bind alignment). Orthogonal to
   *  ``subcategory``. Defaults to ``"miscellaneous"`` for back-compat
   *  with samples generated before the redesign. */
  protein_family: ProteinFamily;
  /** Synthesizer's re-derived reason for the surface call. Reuses
   *  the ``TriageReason`` enum so the catalog can filter by the same
   *  vocabulary regardless of which agent emitted the reason. The
   *  synth re-derives from A1+A2 evidence; sometimes overrides the
   *  triage's own reason. */
  surface_call_reason: TriageReason;
  headline_risks: HeadlineRisk[];
  cited_evidence_ids: string[];
}

export interface Filters {
  surface_accessibility: SurfaceAccessibility;
  confidence: Confidence;
  subcategory: Subcategory;
  /** Mirror of ``executive_summary.state_dependence`` — promoted to
   *  Filters so the catalog can D1-filter on state-conditional
   *  candidates without joining through ``executive_summary``. */
  state_dependence: StateDependence;
  /** Mirror of ``executive_summary.surface_call_reason``. */
  surface_call_reason: TriageReason;
  /** Functional family rolled up from ``executive_summary.protein_family``. */
  protein_family: ProteinFamily;
  evidence_grade: EvidenceGrade;
  ecd_accessibility_class: EcdAccessibilityClass;
  evidence_density: EvidenceDensity;
  expression_level: ExpressionLevel;
  expression_breadth: ExpressionBreadth;
  surface_specificity: SurfaceSpecificity;
  has_shed_form: boolean;
  has_secreted_form: boolean;
  requires_coreceptor_for_expression: boolean;
  /** Full 4-value CoreceptorDependency enum mirror of
   *  ``accessibility_risks.co_receptor_requirements.surface_expression_dependency``.
   *  Alongside the existing ``requires_coreceptor_for_expression`` bool,
   *  which flattens ``"modulatory"`` into ``false``. */
  co_receptor_dependency: CoreceptorDependency;
  has_epitope_masking: boolean;
  has_restricted_subdomain: boolean;
  mouse_ortholog_ecd_pct_identity: number;
  cyno_ortholog_ecd_pct_identity: number;
  /** Derived (NOT agent-emitted): orchestrator sets this to ``true``
   *  iff ``expression_level ∈ {"low", "absent"}``. Replaces the
   *  now-dropped ``HeadlineRisk.low_endogenous_expression`` value —
   *  one canonical signal, the catalog filters on it. */
  low_endogenous_expression: boolean;
  /** Orphan-receptor status. ``true`` (the default) when a validated
   *  endogenous ligand is documented. ``false`` for orphan GPCRs /
   *  nuclear receptors / kinases. Replaces the now-dropped
   *  ``HeadlineRisk.ligand_unknown`` value; tractability signal for
   *  the catalog. */
  has_known_ligand: boolean;
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

/**
 * Mirrors the Pydantic ``IsoformTopology`` class verbatim — the same
 * Python class is used in two slots: ``canonical_topology`` and each
 * entry of ``isoform_topologies[]``. The TS schema previously had a
 * separate ``CanonicalTopology`` interface that omitted
 * ``c_terminal_orientation``; that field has now been added here so
 * both slots type-check identically.
 */
export interface IsoformTopology {
  isoform_id: string;
  uniprot_acc: string;
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

/**
 * AFDB-derived structure metrics. Renamed from ``StructureBlock`` to
 * mirror the Pydantic ``StructureFeatures`` class name so the
 * TS↔Pydantic drift checker (``scripts/check_viewer_types_sync.py``)
 * doesn't trip on the rename.
 */
export interface StructureFeatures {
  afdb_id: string;
  /** AFDB model version (vN, where N is currently 4-6 across our
   *  cohort; widens as AFDB ships new releases). The placeholder
   *  path emits ``"unknown"`` when the API fetch failed. */
  afdb_version: string;
  ecd_mean_plddt: number;
  ecd_disordered_fraction: number;
  source: string;
  license: string;
  attribution: string;
  citations: string[];
}

/**
 * One MaSIF-scored targetable patch on a SURFACE-Bind protein.
 * Sourced from SURFACE-Bind's ``results_no_TM.csv`` per-site arrays.
 */
export interface SurfaceBindSite {
  site_id: number;
  /** Center residue of the MaSIF patch. The full per-patch residue
   *  list isn't published; viewer code can highlight ``anchor_residue``
   *  + nearby residues by computing contacts at render time. */
  anchor_residue: number;
  /** Buried surface area in Å². Compare to the 1,103 ± 244 Å² typical
   *  antibody-antigen interface (Ramaraj 2012). */
  area_a2: number;
  n_seeds_alpha: number;
  n_seeds_beta: number;
  /** Eisenberg-style hydrophobicity score. Positive = hydrophobic /
   *  lipid-facing-style; negative = polar / solvent-exposed-style. */
  hydrophobicity: number;
}

/**
 * SURFACE-Bind summary (Marchand et al. 2026 PNAS,
 * doi:10.1073/pnas.2506269123). The MaSIF / patch-based targetability
 * mapping. ``has_data=true`` means the protein appears in SURFACE-Bind's
 * authoritative ``results_no_TM.csv`` (~1,649 of the ~2,886 predicted
 * surface proteins); ``has_data=false`` means it dropped out via the
 * structural-quality filter.
 *
 * Seed counts split by binder backbone class: ``alpha`` = α-helical
 * binder candidates (3-helix bundles, minihelix designs), ``beta`` =
 * β-strand binder candidates (β-sheet scaffolds). The split lets
 * a reader pick the format that matches their downstream design
 * pipeline.
 */
export interface SurfaceBindFeatures {
  has_data: boolean;
  n_sites: number;
  n_seeds_alpha: number;
  n_seeds_beta: number;
  n_seeds_total: number;
  /** PDB-chain identifier the scoring was run against (typically "A"). */
  chain: string | null;
  /** Per-site detail. Empty when ``has_data=false`` OR when the protein
   *  is in SURFACE-Bind but no patches cleared the targetability
   *  threshold. */
  sites: SurfaceBindSite[];
  /** SURFACE-Bind's own family / sub-family — cross-check against our
   *  ``protein_family`` / ``subcategory``, NOT what they're derived from. */
  main_class: string | null;
  sub_class: string | null;
  /** Human-readable protein name from UniProt via SURFACE-Bind's join. */
  protein_name: string | null;
  /** PDB entries cross-referenced. Truncated in viewer (often 100+). */
  pdbs: string[];
  source: string;
  attribution: string;
  citation: string;
}

export interface DeterministicFeatures {
  canonical_topology: CanonicalTopology;
  isoform_topologies: IsoformTopology[];
  orthologs: OrthologSet;
  paralogs: ParalogEntry[];
  structure: StructureFeatures;
  surface_bind: SurfaceBindFeatures;
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
  /** Species the assay was run on. ``unspecified`` when the source
   *  doesn't say (most common); ``human`` is NOT the default —
   *  silently assuming human is how the old viewer mis-attributed
   *  mouse / rat expression measurements. */
  species?: Species;
  /** ``true`` when the agent inferred species from cell line /
   *  context (e.g. \"HEK293\" → human) rather than reading it
   *  verbatim. Lets the catalog filter out inferred-only rows. */
  species_inferred?: boolean;
  cited_evidence_ids: string[];
}

/** Species discriminator emitted by the v1.0.0 builders for any row
 *  that observed a measurement (expression, modulation, tissue).
 *  Mirrors the Pydantic ``Species`` Literal. */
export type Species =
  | "human"
  | "mouse"
  | "rat"
  | "macaque"
  | "dog"
  | "other"
  | "unspecified";

/**
 * Captures the construct details when a method panel measures an
 * exogenously expressed protein rather than the endogenous one. The
 * ``signal_peptide_source`` is load-bearing for the synthesizer's
 * evidence-grade rollup — a foreign (``exogenous``) SP forces
 * secretory-pathway entry regardless of the protein's native
 * trafficking, so the evidence is supportive-only rather than direct.
 */
export interface OverexpressionContext {
  /** ``native`` = construct uses the protein's own SP (or none was
   *  replaced); ``exogenous`` = a foreign leader was added (IgG
   *  kappa, preprotrypsin, BiP, melittin, …); ``unspecified`` =
   *  methods didn't mention the SP source. The synthesizer tiers
   *  ``exogenous`` below ``native``. */
  signal_peptide_source: "native" | "exogenous" | "unspecified";
  signal_peptide_detail: string | null;
  construct_tag: string | null;
  cell_line: string | null;
  cited_evidence_ids: string[];
}

export interface MethodObservation {
  method_family: MethodFamily;
  method_subclass: MethodSubclass;
  permeabilization: Permeabilization;
  expression_system: ExpressionSystem;
  /** Populated when ``expression_system`` is ``overexpression`` or
   *  ``mixed``. ``null`` for endogenous / knock-in / unknown
   *  systems. */
  overexpression: OverexpressionContext | null;
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
  species?: Species;
  species_inferred?: boolean;
  cited_evidence_ids: string[];
}

export interface CellTypeContext {
  cell_type: string;
  ontology_id: string;
  present_in_tissues: string[];
  species?: Species;
  species_inferred?: boolean;
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
  species?: Species;
  species_inferred?: boolean;
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

/**
 * The Pydantic ``SourceRef`` is the audit-grade ledger shape; the
 * legacy convenience fields below (``pmid``, ``doi``, ``pmcid``,
 * ``journal``, ``authors``, ``year``) are kept for back-compat with
 * the older record format that didn't carry the structured
 * ``source_type`` / ``source_id`` pair. Viewer consumers should
 * prefer ``source_id`` (parse the prefix to recover the ID type)
 * and fall back to the legacy fields only for older records — see
 * the parsing helper in
 * ``viewer/components/surfaceome/EvidenceDrawer/EvidenceDrawer.tsx``.
 */
export interface SourceRef {
  // ---- v1.0.0 audit-grade fields (mirror Pydantic) ----
  source_type?: string;
  /** Format: ``"PMID:12345678"`` / ``"DOI:10.xx/yy"`` /
   *  ``"UniProt:P12345"`` / ``"PDB:2ABC"``. */
  source_id?: string;
  pmc_id?: string | null;
  url?: string | null;
  title?: string | null;
  retrieved_at?: string;
  /** Hash of fetched text at retrieval — tamper detection;
   *  audit-only, viewer doesn't render. */
  content_sha256?: string;
  publication_type?: string;
  /** Retraction-watch hit at retrieval time. Reserved for a future
   *  red "Retracted" badge in the EvidenceDrawer. */
  is_retracted?: boolean;
  retraction_checked_at?: string;
  license?: string;

  // ---- legacy convenience fields (back-compat for v0.x records) ----
  pmid?: string | null;
  doi?: string | null;
  pmcid?: string | null;
  journal?: string | null;
  authors?: string | null;
  year?: number | null;
}

export interface EvidenceSpan {
  /** Verbatim quote anchored to the source location (Pydantic field
   * name is ``quote``, NOT ``text`` — the older TS type drifted). */
  quote: string;
  source: SourceRef;
  section: string;
  figure_or_table_id?: string | null;
  quote_sha256?: string;
  char_offset?: number;
  normalized_source_sha256?: string;
}

export interface Evidence {
  evidence_id: string;
  claim: string;
  claim_type: string;
  evidence_tier: EvidenceTier;
  confidence: number;
  /** Pydantic schema carries ``SourceRef`` per-span (each EvidenceSpan
   * has its own ``source``); the top-level ``source`` here is kept
   * optional for back-compat with earlier records. New consumers
   * should read ``spans[i].source`` directly. */
  source?: SourceRef;
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
