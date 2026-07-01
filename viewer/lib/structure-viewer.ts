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

// Schweke coordinate PDBs are served from the PUBLIC R2 bucket
// ``surfaceome-structures`` (keys ``schweke/{filename}``), NOT from the repo:
// ~1,478 multi-MB files are too much for git, and D1 caps any row at 2 MB
// (the c13 complexes exceed it). The bucket's r2.dev domain serves them
// publicly with CORS (GET/HEAD, any origin) + HTTP range support, which the
// 3Dmol client needs. Override the base via ``NEXT_PUBLIC_STRUCTURES_BASE``
// (e.g. a custom domain like ``structures.deliverome.org``) without touching
// code; the client fetch is 404-tolerant, so a not-yet-ingested PDB just
// shows the tab's graceful "unavailable" state.
const STRUCTURES_BASE = (
  process.env.NEXT_PUBLIC_STRUCTURES_BASE ||
  "https://pub-94415fd52d394bc18219b3957a97b823.r2.dev"
).replace(/\/+$/, "");

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

/** Build a Schweke loader row from the ``deterministic_features
 *  .homo_oligomerization`` block served on the per-gene record. The
 *  block is populated at annotation time by the Python annotator
 *  (``schweke_homomer.lookup`` → ``DeterministicFeatures.homo_oligomerization``)
 *  AND injected at serve time by the Worker's
 *  ``schweke_homomer_public`` LEFT JOIN for records annotated before
 *  the Schweke wiring landed.
 *
 *  Returns ``null`` when the protein isn't a Schweke positive (no row
 *  in either source) OR when the served block lacks the PDB filename
 *  needed to construct the asset URL (older records with only
 *  ``is_homo_oligomer + stoichiometry`` and no ``dimer_pdb_filename``).
 *  Once the Worker enrichment is universal, the filename will always
 *  be present; the null check is a graceful degradation for any record
 *  that slips through both paths.
 *
 *  No filesystem reads — the manifest.json this used to consult was
 *  removed when Schweke became D1-driven. ``pdb_url`` points at the public
 *  R2 bucket (see ``STRUCTURES_BASE``); the client fetch is 404-tolerant,
 *  so a record pointing at a not-yet-ingested PDB just shows the tab with a
 *  fetch-failed state. */
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
  // Prefer the D1-served filename when present (canonical source of
  // truth + future-proof against naming-convention drift); fall back
  // to the convention only when the served record predates the
  // filename fields.
  const rawFilename =
    stoichiometry > 2
      ? homo_oligomerization.complex_pdb_filename
      : homo_oligomerization.dimer_pdb_filename;
  // The full_complexes_bigbang export ships higher-order PDBs as
  // ``{ACC}_V1_{N}_c{K}_model_0_rank_1.pdb``, but the R2 objects (and both
  // Python fallbacks) use the documented short convention
  // ``{ACC}_V1_{N}_c{K}.pdb``. Older D1 rows / baked records carry the long
  // export name verbatim, so strip the trailing ``_model_<n>_rank_<n>``
  // before building the URL — otherwise the fetch 404s for every gene whose
  // record predates the build-script normalization.
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
