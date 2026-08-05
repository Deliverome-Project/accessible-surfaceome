/*  npx --yes tsx tests/internalization_client.test.ts  */
import { parseInternalizationFile } from "../lib/tag-sites-client";

let failures = 0;
function expect(l: string, got: unknown, want: unknown): void {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { failures++; console.error(`FAIL ${l}\n  got:  ${JSON.stringify(got)}\n  want: ${JSON.stringify(want)}`); }
  else { console.log(`ok   ${l}`); }
}

expect("valid parses", parseInternalizationFile({ has_data: true, gene_symbol: "TFRC", uniprot_acc: "P02786", measurements: [], qualitative_statements: [] })?.gene_symbol, "TFRC");
expect("missing measurements -> null", parseInternalizationFile({ has_data: true, gene_symbol: "X", uniprot_acc: "Y", qualitative_statements: [] }), null);
expect("html error -> null", parseInternalizationFile("<html>404</html>"), null);

if (failures > 0) { console.error(`\n${failures} assertion(s) failed`); process.exit(1); }
console.log("\nall assertions passed");
