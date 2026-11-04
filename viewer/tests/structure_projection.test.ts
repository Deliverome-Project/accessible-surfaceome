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
  resolveExperimentalChain,
  sequenceSegments,
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

// ---- The sequence gets the last word ----------------------------------
//
// The first cohort identity audit found 155 genes whose structure loaded
// and covered its mapping while drawing the wrong residues. The three
// shapes below are the ones it found; the sequences are synthetic (a
// non-repeating pseudo-random protein) so each test states only the
// numbering.

function protein(n: number, seed: number): string {
  const aa = "ACDEFGHIKLMNPQRSTVWY";
  let x = seed;
  let out = "";
  for (let i = 0; i < n; i += 1) {
    x = (x * 1103515245 + 12345) % 2147483648;
    out += aa[x % 20];
  }
  return out;
}

test("AKR1A1 2ALR: a DBREF the file's own atoms contradict is overruled", async () => {
  // 2ALR states author 1-324 = UniProt 1-324, but author 1 is UniProt 2
  // (the initiator Met is gone and the chain is numbered from what is
  // left). Trusting DBREF put 12 of 312 residues on the right amino acid.
  const seq = protein(325, 1);
  const pdb = pdbFile({
    chain: "A", ranges: [[1, 312]], resAt: (r) => seq[r],
    dbref: { acc: "P14550", seqBegin: 1, dbBegin: 1, dbEnd: 324 },
  });
  const hit = {
    pdbId: "2ALR", uniprotAcc: "P14550", chainId: "A",
    unpStart: 1, unpEnd: 324, pdbStart: 1, approx: false,
  };
  const segs = await projectExperimentalChain(hit, pdb, "A", seqFetch({ P14550: seq }));
  assert.deepEqual(segs, [{ unpLo: 2, unpHi: 313, offset: -1 }]);
});

test("BSG 7CKO: an isoform chain projects piecewise around the missing exon", async () => {
  // The chain is isoform 2, numbered 1..N in its own numbering, which
  // lacks canonical residues 22-137. No single offset is right anywhere.
  const seq = protein(385, 2);
  const iso = seq.slice(0, 21) + seq.slice(137);
  const pdb = pdbFile({ chain: "B", ranges: [[10, 230]], resAt: (r) => iso[r - 1] });
  const resNames = residueOneLetterByResSeq(pdb, "B");
  const segs = sequenceSegments({ seq, resNames });
  assert.deepEqual(segs, [
    { unpLo: 10, unpHi: 21, offset: 0 },
    { unpLo: 138, unpHi: 346, offset: -116 },
  ]);
  const id = projectedIdentity(segs, { seq, resNames });
  assert.equal(id.matches, id.tested);
});

test("a fusion insert is left uncoloured, not drawn as this protein", () => {
  // A receptor with a 40-residue foreign domain spliced in after residue
  // 100, numbered straight through as one chain.
  const seq = protein(300, 3);
  const chain = seq.slice(0, 100) + protein(40, 99) + seq.slice(100, 250);
  const pdb = pdbFile({ chain: "A", ranges: [[1, 290]], resAt: (r) => chain[r - 1] });
  const resNames = residueOneLetterByResSeq(pdb, "A");
  const segs = sequenceSegments({ seq, resNames });
  assert.deepEqual(segs, [
    { unpLo: 1, unpHi: 100, offset: 0 },
    { unpLo: 101, unpHi: 250, offset: 40 },
  ]);
});

test("substitutions stay on their diagonal (ortholog-level identity)", () => {
  const seq = protein(200, 4);
  // every 7th residue substituted: ~86% identity, still one segment
  const mutant = [...seq].map((c, i) => (i % 7 === 3 ? (c === "W" ? "Y" : "W") : c)).join("");
  const pdb = pdbFile({ chain: "A", ranges: [[1, 200]], resAt: (r) => mutant[r - 1] });
  const segs = sequenceSegments({ seq, resNames: residueOneLetterByResSeq(pdb, "A") });
  assert.deepEqual(segs, [{ unpLo: 1, unpHi: 200, offset: 0 }]);
});

test("a right projection is never replaced", async () => {
  // MS4A1 8VGN via DBREF scores 100%; the alignment is not consulted.
  const pdb = pdbFile({
    chain: "G", ranges: MS4A1_MODELLED, resAt: (r) => MS4A1[r - 1],
    dbref: { acc: "Q11839", seqBegin: 41, dbBegin: 41, dbEnd: 297 },
  });
  const segs = await projectExperimentalChain(
    ms4a1Hit("Q11839"), pdb, "G", seqFetch({ Q11839: MS4A1 }),
  );
  assert.deepEqual(segs, [{ unpLo: 41, unpHi: 297, offset: 0 }]);
});

test("IL17RA 9OT1: a chain whose atoms are another protein is swapped for one that is this protein", async () => {
  // Chain A's SEQRES is an IL17RB–IL17RA fusion, so PDBe maps IL17RA to
  // it, but only the IL17RB half is resolved. Chain C models IL17RA.
  const seq = protein(866, 5);
  const other = protein(500, 6);
  const pdb =
    pdbFile({ chain: "A", ranges: [[330, 480]], resAt: (r) => other[r - 1] }) + "\n" +
    pdbFile({ chain: "C", ranges: [[370, 712]], resAt: (r) => seq[r - 1] });
  const hit = {
    pdbId: "9OT1", uniprotAcc: "Q96F46", chainId: "A",
    unpStart: 361, unpEnd: 866, pdbStart: 501, approx: false,
  };
  const got = await resolveExperimentalChain(hit, pdb, "A", seqFetch({ Q96F46: seq }));
  assert.equal(got.chainId, "C");
  assert.equal(got.modelled, true);
  assert.deepEqual(got.segments, [{ unpLo: 370, unpHi: 712, offset: 0 }]);
});

test("TAS1R3 9NOX: when no chain models the protein, nothing is painted as it", async () => {
  const seq = protein(852, 7);
  const pdb = pdbFile({ chain: "B", ranges: [[7, 250]], resAt: (r) => protein(300, 8)[r - 1] });
  const hit = {
    pdbId: "9NOX", uniprotAcc: "Q7RTX0", chainId: "B",
    unpStart: 18, unpEnd: 852, pdbStart: 1, approx: false,
  };
  const got = await resolveExperimentalChain(hit, pdb, "B", seqFetch({ Q7RTX0: seq }));
  assert.deepEqual(got, { chainId: "B", segments: [], modelled: false });
});

test("a chain that cannot be sequence-checked is drawn as before", async () => {
  const pdb = pdbFile({ chain: "G", ranges: MS4A1_MODELLED, resAt: (r) => MS4A1[r - 1] });
  const got = await resolveExperimentalChain(ms4a1Hit("Q11840"), pdb, "G", noNetwork);
  assert.equal(got.chainId, "G");
  assert.equal(got.modelled, true);
  assert.equal(got.segments[0].offset, -37);
});
