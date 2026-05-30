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
  const topology = canonicalTopology?.per_residue_topology;
  if (!uniprotAcc || !topology) return null;
  if (!/^[A-Z0-9-]+$/i.test(uniprotAcc)) return null;
  const type = deepTMHMMType(topology);
  if (type === "GLOB") return null;
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
