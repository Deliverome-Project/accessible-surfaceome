/*
 * Minimal SurfaceomeRecord fixtures for render tests.
 *
 * The full record schema is huge — these helpers build the smallest
 * possible record that satisfies ``SurfaceomeRecord``'s structural
 * shape, then let the test mutate the fields it cares about. The
 * fixture is intentionally minimal: missing fields would crash a
 * render, but every default lands at the "no documented signal"
 * end of every enum so a smoke test that uses the base fixture
 * exercises only the no-data path.
 */
import type { SurfaceomeRecord } from "../../lib/surfaceome-types";

/** Base record with every required block set to an empty / "no data"
 *  state. Spread it with overrides for the block under test. */
export function baseRecord(): SurfaceomeRecord {
  return {
    schema_version: "2.13.0",
    gene_symbol: "TESTGENE",
    uniprot_acc: "P00001",
    hgnc_id: "HGNC:1",
    reference_assembly: "GRCh38",
    evidence_ledger: [],
    community_notes: [],
    executive_summary: {
      one_paragraph: "",
      accessibility_context_summary: "",
      surface_call: "likely_accessible",
      headline_recommendation: "explore",
      cited_evidence_ids: [],
      confidence_overall: "moderate",
    },
    filters: {},
    triage: {},
    deterministic_features: { canonical_topology: { ecd_length_residues: 100 } },
    biological_context: {
      expression: [],
      tissues: [],
      cell_types: [],
      subcellular_localization: {
        primary_compartment: "plasma_membrane",
        rationale: "",
        dual_localization: [],
        membrane_subdomains: [],
      },
      anatomical_accessibility: [],
      accessibility_modulation: [],
      biological_context_grade: "absent",
      grade_rationale: "",
      grade_cited_evidence_ids: [],
    },
    accessibility_risks: {
      epitope_masking: {
        mechanism: [],
        severity: "low",
        evidence_strength: "moderate",
        rationale: "",
        cited_evidence_ids: [],
      },
      shed_form: {
        present: false,
        severity: "low",
        evidence_strength: "moderate",
        mechanism: null,
        sheddase_if_known: null,
        rationale: "",
        cited_evidence_ids: [],
      },
      secreted_form: {
        present: false,
        severity: "low",
        evidence_strength: "moderate",
        ratio_to_membrane: null,
        source: null,
        rationale: "",
        cited_evidence_ids: [],
      },
      restricted_subdomain: {
        present: false,
        domain: "unknown",
        severity: "low",
        evidence_strength: "moderate",
        rationale: "",
        cited_evidence_ids: [],
      },
      co_receptor_requirements: {
        surface_expression_dependency: "none",
        partners: [],
        evidence_basis: "co_expression_only",
        rationale: "",
        cited_evidence_ids: [],
      },
      ecd_size_assessment: {
        ecd_accessibility_class: "moderate",
        rationale: "",
        cited_evidence_ids: [],
      },
    },
  } as unknown as SurfaceomeRecord;
}
