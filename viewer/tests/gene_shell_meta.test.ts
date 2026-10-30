import assert from "node:assert/strict";
import { test } from "node:test";
import {
  SECURITY_HEADERS,
  geneShellMeta,
  geneSymbolFromPath,
  withSecurityHeaders,
} from "../lib/gene-shell-meta.js";
import { onRequest } from "../functions/[[path]].js";

const ORIGIN = "https://surfaceome.deliverome.org";

test("gene symbol comes from a single path segment", () => {
  assert.equal(geneSymbolFromPath("/EGFR/"), "EGFR");
  assert.equal(geneSymbolFromPath("/HLA-A"), "HLA-A");
  assert.equal(geneSymbolFromPath("/C1orf43/"), "C1orf43");
  assert.equal(geneSymbolFromPath("/"), null);
  assert.equal(geneSymbolFromPath("/a/b/"), null);
  assert.equal(geneSymbolFromPath("/%3Cscript%3E/"), null);
  assert.equal(geneSymbolFromPath("/%E0%A4%A/"), null);
});

test("meta names the gene", () => {
  const m = geneShellMeta("EGFR", ORIGIN);
  assert.equal(m.title, "EGFR — Surfaceome record");
  assert.match(m.description, /human gene EGFR/);
  assert.equal(m.url, `${ORIGIN}/EGFR/`);
});

test("security headers go on HTML only", () => {
  const html = withSecurityHeaders({ "content-type": "text/html; charset=utf-8" });
  for (const [k, v] of Object.entries(SECURITY_HEADERS)) assert.equal(html.get(k), v);
  const json = withSecurityHeaders({ "content-type": "application/json" });
  assert.equal(json.get("Strict-Transport-Security"), null);
});

/** Records what the Function asks HTMLRewriter to do. */
class FakeRewriter {
  static last: Record<string, string> = {};
  handlers: [string, { element(el: unknown): void }][] = [];
  on(sel: string, h: { element(el: unknown): void }) {
    this.handlers.push([sel, h]);
    return this;
  }
  transform(res: Response) {
    FakeRewriter.last = {};
    for (const [sel, h] of this.handlers) {
      h.element({
        setAttribute: (_: string, v: string) => (FakeRewriter.last[sel] = v),
        setInnerContent: (v: string) => (FakeRewriter.last[sel] = v),
      });
    }
    return res;
  }
}
(globalThis as Record<string, unknown>).HTMLRewriter = FakeRewriter;

function context(path: string, accept: string, assetStatus: number, type = "text/html") {
  const request = new Request(`${ORIGIN}${path}`, { headers: { accept } });
  const asset = () => new Response("<html></html>", { status: assetStatus, headers: { "content-type": type } });
  return {
    request,
    next: async () => asset(),
    env: { ASSETS: { fetch: async () => new Response("<html></html>", { headers: { "content-type": "text/html" } }) } },
  };
}

test("gene URL gets the shell, security headers and a per-gene head", async () => {
  const res = await onRequest(context("/EGFR/", "text/html", 404));
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("X-Frame-Options"), "SAMEORIGIN");
  assert.equal(FakeRewriter.last["title"], "EGFR — Surfaceome record");
  assert.equal(FakeRewriter.last['meta[property="og:url"]'], `${ORIGIN}/EGFR/`);
});

test("static pages keep their status and gain security headers", async () => {
  const res = await onRequest(context("/benchmark/", "text/html", 200));
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("Strict-Transport-Security"), "max-age=31536000");
  const asset = await onRequest(context("/_next/static/x.js", "*/*", 200, "text/javascript"));
  assert.equal(asset.headers.get("Strict-Transport-Security"), null);
});

test("non-document requests and missing assets keep their 404", async () => {
  assert.equal((await onRequest(context("/EGFR/", "*/*", 404))).status, 404);
  assert.equal((await onRequest(context("/_next/static/missing.js", "text/html", 404))).status, 404);
});
