"""Unit tests for ortholog topology projection.

Reproduces the two real cyno failure modes the projection fixes:
  * truncated model (EGFR cyno) → a human TM helix aligns to an ortholog
    gap → flagged ``tm_absent_from_model`` rather than silently 0 TM;
  * padded model (CD81 cyno) → DeepTMHMM-on-ortholog miscounts, projection
    recovers the conserved TM count.

Pure Python — no D1, no network, no LFS data.
"""

from __future__ import annotations

import random

from accessible_surfaceome.merge.ortholog_topology_projection import (
    project_human_topology_onto_ortholog,
)

_AA = "ACDEFGHIKLMNPQRSTVWY"


def _seq(n: int, seed: int = 0) -> str:
    """Deterministic, non-periodic amino-acid sequence so the global
    alignment of a prefix / insertion variant is unambiguous."""
    rng = random.Random(seed)
    return "".join(rng.choice(_AA) for _ in range(n))


# Single-pass type-I layout (signal + ECD + one TM + ICD), EGFR-like.
_SINGLE_PASS_TOPO = "S" * 5 + "O" * 20 + "M" * 10 + "I" * 15  # len 50, 1 M run
# Tetraspanin-like layout, four TM helices, CD81-like.
_TETRASPANIN_TOPO = (
    "I" * 4 + "M" * 8 + "O" * 6 + "M" * 8 + "I" * 4 + "M" * 8 + "O" * 10 + "M" * 8 + "I" * 4
)  # len 60, 4 M runs


def test_truncated_single_pass_flags_absent_tm() -> None:
    """EGFR cyno analogue: ortholog model ends inside the ECD, before the TM."""
    human_seq = _seq(50)
    # Truncate to the signal+ECD region only (first 25 residues) — the TM
    # helix (positions 25-34) has no ortholog residue to land on.
    ortholog_seq = human_seq[:25]
    result = project_human_topology_onto_ortholog(
        human_topology=_SINGLE_PASS_TOPO,
        human_sequence=human_seq,
        ortholog_sequence=ortholog_seq,
    )
    assert result is not None
    assert result.tm_absent_from_model is True
    assert result.n_tm_regions_absent == 1
    # No TM physically present in the truncated model.
    assert result.tm_helix_count == 0
    assert result.ecd_length_residues == 20
    assert len(result.per_residue_topology) == len(ortholog_seq)


def test_conserved_tetraspanin_recovers_count() -> None:
    """CD81 cyno analogue (idealised): a faithful ortholog recovers 4 TM."""
    human_seq = _seq(60)
    result = project_human_topology_onto_ortholog(
        human_topology=_TETRASPANIN_TOPO,
        human_sequence=human_seq,
        ortholog_sequence=human_seq,  # identical → trivial 1:1 alignment
    )
    assert result is not None
    assert result.tm_helix_count == 4
    assert result.tm_absent_from_model is False
    assert result.n_tm_regions_absent == 0
    # Identical sequence → topology projects through unchanged.
    assert result.per_residue_topology == _TETRASPANIN_TOPO


def test_padded_with_loop_insertion_keeps_count() -> None:
    """CD81 cyno analogue: a padded model (loop insertion) still recovers 4 TM
    where raw DeepTMHMM-on-ortholog would miscount."""
    human_seq = _seq(60)
    # Insert 5 unrelated residues at index 28 — inside the cytoplasmic loop
    # between the 2nd and 3rd TM helices.
    ortholog_seq = human_seq[:28] + _seq(5, seed=1) + human_seq[28:]
    result = project_human_topology_onto_ortholog(
        human_topology=_TETRASPANIN_TOPO,
        human_sequence=human_seq,
        ortholog_sequence=ortholog_seq,
    )
    assert result is not None
    assert result.tm_helix_count == 4
    assert result.tm_absent_from_model is False
    assert len(result.per_residue_topology) == len(ortholog_seq)


def test_soluble_human_returns_none() -> None:
    """Fully intracellular human protein → nothing to project → None (caller
    keeps the ortholog's raw row)."""
    human_seq = _seq(30)
    result = project_human_topology_onto_ortholog(
        human_topology="I" * 30,
        human_sequence=human_seq,
        ortholog_sequence=_seq(30, seed=2),
    )
    assert result is None


def test_length_mismatch_returns_none() -> None:
    result = project_human_topology_onto_ortholog(
        human_topology="O" * 10,
        human_sequence=_seq(9),
        ortholog_sequence=_seq(10),
    )
    assert result is None


def test_empty_inputs_return_none() -> None:
    assert (
        project_human_topology_onto_ortholog(
            human_topology="", human_sequence="", ortholog_sequence=""
        )
        is None
    )
