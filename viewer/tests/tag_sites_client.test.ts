// viewer/tests/tag_sites_client.test.ts
/*
 * Pins the client parse guard: only accepts a well-formed TaggedSitesFile,
 * returns null otherwise (so a 404 / HTML error page never crashes the shell).
 *   npx --yes tsx tests/tag_sites_client.test.ts
 */
import { fetchTaggedSites, parseTaggedSitesFile } from "../lib/tag-sites-client";

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

// fetchTaggedSites: isoform_pins are static-only, so they must be MERGED from the
// static asset onto a Worker response (which serves sites but not pins).
async function run(): Promise<void> {
  const worker = { has_data: true, gene_symbol: "TFRC", uniprot_acc: "P02786",
                   sites: [{ site_id: "s1" }] };
  const staticFile = { has_data: true, gene_symbol: "TFRC", uniprot_acc: "P02786",
                       sites: [{ site_id: "s1" }],
                       isoform_pins: [{ site_id: "p1", isoform_id: "TFRC-2",
                                        classification: "unique", left_pct: 50 }] };
  const orig = globalThis.fetch;
  globalThis.fetch = (async (url: unknown) => ({
    ok: true,
    json: async () => (String(url).includes("/v1/tag-sites/") ? worker : staticFile),
  })) as unknown as typeof fetch;
  try {
    const merged = await fetchTaggedSites("TFRC", "https://api.example");
    expect("worker sites kept", merged?.sites.length, 1);
    expect("static isoform_pins merged onto worker response", merged?.isoform_pins?.length, 1);
    const staticOnly = await fetchTaggedSites("TFRC"); // no apiBase -> static carries pins
    expect("static path carries isoform_pins", staticOnly?.isoform_pins?.length, 1);
  } finally {
    globalThis.fetch = orig;
  }
}

await run();

if (failures > 0) { console.error(`\n${failures} assertion(s) failed`); process.exit(1); }
console.log("\nall assertions passed");
