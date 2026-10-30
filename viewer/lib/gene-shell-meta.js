/**
 * Per-gene <head> values and security headers for the Pages Function
 * (`functions/[[path]].js`). Every gene URL serves the same `/gene/` HTML,
 * so without these, crawlers and link unfurlers (Slack, X, LinkedIn) see the
 * generic site title on every gene. The client sets the same title after
 * hydration (`app/gene/page.tsx`); this puts it in the HTML that non-JS
 * readers get.
 *
 * Plain JS (no TS) so the Pages Function bundle can import it directly.
 */

// HGNC symbols are letters, digits and hyphens (e.g. C1orf43, HLA-A).
// Anything else is not rewritten into the page.
const SYMBOL_RE = /^[A-Za-z0-9][A-Za-z0-9-]{0,24}$/;

/** The gene symbol a single-segment path names, or null. */
export function geneSymbolFromPath(pathname) {
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length !== 1) return null;
  let seg;
  try {
    seg = decodeURIComponent(segments[0]);
  } catch {
    return null;
  }
  return SYMBOL_RE.test(seg) ? seg : null;
}

/** Title, description and URL for a gene page's <head>. */
export function geneShellMeta(symbol, origin) {
  return {
    title: `${symbol} — Surfaceome record`,
    description:
      `Cell-surface accessibility record for the human gene ${symbol}: ` +
      "topology, surface evidence, expression and risks, with citations.",
    url: `${origin}/${symbol}/`,
  };
}

/**
 * Added to every HTML response. Set here rather than in `public/_headers`
 * because Pages doesn't apply `_headers` to responses a Function builds,
 * which includes every gene page. CSP is limited to frame-ancestors: a full
 * script policy would have to track Next's inline scripts, Turnstile and the
 * structure viewer, and would break silently when any of them change.
 */
export const SECURITY_HEADERS = {
  "Strict-Transport-Security": "max-age=31536000",
  "Content-Security-Policy":
    "frame-ancestors 'self' https://deliverome.org https://*.deliverome.org",
  "X-Frame-Options": "SAMEORIGIN",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
};

/** Copy of `headers` with SECURITY_HEADERS set, for an HTML response. */
export function withSecurityHeaders(headers) {
  const out = new Headers(headers);
  if (!(out.get("content-type") || "").includes("text/html")) return out;
  for (const [k, v] of Object.entries(SECURITY_HEADERS)) out.set(k, v);
  return out;
}
