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
 * SURFACE-Bind alignment (Balbi et al 2026, PMID 41604262) — those are now
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
 * (Balbi et al 2026, PMID 41604262). Dropped
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
  /** ONE sentence on WHEN and WHERE the protein is surface-accessible — the
   *  load-bearing §03 headline (A1.7). Optional for pre-A1.7 records. */
  accessibility_context_summary?: string;
  surface_accessibility: SurfaceAccessibility;
  evidence_grade_summary: EvidenceGrade;
  confidence: Confidence;
  state_dependence: StateDependence;
  /** Architecture axis (how the protein sits in the membrane). */
  subcategory: Subcategory;
  /** Function axis (SURFACE-Bind alignment), the model's high-level call.
   *  Orthogonal to ``subcategory``. Named ``llm_family`` to distinguish it
   *  from the deterministic ``hgnc_gene_groups`` / ``uniprot_family`` tags.
   *  Defaults to ``"miscellaneous"`` for back-compat with samples generated
   *  before the redesign. */
  llm_family: ProteinFamily;
  /** Deterministic, curator-assigned family tags attached by the
   *  orchestrator from the resolved ``IdentifierBundle`` — NOT model
   *  output. ``hgnc_gene_groups`` is HGNC's ``gene_group`` list;
   *  ``uniprot_family`` is the parsed UniProt SIMILARITY family. They
   *  sit beside ``llm_family`` so the reader can cross-check the
   *  model's high-level call against registry / curator ground truth.
   *  Both may be empty / null for genes the registries don't classify. */
  hgnc_gene_groups: string[];
  uniprot_family: string | null;
  /** Synthesizer's re-derived reason for the surface call. Reuses
   *  the ``TriageReason`` enum so the catalog can filter by the same
   *  vocabulary regardless of which agent emitted the reason. The
   *  synth re-derives from A1+A2 evidence; sometimes overrides the
   *  triage's own reason. */
  surface_call_reason: TriageReason;
  headline_risks: HeadlineRisk[];
  cited_evidence_ids: string[];
}

/** Coarse induction-context bucket for the catalog ``induction_trigger``
 *  filter — the dominant CellStateTrigger across a record's
 *  accessibility_modulation rows, grouped so the catalog can ask "show me
 *  stimulus-induced surface candidates" at one level instead of 18. Mirrors
 *  the Pydantic ``InductionTrigger`` Literal. */
