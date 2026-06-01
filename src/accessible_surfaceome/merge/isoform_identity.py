"""Sequence identity of an alternative isoform against its own canonical.

Alternative isoforms are splice products of the *same* gene, so — unlike
orthologs and paralogs — Ensembl Compara emits no pairwise identity for
them. We compute it directly from the sequences the topology sweep already
landed in ``topology_public.sequence`` (canonical + every ``human_isoforms``
row), reusing the BLOSUM62 global aligner that backs the paralog ECD
identity (:mod:`accessible_surfaceome.merge.paralog_ecd_identity`).

Two numbers per isoform, both on a 0–100 scale and both relative to the
*canonical* sequence of the same protein:

* ``full_length_pct_identity`` — global BLOSUM62 alignment of the whole
  isoform against the whole canonical; identity = matches / min(len) * 100.
  The ``min(len)`` denominator mirrors the per-loop convention in
  ``paralog_ecd_identity._pairwise_loop_identity``: a pure truncation
  isoform (no substitutions, just shorter) reads ~100 %, correctly saying
  "identical over its length, only shorter." A reader who wants the
  fraction-of-canonical-covered reads ECD/ICD lengths instead.
* ``ecd_pct_identity`` — length-weighted per-extracellular-loop identity,
  identical method + denominator to the paralog ECD number, so the isoform
  and paralog ECD columns in the viewer are directly comparable. ``None``
  when either the canonical or the isoform has no extracellular ('O')
  residues (e.g. a GLOB intracellular protein, or an isoform that drops the
  entire ECD).
"""

from __future__ import annotations

from dataclasses import dataclass

from accessible_surfaceome.merge.paralog_ecd_identity import (
    _aligner,
    _sanitize,
    compute_ecd_identity,
)


@dataclass(frozen=True)
class IsoformIdentityResult:
    """Identity of one alternative isoform against its canonical sequence."""

    full_length_pct_identity: float | None
    ecd_pct_identity: float | None
    # ECD percent similarity (identity + BLOSUM62-positive substitutions),
    # same definition as the ortholog/paralog ECD similarity. None when there
    # is no ECD to compare.
    ecd_pct_similarity: float | None = None


def _full_length_identity(seq_a: str, seq_b: str) -> float | None:
    """Global BLOSUM62 identity = matches / min(len) * 100, or None if empty."""
    if not seq_a or not seq_b:
        return None
    aligner = _aligner()
    a = _sanitize(seq_a)
    b = _sanitize(seq_b)
    try:
        alignment = aligner.align(a, b)[0]
    except (ValueError, KeyError):
        return None
    matches = 0
    for (a_start, a_end), (b_start, b_end) in zip(alignment.aligned[0], alignment.aligned[1]):
        block_a = a[a_start:a_end]
        block_b = b[b_start:b_end]
        matches += sum(1 for x, y in zip(block_a, block_b) if x == y)
    return matches / min(len(a), len(b)) * 100.0


def compute_isoform_identity(
    *,
    canonical_topology: str,
    canonical_sequence: str,
    isoform_topology: str,
    isoform_sequence: str,
) -> IsoformIdentityResult:
    """Full-length + ECD identity of one isoform vs the canonical sequence."""
    full = _full_length_identity(canonical_sequence, isoform_sequence)
    ecd = compute_ecd_identity(
        human_topology=canonical_topology,
        human_sequence=canonical_sequence,
        paralog_topology=isoform_topology,
        paralog_sequence=isoform_sequence,
    )
    return IsoformIdentityResult(
        full_length_pct_identity=full,
        ecd_pct_identity=ecd.ecd_pct_identity,
        ecd_pct_similarity=ecd.ecd_pct_similarity,
    )
