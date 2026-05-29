"""Unit tests for whole-protein paralog identity (``compute_full_length_identity``).

The full-length path exists so ECD-less proteins (SRC-family kinases,
soluble / cytoplasmic enzymes) — whose per-loop ``ecd_pct_identity`` is
``None`` because they have no extracellular 'O' loops — still get a
homology number for the viewer's antibody cross-reactivity tier.
"""

from __future__ import annotations

from accessible_surfaceome.merge.paralog_ecd_identity import (
    compute_full_length_identity,
    compute_full_length_identity_from_records,
)

# A short Src-homology-domain-ish fragment and a near-paralog of it. These
# stand in for "two ECD-less kinases that are clearly homologous" without
# pulling real UniProt sequences into the test.
SEQ_A = "MGSNKSKPKDASQRRRSLEPAENVHGAGGGAFPASQTPSKPASADGHRGPSAAFAPAAAE"
SEQ_B = "MGSNKSKPKDASQRRRSLEPSENVHGAGGGAFPASQTPSKPATADGHRGPSAAFAPAAAE"


def test_identical_sequences_are_100() -> None:
    assert compute_full_length_identity(SEQ_A, SEQ_A) == 100.0


def test_near_paralog_is_high_but_not_100() -> None:
    pct = compute_full_length_identity(SEQ_A, SEQ_B)
    assert pct is not None
    assert 80.0 < pct < 100.0


def test_defined_for_ecd_less_sequences() -> None:
    # No topology / no 'O' loops involved at all — full-length identity is
    # purely sequence-based, so it returns a real number for proteins that
    # would yield ecd_pct_identity == None.
    pct = compute_full_length_identity("ACDEFGHIKLMNPQRSTVWY", "ACDEFGHIKLMNPQRSTVWY")
    assert pct == 100.0


def test_empty_sequence_returns_none() -> None:
    assert compute_full_length_identity("", SEQ_A) is None
    assert compute_full_length_identity(SEQ_A, "") is None


def test_symmetric() -> None:
    ab = compute_full_length_identity(SEQ_A, SEQ_B)
    ba = compute_full_length_identity(SEQ_B, SEQ_A)
    assert ab is not None and ba is not None
    assert abs(ab - ba) < 1e-9


def test_nonstandard_residues_do_not_crash() -> None:
    # Selenocysteine (U) and ambiguity codes are sanitized to 'X' before the
    # BLOSUM62 aligner sees them — the call must not raise.
    pct = compute_full_length_identity("ACDEUGHIKL", "ACDEXGHIKL")
    assert pct is not None
    assert 0.0 <= pct <= 100.0


def test_normalized_by_min_length() -> None:
    # Shorter sequence fully contained in the longer one → identity uses the
    # min length as the denominator, so a perfect local match scores 100.
    short = "ACDEFGHIKL"
    long = "ACDEFGHIKLMNPQRSTVWY"
    pct = compute_full_length_identity(short, long)
    assert pct == 100.0


def test_from_records_adapter() -> None:
    human = {"sequence": SEQ_A}
    paralog = {"sequence": SEQ_B}
    direct = compute_full_length_identity(SEQ_A, SEQ_B)
    via_adapter = compute_full_length_identity_from_records(human, paralog)
    assert direct == via_adapter
