import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parseFgLibrary, fgLibrarySymbolSet } from "../lib/fg-library.ts";

test("S1E3 published overlay contains the four reviewed complex targets", () => {
  const raw = JSON.parse(readFileSync(new URL("../public/data/fg-library.json", import.meta.url), "utf8"));
  const library = parseFgLibrary(raw);
  const symbols = fgLibrarySymbolSet(library);
  assert.equal(raw.n_genes, 2344);
  assert.equal(symbols.size, raw.n_genes);
  assert.equal(Object.keys(library.oversized).length, 99);
  for (const [symbol, tier] of Object.entries({ ATP1B3: "T1", HFE: "T1", CDC50A: "T2", P2RX6: "T2" })) {
    assert.equal(library.genes[symbol].tier, tier);
    assert.ok(symbols.has(symbol));
  }
  for (const symbol of ["ATP8B1", "CDC50B", "B2M", "GRIN2A", "GRIN3B"]) {
    assert.equal(symbols.has(symbol), false);
  }
});
