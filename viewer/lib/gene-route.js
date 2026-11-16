/**
 * Which requests the Pages Function (`functions/[[path]].js`) answers with
 * the gene shell and a 200. Plain JS (no TS) so the Function bundle can
 * import it directly; unit-tested in `tests/gene_route.test.ts`.
 *
 * A gene URL is one path segment (`/CD44/`) that names a gene with a
 * published record. The list of those symbols is written at build time to
 * `/data/gene-symbols.json` by `scripts/build-data-snapshot.mjs`. A
 * symbol-shaped segment that isn't in it (a typo, an unpublished gene, a
 * dead link) gets the real 404 page, so link checkers and crawlers can tell
 * it apart from a live page.
 */

/** Path of the build-time list of published gene symbols. */
export const GENE_SYMBOLS_PATH = "/data/gene-symbols.json";

const BUILD_ASSET_PREFIXES = ["/_next/", "/data/", "/assets/", "/structure-viewer/"];

/**
 * The single segment of a gene-shaped path, decoded, or null. Rejects
 * multi-segment paths, build-asset prefixes and anything with a file
 * extension, so a missing build asset keeps its real 404.
 */
export function geneSegment(pathname) {
  if (BUILD_ASSET_PREFIXES.some((p) => pathname.startsWith(p))) return null;
  if (/\.[a-z0-9]+$/i.test(pathname)) return null;
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length !== 1) return null;
  try {
    return decodeURIComponent(segments[0]);
  } catch {
    return null;
  }
}

/**
 * Whether the request accepts an HTML document. Browsers send `text/html`;
 * curl, link checkers and many unfurlers send `*` + `/*` or nothing. Only a
 * request that names other types and neither of those (e.g. a JSON fetch)
 * is refused the shell.
 */
export function acceptsHtml(accept) {
  const a = (accept || "").trim();
  return a === "" || a.includes("text/html") || a.includes("*/*");
}

/** Upper-cased set from the build's symbol list, or null if unusable. */
export function symbolSet(list) {
  if (!Array.isArray(list) || list.length === 0) return null;
  return new Set(list.map((s) => String(s).toUpperCase()));
}

/**
 * Decide how to answer a request whose static asset was missing:
 * "gene" → serve the shell with 200, "404" → keep the 404.
 * `published` is the symbol set, or null when the list couldn't be loaded,
 * in which case any symbol-shaped segment is served (the shell shows its
 * own not-found notice), so a missing list never takes gene pages down.
 */
export function routeMissing(pathname, accept, published) {
  const seg = geneSegment(pathname);
  if (!seg || !acceptsHtml(accept)) return "404";
  if (published === null) return "gene";
  return published.has(seg.toUpperCase()) ? "gene" : "404";
}
