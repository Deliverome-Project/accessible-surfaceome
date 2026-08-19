/*
 * Pins the server-only loaders: read per-gene JSON from public/, reject
 * path-traversal keys, return null on miss. Writes temp fixtures under
 * public/ then cleans up.
 *   npx --yes tsx tests/tag_sites_loader.test.ts
 */
import { mkdirSync, writeFileSync, rmSync } from "node:fs";
import path from "node:path";
import { loadTaggedSites } from "../lib/tag-sites";

let failures = 0;
function expect(label: string, got: unknown, want: unknown): void {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { failures++; console.error(`FAIL ${label}\n  got:  ${JSON.stringify(got)}\n  want: ${JSON.stringify(want)}`); }
  else { console.log(`ok   ${label}`); }
}

const pub = path.join(process.cwd(), "public");
const tsDir = path.join(pub, "tag-sites");
mkdirSync(tsDir, { recursive: true });
writeFileSync(path.join(tsDir, "ZZTESTGENE.json"), JSON.stringify({ has_data: true, gene_symbol: "ZZTESTGENE", uniprot_acc: "P00000", sites: [] }));

try {
  expect("loads tag-sites file", loadTaggedSites("ZZTESTGENE")?.gene_symbol, "ZZTESTGENE");
  expect("missing gene → null", loadTaggedSites("ZZNOPE"), null);
  expect("path-traversal key → null", loadTaggedSites("../secret"), null);
  expect("null key → null", loadTaggedSites(null), null);
} finally {
  rmSync(path.join(tsDir, "ZZTESTGENE.json"), { force: true });
}

if (failures > 0) { console.error(`\n${failures} assertion(s) failed`); process.exit(1); }
console.log("\nall assertions passed");
