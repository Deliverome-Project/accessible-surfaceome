/**
 * Catch-all asset-first router for the surfaceome viewer (Cloudflare Pages).
 *
 * The per-gene deep dive is a SINGLE client-rendered shell at `/gene/`
 * (`out/gene/index.html`) — one static file for all ~5k genes, so the
 * deployment stays under Cloudflare Pages' hard 20,000-file cap. Gene URLs
 * like `/TFRC/` have no static file of their own; this Function serves them
 * the shell, which reads the symbol from `window.location` and fetches the
 * record from the Worker at runtime.
 *
 * WHY A FUNCTION AND NOT `_redirects`:
 * A blanket `/*  /gene/  200` rewrite in `_redirects` matches EVERY
 * directory-style navigation path — `/`, `/benchmark/`, `/compare/` — not
 * just unmatched gene URLs (static assets do NOT take precedence over a
 * working splat rewrite for directory paths). That served the gene shell for
 * the whole site. It also masked missing build assets: a request for a
 * `/_next/…` chunk that wasn't in the deploy fell through the splat and
 * returned the shell HTML with a 200, so a partial deploy white-screened
 * instead of erroring — the failure mode that made the outage hard to see.
 *
 * This Function is ASSET-FIRST: try the real asset via `next()`, and only
 * fall back to the shell for genuinely-unmatched *navigation* requests. It
 * never masks a missing build asset (those keep their real 404), and — unlike
 * advanced-mode `_worker.js` — it leaves `_headers` / `_redirects` in force.
 *
 * It also stamps the security headers onto every HTML response, and rewrites
 * the gene shell's <title> / description / og:url to name the gene, so a
 * shared gene link doesn't unfurl as the generic site page.
 *
 * Only symbols with a published record get the shell and a 200 (the list is
 * `/data/gene-symbols.json`, written at build time); every other path keeps
 * its 404, so link checkers and crawlers can tell a dead link from a gene
 * page. The decision lives in `lib/gene-route.js`, which is unit-tested.
 */
import {
  geneShellMeta,
  geneSymbolFromPath,
  withSecurityHeaders,
} from "../lib/gene-shell-meta.js";
import { GENE_SYMBOLS_PATH, routeMissing, symbolSet } from "../lib/gene-route.js";

// Published symbols, loaded once per isolate. null = not loaded (or the
// list is missing, e.g. an offline build), which serves every gene-shaped
// path rather than 404ing real genes.
let publishedPromise;

async function loadPublished(env, origin) {
  try {
    const res = await env.ASSETS.fetch(new URL(GENE_SYMBOLS_PATH, origin).toString());
    if (!res.ok) return null;
    return symbolSet(await res.json());
  } catch {
    return null;
  }
}

function htmlWithSecurityHeaders(res) {
  if (!(res.headers.get("content-type") || "").includes("text/html")) return res;
  return new Response(res.body, {
    status: res.status,
    statusText: res.statusText,
    headers: withSecurityHeaders(res.headers),
  });
}

function rewriteGeneHead(res, meta) {
  const setContent = (attr, value) => ({
    element(el) {
      el.setAttribute(attr, value);
    },
  });
  return new HTMLRewriter()
    .on("title", {
      element(el) {
        el.setInnerContent(meta.title);
      },
    })
    .on('meta[name="description"]', setContent("content", meta.description))
    .on('meta[property="og:title"]', setContent("content", meta.title))
    .on('meta[property="og:description"]', setContent("content", meta.description))
    .on('meta[property="og:url"]', setContent("content", meta.url))
    .on('meta[name="twitter:title"]', setContent("content", meta.title))
    .on('meta[name="twitter:description"]', setContent("content", meta.description))
    .transform(res);
}

export async function onRequest(context) {
  const { request, next, env } = context;

  // Serve the real static asset if one exists (pages, chunks, /data, …).
  const res = await next();
  if (res.status !== 404) return htmlWithSecurityHeaders(res);

  const url = new URL(request.url);
  const p = url.pathname;
  publishedPromise ??= loadPublished(env, url.origin);
  const published = await publishedPromise;
  if (published === null) publishedPromise = undefined; // retry next request

  if (routeMissing(p, request.headers.get("accept"), published) === "gene") {
    const shell = await env.ASSETS.fetch(new URL("/gene/", url).toString());
    // Preserve a clean 200 with the shell's own headers; the body is the
    // client-shell HTML, which resolves the symbol from the URL at runtime.
    const page = new Response(shell.body, {
      status: 200,
      headers: withSecurityHeaders(shell.headers),
    });
    const symbol = geneSymbolFromPath(p);
    return symbol ? rewriteGeneHead(page, geneShellMeta(symbol, url.origin)) : page;
  }

  return htmlWithSecurityHeaders(res);
}
