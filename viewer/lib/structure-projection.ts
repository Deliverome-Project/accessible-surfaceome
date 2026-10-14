/**
 * UniProt → PDB-author residue projection for the experimental structure
 * tab.
 *
 * The topology string, the tag sites and the residue the user types into
 * the highlight box are all in canonical UniProt numbering. 3Dmol selects
 * on the author `resSeq` in the fetched file. Those two agree for most
 * modern depositions and disagree for plenty of older ones, so the viewer
 * picks a linear offset from a few principled candidates and validates it
 * against the file.
 *
 * **Residue counting alone cannot pick the offset.** It was the only test
 * until MS4A1 8VGN exposed the gap: PDBe maps chain G to UniProt 41-297
 * while the chain models 46-219, so the mapped window is wider than the
 * modelled stretch and *every* candidate offset that keeps the chain
 * inside the window lands exactly the same number of residues on real
 * atoms. The tie fell through to the legacy SEQRES offset, -37, and the
 * viewer drew residue 124 whenever the user asked for 161. Interval
 * geometry cannot break that tie either — both windows are the same
 * length and both contain the modelled region.
 *
 * What does break it is the sequence: the residue sitting at author
 * number `u + offset` has to BE the UniProt residue at `u`. That check is
 * decisive (≈100% against ≈5% for a wrong offset here), so when the
 * canonical sequence is available it decides, and residue counting stays
 * as the fallback for anything it cannot judge.
 */

/** Canonical sequence plus the residue identities the fetched file
 *  actually carries, enough to tell a right offset from a wrong one. */
export interface SequenceCheck {
  /** Canonical UniProt sequence; residue ``u`` is ``seq[u - 1]``. */
  seq: string;
  /** Author resSeq → one-letter residue code, read from the file. */
  resNames: Map<number, string>;
}

/** An offset is only allowed to win on sequence when the protein at that
 *  numbering really is this protein. Engineered constructs, ortholog
 *  chains and modified residues all cost a few percent; a wrong offset
 *  scores near the ~5% expected by chance. Anything below this and we
 *  defer to residue counting rather than trust a weak signal. */
export const MIN_IDENTITY = 0.7;

const THREE_TO_ONE: Record<string, string> = {
  ALA: "A", ARG: "R", ASN: "N", ASP: "D", CYS: "C", GLN: "Q", GLU: "E",
  GLY: "G", HIS: "H", ILE: "I", LEU: "L", LYS: "K", MET: "M", PHE: "F",
  PRO: "P", SER: "S", THR: "T", TRP: "W", TYR: "Y", VAL: "V",
  // Selenomethionine is a methionine as far as the UniProt sequence is
  // concerned, and phasing structures are full of it.
  MSE: "M",
};

/** Author resSeq values present (ATOM + HETATM) on a chain in the fetched
 *  PDB file — i.e. the residues 3Dmol can actually select. We can't trust
 *  `best_structures.start` (a SEQRES index) or even PDBe author numbers
 *  (which can diverge from the legacy `.pdb` file RCSB serves, e.g. EGFR
 *  7syd), so the file itself is the only ground truth. */
export function observedResSeq(pdbText: string, chainId: string): Set<number> {
  const out = new Set<number>();
  for (const line of pdbText.split(/\r?\n/)) {
    if (!line.startsWith("ATOM") && !line.startsWith("HETATM")) continue;
    if (line.length < 26) continue;
    if (line.slice(21, 22) !== chainId) continue;
    const resi = Number.parseInt(line.slice(22, 26).trim(), 10);
    if (Number.isInteger(resi)) out.add(resi);
  }
  return out;
}

/** Author resSeq → one-letter residue code for one chain. Only standard
 *  amino acids (plus MSE) are recorded, so ligands and waters sharing the
 *  chain id cannot be mistaken for sequence. */
