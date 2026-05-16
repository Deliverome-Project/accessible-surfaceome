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
  /** AlphaFold DB pdbUrl baked in at build time via the prediction API.
   *  Saves a round-trip vs. re-querying at runtime; the runtime falls
   *  back to a fresh prediction-API call if this URL ever 404s. */
  pdb_url?: string | null;
  /** AFDB model version at the time `pdb_url` was baked. Informational. */
  latest_version?: number | null;
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

/**
 * AFDB serves a single API endpoint per UniProt that returns the
 * current latest model + a ready-to-use ``pdbUrl``. Querying this
 * before fetching the PDB lets the viewer auto-track AFDB version
 * bumps (e.g. O95800 went v4 → v6 in 2025-08; v1–v5 were removed
 * from the file server, so the legacy ``alphafoldPdbUrl(acc, "v4")``
 * 404s).
 */
export function alphafoldPredictionApiUrl(uniprotAcc: string): string {
  return `https://alphafold.ebi.ac.uk/api/prediction/${uniprotAcc}`;
}

/** Shape of one entry returned by ``alphafoldPredictionApiUrl``. The
 *  endpoint returns an array (typically length 1 for a single UniProt).
 *  We only need ``pdbUrl`` + ``latestVersion``; the API has many other
 *  fields we don't depend on. */
export interface AlphafoldPredictionEntry {
  pdbUrl: string;
  cifUrl?: string;
  bcifUrl?: string;
  latestVersion?: number;
  entryId?: string;
  modelEntityId?: string;
}
