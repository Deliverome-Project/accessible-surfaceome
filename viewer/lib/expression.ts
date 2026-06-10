import type { Evidence, ExpressionRow } from "./surfaceome-types";

/**
 * Source bucket for one expression row, derived from its
 * ``cited_evidence_ids`` joined against the gene's evidence ledger.
 *
 *  - **surface** — at least one cite is a surface-specific protein assay
 *    (flow cytometry / surface biotinylation / mass-spec surfaceome).
 *    The row is backed by a direct surface measurement.
 *  - **bulk** — no surface-specific cites, but at least one bulk
 *    protein-level method (IHC / IF / WB). The row measures the
 *    protein but doesn't distinguish surface from intracellular pool.
 *  - **other** — non-RNA evidence that isn't a structured protein
 *    assay (review_assertion / functional_assay / db_annotation /
 *    crystal_structure / etc.). The row's coverage isn't grounded in
 *    a direct protein-localization measurement.
 *
 *  Rows whose cited evidence is **exclusively** RNA-level methods
 *  (RNA-seq / scRNA-seq / RT-qPCR / in-situ hybridization / Northern /
 *  microarray) are filtered out — they don't distinguish whether the
 *  protein is actually made, let alone on the surface, and the
 *  ``expression_builder`` prompt already prescribes excluding them.
 *  This enforces the rule at render time until the upstream prompt
 *  enforcement lands.
 */
export type ExpressionSource = "surface" | "bulk" | "other";

const SURFACE_EVIDENCE_TYPES = new Set([
  "flow_cytometry",
  "surface_biotinylation",
  "mass_spec_surfaceome",
]);

const BULK_PROTEIN_EVIDENCE_TYPES = new Set([
  "immunohistochemistry",
  "immunofluorescence",
  // Western blot only counts as bulk protein here — the surface-specific
  // pairing rule (WB + fractionation/biotinylation from the same source)
  // is enforced in the methods builder, not at row-classify time.
  "western_blot",
]);

const RNA_EVIDENCE_TYPES = new Set([
  "rt_qpcr",
  "rna_seq",
  "single_cell_rna_seq",
  "in_situ_hybridization",
  "northern_blot",
  "microarray",
]);

/** Classify an expression row by the cited evidence_types behind it.
 *  Returns ``null`` when the row should be hidden (every cite is RNA),
 *  otherwise the bucket name. Surface wins over bulk wins over other —
 *  the strongest direct-surface signal in the row's evidence drives
 *  the bucket. */
export function classifyExpressionSource(
  row: ExpressionRow,
  evidenceById: ReadonlyMap<string, Evidence>,
): ExpressionSource | null {
  // ``evidence_type`` is on the wire shape but not (yet) modeled on
  // the TS ``Evidence`` interface — same widening EvidenceDrawer uses.
  type EvidenceWithType = Evidence & { evidence_type?: string };
  const types = new Set<string>();
  for (const id of row.cited_evidence_ids) {
    const ev = evidenceById.get(id) as EvidenceWithType | undefined;
    if (ev?.evidence_type) types.add(ev.evidence_type);
  }
  if (types.size === 0) return "other";
  // RNA-only rows are dropped — the expression_builder prompt
  // already excludes RNA-only sources upstream; this enforces it on
  // the read side too.
  const nonRna = [...types].filter((t) => !RNA_EVIDENCE_TYPES.has(t));
  if (nonRna.length === 0) return null;
  for (const t of nonRna) {
    if (SURFACE_EVIDENCE_TYPES.has(t)) return "surface";
  }
  for (const t of nonRna) {
    if (BULK_PROTEIN_EVIDENCE_TYPES.has(t)) return "bulk";
  }
  return "other";
}

/** Strength rank for the Source column's sort comparator —
 *  surface > bulk > other. Mirrors the convention "strongest evidence
 *  first" used by ``levelRank``. */
export function expressionSourceRank(s: ExpressionSource): number {
  if (s === "surface") return 3;
  if (s === "bulk") return 2;
  return 1;
}

/** Re-export the evidence_type lookup sets for any caller that wants
 *  to bucket evidence in a tooltip / chip without re-classifying a
 *  whole row. */
export const EXPRESSION_SOURCE_SETS = {
  surface: SURFACE_EVIDENCE_TYPES,
  bulk: BULK_PROTEIN_EVIDENCE_TYPES,
  rna: RNA_EVIDENCE_TYPES,
};
