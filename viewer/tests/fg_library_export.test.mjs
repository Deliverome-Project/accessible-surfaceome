import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parseFgLibrary, fgLibrarySymbolSet } from "../lib/fg-library.ts";

test("S1E3 published overlay contains the four reviewed complex targets", () => {
  const raw = JSON.parse(readFileSync(new URL("../public/data/fg-library.json", import.meta.url), "utf8"));
  const library = parseFgLibrary(raw);
  const symbols = fgLibrarySymbolSet(library);
  assert.equal(raw.n_genes, 2369);
  assert.equal(symbols.size, raw.n_genes);
  assert.equal(Object.keys(library.oversized).length, 99);
  for (const [symbol, tier] of Object.entries({ ATP1B3: "T1", HFE: "T1", CDC50A: "T2", P2RX6: "T2" })) {
    assert.equal(library.genes[symbol].tier, tier);
    assert.ok(symbols.has(symbol));
  }
  // L1 gene list (deliverome-analysis s4e9): the frozen 2,368-gene root plus
  // SLC67A1 (gene_list_additions.tsv, Becca 2026-11-02), minus EPPIN
  // (gene_list_exclusions.tsv, removed 2026-10-11).
  assert.equal(library.genes.SLC67A1.tier, "T2");
  for (const symbol of ["ATP8B1", "CDC50B", "B2M", "GRIN2A", "GRIN3B", "EPPIN"]) {
    assert.equal(symbols.has(symbol), false);
  }
});
