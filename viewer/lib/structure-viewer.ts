/*
 * Structure-viewer data loader (server-only).
 * ------------------------------------------------------------
 * Reads per-UniProt structure-viewer JSONs at build time from
 * ``viewer/public/structure-viewer/*.json``. Only ``loadStructureViewerData``
 * touches the filesystem; the pure record-derivation helpers
 * (``structureViewerDataFromRecord``, ``loadSchwekeHomomer``) moved to the
 * browser-safe ``./structure-viewer-types`` leaf so the client gene shell
 * can import them without dragging ``node:fs`` into the browser bundle
 * (webpack can't tree-shake a ``node:*`` import across a ``"use client"``
 * boundary). They're re-exported below for server-side back-compat.
 *
 * Browser-safe constants (TOPOLOGY_COLORS, alphafoldPdbUrl) also live in
 * ``./structure-viewer-types``.
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import type { StructureViewerData } from "./structure-viewer-types";

// Re-export the pure, browser-safe derivations (now defined in the types
// leaf) so existing server-side importers keep resolving them from here.
export {
  loadSchwekeHomomer,
  structureViewerDataFromRecord,
  type SchwekeHomomerLoaderRow,
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
