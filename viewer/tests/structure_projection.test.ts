/*
 * lib/experimental-structure — the UniProt→PDB-author projection.
 *
 *   npx --yes tsx --test tests/structure_projection.test.ts
 *
 * Residue counting cannot choose a projection whenever the mapped window
 * is wider than the modelled stretch, which is the usual case. Both genes
 * the old ordering was tuned around turned out to be drawn wrong:
 *
 *   MS4A1 8VGN  chain G maps to UniProt 41-297 and models author 46-219,
 *               with author == UniProt. The SEQRES offset -37 and the
 *               correct 0 both cover 165 residues, so the tie fell to
 *               -37 and residue 161 (Tyr, in the extracellular loop)
 *               was drawn as 124 (Leu, inside TM3) — and every
 *               compartment colour and the membrane slab moved with it.
 *   EGFR 7syd   the file numbers chain A 1-614 for UniProt 25-638.
 *               Offset 0 scores 8% sequence identity; DBREF's -24 scores
 *               99.8%. The comment that both candidates were 0 and the
 *               structure "already rendered" was measuring coverage, not
 *               correctness.
 *
 * Both files state the answer in their own DBREF records, and amino-acid
 * identity confirms it. Fixture provenance: the MS4A1 sequence is AFDB's
 * uniprotSequence for P11836 (297 aa) and the modelled ranges are RCSB
 * 8VGN auth_seq_id on chain G.
 */
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  bestLinearOffset,
  observedResSeq,
  overlapCount,
  projectedIdentity,
  projectExperimentalChain,
  residueOneLetterByResSeq,
} from "../lib/experimental-structure";

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

/** A minimal PDB: one CA line per modelled residue, real column
 *  positions, optionally preceded by the DBREF that states the
 *  numbering. ``resAt`` maps an AUTHOR number to its residue. */
function pdbFile(opts: {
  chain: string;
  ranges: Array<[number, number]>;
  resAt: (authorResi: number) => string | undefined;
  dbref?: { acc: string; seqBegin: number; dbBegin: number; dbEnd: number };
}): string {
  const lines: string[] = [];
  if (opts.dbref) {
    const d = opts.dbref;
    // Real DBREF column positions, read off RCSB 8VGN.
    const cols = new Array(80).fill(" ");
    const put = (at: number, text: string) => {
      for (let i = 0; i < text.length; i += 1) cols[at + i] = text[i];
    };
    put(0, "DBREF  TEST ");
    put(12, opts.chain);
    put(14, String(d.seqBegin).padStart(4));
    put(20, String(d.seqBegin + (d.dbEnd - d.dbBegin)).padStart(4));
    put(26, "UNP");
    put(33, d.acc);
    put(42, "TEST_HUMAN");
    put(55, String(d.dbBegin).padStart(5));
    put(62, String(d.dbEnd).padStart(5));
    lines.push(cols.join(""));
  }
  let serial = 1;
  for (const [lo, hi] of opts.ranges) {
    for (let r = lo; r <= hi; r += 1) {
      const three = ONE_TO_THREE[opts.resAt(r) ?? ""];
      if (!three) continue;
      lines.push(
        "ATOM  " + String(serial).padStart(5) + "  CA  " + three.padStart(3) +
        " " + opts.chain + String(r).padStart(4) +
        "      11.000  12.000  13.000  1.00 50.00           C",
      );
      serial += 1;
    }
  }
  return lines.join("\n");
}

/** Stub AFDB's prediction endpoint; everything else runs as written. */
function seqFetch(byAcc: Record<string, string>): typeof fetch {
  return (async (url: string) => {
    const acc = String(url).split("/").pop() as string;
    return { ok: true, json: async () => [{ uniprotAccession: acc, uniprotSequence: byAcc[acc] }] };
  }) as unknown as typeof fetch;
}

const noNetwork: typeof fetch = (async () => {
  throw new Error("the test must not reach the network");
}) as unknown as typeof fetch;

/** The canonical-sequence memo lives for the process, so each test uses
 *  its own accession rather than leaking a cached answer into the next. */
const ms4a1Hit = (acc: string) => ({
  pdbId: "8vgn", uniprotAcc: acc, chainId: "G",
  unpStart: 41, unpEnd: 297, pdbStart: 4, approx: false,
});

test("MS4A1 8VGN: residue counting ties, so it cannot choose", () => {
  const pdb = pdbFile({
    chain: "G", ranges: MS4A1_MODELLED, resAt: (r) => MS4A1[r - 1],
  });
  const observed = observedResSeq(pdb, "G");
  assert.equal(observed.size, 165);
  assert.equal(overlapCount(41, 297, 0, observed), 165);
  assert.equal(overlapCount(41, 297, -37, observed), 165);
  // and the tie-break keeps the wrong one
  assert.equal(bestLinearOffset(41, 297, [0, -37], observed, -37), -37);
  assert.equal(161 + -37, 124);
});

