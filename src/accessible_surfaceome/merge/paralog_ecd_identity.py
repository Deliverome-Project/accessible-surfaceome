"""Compute per-loop BLOSUM62 ECD identity between human canonical paralogs.

Given two proteins' canonical DeepTMHMM topology + sequence, define each
contiguous run of ``'O'`` (extracellular) residues as a loop. Pair loops
positionally (loop 1 of A ↔ loop 1 of B, etc.) up to ``min(n_loops_a,
n_loops_b)``. For each loop pair:

    BLOSUM62 global pairwise alignment (gap_open=-10, gap_extend=-0.5).
    loop_identity = matches / max(len_loop_a, len_loop_b)

Aggregate per protein-pair, length-weighted across all aligned loops::

    ecd_pct_identity = sum(loop_identity_i * loop_len_i) / sum(loop_len_i) * 100

The denominator switched from ``min(len)`` to ``max(len)`` (2026-06) so
truncated loops no longer read 100% identity — see the docstring on
:mod:`accessible_surfaceome.merge._sequence_identity` for the rationale.
``loop_len_i`` used for the aggregator weight is still the ``min`` of the
two paired loop lengths (the safe shared signal); only the per-loop
identity denominator changed.

When either protein has zero ``'O'`` residues → ``ecd_pct_identity = None``,
``n_ecd_loops_compared = 0``.

Reproducing the GPR75 example: GPR75 (O95800, 7TM GPCR) vs CCRL2 (O00421) →
both have an N-terminal ECD + three ECLs. The value will be slightly lower
than the GPR75.json snapshot's ``ecd_pct_identity: 18.2`` after the
``max(len)`` switch — published records will need re-annotation to refresh
the number.
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
    weighted_similarity = 0.0
    for i in range(n_compare):
        h = human_loops[i]
        p = paralog_loops[i]
        loop_len = min(h.length, p.length)
        if loop_len == 0:
            continue
        identity, similarity = _loop_id_and_sim(h, p)
        weighted_identity += identity * loop_len
        weighted_similarity += similarity * loop_len
        total_weight += loop_len

    if total_weight == 0:
        return EcdIdentityResult(
            ecd_pct_identity=None,
            n_ecd_loops_compared=0,
            n_human_loops=len(human_loops),
            n_paralog_loops=len(paralog_loops),
            ecd_pct_similarity=None,
        )

    pct = (weighted_identity / total_weight) * 100.0
    pct_sim = (weighted_similarity / total_weight) * 100.0
    return EcdIdentityResult(
        ecd_pct_identity=pct,
        n_ecd_loops_compared=n_compare,
        n_human_loops=len(human_loops),
        n_paralog_loops=len(paralog_loops),
        ecd_pct_similarity=pct_sim,
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
