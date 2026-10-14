/*
 * Unit test for the UniProt→PDB-author projection (lib/structure-projection.ts).
 *
 * The viewer has no JS unit-test runner, so this is a standalone tsx
 * script (same convention as surface_bind_ec_sites.test.ts):
 *
 *   npx --yes tsx tests/structure_projection.test.ts
 *
 * The case that forced this module out of the component: MS4A1 (P11836)
 * on 8VGN chain G. PDBe maps the chain to UniProt 41-297; the chain
 * models author 46-103 and 113-219, and its author numbers ARE the
 * UniProt numbers. The legacy SEQRES offset is -37. Both offsets land
 * the same 165 residues on real atoms, so residue counting ties, the tie
 * kept the legacy offset, and asking the viewer for residue 161 drew
 * residue 124 — a leucine in the middle of TM3 instead of the surface
 * tyrosine in the extracellular loop. Only the amino acids separate them.
 *
 * Fixture provenance: the sequence is AFDB's `uniprotSequence` for
 * P11836 (alphafold.ebi.ac.uk/api/prediction/P11836, 297 aa) and the
 * modelled ranges are read from RCSB 8VGN `auth_seq_id` on chain G. The
 * deposit's residue identities match the canonical sequence at the same
 * numbers for all 165 residues, which is what makes offset 0 correct.
 */

import {
  bestLinearOffset,
  identityScore,
  observedResSeq,
  overlapCount,
  residueOneLetterByResSeq,
} from "../lib/structure-projection";
import type { SequenceCheck } from "../lib/structure-projection";

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

const MS4A1 =
  "MTTPRNSVNGTFPAEPMKGPIAMQSGPKPLFRRMSSLVGPTQSFFMRESKTLGAVQIMNG" +
  "LFHIALGGLLMIPAGIYAPICVTVWYPLWGGIMYIISGSLLAATEKNSRKCLVKGKMIMN" +
  "SLSLFAAISGMILSIMDILNIKISHFLKMESLNFIRAHTPYINIYNCEPANPSEKNSPST" +
  "QYCYSIQSLFLGILSVMLIFAFFQELVIAGIVENEWKRTCSRPKSNIVLLSAEEKKEQTI" +
  "EIKEEVVGLTETSSQPKNEEDIEIIPIQEEEEEETETNFPEPPQDQESSPIENDSSP";

const MS4A1_MODELLED: Array<[number, number]> = [[46, 103], [113, 219]];

const ONE_TO_THREE: Record<string, string> = {
  A: "ALA", R: "ARG", N: "ASN", D: "ASP", C: "CYS", Q: "GLN", E: "GLU",
  G: "GLY", H: "HIS", I: "ILE", L: "LEU", K: "LYS", M: "MET", F: "PHE",
  P: "PRO", S: "SER", T: "THR", W: "TRP", Y: "TYR", V: "VAL",
};

/** One CA line per modelled residue, in real PDB column positions. */
function pdbChain(
  chain: string,
  ranges: Array<[number, number]>,
  resAt: (resi: number) => string,
): string {
  const lines: string[] = [];
  let serial = 1;
  for (const [lo, hi] of ranges) {
    for (let r = lo; r <= hi; r += 1) {
      const three = ONE_TO_THREE[resAt(r)];
      if (!three) continue;
      lines.push(
        "ATOM  " + String(serial).padStart(5) + "  CA  " + three.padStart(3) +
        " " + chain + String(r).padStart(4) + "      11.000  12.000  13.000  1.00 50.00           C",
      );
      serial += 1;
    }
  }
  return lines.join("\n");
}

// ---------------------------------------------------------------------
// MS4A1 / 8VGN chain G — author numbering equals UniProt numbering.
// ---------------------------------------------------------------------
const pdb = pdbChain("G", MS4A1_MODELLED, (r) => MS4A1[r - 1]);
const observed = observedResSeq(pdb, "G");
const resNames = residueOneLetterByResSeq(pdb, "G");
const check: SequenceCheck = { seq: MS4A1, resNames };
const UNP_LO = 41;
const UNP_HI = 297;
const SEQRES_OFFSET = -37;

expect("8VGN chain G models 165 residues", observed.size, 165);
expect("the file has a tyrosine at author 161", resNames.get(161), "Y");
expect("the file has a leucine at author 124", resNames.get(124), "L");

// Why counting alone cannot choose: the mapped window is wider than the
// modelled stretch, so both offsets keep all 165 residues inside it.
expect(
  "offset 0 and the legacy offset cover the same residue count",
  [
    overlapCount(UNP_LO, UNP_HI, 0, observed),
    overlapCount(UNP_LO, UNP_HI, SEQRES_OFFSET, observed),
  ],
  [165, 165],
);

// What does choose: the amino acids.
expect(
  "offset 0 puts the right residue at every tested position",
  identityScore(UNP_LO, UNP_HI, 0, check),
  { matches: 165, tested: 165 },
);
const wrong = identityScore(UNP_LO, UNP_HI, SEQRES_OFFSET, check);
expect(
  "the legacy offset is near chance",
  wrong.matches / wrong.tested < 0.2,
  true,
);

expect(
  "with the sequence, the projection is author == UniProt",
  bestLinearOffset(UNP_LO, UNP_HI, [0, SEQRES_OFFSET], observed, SEQRES_OFFSET, check),
  0,
);
expect(
  "so residue 161 selects author 161",
  161 + bestLinearOffset(UNP_LO, UNP_HI, [0, SEQRES_OFFSET], observed, SEQRES_OFFSET, check),
  161,
);

// The seeded defect: drop the sequence and the shipped bug comes back,
// which is what the dev site was doing — 161 drew 124.
expect(
  "without a sequence the tie still falls to the legacy offset",
  bestLinearOffset(UNP_LO, UNP_HI, [0, SEQRES_OFFSET], observed, SEQRES_OFFSET, null),
  SEQRES_OFFSET,
);
expect(
  "which is the off-by-37 that drew 124 for 161",
  161 + SEQRES_OFFSET,
  124,
);

// A sequence that does not describe this chain must not be trusted
// either — below the identity bar, counting takes over again.
const bogus: SequenceCheck = { seq: "A".repeat(MS4A1.length), resNames };
expect(
  "an unconvincing sequence defers to residue counting",
  bestLinearOffset(UNP_LO, UNP_HI, [0, SEQRES_OFFSET], observed, SEQRES_OFFSET, bogus),
  SEQRES_OFFSET,
);

// ---------------------------------------------------------------------
// Non-regression: the two cases the counting rule already got right.
// ---------------------------------------------------------------------
// GPR75 9xqc shape — the legacy offset shifts part of the window off the
// end of the chain, so counting strictly prefers 0 with no sequence.
const gprObserved = new Set<number>();
for (let r = 1; r <= 266; r += 1) gprObserved.add(r);
expect(
  "a strictly better count still wins without a sequence",
  bestLinearOffset(1, 266, [0, -34], gprObserved, -34, null),
  0,
);

// EGFR 7syd shape — the SEQRES offset is itself 0, nothing to choose.
const egfrObserved = new Set<number>();
for (let r = 1; r <= 614; r += 1) egfrObserved.add(r);
expect(
  "identical candidates are a no-op",
  bestLinearOffset(1, 1210, [0, 0], egfrObserved, 0, null),
  0,
);

console.log("=== verdict ===");
if (failures === 0) {
  console.log("PASS");
} else {
  console.error(`FAIL (${failures})`);
  process.exit(1);
}