test("MS4A1 8VGN: DBREF states author == UniProt, and 161 is the tyrosine", async () => {
  const pdb = pdbFile({
    chain: "G", ranges: MS4A1_MODELLED, resAt: (r) => MS4A1[r - 1],
    dbref: { acc: "P11836", seqBegin: 41, dbBegin: 41, dbEnd: 297 },
  });
  const segs = await projectExperimentalChain(ms4a1Hit("P11836"), pdb, "G", noNetwork);
  assert.deepEqual(segs, [{ unpLo: 41, unpHi: 297, offset: 0 }]);
  const resNames = residueOneLetterByResSeq(pdb, "G");
  assert.equal(resNames.get(161 + segs[0].offset), "Y");
  assert.equal(MS4A1[160], "Y");
});

test("MS4A1 8VGN: with no DBREF, the sequence still settles it", async () => {
  // Converted mmCIF carries no DBREF — exactly the entries the mmCIF
  // fallback added — so this is the path those take.
  const pdb = pdbFile({
    chain: "G", ranges: MS4A1_MODELLED, resAt: (r) => MS4A1[r - 1],
  });
  const segs = await projectExperimentalChain(
    ms4a1Hit("Q11836"), pdb, "G", seqFetch({ "Q11836": MS4A1 }),
  );
  assert.equal(segs[0].offset, 0);
  const id = projectedIdentity(segs, {
    seq: MS4A1, resNames: residueOneLetterByResSeq(pdb, "G"),
  });
  assert.equal(id.matches, id.tested);
});

test("MS4A1 8VGN: no DBREF and no sequence reproduces the old answer", async () => {
  const pdb = pdbFile({
    chain: "G", ranges: MS4A1_MODELLED, resAt: (r) => MS4A1[r - 1],
  });
  const dead: typeof fetch = (async () => ({ ok: false })) as unknown as typeof fetch;
  const segs = await projectExperimentalChain(ms4a1Hit("Q11837"), pdb, "G", dead);
  assert.equal(segs[0].offset, -37, "degrades to counting, not to an error");
});

test("EGFR 7syd: PDBe maps the whole protein, the file numbers the mature chain", async () => {
  // Real numbers: PDBe best_structures gives 7syd chain A unp 1-1210
  // with seqres start 1, so BOTH candidate offsets are 0 — exactly the
  // "nothing to choose" case the old comment described. The file numbers
  // chain A 1-614 for UniProt 25-638 (the signal peptide is 1-24), so 0
  // is 614 residues of the wrong protein and DBREF's -24 is right.
  const seq = Array.from({ length: 1210 }, (_, i) => "ACDEFGHIKLMNPQRSTVWY"[(i * 7) % 20]).join("");
  const pdb = pdbFile({
    chain: "A", ranges: [[1, 614]], resAt: (r) => seq[r + 24 - 1],
    dbref: { acc: "P00533", seqBegin: 1, dbBegin: 25, dbEnd: 638 },
  });
  const hit = {
    pdbId: "7syd", uniprotAcc: "P00533", chainId: "A",
    unpStart: 1, unpEnd: 1210, pdbStart: 1, approx: false,
  };
  const observed = observedResSeq(pdb, "A");
  assert.equal(bestLinearOffset(1, 1210, [0, 0], observed, 0), 0, "counting has nothing to choose");

  const resNames = residueOneLetterByResSeq(pdb, "A");
  const wrong = projectedIdentity([{ unpLo: 1, unpHi: 1210, offset: 0 }], { seq, resNames });
  assert.ok(wrong.matches / wrong.tested < 0.2, "offset 0 is near chance");
  const right = projectedIdentity([{ unpLo: 25, unpHi: 638, offset: -24 }], { seq, resNames });
  assert.equal(right.matches, right.tested);

  // DBREF settles it from the file alone — no network at all.
  const segs = await projectExperimentalChain(hit, pdb, "A", noNetwork);
  assert.deepEqual(segs, [{ unpLo: 25, unpHi: 638, offset: -24 }]);
});

test("a chain the canonical sequence does not describe falls back to counting", async () => {
  const pdb = pdbFile({
    chain: "G", ranges: MS4A1_MODELLED, resAt: (r) => MS4A1[r - 1],
  });
  const bogus = "A".repeat(MS4A1.length);
  const segs = await projectExperimentalChain(
    ms4a1Hit("Q11838"), pdb, "G", seqFetch({ "Q11838": bogus }),
  );
  assert.equal(segs[0].offset, -37, "a weak signal is not trusted");
});
