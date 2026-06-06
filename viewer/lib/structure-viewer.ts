/*
 * Structure-viewer data loader (server-only).
 * ------------------------------------------------------------
 * Reads per-UniProt structure-viewer JSONs at build time from
 * ``viewer/public/structure-viewer/*.json``. Same fs-from-public
 * trick as ``viewer/lib/surfaceome.ts`` — the file is also reachable
 * over HTTP at ``/structure-viewer/{UNIPROT}.json`` for any future
 * client-side loaders.
 *
 * Returns ``null`` when no JSON exists for the UniProt. The per-gene
 * page skips the structure card in that case rather than rendering
 * an empty placeholder. Most truly-soluble proteins are skipped at
 * build time (DeepTMHMM type GLOB) so they don't get a misleading
 * "membrane topology" viewer; opt them in via the build script's
 * ``--include-globular`` flag when the protein belongs in the
 * surfaceome via lipid anchor (e.g. SRC's N-terminal myristoyl).
 *
 * Browser-safe constants (TOPOLOGY_COLORS, alphafoldPdbUrl) live in
 * ``./structure-viewer-types`` so the client component doesn't drag
 * fs / path into the bundle.
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import {
  alphafoldPdbUrl,
  type DeepTMHMMState,
  type DeepTMHMMType,
  type StructureViewerData,
} from "./structure-viewer-types";

const DATA_DIR = path.join(process.cwd(), "public", "structure-viewer");
const SCHWEKE_DIR = path.join(
  process.cwd(),
  "public",
  "data",
  "structures",
  "schweke",
);

/** A subset of {@link StructureVariantSchwekeHomomer} (defined in the
 *  client component) — repeated here so this server-side loader doesn't
 *  import the heavy 3Dmol-dependent client file. The caller assembles
 *  the full variant by adding ``source``, ``id``, ``label``,
 *  ``topology``, and ``deeptmhmm_type`` at the call site (where the
 *  canonical topology / type is already in hand). */
export interface SchwekeHomomerLoaderRow {
  uniprot_acc: string;
  pdb_url: string;
  af_model_num: number;
  ecd_only: boolean;
  /** Cyclic-symmetry order N of the rendered model (homo-N-mer). 2
   *  for a plain dimer from ``AF_dimer_models_core.zip``; 3..13 for an
   *  AnAnaS-reconstructed full complex from
   *  ``full_complexes_bigbang.zip``. The viewer uses this both to
   *  size the per-chain darken gradient (chain 0 = full topology palette,
   *  chain N-1 = ~black) and to label the caption ("homo-dimer",
   *  "homo-heptamer", "homo-13-mer"). */
  stoichiometry: number;
}

/** One manifest entry. Default ``stoichiometry`` is 2 (a plain
 *  ``AF_dimer_models_core`` dimer); set ``stoichiometry`` to N≥3 when
 *  the asset under ``/data/structures/schweke/`` is an AnAnaS-
 *  reconstructed full complex (file pattern ``{ACC}_V1_{M}_cN.pdb``). */
type SchwekeManifestEntry = {
  af_model_num: number;
  ecd_only: boolean;
  stoichiometry?: number;
};

type SchwekeManifest = Record<string, SchwekeManifestEntry>;

let _schwekeManifestCache: SchwekeManifest | null | undefined;

function _readSchwekeManifest(): SchwekeManifest | null {
  if (_schwekeManifestCache !== undefined) return _schwekeManifestCache;
  try {
    const raw = readFileSync(
      path.join(SCHWEKE_DIR, "manifest.json"),
      "utf-8",
    );
    const parsed = JSON.parse(raw) as SchwekeManifest;
    // Strip JSON-comment keys (we use a leading-underscore convention
    // because the manifest is hand-written, not generated).
    const cleaned: SchwekeManifest = {};
    for (const [k, v] of Object.entries(parsed)) {
      if (k.startsWith("_")) continue;
      cleaned[k] = v;
    }
    _schwekeManifestCache = cleaned;
    return cleaned;
  } catch {
    _schwekeManifestCache = null;
    return null;
  }
}

/** Load the Schweke et al. 2024 (PMID 38325366) AF2 homo-oligomer entry
 *  for ``uniprotAcc`` — when one exists in the manifest at
 *  ``viewer/public/data/structures/schweke/manifest.json``. Returns
 *  ``null`` for genes that aren't in Schweke's 8,195-homomer reference
 *  set or whose PDB asset hasn't been ingested yet (a separate bulk-
 *  extract pass against the figshare deposit DOI
 *  10.6084/m9.figshare.22309177 — see
 *  ``data/external/schweke_homomer_atlas/PROVENANCE.md``).
 *
 *  The PDB file is served as a static asset under
 *  ``/data/structures/schweke/{ACC}_V1_{N}.pdb``; the loader trusts the
 *  manifest and doesn't existence-check the asset — the client tab
 *  surfaces a fetch error if it's missing. */
