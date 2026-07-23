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
  M: "#FFD579", // TM helix
  O: "#8878C8", // extracellular — brand lavender-bright (purple)
  I: "#A9CFA8", // intracellular (inside)
  S: "#DD5955", // signal peptide — red
  B: "#C7CED6", // beta-strand (rare in this dataset)
};

/**
 * Neutral slate-gray for the translucent bilayer slab. Reads as
 * "membrane the TM helix is embedded in" while leaving the purple
 * extracellular cartoon as the page's high-saturation accent.
 * Shared with the legend so the swatch matches the rendered slab.
 */
export const MEMBRANE_COLOR = "#A0A4AB";

/**
 * Latest AFDB model version we know about. Bumped manually when
 * AFDB rolls a new release across the predominant model set (v4 →
 * v6 in 2025-08; v1–v5 were retired from the file server at that
 * time, which is why `alphafoldPdbUrl(acc, "v4")` started 404ing).
 *
 * Most code paths should NOT consume this directly — they should
 * resolve the canonical URL through {@link alphafoldPredictionApiUrl}
 * so the version always matches what AFDB is currently serving.
 * `LATEST_KNOWN_AFDB_VERSION` is the *fallback* used when the
 * prediction API itself is unreachable; keep it pinned to the
 * latest stable so the offline-fallback path lands as close to a
 * real URL as possible.
 *
 * When you bump this past `vN`: also bump the v4 fallbacks in
 * `src/accessible_surfaceome/agents/surfaceome_v1/_stub_structure`
 * + `orchestrator.py` (they're cosmetic placeholders but should
 * track) and re-run `scripts/build_structure_viewer_data.py` to
 * refresh any baked URLs in `viewer/public/structure-viewer/*.json`.
 */
export const LATEST_KNOWN_AFDB_VERSION = "v6";

export function alphafoldPdbUrl(
  uniprotAcc: string,
  version: string = LATEST_KNOWN_AFDB_VERSION,
): string {
  return `https://alphafold.ebi.ac.uk/files/AF-${uniprotAcc}-F1-model_${version}.pdb`;
}

/**
 * AFDB serves a single API endpoint per UniProt that returns the
 * current latest model + a ready-to-use ``pdbUrl``. Querying this
 * before fetching the PDB lets the viewer auto-track AFDB version
 * bumps without us having to keep {@link LATEST_KNOWN_AFDB_VERSION}
 * in lockstep with every minor release.
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

// ---------------------------------------------------------------------------
// Browser-safe structure derivation.
// ---------------------------------------------------------------------------
// `structureViewerDataFromRecord` + `loadSchwekeHomomer` were previously in
// `./structure-viewer.ts`, but that module's top-level `node:fs` import
// (needed only by the file-reading `loadStructureViewerData`) can't be
// tree-shaken across a `"use client"` boundary — importing either pure
// function from a client component would drag `node:fs` into the browser
// bundle and fail the build with `UnhandledSchemeError`. They're pure (no
// fs / path), so they live here in the types leaf — same pattern as the
// enum helpers in `./enums` — and `./structure-viewer.ts` re-exports them
// for existing server-side importers. The client gene shell imports them
// straight from here.

// Schweke coordinate PDBs are served from the PUBLIC R2 bucket
// ``surfaceome-structures`` (keys ``schweke/{filename}``). Override the
// base via ``NEXT_PUBLIC_STRUCTURES_BASE`` without touching code; the
// client fetch is 404-tolerant, so a not-yet-ingested PDB just shows the
// tab's graceful "unavailable" state.
export const STRUCTURES_BASE = (
  process.env.NEXT_PUBLIC_STRUCTURES_BASE ||
  "https://pub-94415fd52d394bc18219b3957a97b823.r2.dev"
).replace(/\/+$/, "");

/** A subset of the full Schweke homomer variant the StructureViewer
 *  consumes — the caller (GeneHeader) assembles the rest (``source``,
 *  ``id``, ``label``, ``topology``, ``deeptmhmm_type``) at the call site
 *  where the canonical topology / type is already in hand. */
export interface SchwekeHomomerLoaderRow {
  uniprot_acc: string;
  pdb_url: string;
  af_model_num: number;
  ecd_only: boolean;
  /** Cyclic-symmetry order N of the rendered model (homo-N-mer). 2 for a
   *  plain dimer; 3..13 for an AnAnaS-reconstructed full complex. */
  stoichiometry: number;
}

/** Build a Schweke loader row from the ``deterministic_features
 *  .homo_oligomerization`` block served on the per-gene record. Returns
 *  ``null`` when the protein isn't a Schweke positive OR when the served
 *  block lacks the PDB filename needed to construct the asset URL. Pure —
 *  no filesystem reads; ``pdb_url`` points at the public R2 bucket (see
 *  ``STRUCTURES_BASE``) and the client fetch is 404-tolerant. */
