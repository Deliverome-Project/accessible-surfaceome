import assert from "node:assert/strict";
import { test } from "node:test";
import {
  antibodyLink,
  antibodyRegistryUrl,
  antibodySearchUrl,
} from "../lib/antibody-links";

test("RRID link resolves to the Antibody Registry, stripping the RRID: prefix", () => {
  assert.equal(
    antibodyRegistryUrl("RRID:AB_2533976"),
    "https://www.antibodyregistry.org/search?q=AB_2533976",
  );
  // bare id (no prefix) also works
  assert.equal(
    antibodyRegistryUrl("AB_123"),
    "https://www.antibodyregistry.org/search?q=AB_123",
  );
});

test("search URL seeds the gene symbol + reagent keywords", () => {
  const url = antibodySearchUrl("EGFR", {
    name: "anti-EGFR",
    clone: "528",
    vendor: "Santa Cruz",
    catalog: "sc-120",
  });
  assert.ok(url.startsWith("https://www.google.com/search?q="));
  const q = decodeURIComponent(url.split("q=")[1]);
  assert.ok(q.includes("EGFR"));
  assert.ok(q.includes("528"));
  assert.ok(q.includes("Santa Cruz"));
  assert.ok(q.includes("sc-120"));
  // free-text name dropped when structured keywords exist
  assert.ok(!q.includes("anti-EGFR"));
});

test("search URL falls back to the name when no reagent keywords", () => {
  const url = antibodySearchUrl("EGFR", { name: "cetuximab-like clone" });
  const q = decodeURIComponent(url.split("q=")[1]);
  assert.ok(q.includes("cetuximab-like clone"));
});

test("antibodyLink prefers RRID over search", () => {
  const link = antibodyLink("EGFR", {
    name: "anti-EGFR",
    clone: "528",
    rrid: "RRID:AB_2533976",
  });
  assert.equal(link?.kind, "rrid");
  assert.ok(link?.href.includes("antibodyregistry.org"));
});

test("antibodyLink falls back to search when no RRID", () => {
  const link = antibodyLink("EGFR", { name: "anti-EGFR", clone: "528" });
  assert.equal(link?.kind, "search");
  assert.ok(link?.href.includes("google.com/search"));
});

test("antibodyLink returns null when there is nothing to search on", () => {
  const link = antibodyLink("", { name: "" });
  assert.equal(link, null);
});
