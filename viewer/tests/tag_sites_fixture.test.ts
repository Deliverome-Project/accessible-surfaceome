/*
 * Pins the committed TFRC seed fixtures: they load, expose a surface_loop
 * deterministic site, and the shipped provenances are only the rendered ones.
 *   npx --yes tsx tests/tag_sites_fixture.test.ts
 */
import { loadTaggedSites, loadInternalization } from "../lib/tag-sites";

let failures = 0;
function expect(label: string, got: unknown, want: unknown): void {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { failures++; console.error(`FAIL ${label}\n  got:  ${JSON.stringify(got)}\n  want: ${JSON.stringify(want)}`); }
  else { console.log(`ok   ${label}`); }
}

const ts = loadTaggedSites("TFRC");
expect("TFRC tag-sites loads", ts?.has_data, true);
expect("TFRC uniprot", ts?.uniprot_acc, "P02786");
expect(
  "shipped provenances are rendered-only",
  [...new Set((ts?.sites ?? []).map((s) => s.provenance))].sort(),
  ["deterministic_computed", "literature_retrieved"],
);
expect("has a surface_loop deterministic site", (ts?.sites ?? []).some((s) => s.det_path === "surface_loop"), true);

const intl = loadInternalization("TFRC");
expect("TFRC internalization loads", intl?.has_data, true);
expect("has ≥1 measurement", (intl?.measurements.length ?? 0) > 0, true);

if (failures > 0) { console.error(`\n${failures} assertion(s) failed`); process.exit(1); }
console.log("\nall assertions passed");
