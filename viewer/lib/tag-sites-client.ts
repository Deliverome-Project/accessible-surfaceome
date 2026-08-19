// viewer/lib/tag-sites-client.ts
/*
 * Client-safe access to tag-sites (no node:fs). The gene route is a client
 * shell, so it prefers the D1-backed Worker (/v1/tag-sites/{SYMBOL}) and falls
 * back to the static /tag-sites/{SYMBOL}.json asset — robust across the D1
 * rollout (static works today; the Worker takes over once tag_site_public is
 * synced) and in local dev where no apiBase is passed.
 */
import type { TaggedSitesFile } from "./tag-sites-types";

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

async function tryFetch(url: string): Promise<TaggedSitesFile | null> {
  try {
    const res = await fetch(url, { cache: "force-cache" });
    if (!res.ok) return null;
    return parseTaggedSitesFile(await res.json());
  } catch {
    return null;
  }
}

/** Fetch + parse tag-sites for a symbol. Prefers the D1-backed Worker when
 *  ``apiBase`` is given and it has rows; otherwise falls back to the static
 *  asset. Returns null when neither has data, so the overlay degrades gracefully.
 *
 *  ``isoform_pins`` are shipped STATIC-ONLY: they are a build-time-derived
 *  overlay (per-isoform gates + shared/unique classification), regenerated in
 *  lockstep with ``/tag-sites/{SYMBOL}.json``, and the Worker/`tag_site_public`
 *  row schema doesn't carry them. So when the Worker serves the sites, we still
 *  source ``isoform_pins`` from the static asset and merge them on. */
export async function fetchTaggedSites(
  symbol: string,
  apiBase?: string,
): Promise<TaggedSitesFile | null> {
  const key = encodeURIComponent(symbol);
  let worker: TaggedSitesFile | null = null;
  if (apiBase) {
    const fromWorker = await tryFetch(`${apiBase}/v1/tag-sites/${key}`);
    if (fromWorker?.has_data && fromWorker.sites.length > 0) worker = fromWorker;
  }
  // No Worker data -> the static asset carries everything (sites + isoform_pins).
  if (!worker) return tryFetch(`/tag-sites/${key}.json`);
  // Worker served the sites; merge the static-only isoform_pins when it lacks them.
  if (!worker.isoform_pins || worker.isoform_pins.length === 0) {
    const staticFile = await tryFetch(`/tag-sites/${key}.json`);
    if (staticFile?.isoform_pins?.length) {
      return { ...worker, isoform_pins: staticFile.isoform_pins };
    }
  }
  return worker;
}
