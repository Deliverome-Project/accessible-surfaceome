import assert from "node:assert/strict";
import { test } from "node:test";
import {
  emptyCatalogUrlState,
  isEmptyCatalogUrlState,
  parseCatalogUrl,
  serializeCatalogUrl,
  type CatalogUrlVocabulary,
} from "../lib/catalog-url-state";

const VOCAB: CatalogUrlVocabulary = {
  presets: ["canonical", "likely", "induced"],
  triggers: ["cancer", "immune"],
  db: ["uniprot", "go", "surfy", "cspa", "hpa"],
  tiers: ["canonical", "likely", "low", "uncertain", "no"],
  verdicts: ["yes", "contextual", "no"],
  reasons: ["gpi_anchored", "cytoplasmic"],
  ddEnum: { surface_method_direct: ["flow_cytometry", "functional_surface_assay"] },
  ddBoolKeys: ["has_tm"],
  sortKeys: ["symbol", "n_sources", "dd_access", "dd_conf"],
};

test("the default view serializes to an empty query", () => {
  const s = emptyCatalogUrlState();
  assert.equal(serializeCatalogUrl(s), "");
  assert.ok(isEmptyCatalogUrlState(s));
  assert.ok(isEmptyCatalogUrlState(parseCatalogUrl("", VOCAB)));
});

test("a paper-figure link parses to the intended filters", () => {
  // Figure 3: the 87 definitive surface calls no database lists.
  const s = parseCatalogUrl("?nsrc=0&triage=yes", VOCAB);
  assert.deepEqual(s.nSources, [0]);
  assert.deepEqual(s.verdicts, ["yes"]);
  assert.equal(s.deepDive, null);
});

test("round-trips every parameter, in a fixed key order", () => {
  const s = emptyCatalogUrlState();
  s.q = "cd 3";
  s.presets = ["induced"];
  s.triggers = ["cancer", "immune"];
  s.lowLit = true;
  s.db = ["uniprot", "hpa"];
  s.nSources = [5, 0];
  s.tiers = ["low", "no"];
  s.verdicts = ["contextual"];
  s.reasons = ["gpi_anchored"];
  s.deepDive = "yes";
  s.surfaceBind = "ge1";
  s.ddEnum = { surface_method_direct: ["flow_cytometry"] };
  s.ddBool = { has_tm: "yes" };
  s.sort = "dd_conf";
  s.dir = "asc";
  const qs = serializeCatalogUrl(s);
  assert.equal(
    qs,
    "q=cd%203&preset=induced&trigger=cancer,immune&lowlit=1&db=uniprot,hpa&nsrc=0,5" +
      "&tier=low,no&triage=contextual&reason=gpi_anchored&dd=yes&sb=ge1" +
      "&f.surface_method_direct=flow_cytometry&b.has_tm=yes&sort=dd_conf&dir=asc",
  );
  const back = parseCatalogUrl(qs, VOCAB);
  assert.deepEqual(back, { ...s, nSources: [0, 5] });
});

test("unknown values and parameters are dropped, not fatal", () => {
  const s = parseCatalogUrl(
    "?tier=canonical,bogus&nsrc=0,9,x&db=uniprot,nope&f.surface_method_direct=flow_cytometry,zzz" +
      "&f.not_a_field=1&b.has_tm=maybe&dd=perhaps&sb=lots&utm_source=x",
    VOCAB,
  );
  assert.deepEqual(s.tiers, ["canonical"]);
  assert.deepEqual(s.nSources, [0]);
  assert.deepEqual(s.db, ["uniprot"]);
  assert.deepEqual(s.ddEnum, { surface_method_direct: ["flow_cytometry"] });
  assert.deepEqual(s.ddBool, {});
  assert.equal(s.deepDive, null);
  assert.equal(s.surfaceBind, null);
});

test("duplicate values collapse", () => {
  assert.deepEqual(parseCatalogUrl("?tier=low,low,no", VOCAB).tiers, ["low", "no"]);
});

test("a sort-only link is not the default view and round-trips", () => {
  const s = parseCatalogUrl("?sort=n_sources", VOCAB);
  assert.equal(s.sort, "n_sources");
  assert.equal(s.dir, null, "no dir means the column's natural direction");
  assert.ok(!isEmptyCatalogUrlState(s));
  assert.equal(serializeCatalogUrl(s), "sort=n_sources");
});

test("filters and sort combine in one link", () => {
  const s = parseCatalogUrl("?preset=likely&sort=symbol&dir=desc", VOCAB);
  assert.deepEqual(s.presets, ["likely"]);
  assert.equal(s.sort, "symbol");
  assert.equal(s.dir, "desc");
});

test("an unknown sort column is dropped along with its dir; a bad dir is ignored", () => {
  const unknown = parseCatalogUrl("?sort=not_a_column&dir=asc", VOCAB);
  assert.equal(unknown.sort, null);
  assert.equal(unknown.dir, null);
  assert.ok(isEmptyCatalogUrlState(unknown));
  const badDir = parseCatalogUrl("?sort=dd_conf&dir=sideways", VOCAB);
  assert.equal(badDir.sort, "dd_conf");
  assert.equal(badDir.dir, null);
});
