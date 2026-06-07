"""Pin the shared identity calculation so isoform / paralog / ortholog
%identity numbers can't drift apart and so a pure truncation no longer
reports as 100% identical.

This guards three call sites:

* :mod:`accessible_surfaceome.merge._sequence_identity` — the new shared
  helper. ``pct_identity`` and ``pct_identity_and_similarity`` must use
  ``max(len_a, len_b)`` as the denominator.
* :mod:`accessible_surfaceome.merge.paralog_ecd_identity` — per-loop
  identity for paralog AND ortholog ECDs. ``_pairwise_loop_identity`` and
  ``_loop_id_and_sim`` must delegate to the shared helper.
* :mod:`accessible_surfaceome.merge.isoform_identity` — full-length
  isoform identity. Must call the shared helper too.

The truncation test pins TGOLN2-style behavior: an isoform that's just
the first N residues of canonical (no substitutions) used to read 100%
and now must read N / len(canonical) * 100.
"""

from __future__ import annotations

from accessible_surfaceome.merge._sequence_identity import (
    pct_identity,
    pct_identity_and_similarity,
)
from accessible_surfaceome.merge.isoform_identity import compute_isoform_identity
from accessible_surfaceome.merge.paralog_ecd_identity import (
    LoopSpan,
    _loop_id_and_sim,
    _pairwise_loop_identity,
)


# A canonical ECD-style sequence with three contiguous "extracellular" regions
# (each is a real BLOSUM62-alignable string). The truncation iso is just the
# first 30 residues of it — no substitutions, no insertions.
CANONICAL_FULL = "MAKVTLISTTPNVERLENGRKEYMASGEYVDLPCISLEDFNTGRPCKYVHFGSWEIRYPNGNSLGGAFDDPSC"
TRUNCATION_30 = CANONICAL_FULL[:30]
ASSUMED_LEN = len(CANONICAL_FULL)  # 72 residues


def test_identical_sequences_read_100_percent() -> None:
    assert pct_identity(CANONICAL_FULL, CANONICAL_FULL) == 100.0


def test_pure_truncation_reads_coverage_not_100() -> None:
    """The headline bug: a clean truncation must NOT read 100%."""
    pct = pct_identity(CANONICAL_FULL, TRUNCATION_30)
    assert pct is not None
    # Coverage = 30 / 72 = 41.67 %. Allow ±0.5 to absorb alignment quirks.
    expected = 30 / ASSUMED_LEN * 100.0
    assert abs(pct - expected) < 0.5, (
        f"truncation should read ~{expected:.2f}%, got {pct:.2f}%"
    )


def test_truncation_is_below_full_length() -> None:
    """Belt-and-suspenders: identity should be strictly below 100% for any
    sequence shorter than its reference."""
    pct = pct_identity(CANONICAL_FULL, TRUNCATION_30)
    assert pct is not None
    assert pct < 99.0


def test_empty_inputs_return_none() -> None:
    assert pct_identity("", CANONICAL_FULL) is None
    assert pct_identity(CANONICAL_FULL, "") is None


def test_identity_and_similarity_share_denominator() -> None:
    """Identity ≤ similarity, and both use ``max(len)`` so a clean
    truncation reads as coverage rather than 100."""
    ident, sim = pct_identity_and_similarity(CANONICAL_FULL, TRUNCATION_30)
    assert ident is not None and sim is not None
    assert ident <= sim
    assert ident < 100.0  # the bug we're guarding against


def test_pairwise_loop_identity_uses_max_denominator() -> None:
    """``paralog_ecd_identity._pairwise_loop_identity`` must agree with
    the shared helper: a clean truncation reads coverage, not 1.0."""
    loop_canonical = LoopSpan(start=0, end=ASSUMED_LEN, sequence=CANONICAL_FULL)
    loop_short = LoopSpan(start=0, end=30, sequence=TRUNCATION_30)
    frac = _pairwise_loop_identity(loop_canonical, loop_short)
    # The function returns a FRACTION (0-1) per its docstring.
    assert frac < 0.99, f"truncated loop must not read ~100%, got {frac:.4f}"


def test_loop_id_and_sim_uses_max_denominator() -> None:
    """``_loop_id_and_sim`` returns (identity, similarity) FRACTIONS that
    use the same max-len denominator as the rest of the helpers."""
    loop_canonical = LoopSpan(start=0, end=ASSUMED_LEN, sequence=CANONICAL_FULL)
    loop_short = LoopSpan(start=0, end=30, sequence=TRUNCATION_30)
    ident, sim = _loop_id_and_sim(loop_canonical, loop_short)
    assert ident <= sim
    assert ident < 0.99, f"truncated loop must not read ~100%, got {ident:.4f}"


def test_isoform_full_length_identity_uses_max_denominator() -> None:
    """End-to-end: an isoform that's just the first 30 residues of canonical
    must not be marked 100% identical at the full-length level."""
    # Topology of a soluble protein — no 'O' or 'M' residues so the ECD
    # branch is skipped (ecd_pct_identity will be None); we're testing
    # the full-length path specifically.
    canonical_topo = "I" * ASSUMED_LEN
    isoform_topo = "I" * 30
    result = compute_isoform_identity(
        canonical_topology=canonical_topo,
        canonical_sequence=CANONICAL_FULL,
        isoform_topology=isoform_topo,
        isoform_sequence=TRUNCATION_30,
    )
    assert result.full_length_pct_identity is not None
    assert result.full_length_pct_identity < 99.0, (
        f"full-length identity for a clean truncation must read coverage, "
        f"not ~100%; got {result.full_length_pct_identity:.2f}%"
    )
