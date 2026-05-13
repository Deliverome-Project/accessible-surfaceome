/*
 * Structure-viewer data shape.
 * ------------------------------------------------------------
 * Mirrors the JSON emitted by ``scripts/build_structure_viewer_data.py``.
 * One file per UniProt accession under
 * ``viewer/public/structure-viewer/{UNIPROT}.json`` — loaded at SSG
 * time on the per-gene page and passed as props to
 * ``<StructureViewerCard>``.
 *
 * Indices are 1-based, end-inclusive — same convention 3Dmol uses
 * for ``viewer.setStyle({resi: "start-end"})``.
 */

export type DeepTMHMMState = "M" | "O" | "I" | "S" | "B";

export type DeepTMHMMType = "TM" | "SP+TM" | "SP" | "BETA" | "GLOB";

export interface StructureViewerData {
  uniprot_acc: string;
  deeptmhmm_type: DeepTMHMMType;
  sequence_length: number;
  /** Per-residue topology string. One character per residue, alphabet M/O/I/S/B. */
  topology: string;
  /** Collapsed [start, end] spans per state. Empty list if state never appears. */
  topology_ranges: Record<DeepTMHMMState, [number, number][]>;
  tm_helix_count: number;
  signal_peptide_length: number;
  source_cohort: string;
  source_tool: string;
}

/**
 * The DeepTMHMM topology color palette — kept in sync with the original
 * deliverome-internal structure-site viewer (see
 * ``cloudflare/surfaceome_structure_site_viewer/deploy_static/index.html``
 * in that repo, ``TOPOLOGY_COLORS``).
 *
 * Lives in the types file (no ``node:`` imports) so the client-side
 * 3Dmol component can import it without dragging in fs/path. Server-side
 * loader logic stays in ``./structure-viewer.ts``.
 */
export const TOPOLOGY_COLORS: Record<string, string> = {
  M: "#FFD579", // TM helix (membrane)
  O: "#D7DCE3", // extracellular (outside)
  I: "#A9CFA8", // intracellular (inside)
  S: "#7D8896", // signal peptide
  B: "#C7CED6", // beta-strand (rare in this dataset)
};

export function alphafoldPdbUrl(uniprotAcc: string, version = "v4"): string {
  return `https://alphafold.ebi.ac.uk/files/AF-${uniprotAcc}-F1-model_${version}.pdb`;
}
