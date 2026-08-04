/*
 * Tagged-sites + internalization loaders (server-only).
 * Reads per-gene JSON at build time from viewer/public/tag-sites/*.json and
 * viewer/public/internalization/*.json. Mirrors lib/structure-viewer.ts:
 * only these functions touch node:fs, guarded against path traversal.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import type { TaggedSitesFile, InternalizationFile } from "./tag-sites-types";

const TAG_SITES_DIR = path.join(process.cwd(), "public", "tag-sites");
const INTERNALIZATION_DIR = path.join(process.cwd(), "public", "internalization");

// HGNC symbols are uppercase alphanumeric with - . and digits; reject
// anything that could escape the data dir.
const SAFE_KEY = /^[A-Z0-9.\-]+$/i;

function loadJson<T>(dir: string, key: string | null | undefined): T | null {
  if (!key || !SAFE_KEY.test(key)) return null;
  try {
    return JSON.parse(readFileSync(path.join(dir, `${key}.json`), "utf-8")) as T;
  } catch {
    return null;
  }
}

export function loadTaggedSites(symbol: string | null | undefined): TaggedSitesFile | null {
  return loadJson<TaggedSitesFile>(TAG_SITES_DIR, symbol);
}

export function loadInternalization(symbol: string | null | undefined): InternalizationFile | null {
  return loadJson<InternalizationFile>(INTERNALIZATION_DIR, symbol);
}
