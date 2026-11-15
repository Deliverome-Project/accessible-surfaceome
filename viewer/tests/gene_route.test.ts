/*
 *   npx --yes tsx --test tests/gene_route.test.ts
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { acceptsHtml, geneSegment, routeMissing, symbolSet } from "../lib/gene-route.js";

const published = symbolSet(["CD44", "HLA-A", "C1orf43"]);
const HTML = "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8";

test("published genes get the shell, with or without a trailing slash and in any case", () => {
  for (const p of ["/CD44/", "/CD44", "/cd44/", "/HLA-A/", "/C1orf43/"]) {
    assert.equal(routeMissing(p, HTML, published), "gene", p);
  }
});

test("curl and link checkers (*/* or no Accept) get the shell too", () => {
  assert.equal(routeMissing("/CD44/", "*/*", published), "gene");
  assert.equal(routeMissing("/CD44/", null, published), "gene");
  assert.equal(routeMissing("/CD44/", "application/json", published), "404");
});

test("unknown symbols, multi-segment paths and missing assets keep their 404", () => {
  for (const p of [
    "/zzqq-nonsense/",
    "/NOTAGENE/",
    "/a/b/",
    "/_next/static/chunks/x.js",
    "/data/surfaceome/CD44.json",
    "/favicon.ico",
    "/%E0%A4%A/",
  ]) {
    assert.equal(routeMissing(p, HTML, published), "404", p);
  }
});

test("without a symbol list every gene-shaped path is served", () => {
  assert.equal(symbolSet([]), null);
  assert.equal(symbolSet(undefined), null);
  assert.equal(routeMissing("/zzqq/", HTML, null), "gene");
  assert.equal(routeMissing("/a/b/", HTML, null), "404");
});

test("helpers", () => {
  assert.equal(geneSegment("/CD44/"), "CD44");
  assert.equal(geneSegment("/"), null);
  assert.equal(acceptsHtml(""), true);
  assert.equal(acceptsHtml("image/avif,image/webp"), false);
});
