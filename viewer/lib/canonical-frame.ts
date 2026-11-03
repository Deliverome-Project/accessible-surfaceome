/**
 * Canonical ↔ proteoform residue numbering.
 *
 * A residue number only means something against the sequence it was read
 * off. Canonical MS4A1 161 is the recommended tag site; the same number
 * on the Mouse tab is mouse residue 161, which is a different residue
 * entirely, and on a truncated isoform it may not exist at all. Showing
 * one number across those tabs invites the reader to compare positions
 * that were never the same position.
 *
 * The alignment is already computed: every isoform and ortholog carries
 * ``per_residue_topology_canonical_frame`` — its topology re-indexed onto
 * the canonical axis, one character per canonical residue, with ``'-'``
 * where the proteoform does not cover that position. Counting the
 * non-gap characters up to a canonical residue gives that proteoform's
 * own residue number.
 *
 * The gate is per position, not a global identity threshold: a 73%
 * identical ortholog can conserve a loop exactly, and an 85% identical
 * isoform can have it spliced out. Only the aligned position answers it,
 * so an uncovered position says so rather than guessing.
 */

export interface ProteoformResidue {
  /** The proteoform's own residue number, or ``null`` when it does not
   *  cover this canonical position. */
  residue: number | null;
  /** One-letter residue, when the proteoform sequence was supplied.
   *  ``null`` if uncovered or no sequence was given. */
  aa: string | null;
  /** True when the proteoform carries the same amino acid as the
   *  canonical. False for a substitution — MS4A1 161 is a tyrosine, and
   *  the aligned mouse residue is a proline. ``null`` without sequences. */
  conserved: boolean | null;
}

const UNCOVERED: ProteoformResidue = { residue: null, aa: null, conserved: null };

/** Map a canonical residue number onto one proteoform.
 *
 * ``frame`` is ``per_residue_topology_canonical_frame`` (length ==
 * canonical length). ``seq`` and ``canonicalSeq`` are optional; supply
 * them to get the residue letter and whether it is conserved. */
export function projectCanonicalResidue(
  canonicalResidue: number,
  frame: string | null | undefined,
  seq?: string | null,
  canonicalSeq?: string | null,
): ProteoformResidue {
  if (!frame) return UNCOVERED;
  const u = canonicalResidue;
  if (!Number.isInteger(u) || u < 1 || u > frame.length) return UNCOVERED;
  if (frame[u - 1] === "-") return UNCOVERED;
  // Insertions relative to the canonical are dropped from the frame, so
  // the count of non-gap characters IS the proteoform's residue number.
  let residue = 0;
  for (let i = 0; i < u; i += 1) if (frame[i] !== "-") residue += 1;
  if (residue < 1) return UNCOVERED;
  const aa = seq && residue <= seq.length ? seq[residue - 1] : null;
  const canonicalAa =
    canonicalSeq && u <= canonicalSeq.length ? canonicalSeq[u - 1] : null;
  return {
    residue,
    aa,
    conserved: aa !== null && canonicalAa !== null ? aa === canonicalAa : null,
  };
}

/** A proteoform as the viewer tabs hold it: whatever carries a canonical
 *  frame, its own sequence, and a label to show. */
export interface ProteoformLike {
  label: string;
  frame: string | null | undefined;
  sequence?: string | null;
  /** Percent identity to the canonical, for context in the caption. It
   *  does NOT gate the mapping — coverage at the position does. */
  pctIdentity?: number | null;
}

/** Map one canonical residue across several proteoforms at once. */
export function projectAcrossProteoforms(
  canonicalResidue: number,
  proteoforms: ProteoformLike[],
  canonicalSeq?: string | null,
): Array<ProteoformLike & ProteoformResidue> {
  return proteoforms.map((p) => ({
    ...p,
    ...projectCanonicalResidue(canonicalResidue, p.frame, p.sequence, canonicalSeq),
  }));
}
