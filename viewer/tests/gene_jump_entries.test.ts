/*
 * Behavioral test for buildGeneJumpEntries() — the pure helper that turns the
 * /v1/genes index + the build-baked synonym overlay into the GeneJump
 * typeahead set. Regression guard for the "Nav1.7 doesn't find SCN9A on the
 * gene-page dropdown" bug: the dropdown searched g.synonyms, but the entries
 * carried none (the /v1/genes index has no synonyms), so only the symbol
 * matched. The overlay restores alias matching, the same way the homepage
 * catalog search gets it from loadGeneNamesMap.
 *
 * The viewer has no JS unit-test runner, so this is a standalone tsx script:
 *   npx --yes tsx tests/gene_jump_entries.test.ts
 * Exits non-zero on the first failed assertion.
 */
import { buildGeneJumpEntries } from "../lib/gene-jump-entries";

let failures = 0;
function check(label: string, cond: boolean): void {
  if (cond) {
    console.log(`  ok   ${label}`);
  } else {
    console.error(`  FAIL ${label}`);
    failures += 1;
  }
}

// Mirrors GeneJump.tsx's match predicate (symbol or any synonym contains the
// upper-cased query) so the test pins the actual user-visible behaviour.
function matches(entry: { symbol: string; synonyms?: string[] }, query: string): boolean {
  const q = query.trim().toUpperCase();
  if (entry.symbol.toUpperCase().includes(q)) return true;
  return (entry.synonyms ?? []).some((a) => a.toUpperCase().includes(q));
}

const genesJson = {
  genes: [
    { gene_symbol: "SCN9A" },
    { gene_symbol: "TFRC" },
    { gene_symbol: "" }, // empty → dropped
  ],
};
const overlay = {
  SCN9A: ["ETHA", "FEB3B", "Nav1.7", "PN1"],
  // TFRC deliberately absent from the overlay
};

// --- with overlay: alias query resolves to the right gene ---
const withOverlay = buildGeneJumpEntries(genesJson, overlay);
check("empty gene_symbol is dropped", withOverlay.length === 2);
const scn9a = withOverlay.find((e) => e.symbol === "SCN9A")!;
check("SCN9A carries its synonyms", (scn9a.synonyms ?? []).includes("Nav1.7"));
check('"Nav1.7" matches SCN9A (exact case)', matches(scn9a, "Nav1.7"));
check('"nav1.7" matches SCN9A (case-insensitive)', matches(scn9a, "nav1.7"));
check(
  "SCN9A is NOT hit by an unrelated alias query",
  !matches(scn9a, "TFRC"),
);
const tfrc = withOverlay.find((e) => e.symbol === "TFRC")!;
check("gene absent from overlay has no synonyms", tfrc.synonyms === undefined);
check("symbol match still works without synonyms", matches(tfrc, "TFRC"));

// --- null / missing overlay: degrades to symbol-only, never throws ---
const noOverlay = buildGeneJumpEntries(genesJson, null);
check("null overlay → entries built", noOverlay.length === 2);
check(
  "null overlay → no synonyms (pre-fix symbol-only behaviour)",
  noOverlay.every((e) => e.synonyms === undefined),
);
check(
  'null overlay → alias query "Nav1.7" does NOT match (documents the old bug)',
  !matches(noOverlay.find((e) => e.symbol === "SCN9A")!, "Nav1.7"),
);

// --- malformed input is tolerated ---
check("null genesJson → []", buildGeneJumpEntries(null, overlay).length === 0);
check("missing genes key → []", buildGeneJumpEntries({}, overlay).length === 0);

console.log("=== verdict ===");
if (failures === 0) {
  console.log("PASS");
} else {
  console.error(`FAIL (${failures} assertion(s))`);
  process.exit(1);
}
