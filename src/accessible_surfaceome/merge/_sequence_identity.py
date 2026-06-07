"""Shared BLOSUM62 alignment + pairwise %identity / %similarity counting.

Single source of truth for the per-gene record's isoform-vs-canonical,
paralog ECD, and ortholog ECD identity numbers. Previously the calculation
was duplicated across :mod:`paralog_ecd_identity` (per-loop) and
:mod:`isoform_identity` (full-length); both used ``min(len_a, len_b)`` as
the denominator, so a truncated isoform / paralog / ortholog read **100%
identical** even when it was clearly shorter than the reference. This
helper unifies the math and switches the denominator to
``max(len_a, len_b)`` so the published numbers track biologist
expectations:

    | scenario                       | matches  | max_len | reads |
    |--------------------------------|----------|---------|-------|
    | identical sequences            | len      | len     | 100%  |
    | pure truncation (b ⊂ a)        | len(b)   | len(a)  | cov%  |
    | same-length, substitutions     | <len     | len     | <100% |

The truncation case is the one the previous ``min(len)`` convention got
wrong: TGOLN2's iso4 (309 res, a clean truncation of canonical's 367 res
ECD) used to read 100% — implying "identical to canonical" — when it's
really only 84% of the canonical sequence. The ``max(len)`` convention
reads 84.2% in that case, which is what the reader expects.

Three call sites import from here:

* :mod:`paralog_ecd_identity` — per-loop identity and similarity for
  paralog and ortholog ECD numbers (the same aggregator backs both).
* :mod:`isoform_identity` — full-length isoform identity.
* :mod:`ortholog_topology_projection` — the shared aligner + sanitizer
  primitives (it doesn't compute identity itself; only projection).

If you find yourself writing a fourth "BLOSUM62 identity" helper somewhere
in the repo, plug it in here instead so the convention stays consistent.
"""

from __future__ import annotations

from functools import lru_cache

from Bio.Align import PairwiseAligner, substitution_matrices

# ---------------------------------------------------------------------------
# Primitives (aligner + residue sanitizer + BLOSUM62 matrix). Moved here
# from paralog_ecd_identity so every identity-computing helper imports a
# single BLOSUM62 matrix instance and a single aligner config.
# ---------------------------------------------------------------------------

# BLOSUM62 doesn't know the 20 standard residues' extensions (selenocysteine
# 'U', ambiguity 'B' / 'Z' / 'X' / 'J' / 'O', stop codon '*'). Rare in the
# proteomes we align here, but the aligner raises KeyError on first
# encounter, so sanitize them to 'X' before aligning.
_NONSTANDARD = set("UBJZXO*")


def _sanitize(sequence: str) -> str:
    """Replace non-BLOSUM62 residues with 'X' so the aligner doesn't choke.

    Returns the input unchanged when no replacement is needed (the common
    case), so the fast path doesn't pay an allocation.
    """
    if not any(ch in _NONSTANDARD for ch in sequence):
        return sequence
    return "".join("X" if ch in _NONSTANDARD else ch for ch in sequence)


@lru_cache(maxsize=1)
def _blosum62():
    return substitution_matrices.load("BLOSUM62")


@lru_cache(maxsize=1)
def _aligner() -> PairwiseAligner:
    """A global BLOSUM62 aligner with the gap penalty we use throughout."""
    a = PairwiseAligner()
    a.substitution_matrix = _blosum62()
    # (-10, -0.5) is the convention paralog_ecd_identity has used since
    # it shipped — keep it identical so the consolidation doesn't shift
    # already-published numbers.
    a.open_gap_score = -10.0
    a.extend_gap_score = -0.5
    a.mode = "global"
    return a


# ---------------------------------------------------------------------------
# The shared counter: matches + positives over the gap-free blocks of a
# global BLOSUM62 alignment. Both per-loop and full-length callers use it.
# ---------------------------------------------------------------------------


def alignment_match_counts(seq_a: str, seq_b: str) -> tuple[int, int]:
    """``(matches, positives)`` over the gap-free blocks of a global
    BLOSUM62 alignment of ``seq_a`` vs ``seq_b``.

    * ``matches`` — positions where the two aligned residues are identical.
    * ``positives`` — matches *plus* BLOSUM62-positive substitutions
      (the conservative-substitution definition used for similarity).

    Both return ``0`` on empty input or aligner failure so callers can
    safely divide by their chosen denominator.
    """
    if not seq_a or not seq_b:
        return 0, 0
    a = _sanitize(seq_a)
    b = _sanitize(seq_b)
    try:
        alignment = _aligner().align(a, b)[0]
    except (ValueError, KeyError):
        return 0, 0
    mat = _blosum62()
    matches = positives = 0
    # alignment.aligned is shape (2, n_blocks, 2): equal-length, gap-free
    # blocks of [target_start, target_end] / [query_start, query_end].
    for (a0, a1), (b0, b1) in zip(alignment.aligned[0], alignment.aligned[1]):
        for x, y in zip(a[a0:a1], b[b0:b1]):
            if x == y:
                matches += 1
                positives += 1
            else:
                try:
                    if mat[x, y] > 0:
                        positives += 1
                except (KeyError, IndexError):
                    pass
    return matches, positives


# ---------------------------------------------------------------------------
# Public identity / similarity APIs. The denominator is ``max(len_a, len_b)``
# in BOTH — this is the load-bearing change vs the old ``min(len)``.
# ---------------------------------------------------------------------------


def pct_identity(seq_a: str, seq_b: str) -> float | None:
    """%identity = matches / max(len_a, len_b) * 100.

    Returns ``None`` when either sequence is empty (no defensible answer).
    """
    if not seq_a or not seq_b:
        return None
    matches, _ = alignment_match_counts(seq_a, seq_b)
    return matches / max(len(seq_a), len(seq_b)) * 100.0


def pct_identity_and_similarity(
    seq_a: str, seq_b: str
) -> tuple[float, float] | tuple[None, None]:
    """(%identity, %similarity), both on a 0-100 scale with denominator
    ``max(len_a, len_b)``.

    Returns ``(None, None)`` on empty input — the caller is responsible
    for treating that as "no comparison possible" (e.g. an ECD-less
    isoform vs an ECD-bearing canonical).
    """
    if not seq_a or not seq_b:
        return None, None
    matches, positives = alignment_match_counts(seq_a, seq_b)
    denom = max(len(seq_a), len(seq_b))
    return matches / denom * 100.0, positives / denom * 100.0


__all__ = [
    "alignment_match_counts",
    "pct_identity",
    "pct_identity_and_similarity",
    "_aligner",
    "_sanitize",
    "_blosum62",
]