export type InductionTrigger =
  | "none"
  | "oncogenic"
  | "immune"
  | "stress_hypoxia"
  | "cell_death"
  | "infection"
  | "other";

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
  /** Functional family rolled up from ``executive_summary.llm_family``. */
  llm_family: ProteinFamily;
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
  /** Stance-map counts (5b.8) derived from
   *  ``surface_evidence.claim_stances`` by the orchestrator. Lets the
   *  catalog distinguish "conflicting grade with 1 contradiction →
   *  artifact-suspect" from "≥3 contradictions → real disagreement"
   *  without re-parsing grade_rationale prose. Defaults to 0 — old
   *  records (no stance map emitted) read as 0. */
  n_supporting_claims_high_weight: number;
  n_contradicting_claims_high_weight: number;
  /** Derived from ``surface_evidence.methods[]`` — true iff any
   *  MethodObservation has expression_system ∈ {overexpression, mixed}
   *  AND accessibility_relevance ∈ {direct_surface_accessibility,
   *  supports_surface_localization}. Signals "the gene has been shown
   *  to surface-localize in an OE context" — useful for filtering
   *  targets amenable to OE-based validation experiments. */
  overexpression_surface_localization_observed: boolean;
  /** Deep-block rollups promoted to top-level catalog facets — all
   *  deterministic, derived by the orchestrator in ``_derive_filters``.
   *  ``tumor_associated``: ≥1 ``biological_context.expression`` row in a
   *  tumor / tumor-adjacent context. ``induction_trigger``: dominant
   *  CellStateTrigger across ``accessibility_modulation`` rows, bucketed
   *  (``"none"`` when no modulation row carries one). ``has_live_cell_
   *  surface_evidence``: ≥1 ``surface_evidence.methods`` row showing direct
   *  surface accessibility on live/intact cells in an endogenous context. */
  tumor_associated: boolean;
  induction_trigger: InductionTrigger;
  has_live_cell_surface_evidence: boolean;
  /** Per-chip rationales — every catalog chip carries its "why".
   *  Four mirror the synthesizer's LLM-emitted rollups; two are
   *  orchestrator-composed for the derived booleans. Optional: records
   *  emitted before this field existed (genes not yet re-annotated)
   *  omit them, and the viewer renders the chip without an expansion.
   *  The other five chips (co-receptor, restricted-subdomain, shed,
   *  secreted, epitope-masking) carry their rationale in the deep
   *  ``accessibility_risks`` blocks, not here. */
  expression_level_rationale?: string;
  expression_breadth_rationale?: string;
  surface_specificity_rationale?: string;
  has_known_ligand_rationale?: string;
  low_endogenous_expression_rationale?: string;
  overexpression_surface_localization_observed_rationale?: string;
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
  /** AA sequence the per_residue_topology indexes 1:1 (A1.8). */
  sequence?: string | null;
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
  /** AA sequence the per_residue_topology indexes 1:1 (A1.8). */
  sequence?: string | null;
  tool_version: string;
  retrieved_at: string;
  // Sequence identity of an alternative isoform against this protein's own
  // canonical sequence (BLOSUM62 global alignment over the shorter length).
  // Null on the canonical row itself and on records predating the identity
  // sweep; ecd_pct_identity_to_canonical is also null when the protein has no
  // extracellular residues (e.g. SRC — a GLOB intracellular kinase).
  full_length_pct_identity_to_canonical?: number | null;
  ecd_pct_identity_to_canonical?: number | null;
  ecd_pct_similarity_to_canonical?: number | null;
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
  /** Per-residue DeepTMHMM topology string for the ortholog's canonical
   *  isoform. Sourced from D1's ``topology_public`` filtered to
   *  cohort=``mouse_ortholog`` / ``cyno_ortholog``. Null when the
   *  topology cohort hasn't covered this ortholog yet; the
   *  IsoformsCard renders a "no topology" placeholder in that case. */
  per_residue_topology: string | null;
  /** DeepTMHMM categorical label: 'TM' | 'SP+TM' | 'SP' | 'BETA' |
   *  'GLOB'. Null when ``per_residue_topology`` is null. */
  deeptmhmm_label: string | null;
  /** Topology-projection provenance. When set
   *  (``"projected_from_human_canonical"``), per_residue_topology /
   *  tm_helix_count / ecd_length_residues above are the HUMAN canonical
   *  topology projected onto this ortholog via global alignment — not raw
   *  DeepTMHMM-on-ortholog (unreliable on truncated / padded cyno models).
   *  Optional for back-compat with records predating the projection. */
  topology_projection_source?: string | null;
  /** True when a human TM helix aligned entirely to a gap in the ortholog
   *  sequence (a truncated model): the helix is conserved by homology but
   *  physically absent from this model. Drives the gray "partial model"
   *  topology dot. ``n_tm_regions_absent`` is how many fell in gaps. */
  tm_absent_from_model?: boolean;
  n_tm_regions_absent?: number;
  /** AA sequence the per_residue_topology indexes 1:1 (A1.8). */
  sequence?: string | null;
}

export interface OrthologSet {
  mouse: OrthologEntry[];
  cynomolgus: OrthologEntry[];
  /** "Checked, none found" sentinel (mirrors SurfaceBindFeatures.has_data).
   *  `true` with empty mouse+cynomolgus = checked against Compara, no one2one
   *  ortholog exists. Absent/false on stub or pre-sentinel snapshots. */
  checked?: boolean;
}

/**
 * One within-species paralog (Ensembl Compara). `ecd_pct_identity` is
 * `null` for ECD-less proteins (inner-leaflet kinases like SRC, soluble
 * proteins, cytoplasmic enzymes) — there's no extracellular domain to
 * align. `full_length_pct_identity` is the whole-protein identity from
 * Compara/BioMart (same source as the ortholog full-length identity),
 * which IS populated for those proteins, so the IsoformsCard chip falls
 * back to it to still color the cross-reactivity risk tier (same ≥70 /
 * 50–70 / <50 cutoffs, keyed on whole-protein homology). Mirrors Python's
 * ``ParalogEntry`` (``ecd_pct_identity`` / ``full_length_pct_identity``:
 * ``float | None``).
 */
