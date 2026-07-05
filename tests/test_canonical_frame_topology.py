"""Unit tests for canonical-frame topology projection.

Covers the four cases the viewer relies on to line homologous features up on
a shared canonical axis:

  * identical sequences → topology unchanged (the canonical-vs-self invariant);
  * an N-terminally-deleted variant → leading gap chars;
  * an internal-deletion variant → internal gap chars;
  * an insertion variant → the inserted columns are dropped (output stays
    len(canonical_sequence)).

Pure Python — no D1, no network, no LFS data.
"""

from __future__ import annotations

import random

from accessible_surfaceome.merge.canonical_frame_topology import (
    GAP_CHAR,
    project_topology_onto_canonical_frame,
)

_AA = "ACDEFGHIKLMNPQRSTVWY"


def _seq(n: int, seed: int = 0) -> str:
    """Deterministic, non-periodic amino-acid sequence so a prefix / internal
    deletion / insertion aligns unambiguously against the canonical."""
    rng = random.Random(seed)
    return "".join(rng.choice(_AA) for _ in range(n))


# Single-pass type-I layout: signal + ECD + one TM + ICD (len 50, 1 M run).
_CANON_SEQ = _seq(50)
_CANON_TOPO = "S" * 5 + "O" * 20 + "M" * 10 + "I" * 15


def test_identical_sequence_unchanged() -> None:
    """Canonical projected against itself equals its own topology, no gaps."""
    out = project_topology_onto_canonical_frame(
        canonical_sequence=_CANON_SEQ,
        variant_sequence=_CANON_SEQ,
        variant_topology=_CANON_TOPO,
    )
    assert out == _CANON_TOPO
    assert GAP_CHAR not in out
    assert len(out) == len(_CANON_SEQ)


def test_variant_equal_but_not_identity_object() -> None:
    """A distinct string equal to the canonical still projects 1:1 (the
    fast-path compares by value, not identity)."""
    out = project_topology_onto_canonical_frame(
        canonical_sequence=_CANON_SEQ,
        variant_sequence="".join(_CANON_SEQ),  # equal value, new object
        variant_topology=_CANON_TOPO,
    )
    assert out == _CANON_TOPO


def test_n_terminal_deletion_leading_gaps() -> None:
    """A variant missing the first 10 canonical residues → 10 leading gaps,
    then the variant's topology on the remaining canonical coordinates."""
    n_del = 10
    variant_seq = _CANON_SEQ[n_del:]
    variant_topo = _CANON_TOPO[n_del:]
    out = project_topology_onto_canonical_frame(
        canonical_sequence=_CANON_SEQ,
        variant_sequence=variant_seq,
        variant_topology=variant_topo,
    )
    assert out is not None
    assert len(out) == len(_CANON_SEQ)
    # First n_del canonical positions are uncovered by the variant → gaps.
    assert out[:n_del] == GAP_CHAR * n_del
    # The rest carries the variant's own labels on the aligned coordinates,
    # which — for a clean prefix deletion — is exactly the canonical tail.
    assert out[n_del:] == _CANON_TOPO[n_del:]


def test_internal_deletion_internal_gaps() -> None:
    """A variant missing an internal block (residues 20..29) → those exact
    canonical positions become gaps; flanks keep their labels."""
    lo, hi = 20, 30
    variant_seq = _CANON_SEQ[:lo] + _CANON_SEQ[hi:]
    variant_topo = _CANON_TOPO[:lo] + _CANON_TOPO[hi:]
    out = project_topology_onto_canonical_frame(
        canonical_sequence=_CANON_SEQ,
        variant_sequence=variant_seq,
        variant_topology=variant_topo,
    )
    assert out is not None
    assert len(out) == len(_CANON_SEQ)
    # The deleted window is gaps on the canonical axis…
    assert out[lo:hi] == GAP_CHAR * (hi - lo)
    # …and the flanking regions are gap-free, holding the canonical labels.
    assert GAP_CHAR not in out[:lo]
    assert GAP_CHAR not in out[hi:]
    assert out[:lo] == _CANON_TOPO[:lo]
    assert out[hi:] == _CANON_TOPO[hi:]


def test_insertion_columns_dropped() -> None:
    """A variant with an internal insertion projects back to exactly
    len(canonical) — the inserted residues have no canonical coordinate and
    are dropped, so no gap is introduced and the length is preserved."""
    ins_at = 28
    insert = _seq(6, seed=99)
    variant_seq = _CANON_SEQ[:ins_at] + insert + _CANON_SEQ[ins_at:]
    # Give the inserted stretch a distinctive label ('B') so we can prove it
    # never lands on the canonical axis.
    variant_topo = _CANON_TOPO[:ins_at] + "B" * len(insert) + _CANON_TOPO[ins_at:]
    out = project_topology_onto_canonical_frame(
        canonical_sequence=_CANON_SEQ,
        variant_sequence=variant_seq,
        variant_topology=variant_topo,
    )
    assert out is not None
    # Length is the canonical's, NOT the (longer) variant's.
    assert len(out) == len(_CANON_SEQ)
    # A clean insertion into an otherwise-identical variant → the canonical
    # labels survive on every canonical coordinate, and the inserted 'B' run
    # is dropped entirely.
    assert out == _CANON_TOPO
    assert "B" not in out
    assert GAP_CHAR not in out


def test_substitution_variant_relabels_positions() -> None:
    """Same-length variant with a different topology call in a stretch → the
    projection carries the VARIANT's labels (it relocates, never invents),
    so a soluble/decoy isoform's divergent topology shows through."""
    # Same length, but the variant lost its TM helix (soluble isoform): the
    # M-run region reads 'O' instead of 'M'.
    variant_topo = "S" * 5 + "O" * 30 + "I" * 15
    out = project_topology_onto_canonical_frame(
        canonical_sequence=_CANON_SEQ,
        variant_sequence=_CANON_SEQ,  # identical sequence, different topology
        variant_topology=variant_topo,
    )
    # Identical sequence → 1:1, so the variant's own (soluble) topology shows.
    assert out == variant_topo
    assert "M" not in out


def test_length_mismatch_returns_none() -> None:
    """variant_topology must index variant_sequence 1:1."""
    out = project_topology_onto_canonical_frame(
        canonical_sequence=_CANON_SEQ,
        variant_sequence=_seq(40, seed=3),
        variant_topology="O" * 39,  # off by one
    )
    assert out is None


def test_empty_inputs_return_none() -> None:
    assert (
        project_topology_onto_canonical_frame(
            canonical_sequence="", variant_sequence="", variant_topology=""
        )
        is None
    )
    assert (
        project_topology_onto_canonical_frame(
            canonical_sequence=_CANON_SEQ,
            variant_sequence="",
            variant_topology="",
        )
        is None
    )


def test_output_only_uses_variant_chars_plus_gap() -> None:
    """Every char in the output is either a variant topology char or GAP_CHAR
    — the projection never emits anything of its own except the gap sentinel."""
    variant_seq = _CANON_SEQ[8:42]  # both-ends truncation
    variant_topo = _CANON_TOPO[8:42]
    out = project_topology_onto_canonical_frame(
        canonical_sequence=_CANON_SEQ,
        variant_sequence=variant_seq,
        variant_topology=variant_topo,
    )
    assert out is not None
    assert set(out) <= set(variant_topo) | {GAP_CHAR}
    # Both ends are truncated → leading and trailing gaps.
    assert out.startswith(GAP_CHAR)
    assert out.endswith(GAP_CHAR)
