"""Compute per-loop BLOSUM62 ECD identity between human canonical paralogs.

Given two proteins' canonical DeepTMHMM topology + sequence, define each
contiguous run of ``'O'`` (extracellular) residues as a loop. Pair loops
positionally (loop 1 of A ↔ loop 1 of B, etc.) up to ``min(n_loops_a,
n_loops_b)``. For each loop pair:

    BLOSUM62 global pairwise alignment (gap_open=-10, gap_extend=-0.5).
    loop_identity = matches / min(len_loop_a, len_loop_b)

Aggregate per protein-pair, length-weighted across all aligned loops::

    ecd_pct_identity = sum(loop_identity_i * loop_len_i) / sum(loop_len_i) * 100

Loop length used for both the denominator and the weight is the **min** of the
two paired loop lengths — symmetric and bounded in [0, 1].

When either protein has zero ``'O'`` residues → ``ecd_pct_identity = None``,
``n_ecd_loops_compared = 0``.

Reproducing the GPR75 example: GPR75 (O95800, 7TM GPCR) vs CCRL2 (O00421) →
both have an N-terminal ECD + three ECLs. With BLOSUM62 length-weighted per-loop
alignment, the value lands in the high-teens — close to GPR75.json's
``ecd_pct_identity: 18.2``, regenerated rather than reproduced exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from Bio.Align import PairwiseAligner, substitution_matrices


@dataclass(frozen=True)
class LoopSpan:
    """One contiguous extracellular loop with its sequence."""

    start: int   # inclusive 0-based index into the protein sequence
    end: int     # exclusive
    sequence: str

    @property
    def length(self) -> int:
        return self.end - self.start


def extract_ecd_loops(per_residue_topology: str, sequence: str) -> list[LoopSpan]:
    """Extract each contiguous 'O' run as a loop with its sliced sequence.

    Strict length check between topology and sequence; that's a parser invariant.
    """
    if len(per_residue_topology) != len(sequence):
        raise ValueError(
            f"Topology length {len(per_residue_topology)} != sequence length {len(sequence)}"
        )
    loops: list[LoopSpan] = []
    start: int | None = None
    for i, ch in enumerate(per_residue_topology):
        if ch == "O":
            if start is None:
                start = i
        else:
            if start is not None:
                loops.append(LoopSpan(start=start, end=i, sequence=sequence[start:i]))
                start = None
    if start is not None:
        loops.append(
            LoopSpan(start=start, end=len(sequence), sequence=sequence[start:])
        )
    return loops


@lru_cache(maxsize=1)
def _aligner() -> PairwiseAligner:
    aligner = PairwiseAligner()
    aligner.substitution_matrix = substitution_matrices.load("BLOSUM62")
    aligner.open_gap_score = -10.0
    aligner.extend_gap_score = -0.5
    aligner.mode = "global"
    return aligner


def _count_matches(aligned_a: str, aligned_b: str) -> int:
    """Count positions where the two aligned strings agree (no gaps)."""
    return sum(1 for a, b in zip(aligned_a, aligned_b) if a == b and a != "-")


def _pairwise_loop_identity(loop_a: LoopSpan, loop_b: LoopSpan) -> float:
    """Global BLOSUM62 alignment of two loops; identity = matches / min_len.

    Returns 0.0 when either loop is empty (defensive — the caller should
    skip empty loops, but extract_ecd_loops can in principle hand back
    zero-length spans if topology has malformed contiguous-O detection).
    """
    if loop_a.length == 0 or loop_b.length == 0:
        return 0.0
    aligner = _aligner()
    # BLOSUM62 only knows the 20 standard residues; substitute selenocysteine
    # (U) and the ambiguity codes BZXJO* with X. Rare (selenoproteins, stop
    # codons in odd entries) and the residue subbed never matches anyway.
    seq_a = _sanitize(loop_a.sequence)
    seq_b = _sanitize(loop_b.sequence)
    try:
        alignment = aligner.align(seq_a, seq_b)[0]
    except (ValueError, KeyError):
        return 0.0
    # Use Biopython's coordinates representation: alignment.aligned is a
    # numpy array of shape (2, n_blocks, 2) holding [target_start,target_end]
    # / [query_start,query_end] for each aligned block. Within each block the
    # two slices are guaranteed equal-length and gap-free, so identical
    # residues at matching positions are matches; that gives an exact count
    # without restringifying.
    aligned = alignment.aligned  # numpy ndarray
    matches = 0
    for (a_start, a_end), (b_start, b_end) in zip(aligned[0], aligned[1]):
        block_a = seq_a[a_start:a_end]
        block_b = seq_b[b_start:b_end]
        matches += sum(1 for x, y in zip(block_a, block_b) if x == y)
    return matches / min(loop_a.length, loop_b.length)


_NONSTANDARD = set("UBJZXO*")


def _sanitize(sequence: str) -> str:
    """Replace non-BLOSUM62 residues with 'X' so the aligner doesn't choke."""
    if not any(ch in _NONSTANDARD for ch in sequence):
        return sequence
    return "".join("X" if ch in _NONSTANDARD else ch for ch in sequence)


@dataclass(frozen=True)
class EcdIdentityResult:
    """Result for one (human, paralog) pair."""

    ecd_pct_identity: float | None
    n_ecd_loops_compared: int
    n_human_loops: int
    n_paralog_loops: int


def compute_ecd_identity(
    *,
    human_topology: str,
    human_sequence: str,
    paralog_topology: str,
    paralog_sequence: str,
) -> EcdIdentityResult:
    """Length-weighted per-loop BLOSUM62 identity for an (human, paralog) pair."""
    human_loops = extract_ecd_loops(human_topology, human_sequence)
    paralog_loops = extract_ecd_loops(paralog_topology, paralog_sequence)

    if not human_loops or not paralog_loops:
        return EcdIdentityResult(
            ecd_pct_identity=None,
            n_ecd_loops_compared=0,
            n_human_loops=len(human_loops),
            n_paralog_loops=len(paralog_loops),
        )

    n_compare = min(len(human_loops), len(paralog_loops))
    total_weight = 0
    weighted_identity = 0.0
    for i in range(n_compare):
        h = human_loops[i]
        p = paralog_loops[i]
        loop_len = min(h.length, p.length)
        if loop_len == 0:
            continue
        identity = _pairwise_loop_identity(h, p)
        weighted_identity += identity * loop_len
        total_weight += loop_len

    if total_weight == 0:
        return EcdIdentityResult(
            ecd_pct_identity=None,
            n_ecd_loops_compared=0,
            n_human_loops=len(human_loops),
            n_paralog_loops=len(paralog_loops),
        )

    pct = (weighted_identity / total_weight) * 100.0
    return EcdIdentityResult(
        ecd_pct_identity=pct,
        n_ecd_loops_compared=n_compare,
        n_human_loops=len(human_loops),
        n_paralog_loops=len(paralog_loops),
    )


def compute_ecd_identity_from_records(
    human_record: dict[str, Any],
    paralog_record: dict[str, Any],
) -> EcdIdentityResult:
    """Adapter for parse_3line / topology_records.jsonl record dicts."""
    return compute_ecd_identity(
        human_topology=human_record["per_residue_topology"],
        human_sequence=human_record["sequence"],
        paralog_topology=paralog_record["per_residue_topology"],
        paralog_sequence=paralog_record["sequence"],
    )
