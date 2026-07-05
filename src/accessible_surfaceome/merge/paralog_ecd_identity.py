"""BLOSUM62 ECD identity between a canonical protein and a variant.

Backs the extracellular-domain (ECD) %identity / %similarity for the three
variant kinds — alternative isoforms, within-species paralogs, and cross-
species orthologs — all against the human canonical, so the three columns in
the viewer are computed by identical arithmetic.

Method (``compute_ecd_identity``): align the variant to the canonical with the
shared global BLOSUM62 aligner (gap_open=-10, gap_extend=-0.5), then score ONLY
the alignment columns whose CANONICAL residue is extracellular (``'O'``)::

    ecd_pct_identity   = identical_canonical_ECD_residues / max(canon_ECD, var_ECD) * 100
    ecd_pct_similarity = (identical + BLOSUM62-positive) / max(canon_ECD, var_ECD) * 100

The ``max(canon_ECD_len, var_ECD_len)`` denominator (consistent with the
full-length ``max(len)`` convention in
:mod:`accessible_surfaceome.merge._sequence_identity`) means BOTH a lost
extracellular loop (variant shorter ECD) AND a gained one penalise the score.

**This replaced a positional loop-pairing method** (2026-07) that defined each
contiguous ``'O'`` run as a loop and paired loops BY INDEX (loop 1 ↔ loop 1)
up to ``min(n_loops)``. That mis-paired non-homologous loops whenever the
variant's extracellular-loop COUNT or ORDER differed from the canonical: an
N-terminally-truncated variant that drops an early loop shifts every later
loop's index. CD63 isoform P08962-3 (keeps the large EC2 loop, loses the small
EC1) read ~4% under the old method — canonical EC1 vs the isoform's EC2 — vs
the true ~84% (EC2 preserved, EC1 lost). ``extract_ecd_loops`` /
``_pairwise_loop_identity`` / ``_loop_id_and_sim`` remain for the per-loop unit
tests and the ``n_*_loops`` metadata, but no longer drive the aggregate.

When neither side has any ``'O'`` residue → ``ecd_pct_identity = None``.
Published records + the ``compara_paralog`` / ``compara_ortholog_ecd`` tables
carry values from the old method until recomputed (no LLM re-run needed — the
number is a pure function of the stored sequences + topology).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from accessible_surfaceome.merge._sequence_identity import (
    _aligner,  # noqa: F401 — re-exported for downstream scripts
    _blosum62,  # noqa: F401 — re-exported for downstream scripts
    _sanitize,  # noqa: F401 — re-exported for downstream scripts
    alignment_match_counts,
)


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


def _pairwise_loop_identity(loop_a: LoopSpan, loop_b: LoopSpan) -> float:
    """Global BLOSUM62 alignment of two loops; identity = matches / max_len.

    Returns 0.0 when either loop is empty (defensive — the caller should
    skip empty loops, but extract_ecd_loops can in principle hand back
    zero-length spans if topology has malformed contiguous-O detection).

    Delegates the alignment + match counting to
    :func:`accessible_surfaceome.merge._sequence_identity.alignment_match_counts`
    so paralog, ortholog (via the shared aggregator below), and isoform
    identity numbers all flow through the same arithmetic.
    """
    if loop_a.length == 0 or loop_b.length == 0:
        return 0.0
    matches, _ = alignment_match_counts(loop_a.sequence, loop_b.sequence)
    return matches / max(loop_a.length, loop_b.length)


def _loop_id_and_sim(loop_a: LoopSpan, loop_b: LoopSpan) -> tuple[float, float]:
    """(identity, similarity) fractions over max_len for one loop pair.

    Identity = exact matches / max_len (matches ``_pairwise_loop_identity``).
    Similarity additionally counts BLOSUM62-positive substitutions (score > 0)
    — the conventional "conservative substitution" definition. Shared with
    isoform full-length identity via ``_sequence_identity``.
    """
    if loop_a.length == 0 or loop_b.length == 0:
        return 0.0, 0.0
    matches, positives = alignment_match_counts(loop_a.sequence, loop_b.sequence)
    denom = max(loop_a.length, loop_b.length)
    return matches / denom, positives / denom


@dataclass(frozen=True)
class EcdIdentityResult:
    """Result for one (human, paralog) pair."""

    ecd_pct_identity: float | None
    n_ecd_loops_compared: int
    n_human_loops: int
    n_paralog_loops: int
    # ECD percent SIMILARITY (identity + BLOSUM62-positive substitutions),
    # 0–100. None whenever ecd_pct_identity is None (no ECD to compare).
    ecd_pct_similarity: float | None = None


def _empty_result(n_human_loops: int, n_paralog_loops: int) -> EcdIdentityResult:
    return EcdIdentityResult(
        ecd_pct_identity=None,
        n_ecd_loops_compared=0,
        n_human_loops=n_human_loops,
        n_paralog_loops=n_paralog_loops,
        ecd_pct_similarity=None,
    )


def compute_ecd_identity(
    *,
    human_topology: str,
    human_sequence: str,
    paralog_topology: str,
    paralog_sequence: str,
) -> EcdIdentityResult:
    """Homology-aligned, canonical-anchored ECD identity + similarity.

    Aligns the variant (``paralog_*`` — an isoform / paralog / ortholog) to the
    canonical (``human_*``) with the shared global BLOSUM62 aligner, then scores
    ONLY the alignment columns whose CANONICAL residue is extracellular
    (``'O'``): how many canonical ECD residues align to an identical
    (``ecd_pct_identity``) / additionally BLOSUM62-positive
    (``ecd_pct_similarity``) variant residue. Normalised by
    ``max(canonical_ECD_len, variant_ECD_len)`` so BOTH a lost extracellular
    loop (variant shorter ECD) AND a gained one (variant longer ECD) are
    penalised — consistent with the full-length ``max(len)`` convention in
    :mod:`accessible_surfaceome.merge._sequence_identity`.

    This replaces the previous POSITIONAL loop pairing (``loop i`` of A vs
    ``loop i`` of B), which silently compared non-homologous loops whenever the
    variant's extracellular-loop COUNT or ORDER differed from the canonical: an
    N-terminally-truncated variant that drops an early loop shifts every later
    loop's index. (CD63 isoform P08962-3 keeps the large EC2 loop but loses the
    small EC1 — the old code paired canonical EC1 against the isoform's EC2 and
    read ~4% instead of the ~84% that reflects "EC2 preserved, EC1 lost".)

    Returns ``ecd_pct_identity = None`` when neither side has any extracellular
    residue, or when a topology string doesn't index its sequence 1:1 (stale
    input — positions can't be mapped).
    """
    # Topology must index its sequence 1:1 for both loop extraction and the
    # per-column position lookup below.
    if len(human_topology) != len(human_sequence) or len(paralog_topology) != len(
        paralog_sequence
    ):
        return _empty_result(0, 0)

    n_human_loops = len(extract_ecd_loops(human_topology, human_sequence))
    n_paralog_loops = len(extract_ecd_loops(paralog_topology, paralog_sequence))

    # ``max`` denominator: penalise a variant that lost OR gained ECD residues.
    canon_ecd_len = human_topology.count("O")
    var_ecd_len = paralog_topology.count("O")
    denom = max(canon_ecd_len, var_ecd_len)
    if denom == 0:
        return _empty_result(n_human_loops, n_paralog_loops)

    c_seq = _sanitize(human_sequence)
    v_seq = _sanitize(paralog_sequence)
    try:
        alignment = _aligner().align(c_seq, v_seq)[0]
    except (ValueError, KeyError, IndexError):
        return _empty_result(n_human_loops, n_paralog_loops)

    mat = _blosum62()
    identical = 0
    positives = 0
    # ``alignment.aligned`` is shape (2, n_blocks, 2): gap-free aligned blocks
    # of [canonical_start, canonical_end] / [variant_start, variant_end]. Within
    # a block, canonical residue c0+k aligns to variant residue v0+k. Score only
    # the columns whose CANONICAL residue is extracellular ('O'), pairing each
    # canonical ECD residue with the variant residue actually aligned to it
    # (homology), never by loop index.
    for (c0, _c1), (v0, _v1) in zip(alignment.aligned[0], alignment.aligned[1]):
        for k in range(int(_c1) - int(c0)):
            ci = int(c0) + k
            if human_topology[ci] != "O":
                continue
            x = c_seq[ci]
            y = v_seq[int(v0) + k]
            if x == y:
                identical += 1
                positives += 1
            else:
                try:
                    if mat[x, y] > 0:
                        positives += 1
                except (KeyError, IndexError):
                    pass

    return EcdIdentityResult(
        ecd_pct_identity=identical / denom * 100.0,
        n_ecd_loops_compared=min(n_human_loops, n_paralog_loops),
        n_human_loops=n_human_loops,
        n_paralog_loops=n_paralog_loops,
        ecd_pct_similarity=positives / denom * 100.0,
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


# NOTE: a *full-length* (whole-protein) paralog identity is intentionally NOT
# computed here. Ensembl Compara already emits one — ``biomart_percent_identity``
# in the ``compara_paralog`` table, populated for 100% of paralog pairs,
# including the ECD-less proteins whose per-loop ``ecd_pct_identity`` is None.
# The deep-dive builder surfaces that value as
# ``ParalogEntry.full_length_pct_identity`` (see
# ``surfaceome_v1/d1_deterministic.py:_fetch_paralogs``). This mirrors how the
# ortholog full-length identity is sourced (``compara_ortholog.percent_identity``,
# also from Compara/BioMart), so the paralog and ortholog full-length numbers
# are computed the same way and are directly comparable in the viewer.