export function residueOneLetterByResSeq(
  pdbText: string,
  chainId: string,
): Map<number, string> {
  const out = new Map<number, string>();
  for (const line of pdbText.split(/\r?\n/)) {
    if (!line.startsWith("ATOM") && !line.startsWith("HETATM")) continue;
    if (line.length < 26) continue;
    if (line.slice(21, 22) !== chainId) continue;
    const one = THREE_TO_ONE[line.slice(17, 20).trim().toUpperCase()];
    if (!one) continue;
    const resi = Number.parseInt(line.slice(22, 26).trim(), 10);
    if (!Number.isInteger(resi) || out.has(resi)) continue;
    out.set(resi, one);
  }
  return out;
}

/** Count residues of UniProt window ``[unpLo, unpHi]`` that, shifted by
 *  ``offset``, land on an observed author resSeq. */
export function overlapCount(
  unpLo: number,
  unpHi: number,
  offset: number,
  observed: Set<number>,
): number {
  let n = 0;
  for (let u = unpLo; u <= unpHi; u += 1) {
    if (observed.has(u + offset)) n += 1;
  }
  return n;
}

/** How much of the window, projected by ``offset``, lands on a residue of
 *  the right identity. ``tested`` counts the positions that landed on an
 *  amino acid at all, so the fraction is "of the residues this offset
 *  claims, how many are the right ones" rather than being diluted by the
 *  unmodelled parts of the chain. */
export function identityScore(
  unpLo: number,
  unpHi: number,
  offset: number,
  check: SequenceCheck,
): { matches: number; tested: number } {
  let matches = 0;
  let tested = 0;
  const hi = Math.min(unpHi, check.seq.length);
  for (let u = Math.max(unpLo, 1); u <= hi; u += 1) {
    const got = check.resNames.get(u + offset);
    if (got === undefined) continue;
    tested += 1;
    if (got === check.seq[u - 1]) matches += 1;
  }
  return { matches, tested };
}

/** Pick the UniProt→author offset for ``[unpLo, unpHi]``.
 *
 *  ``candidates`` are principled guesses: ``0`` (file numbered by UniProt
 *  residue — the modern norm, true for GPR75 9xqc and for MS4A1 8VGN),
 *  the SEQRES-based legacy offset, and (for fusions) the SIFTS author
 *  offset.
 *
 *  With ``check``, the offset that puts the right amino acids at the
 *  right numbers wins, provided it clears `MIN_IDENTITY` — sequence is
 *  ground truth and settles the ties residue counting cannot see.
 *  Without it (or when nothing clears the bar) the old rule stands: most
 *  residues landing on real atoms, ties keeping ``fallback`` so a
 *  structure that already rendered can never regress. */
export function bestLinearOffset(
  unpLo: number,
  unpHi: number,
  candidates: number[],
  observed: Set<number>,
  fallback: number,
  check?: SequenceCheck | null,
): number {
  // fallback first so an exact tie, on either rule, keeps it.
  const ordered = [fallback, ...candidates.filter((c) => c !== fallback)];

  if (check && check.seq.length > 0 && check.resNames.size > 0) {
    let best: number | null = null;
    let bestFrac = 0;
    let bestMatches = 0;
    for (const c of ordered) {
      const { matches, tested } = identityScore(unpLo, unpHi, c, check);
      if (tested === 0) continue;
      const frac = matches / tested;
      if (frac > bestFrac || (frac === bestFrac && matches > bestMatches)) {
        best = c;
        bestFrac = frac;
        bestMatches = matches;
      }
    }
    if (best !== null && bestFrac >= MIN_IDENTITY) return best;
  }

  let best = fallback;
  let bestScore = overlapCount(unpLo, unpHi, fallback, observed);
  for (const c of ordered) {
    if (c === fallback) continue;
    const score = overlapCount(unpLo, unpHi, c, observed);
    if (score > bestScore) {
      best = c;
      bestScore = score;
    }
  }
  return best;
}
