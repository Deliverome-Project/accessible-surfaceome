/*
 * Pins the tag-sites data contracts compile and that the provenance
 * token map only covers the two RENDERED provenances (validated_literature
 * is validation-only and must NOT get an overlay color).
 *   npx --yes tsx tests/tag_sites_types.test.ts
 */
import {
  PROVENANCE_TOKEN,
  type TaggedSite,
} from "../lib/tag-sites-types";

let failures = 0;
function expect(label: string, got: unknown, want: unknown): void {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { failures++; console.error(`FAIL ${label}\n  got:  ${JSON.stringify(got)}\n  want: ${JSON.stringify(want)}`); }
  else { console.log(`ok   ${label}`); }
}

expect(
  "token map keys are exactly the two rendered provenances",
  Object.keys(PROVENANCE_TOKEN).sort(),
  ["deterministic_computed", "literature_retrieved"],
);

// A deterministic internal site is representable end-to-end.
const site: TaggedSite = {
  site_id: "TFRC-internal-290", gene_symbol: "TFRC", uniprot_acc: "P02786",
  provenance: "deterministic_computed", det_path: "surface_loop", site_kind: "internal",
  insert_after_residue: 290, residue_before: "I", residue_after: "V",
  topology_state: "O", extracellular: true, compartment: "extracellular",
  tag_type: "ALFA", tag_length_aa: 15, linker: "GS both sides",
  evidence_type: null, functional_impact_measured: null, confidence: "medium",
  rationale: null, sources: [], plddt: 96, conservation_rank: 7, median_conservation: 0.28,
};
expect("site round-trips gene", site.gene_symbol, "TFRC");

if (failures > 0) { console.error(`\n${failures} assertion(s) failed`); process.exit(1); }
console.log("\nall assertions passed");
