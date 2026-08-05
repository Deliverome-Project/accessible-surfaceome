// viewer/lib/tag-sites-client.ts
/*
 * Client-safe access to the static tag-sites JSON (no node:fs). The gene
 * route is a client shell, so it fetches /tag-sites/{SYMBOL}.json as a static
 * asset rather than using the server-only lib/tag-sites.ts loader.
 */
import type { TaggedSitesFile, InternalizationFile } from "./tag-sites-types";

/** Narrow an unknown payload to TaggedSitesFile, or null. Guards against a
 *  404 HTML page or malformed JSON silently becoming a "record". */
export function parseTaggedSitesFile(raw: unknown): TaggedSitesFile | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  if (typeof o.gene_symbol !== "string") return null;
  if (typeof o.uniprot_acc !== "string") return null;
  if (typeof o.has_data !== "boolean") return null;
  if (!Array.isArray(o.sites)) return null;
  return o as unknown as TaggedSitesFile;
}

/** Fetch + parse the static tag-sites asset for a symbol. Returns null on any
 *  failure (missing file, network, bad JSON) so the shell degrades gracefully. */
export async function fetchTaggedSites(symbol: string): Promise<TaggedSitesFile | null> {
  try {
    const res = await fetch(`/tag-sites/${encodeURIComponent(symbol)}.json`, { cache: "force-cache" });
    if (!res.ok) return null;
    return parseTaggedSitesFile(await res.json());
  } catch {
    return null;
  }
}

/** Narrow an unknown payload to InternalizationFile, or null (guards against
 *  a 404 HTML page or malformed JSON silently becoming a "record"). */
export function parseInternalizationFile(raw: unknown): InternalizationFile | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  if (typeof o.gene_symbol !== "string") return null;
  if (typeof o.uniprot_acc !== "string") return null;
  if (typeof o.has_data !== "boolean") return null;
  if (!Array.isArray(o.measurements)) return null;
  if (!Array.isArray(o.qualitative_statements)) return null;
  return o as unknown as InternalizationFile;
}

/** Fetch + parse the static internalization asset for a symbol. Returns null
 *  on any failure so the shell degrades gracefully. */
export async function fetchInternalization(symbol: string): Promise<InternalizationFile | null> {
  try {
    const res = await fetch(`/internalization/${encodeURIComponent(symbol)}.json`, { cache: "force-cache" });
    if (!res.ok) return null;
    return parseInternalizationFile(await res.json());
  } catch {
    return null;
  }
}
