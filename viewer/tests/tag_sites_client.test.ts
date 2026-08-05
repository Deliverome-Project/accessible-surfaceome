// viewer/tests/tag_sites_client.test.ts
/*
 * Pins the client parse guard: only accepts a well-formed TaggedSitesFile,
 * returns null otherwise (so a 404 / HTML error page never crashes the shell).
 *   npx --yes tsx tests/tag_sites_client.test.ts
 */
import { parseTaggedSitesFile } from "../lib/tag-sites-client";

let failures = 0;
function expect(label: string, got: unknown, want: unknown): void {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { failures++; console.error(`FAIL ${label}\n  got:  ${JSON.stringify(got)}\n  want: ${JSON.stringify(want)}`); }
  else { console.log(`ok   ${label}`); }
}

expect("valid file parses", parseTaggedSitesFile({ has_data: true, gene_symbol: "TFRC", uniprot_acc: "P02786", sites: [] })?.gene_symbol, "TFRC");
expect("missing sites -> null", parseTaggedSitesFile({ has_data: true, gene_symbol: "X", uniprot_acc: "Y" }), null);
expect("non-object -> null", parseTaggedSitesFile("<html>404</html>"), null);
expect("null -> null", parseTaggedSitesFile(null), null);

if (failures > 0) { console.error(`\n${failures} assertion(s) failed`); process.exit(1); }
console.log("\nall assertions passed");
