// viewer/tests/tag_sites_overlay.test.ts
/*
 * Pins the pure overlay mapper: rendered provenances only, residue resolution
 * (terminal_c -> C-terminus), left-percent, and clamping.
 *   npx --yes tsx tests/tag_sites_overlay.test.ts
 */
import { renderableTagSites } from "../lib/tag-sites-overlay";
import type { TaggedSite } from "../lib/tag-sites-types";

let failures = 0;
function expect(label: string, got: unknown, want: unknown): void {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { failures++; console.error(`FAIL ${label}\n  got:  ${JSON.stringify(got)}\n  want: ${JSON.stringify(want)}`); }
  else { console.log(`ok   ${label}`); }
}

function site(p: Partial<TaggedSite>): TaggedSite {
  return {
    site_id: "s", gene_symbol: "TFRC", uniprot_acc: "P02786",
    provenance: "literature_retrieved", det_path: null, site_kind: "internal",
    insert_after_residue: 100, residue_before: null, residue_after: null,
    topology_state: "O", extracellular: true, compartment: "extracellular",
    tag_type: "ALFA", tag_length_aa: 15, linker: null, evidence_type: null,
    functional_impact_measured: null, confidence: null, rationale: null,
    sources: [], plddt: null, conservation_rank: null, median_conservation: null,
    ...p,
  };
}

const L = 200; // topology length

const out = renderableTagSites([
  site({ site_id: "internal", insert_after_residue: 100, provenance: "literature_retrieved" }),
  site({ site_id: "cterm", site_kind: "terminal_c", insert_after_residue: null, provenance: "deterministic_computed", det_path: "disorder" }),
  site({ site_id: "validated", provenance: "validated_literature" }), // must be dropped
  site({ site_id: "nulljunction", site_kind: "internal", insert_after_residue: null }), // -> residue 1
], L);

expect("validated_literature dropped", out.map((s) => s.siteId), ["internal", "cterm", "nulljunction"]);
expect("internal residue 100 -> 50%", out[0].leftPct, 50);
expect("terminal_c resolves to C-terminus (residue L)", out[1].residue, L);
expect("terminal_c -> 100%", out[1].leftPct, 100);
expect("null internal junction -> residue 1", out[2].residue, 1);
expect("provenance carried", out[1].provenance, "deterministic_computed");

// out-of-range residue is dropped, not clamped silently into a wrong position
const oob = renderableTagSites([site({ site_id: "oob", insert_after_residue: 9999 })], L);
expect("out-of-range residue dropped", oob.length, 0);

if (failures > 0) { console.error(`\n${failures} assertion(s) failed`); process.exit(1); }
console.log("\nall assertions passed");
