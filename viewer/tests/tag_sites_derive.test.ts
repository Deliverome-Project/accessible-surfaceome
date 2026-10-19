/*
 * Pins junction verification against the canonical sequence and the
 * compartment/extracellular derivation from DeepTMHMM topology.
 *   npx --yes tsx tests/tag_sites_derive.test.ts
 */
import { verifyJunction, deriveCompartment } from "../lib/tag-sites-derive";

let failures = 0;
function expect(label: string, got: unknown, want: unknown): void {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { failures++; console.error(`FAIL ${label}\n  got:  ${JSON.stringify(got)}\n  want: ${JSON.stringify(want)}`); }
  else { console.log(`ok   ${label}`); }
}

// sequence indexed 1..N: position 3 = "C", position 4 = "D"
const seq = "ABCDEFG"; // A1 B2 C3 D4 E5 F6 G7

expect("valid internal junction after C3 (before C, after D)",
  verifyJunction(seq, { insert_after_residue: 3, residue_before: "C", residue_after: "D", site_kind: "internal" }), true);
expect("wrong residue_before invalidates",
  verifyJunction(seq, { insert_after_residue: 3, residue_before: "X", residue_after: "D", site_kind: "internal" }), false);
expect("out-of-range junction invalidates",
  verifyJunction(seq, { insert_after_residue: 99, residue_before: "C", residue_after: "D", site_kind: "internal" }), false);
expect("terminal_n before residue 1 needs no before-check",
  verifyJunction(seq, { insert_after_residue: null, residue_before: null, residue_after: "A", site_kind: "terminal_n" }), true);

// topology: S1-2, O3-5, M6, I7  → residue 4 extracellular, residue 7 intracellular
const topo = "SSOOOMI";
expect("internal junction at residue 4 → extracellular",
  deriveCompartment(topo, 4, "internal"), { compartment: "extracellular", extracellular: true, topology_state: "O" });
expect("junction in intracellular tail",
  deriveCompartment(topo, 7, "internal"), { compartment: "intracellular", extracellular: false, topology_state: "I" });
expect("missing topology → unknown, not EC",
  deriveCompartment("", 4, "internal"), { compartment: "unknown", extracellular: false, topology_state: null });

if (failures > 0) { console.error(`\n${failures} assertion(s) failed`); process.exit(1); }
console.log("\nall assertions passed");
