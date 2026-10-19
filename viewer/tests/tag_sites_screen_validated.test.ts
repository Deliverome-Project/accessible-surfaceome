// viewer/tests/tag_sites_screen_validated.test.ts
/*
 * Pins the screen_validated provenance -> overlay category mapping + label.
 * screen_validated (Tedman GPCR N-terminal HA controls) must resolve to its
 * OWN category (not fall into the generic "literature" bucket) so it colors
 * with --tag-site-screen-validated and reads "Screen-validated" in legends.
 *   npx --yes tsx tests/tag_sites_screen_validated.test.ts
 */
import { CATEGORY_HEX, CATEGORY_LABEL, tagSiteCategory } from "../lib/tag-sites-types";

let failures = 0;
function expect(label: string, got: unknown, want: unknown): void {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) {
    failures++;
    console.error(`FAIL ${label}\n  got:  ${JSON.stringify(got)}\n  want: ${JSON.stringify(want)}`);
  } else {
    console.log(`ok   ${label}`);
  }
}

const cat = tagSiteCategory({
  provenance: "screen_validated",
  det_path: null,
  site_kind: "terminal_n",
});
expect("screen_validated -> screen_validated category", cat, "screen_validated");
expect("screen_validated label", CATEGORY_LABEL[cat], "Screen-validated");
expect("screen_validated hex is #rrggbb", /^#[0-9a-fA-F]{6}$/.test(CATEGORY_HEX[cat]), true);

if (failures > 0) {
  console.error(`\n${failures} assertion(s) failed`);
  process.exit(1);
}
console.log("\nall assertions passed");
