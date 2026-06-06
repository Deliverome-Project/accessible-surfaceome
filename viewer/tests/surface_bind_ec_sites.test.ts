/*
 * Unit test for the SURFACE-Bind EC-site helper (lib/surface-bind.ts).
 *
 * The viewer has no JS unit-test runner, so this is a standalone tsx
 * script (same convention as list_surfaceome_genes.test.ts):
 *
 *   npx --yes tsx tests/surface_bind_ec_sites.test.ts
 *
 * What it pins:
 *   - EGFR (P00533): SURFACE-Bind scores 8 patches, but 3 anchors sit
 *     in the cytoplasmic kinase domain. Only 5 are extracellular —
 *     the count the viewer labels "EC sites" must be 5, not 8.
 *   - all-intracellular protein → 0 EC sites (scored, but none EC).
 *   - missing / short topology → anchor compartment "unknown", which
 *     is NOT counted as EC (we never claim EC without evidence).
 */

import { compartmentAt, ecSites } from "../lib/surface-bind";

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

/** Build a DeepTMHMM-style per-residue topology string with the EGFR
 *  P00533 architecture: signal 1-24, ECD 25-645, TM 646-668,
 *  cytoplasmic 669-end. 1 char per residue. */
function egfrTopology(length = 1210): string {
  const chars: string[] = [];
  for (let r = 1; r <= length; r++) {
    if (r <= 24) chars.push("S");
    else if (r <= 645) chars.push("O");
    else if (r <= 668) chars.push("M");
    else chars.push("I");
  }
  return chars.join("");
}

type Site = { site_id: number; anchor_residue: number; area_a2: number };
function sitesFrom(anchors: number[]): Site[] {
  return anchors.map((a, i) => ({ site_id: i, anchor_residue: a, area_a2: 1200 }));
}

// --- EGFR: 8 scored anchors, 5 extracellular -------------------------
const topo = egfrTopology();
const egfrAnchors = [743, 948, 599, 178, 764, 69, 549, 372];
const ec = ecSites(sitesFrom(egfrAnchors), topo);
expect("EGFR EC-site count is 5", ec.length, 5);
expect(
  "EGFR EC anchors are the extracellular ones",
  ec.map((s) => s.anchor_residue).sort((a, b) => a - b),
  [69, 178, 372, 549, 599],
);

// --- per-residue compartment classification --------------------------
expect("anchor in ECD → extracellular", compartmentAt(topo, 599), "extracellular");
expect("anchor in kinase domain → intracellular", compartmentAt(topo, 743), "intracellular");
expect("anchor in TM helix → membrane", compartmentAt(topo, 650), "membrane");
expect("anchor in signal peptide → signal", compartmentAt(topo, 10), "signal");

// --- all-intracellular protein → 0 EC sites --------------------------
const allIc = ecSites(sitesFrom([700, 800, 900]), topo);
expect("all-intracellular protein → 0 EC sites", allIc.length, 0);

// --- missing / short topology → unknown, not counted as EC -----------
expect("empty topology → 0 EC sites", ecSites(sitesFrom([69, 178]), "").length, 0);
expect("out-of-range residue → unknown", compartmentAt(topo, 99999), "unknown");

if (failures > 0) {
  console.error(`\n${failures} assertion(s) failed`);
  process.exit(1);
}
console.log("\nall assertions passed");