export interface ParalogEntry {
  paralog_symbol: string;
  paralog_uniprot_acc: string;
  ecd_pct_identity: number | null;
  full_length_pct_identity: number | null;
  family_id: string;
  compara_version: string;
  // A1.9: topology + sequence populated only for CLOSE paralogs (>=80% ECD
  // identity) — null for far/ECD-less paralogs and pre-population records,
  // which avoids the all-GLOB noise that motivated the earlier revert.
  per_residue_topology?: string | null;
  tm_helix_count?: number | null;
  ecd_length_residues?: number | null;
  sequence?: string | null;
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
  // AlphaFold model download links from the AFDB prediction API — the
  // non-derivable bits (the working URL needs the current model version).
  // Null on the placeholder path (AFDB unreachable) and on older records.
  model_cif_url?: string | null;
  model_pdb_url?: string | null;
  model_pae_url?: string | null;
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
 * SURFACE-Bind summary (Balbi et al 2026, PMID 41604262).
 * The MaSIF / patch-based targetability
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
/** The single best experimental structure (highest coverage × resolution),
 *  ranked from `pdbs` via PDBe SIFTS (A1.10). */
export interface RepresentativeStructure {
  pdb_id: string;
  chain: string | null;
  method: string | null;
  resolution_angstrom: number | null;
  coverage_fraction: number | null;
  residue_start: number | null;
  residue_end: number | null;
  source: string;
}

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
   *  ``llm_family`` / ``subcategory``, NOT what they're derived from. */
  main_class: string | null;
  sub_class: string | null;
  /** Human-readable protein name from UniProt via SURFACE-Bind's join. */
  protein_name: string | null;
  /** PDB entries cross-referenced. Truncated in viewer (often 100+). */
  pdbs: string[];
  /** The one best experimental structure ranked from `pdbs` (A1.10). */
  representative_structure?: RepresentativeStructure | null;
  source: string;
  attribution: string;
  citation: string;
}

/**
 * Schweke et al. 2024 AF2 homo-oligomer prediction (PMID 38325366).
 * Positives-only refset (~1,049 of the v2 candidate-universe), so
 * `is_homo_oligomer=false` means "not in Schweke's positives" rather than
 * "AF2 explicitly says monomer" — known under-call on big multi-pass
 * channels (KCNQ1, KCNMA1) and ligand/covalent dimers (EGFR, INSR).
 */
export interface HomoOligomerizationFeatures {
  /** `false` is the explicit "not in Schweke's positive refset" signal —
   *  block is always present so the catalog distinguishes "absent from
   *  Schweke" from "in Schweke but no usable model". */
  is_homo_oligomer: boolean;
  /** Cyclic-symmetry order N (2 for dimer, 3–13 for AnAnaS-reconstructed
   *  full complex). Null when `is_homo_oligomer=false` or Schweke
   *  flagged a dimer but didn't reconstruct higher-order. */
  stoichiometry?: number | null;
  /** AF2 model rank (1..5) Schweke retained as canonical. The viewer
   *  uses this to construct the PDB asset URL ({ACC}_V1_{N}.pdb).
   *  Null when `is_homo_oligomer=false`. */
  af_model_num?: number | null;
  /** True iff Schweke's nodiso3 filter stripped the TM helix as a
   *  disconnected cluster — the predicted homomer is ECD-only.
   *  Important context for the epitope-masking prior. */
  is_ecd_only: boolean;
  /** True iff Schweke published a higher-order complex (c≥3) for this
   *  protein in addition to the dimer model. */
  has_higher_order_complex: boolean;
  /** PDB filename for the dimer model ({ACC}_V1_{N}.pdb). Null when
   *  is_homo_oligomer=false. */
  dimer_pdb_filename?: string | null;
  /** PDB filename for the higher-order complex
   *  ({ACC}_V1_{N}_c{stoichiometry}.pdb). Null for dimer-only entries. */
  complex_pdb_filename?: string | null;
  source: string;
  citation: string;
}

