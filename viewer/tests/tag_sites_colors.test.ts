// viewer/tests/tag_sites_colors.test.ts
/*
 * Pins the WebGL hex map: same two keys as PROVENANCE_TOKEN, each a #rrggbb
 * string. 3Dmol needs concrete hex (CSS vars don't resolve in WebGL), so the
 * hex map must stay in sync with the --tag-site-* tokens.
 *   npx --yes tsx tests/tag_sites_colors.test.ts
 */
import { PROVENANCE_TOKEN, PROVENANCE_HEX } from "../lib/tag-sites-types";

let failures = 0;
function expect(label: string, got: unknown, want: unknown): void {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { failures++; console.error(`FAIL ${label}\n  got:  ${JSON.stringify(got)}\n  want: ${JSON.stringify(want)}`); }
  else { console.log(`ok   ${label}`); }
}

expect("hex map keys match token map keys",
  Object.keys(PROVENANCE_HEX).sort(), Object.keys(PROVENANCE_TOKEN).sort());
for (const [k, v] of Object.entries(PROVENANCE_HEX)) {
  expect(`${k} is #rrggbb`, /^#[0-9a-fA-F]{6}$/.test(v), true);
}

if (failures > 0) { console.error(`\n${failures} assertion(s) failed`); process.exit(1); }
console.log("\nall assertions passed");
