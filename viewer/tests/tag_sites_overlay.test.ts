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

// category derivation (the fine-grained color axis): lane / terminus / snorkel / literature
const cats = renderableTagSites([
  site({ site_id: "lit", provenance: "literature_retrieved" }),
  site({ site_id: "diso", provenance: "deterministic_computed", det_path: "disorder" }),
  site({ site_id: "loop", provenance: "deterministic_computed", det_path: "surface_loop" }),
  site({ site_id: "tn", provenance: "deterministic_computed", det_path: "terminal", site_kind: "terminal_n", insert_after_residue: null }),
  site({ site_id: "tc", provenance: "deterministic_computed", det_path: "terminal", site_kind: "terminal_c", insert_after_residue: null }),
  site({ site_id: "snork", provenance: "deterministic_computed", det_path: "snorkel", site_kind: "terminal_c", insert_after_residue: null }),
], L);
expect("categories derived per lane/terminus/snorkel/literature",
  cats.map((s) => s.category),
  ["literature", "disorder", "surface_loop", "terminal_n", "terminal_c", "snorkel"]);

// out-of-range residue is dropped, not clamped silently into a wrong position
const oob = renderableTagSites([site({ site_id: "oob", insert_after_residue: 9999 })], L);
expect("out-of-range residue dropped", oob.length, 0);

if (failures > 0) { console.error(`\n${failures} assertion(s) failed`); process.exit(1); }
console.log("\nall assertions passed");

// One anchor ball per span: deterministic sites sharing a residue_range collapse
// to a single representative (the residue closest to the span midpoint).
const collapsed = renderableTagSites([
  site({ site_id: "d1", provenance: "deterministic_computed", det_path: "disorder", insert_after_residue: 27, residue_range: "H27-K159" }),
  site({ site_id: "d2", provenance: "deterministic_computed", det_path: "disorder", insert_after_residue: 91, residue_range: "H27-K159" }),
  site({ site_id: "d3", provenance: "deterministic_computed", det_path: "disorder", insert_after_residue: 159, residue_range: "H27-K159" }),
  site({ site_id: "loop", provenance: "deterministic_computed", det_path: "surface_loop", insert_after_residue: 200, residue_range: "A190-A210" }),
], 400);
const disorderBalls = collapsed.filter((r) => r.category === "disorder");
expect("one anchor per disorder span", disorderBalls.length, 1);
expect("anchor is midpoint-closest (91 in H27-K159)", disorderBalls[0].residue, 91);
expect("separate span (surface_loop) kept", collapsed.filter((r) => r.category === "surface_loop").length, 1);

// screen_validated (Tedman-style control tag sites) must render, not be dropped
// like validated_literature — same category-derivation path as tagSiteCategory.
const screenValidated = renderableTagSites([
  site({
    site_id: "X-nterm", gene_symbol: "X", uniprot_acc: "P1", provenance: "screen_validated",
    det_path: null, site_kind: "terminal_n", insert_after_residue: null, residue_before: null,
    residue_after: "M", topology_state: "S", extracellular: true, compartment: "extracellular",
    tag_type: "HA", tag_length_aa: 9, linker: null, evidence_type: null,
    functional_impact_measured: null, confidence: "high", rationale: null, sources: [],
    plddt: null, conservation_rank: null, median_conservation: null,
  }),
], 300);
expect("screen_validated N-terminal site renders", screenValidated.length, 1);
expect("screen_validated category carried", screenValidated[0]?.category, "screen_validated");

// literature_enriched must render. The enrichment pass publishes BESIDE
// literature_retrieved rather than over it, and the provenance was added to the
// TaggedSiteProvenance union without being added to RENDERED or to the four
// scattered `=== "literature_retrieved"` checks — so the pass stored and served
// sites that no surface displayed. AQP4 after 141 and FZD1 after 69 are the two
// positioned sites this unblocks.
const enriched = renderableTagSites([
  site({ site_id: "AQP4-enr", gene_symbol: "AQP4", provenance: "literature_enriched",
         site_kind: "internal", insert_after_residue: 141, extracellular: true }),
], 323);
expect("literature_enriched renders", enriched.length, 1);
expect("literature_enriched residue carried", enriched[0]?.residue, 141);
expect("literature_enriched colours as literature", enriched[0]?.category, "literature");

// ...and is held to the same surface-accessibility rule as literature_retrieved:
// an intracellular published tag is not a surface site, except a terminal_n one
// (placed after signal-peptide cleavage, so its residue may read "signal").
const enrichedIntra = renderableTagSites([
  site({ site_id: "intra", provenance: "literature_enriched", site_kind: "internal",
         insert_after_residue: 50, extracellular: false }),
], 300);
expect("intracellular literature_enriched dropped", enrichedIntra.length, 0);

const enrichedNterm = renderableTagSites([
  site({ site_id: "nterm", provenance: "literature_enriched", site_kind: "terminal_n",
         insert_after_residue: 22, extracellular: false, topology_state: "S" }),
], 300);
expect("terminal_n literature_enriched kept despite !extracellular", enrichedNterm.length, 1);

// validated_literature stays unrendered — widening RENDERED must not widen it.
const validationOnly = renderableTagSites([
  site({ site_id: "vl", provenance: "validated_literature", site_kind: "internal",
         insert_after_residue: 100, extracellular: true }),
], 300);
expect("validated_literature still dropped", validationOnly.length, 0);

if (failures > 0) { console.error(`\n${failures} assertion(s) failed`); process.exit(1); }
console.log("\nall assertions passed (incl. screen_validated + literature_enriched)");