export function loadSchwekeHomomer(
  uniprotAcc: string | null | undefined,
  homo_oligomerization?:
    | {
        is_homo_oligomer: boolean;
        stoichiometry?: number | null;
        af_model_num?: number | null;
        is_ecd_only: boolean;
        dimer_pdb_filename?: string | null;
        complex_pdb_filename?: string | null;
      }
    | null,
): SchwekeHomomerLoaderRow | null {
  if (!uniprotAcc) return null;
  if (!/^[A-Z0-9-]+$/i.test(uniprotAcc)) return null;
  if (!homo_oligomerization || !homo_oligomerization.is_homo_oligomer) {
    return null;
  }
  const acc = uniprotAcc.toUpperCase();
  const stoichiometry =
    typeof homo_oligomerization.stoichiometry === "number" &&
    homo_oligomerization.stoichiometry >= 2
      ? homo_oligomerization.stoichiometry
      : 2;
  // File-naming convention: dimers (c2) come from AF_dimer_models_core
  // and live at ``{ACC}_V1_{N}.pdb``; higher-order complexes (c≥3) come
  // from full_complexes_bigbang and live at ``{ACC}_V1_{N}_c{N}.pdb``.
  // Prefer the D1-served filename when present.
  const rawFilename =
    stoichiometry > 2
      ? homo_oligomerization.complex_pdb_filename
      : homo_oligomerization.dimer_pdb_filename;
  // Strip the trailing ``_model_<n>_rank_<n>`` the full_complexes_bigbang
  // export appends, so older baked records still resolve.
  const filename =
    rawFilename?.replace(/_model_\d+_rank_\d+(?=\.pdb$)/i, "") ?? rawFilename;
  if (!filename && homo_oligomerization.af_model_num == null) {
    return null;
  }
  const base = `${STRUCTURES_BASE}/schweke`;
  const pdb_url = filename
    ? `${base}/${filename}`
    : stoichiometry > 2
      ? `${base}/${acc}_V1_${homo_oligomerization.af_model_num}_c${stoichiometry}.pdb`
      : `${base}/${acc}_V1_${homo_oligomerization.af_model_num}.pdb`;
  return {
    uniprot_acc: acc,
    pdb_url,
    af_model_num: homo_oligomerization.af_model_num ?? 1,
    ecd_only: homo_oligomerization.is_ecd_only,
    stoichiometry,
  };
}

/** Collapse a per-residue topology string into 1-based, end-inclusive
 *  [start, end] spans per DeepTMHMM state. */
function topologyRanges(
  topology: string,
): Record<DeepTMHMMState, [number, number][]> {
  const ranges: Record<DeepTMHMMState, [number, number][]> = {
    M: [],
    O: [],
    I: [],
    S: [],
    B: [],
  };
  let i = 0;
  while (i < topology.length) {
    const ch = topology[i] as DeepTMHMMState;
    let j = i;
    while (j + 1 < topology.length && topology[j + 1] === ch) j += 1;
    if (ch in ranges) ranges[ch].push([i + 1, j + 1]);
    i = j + 1;
  }
  return ranges;
}

function deepTMHMMType(topology: string): DeepTMHMMType {
  const hasM = topology.includes("M");
  const hasS = topology.includes("S");
  if (hasM && hasS) return "SP+TM";
  if (hasM) return "TM";
  if (topology.includes("B")) return "BETA";
  if (hasS) return "SP";
  return "GLOB";
}

/**
 * Derive structure-viewer data from a deep-dive record's canonical
 * topology (which comes from D1 via the Worker). This is the primary
 * structure-data path for the client gene shell — the deep-dive record
 * carries `canonical_topology` for every gene, so it renders the 3D
 * viewer without any per-gene static file.
 *
 * Returns null only when there is no UniProt accession. An empty
 * per-residue topology falls through as GLOB (whole-protein gray) rather
 * than hiding the viewer — the AFDB model still exists and is worth
 * rendering. `pdb_url` is left null so the client routes the first fetch
 * through the AFDB prediction API (auto-tracks version bumps instead of
 * 404ing on a stale baked URL).
 */
export function structureViewerDataFromRecord(
  uniprotAcc: string | null | undefined,
  canonicalTopology:
    | {
        per_residue_topology?: string | null;
        tm_helix_count?: number;
        signal_peptide_length?: number;
        tool_version?: string;
      }
    | null
    | undefined,
): StructureViewerData | null {
  if (!uniprotAcc) return null;
  if (!/^[A-Z0-9-]+$/i.test(uniprotAcc)) return null;
  const topology = canonicalTopology?.per_residue_topology ?? "";
  const type = deepTMHMMType(topology);
  return {
    uniprot_acc: uniprotAcc,
    deeptmhmm_type: type,
    sequence_length: topology.length,
    topology,
    topology_ranges: topologyRanges(topology),
    tm_helix_count: canonicalTopology?.tm_helix_count ?? 0,
    signal_peptide_length: canonicalTopology?.signal_peptide_length ?? 0,
    source_cohort: "deep_dive_record",
    source_tool: canonicalTopology?.tool_version ?? "deeptmhmm",
    pdb_url: null,
    latest_version: null,
  };
}