export function loadSchwekeHomomer(
  uniprotAcc: string | null | undefined,
): SchwekeHomomerLoaderRow | null {
  if (!uniprotAcc) return null;
  if (!/^[A-Z0-9-]+$/i.test(uniprotAcc)) return null;
  const manifest = _readSchwekeManifest();
  if (!manifest) return null;
  const acc = uniprotAcc.toUpperCase();
  const entry = manifest[acc];
  if (!entry) return null;
  const stoichiometry =
    typeof entry.stoichiometry === "number" && entry.stoichiometry >= 2
      ? entry.stoichiometry
      : 2;
  // File-naming convention: dimers (c2) come from AF_dimer_models_core
  // and live at ``{ACC}_V1_{N}.pdb``; higher-order complexes (c≥3) come
  // from full_complexes_bigbang and live at ``{ACC}_V1_{N}_c{N}.pdb``.
  // Keep both shapes in sync with the bulk-extract script.
  const pdb_url =
    stoichiometry > 2
      ? `/data/structures/schweke/${acc}_V1_${entry.af_model_num}_c${stoichiometry}.pdb`
      : `/data/structures/schweke/${acc}_V1_${entry.af_model_num}.pdb`;
  return {
    uniprot_acc: acc,
    pdb_url,
    af_model_num: entry.af_model_num,
    ecd_only: entry.ecd_only,
    stoichiometry,
  };
}

export function loadStructureViewerData(
  uniprotAcc: string | null | undefined,
): StructureViewerData | null {
  if (!uniprotAcc) return null;
  // UniProt accessions are uppercase alphanumeric. Reject anything that
  // could escape the data dir so a malformed record can't trigger a
  // path-traversal read.
  if (!/^[A-Z0-9-]+$/i.test(uniprotAcc)) return null;
  try {
    const raw = readFileSync(path.join(DATA_DIR, `${uniprotAcc}.json`), "utf-8");
    return JSON.parse(raw) as StructureViewerData;
  } catch {
    return null;
  }
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
 * topology — which comes from D1 via the Worker — when no precomputed
 * static `structure-viewer/{UNIPROT}.json` exists.
 *
 * The static files only cover the 2,359-protein topology-sweep cohort, so
 * deep-dived genes outside it (e.g. CD81, HSPA5) have topology in their
 * record but no static file, and the gene page showed no structure. This
 * fallback reuses the record's DeepTMHMM topology + the AFDB URL so any
 * gene whose record carries topology renders. Returns null for GLOB
 * (soluble) topology, matching the build script's default skip; opted-in
 * globular cases (e.g. SRC's lipid anchor) already ship a static file and
 * never reach this fallback.
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
  // An empty per_residue_topology (DeepTMHMM produced no string for this
  // protein — e.g. IZUMO4 / Q1ZYL8) must NOT hide the structure: the AFDB
  // model still exists and is worth rendering. Fall through with an empty
  // topology → GLOB / no coloring / whole-protein gray (the same look GLOB
  // proteins already get) instead of returning null, which showed no
  // viewer at all even though the model loads fine.
  const topology = canonicalTopology?.per_residue_topology ?? "";
  const type = deepTMHMMType(topology);
  // GLOB (globular / no membrane topology — e.g. BAX, LYN, HMGB1, the
  // cytoplasmic kinases) is NOT excluded: a globular protein still has an
  // AlphaFold model worth showing, and the viewer renders it in
  // whole-protein gray (no topology coloring) — exactly how the pre-baked
  // static-cohort path already renders GLOB entries like SRC (P12931).
  // Returning null here was the sole reason those genes showed no 3D
  // structure even though their AFDB model exists; the deep-dive record
  // carries `canonical_topology` for every gene, so the fallback can
  // serve GLOB just like the membrane types.
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
    // Leave the AFDB URL unresolved (null) so the client routes the
    // first fetch through the prediction API. Previously this baked
    // `alphafoldPdbUrl(acc)` with the helper's hardcoded default
    // version; for any UniProt whose model had been bumped past that
    // version (EGFR / P00533, GPR75 / O95800, …) the stale file
    // 404'd and produced browser-console noise. Resolving via the
    // prediction API up front is one extra ~1 KB JSON fetch, cached
    // aggressively by AFDB. Static-file path (loadStructureViewerData)
    // still emits a baked URL so it doesn't pay the round-trip for
    // canonical views.
    pdb_url: null,
    latest_version: null,
  };
}