export interface DeterministicFeatures {
  canonical_topology: CanonicalTopology;
  isoform_topologies: IsoformTopology[];
  orthologs: OrthologSet;
  paralogs: ParalogEntry[];
  /** "Checked, none found" sentinels for the bare lists above (same rationale
   *  as OrthologSet.checked). `true` once the loader queried D1 even when the
   *  list is empty (genuine singleton / single-isoform gene). Optional for
   *  back-compat with pre-sentinel snapshots. */
  paralogs_checked?: boolean;
  isoform_topologies_checked?: boolean;
  structure: StructureFeatures;
  surface_bind: SurfaceBindFeatures;
  /** Schweke 2024 AF2 homo-oligomer prediction. Always present, with
   *  `is_homo_oligomer=false` as the explicit "not in the positive set"
   *  signal. Strong AF2-derived structural prior on the synthesizer's
   *  `epitope_masking.mechanism = "homo-oligomerization"` call. */
  homo_oligomerization: HomoOligomerizationFeatures;
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
  | "functional_surface_assay"
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

// Audit trail of A1 ledger claims the methods builder rejected at the
// inclusion stage as receptor-engagement-as-soluble-ligand evidence —
// e.g. HMGB1 binding TREM-1 on monocytes. The protein is the soluble
// partner; the TM partner is the membrane component. These describe
// biology, not surface accessibility of this protein. Parallel to
// `non_surface_expression`; empty for records emitted before the
// inclusion filter landed.
export interface ExcludedClaim {
  evidence_id: string;
  /** Short ≤240-char rationale naming the receptor / partner the protein
   *  was binding (e.g. "HMGB1 binding TREM-1 on monocytes — soluble
   *  ligand engagement, not surface anchoring of HMGB1"). */
  reason: string;
}

export interface Contradiction {
  claim: string;
  contradiction_type: ContradictionType;
  severity_for_surface_accessibility: ContradictionSeverity;
  likely_explanation: string | null;
  cited_evidence_ids: string[];
}

// Per-claim stance map (5b.8) — structured per-claim accounting that
// backs the evidence_grade verdict alongside the prose rationale.
// Each row names one EvidenceClaim id + its stance + weight. Drives the
// derived Filters.n_supporting_claims_high_weight /
// n_contradicting_claims_high_weight catalog filter fields.
export type ClaimStance =
  | "supports_surface"
  | "contradicts_surface"
  | "tangential"
  | "expression_only";

export type ClaimWeight = "high" | "moderate" | "low";

export interface ClaimStanceRow {
  claim_id: string;
  stance: ClaimStance;
  weight: ClaimWeight;
  /** Optional ≤120-char qualifier (e.g. "antibody from non-KO-validated paper"). */
  note: string | null;
}

export interface SurfaceEvidence {
  evidence_grade: EvidenceGrade;
  grade_rationale: string;
  /** Per-claim stance map; empty for records emitted before 5b.8. */
  claim_stances: ClaimStanceRow[];
  methods: MethodObservation[];
  non_surface_expression: NonSurfaceExpression[];
  contradicting_evidence: Contradiction[];
  /** Audit trail of A1 ledger claims rejected at the methods-builder
   *  inclusion stage as receptor-engagement-as-soluble-ligand evidence.
   *  Empty for records emitted before the inclusion filter landed. */
  excluded_as_ligand_engagement: ExcludedClaim[];
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

/** One (tissue × cell_type × disease_context) expression observation —
 *  the v2 unification of TissueContext + CellTypeContext. Self-describing:
 *  each row carries its own disease context + present level. */
export interface ExpressionRow {
  tissue: string;
  /** The specific cell type when named; null for a tissue-level row. */
  cell_type: string | null;
  present: TissueLevel;
  disease_context: DiseaseContext;
  /** Free-text specific disease (e.g. "clear-cell renal carcinoma"). */
  disease_label: string | null;
  cell_states: string[];
  species?: Species;
  species_inferred?: boolean;
  cited_evidence_ids: string[];
}

/** DEPRECATED (v1 only). Superseded by ExpressionRow; retained so v1
 *  records still type-check. */
export interface TissueContext {
  tissue: string;
  /** Optional cell-type narrowing for the tissue observation (e.g. a
   *  specific epithelial subtype). Older records omit it. */
  cell_type?: string | null;
  present: TissueLevel;
  disease_context: DiseaseContext;
  /** Specific disease name when `disease_context` can't name it on its own
   *  (e.g. "Fabry disease"). Optional — older records omit it. */
  disease_label?: string | null;
  cell_types: string[];
  cell_states: string[];
  species?: Species;
  species_inferred?: boolean;
  cited_evidence_ids: string[];
}

/** DEPRECATED (v1 only). Superseded by ExpressionRow. */
export interface CellTypeContext {
  cell_type: string;
  ontology_id: string;
  present_in_tissues: string[];
  /** Per-cell disease context / level / specific-disease label, so a
   *  cell-of-origin row is self-describing instead of inheriting from a
   *  paired tissue row. Optional — older records omit them. */
  disease_context?: DiseaseContext;
  present?: TissueLevel;
  disease_label?: string | null;
  species?: Species;
  species_inferred?: boolean;
  cited_evidence_ids: string[];
}

export interface DualLocalization {
  compartment: Compartment;
  fraction_estimate: number | null;
  condition: string | null;
  rationale: string;
  cited_evidence_ids: string[];
}

export interface MembraneSubdomain {
  subdomain: string;
  rationale: string;
  cited_evidence_ids: string[];
}

export interface SubcellularLocalization {
  primary_compartment: Compartment;
  rationale: string;
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
  /** Schema 2.5.0: both nullable. Contrast row has both set; single-
   *  context row (former cell_states block) has both null. */
  baseline_context: string | null;
  modulating_state: string | null;
  change: string;
  accessibility_implication: string;
  /** Up/down direction of the surface-pool change — orthogonal to the
   *  favorable/restricted verdict in `accessibility_implication`. Mirrors
   *  Pydantic's `direction: ModulationDirection = "unclear"` (always present). */
  direction: ModulationDirection;
  species?: Species;
  species_inferred?: boolean;
  cited_evidence_ids: string[];
}

export type ModulationDirection =
  | "increases"
  | "decreases"
  | "bidirectional"
  | "no_change"
  | "unclear";

export interface BiologicalContext {
  /** v2: one self-describing row per (tissue × cell_type × disease). */
  expression: ExpressionRow[];
  /** DEPRECATED (v1 only) — v2 leaves these empty. Schema 2.5.0
   *  retired ``cell_states`` entirely; single-context state observations
   *  now live in ``accessibility_modulation`` as rows with
   *  ``baseline_context: null`` + ``modulating_state: null``. */
  tissues: TissueContext[];
  cell_types: CellTypeContext[];
  subcellular_localization: SubcellularLocalization;
  anatomical_accessibility: AnatomicalAccessibilityObservation[];
  accessibility_modulation: AccessibilityModulationObservation[];
  /** A2 rollup — the A2 analog of SurfaceEvidence.evidence_grade: how
   *  well-characterized & internally consistent the A2 biological picture is
   *  (coverage × consistency across expression / localization / anatomical /
   *  modulation). */
  biological_context_grade: "rich" | "moderate" | "sparse" | "absent";
  grade_rationale: string;
  grade_cited_evidence_ids: string[];
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
  rationale: string;
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
  rationale: string;
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
  | "oligomerization"
  | "conformational"
  | "cleaved"
  | "none";

export type EpitopeMaskingSeverity = "high" | "moderate" | "low" | "none";

export interface EpitopeMasking {
  /** PR23 round 6: upgraded from a single value to a list so
   *  multi-mechanism cases (GRP78: glycan + partner; GPR75:
   *  glycan + conformational; CD81: partner + oligomerization)
   *  don't collapse to one value. `oligomerization` is the HOMO
   *  self-association axis (homodimer / homo-oligomer interface),
   *  distinct from `partner` (a second protein) and `conformational`
   *  (a monomer state). Empty list means no mechanism documented;
   *  `["none"]` is the explicit "no masking" call. */
  mechanism: EpitopeMaskingMechanism[];
  severity: EpitopeMaskingSeverity;
  evidence_strength: EvidenceStrength;
  rationale: string;
  cited_evidence_ids: string[];
}

/**
 * Risk-side view of the Schweke 2024 AF2 homo-oligomer prediction
 * (PMID 38325366), populated by the v2 orchestrator from
 * `deterministic_features.homo_oligomerization`. Rendered as a sibling
 * chip to `epitope_masking` so the reader can scan the deterministic
 * AF2 signal independently from the LLM-emitted masking mechanism.
 *
 * Severity is derived from cyclic-symmetry order N: `<=2` → `low`,
 * `3..7` → `moderate`, `8..24` → `high`, `null` → `unknown`. Optional
 * field — older records emitted before this chip existed validate
 * with `homo_oligomerization_prediction` absent.
 */
export interface HomoOligomerizationPredictionRisk {
  /** `true` iff Schweke flagged the protein in the positive refset.
   *  Mirrors `HomoOligomerizationFeatures.is_homo_oligomer`. */
  present: boolean;
  /** Cyclic-symmetry order N. Null when `present=false` or Schweke
   *  flagged a dimer but didn't reconstruct higher-order. */
  stoichiometry?: number | null;
  /** Derived from `stoichiometry` deterministically — the viewer
   *  reads this directly for the chip color. */
  severity: Severity;
  /** Schweke `nodiso3` flag: the predicted homomer is ECD-only.
   *  Important context — the soluble ECD IS the dimerizing surface. */
  is_ecd_only: boolean;
  /** Default `"Schweke 2024 (PMID 38325366)"`. */
  source: string;
  /** Empty by default — this is a deterministic AF2 prediction, not
   *  a literature-anchored claim. Kept for shape consistency with
   *  the other accessibility-risk blocks. */
  cited_evidence_ids: string[];
}

export interface AccessibilityRisks {
  shed_form: ShedForm;
  secreted_form: SecretedForm;
  restricted_subdomain: RestrictedSubdomain;
  co_receptor_requirements: CoReceptorRequirements;
  ecd_size_assessment: EcdSizeAssessment;
  epitope_masking: EpitopeMasking;
  /** Deterministic AF2 homo-oligomer prediction (Schweke 2024)
   *  rendered as a sibling chip to `epitope_masking`. Optional —
   *  null/absent on records emitted before this chip existed. */
  homo_oligomerization_prediction?: HomoOligomerizationPredictionRisk | null;
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
  /** Cross-planner duplicate marker. Populated by the orchestrator's
   *  post-promotion dedup pass when two ``Evidence`` records share
   *  the same ``(spans[0].source.source_id, spans[0].quote_sha256)``
   *  — i.e. A1 and A2 both extracted the same span from the same
   *  paper. Non-null = "this entry was folded onto the referenced
   *  canonical record". The duplicate IS kept in the ledger so
   *  per-builder citations still resolve to the exact id they used;
   *  the viewer's EvidenceLedgerCard collapses duplicates onto the
   *  canonical card so the reader sees ONE entry per unique source
   *  span (with both planner interpretations stacked). */
  duplicate_of?: string | null;
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
  /** The prompt corpus version active when this record was synthesized
   *  (e.g. ``"2.50.1"``). Default ``""`` for legacy records that pre-date
   *  the field. Used by the freshness dot + post-cohort forensic
   *  queries — joins the record to the prompt corpus that produced it
   *  without going through the D1 mirror column. */
  prompt_corpus_version: string;
  gene: GeneIdentifier;
  triage_signal: TriageSignal;
  /** The triage agent's prose justification for its verdict
   *  (``TriageRecord.verdict_reasoning``). Orchestrator-populated from
   *  the same triage record that derives ``triage_signal``; surfaced in
   *  the gene-header Triage row's "Reasoning" drawer. ``null`` when no
   *  triage record exists for the gene. */
  triage_reasoning: string | null;
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
  /** Layered annotation: CellxGene RNA enrichment.
   *  Embedded by ``scripts/embed_cellxgene_into_records.py`` AFTER
   *  the deep-dive synthesis (not a deep-dive output). Typed
   *  loosely as a dict here; the structured shape lives in
   *  ``viewer/lib/cellxgene-enrichment.ts`` as ``CellxGeneEnrichment``.
   *  ``null`` for records the cellxgene build hasn't covered yet. */
  cellxgene: Record<string, unknown> | null;
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
