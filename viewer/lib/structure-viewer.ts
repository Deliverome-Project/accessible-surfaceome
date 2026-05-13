/*
 * Structure-viewer data loader (server-only).
 * ------------------------------------------------------------
 * Reads per-UniProt structure-viewer JSONs at build time from
 * ``viewer/public/structure-viewer/*.json``. Same fs-from-public
 * trick as ``viewer/lib/surfaceome.ts`` — the file is also reachable
 * over HTTP at ``/structure-viewer/{UNIPROT}.json`` for any future
 * client-side loaders.
 *
 * Returns ``null`` when no DeepTMHMM record exists for the UniProt
 * (e.g. soluble cytoplasmic proteins like HSPA1A). The per-gene page
 * skips the structure card in that case rather than rendering an
 * empty placeholder.
 *
 * Browser-safe constants (TOPOLOGY_COLORS, alphafoldPdbUrl) live in
 * ``./structure-viewer-types`` so the client component doesn't drag
 * fs / path into the bundle.
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import type { StructureViewerData } from "./structure-viewer-types";

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
