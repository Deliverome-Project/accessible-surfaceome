"""Regression tests for the homology-aligned, canonical-anchored ECD identity.

Pins the fix for the positional loop-pairing bug in
``paralog_ecd_identity.compute_ecd_identity``: an N-terminally-truncated variant
that DROPS an early extracellular loop but KEEPS a later one used to be scored
by comparing non-homologous loops (canonical loop 0 vs the variant's loop 0,
which is really the canonical's loop 1). CD63 isoform P08962-3 read ~4% instead
of the true ~84%. The metric now aligns the variant to the canonical and scores
canonical extracellular positions by homology, with a ``max`` ECD-length
denominator so a lost OR gained loop is penalised.
"""

from accessible_surfaceome.merge.paralog_ecd_identity import compute_ecd_identity

# Canonical, tetraspanin-like:
#   N-term(3,I) · TM1(4) · EC1(4, small O-loop) · TM2(4) · ICD(3,I)
#   · TM3(4) · EC2(10, large O-loop) · TM4(4) · C-term(3,I)
# Canonical ECD length = 4 (EC1) + 10 (EC2) = 14.
_CANON_SEQ = "MKN" + "LLLL" + "DERT" + "VVVV" + "KKK" + "WWWW" + "FGHIKLMNPQ" + "YYYY" + "SSS"
_CANON_TOPO = "III" + "MMMM" + "OOOO" + "MMMM" + "III" + "MMMM" + "OOOOOOOOOO" + "MMMM" + "III"


def test_n_truncation_keeps_later_loop_scored_by_homology() -> None:
    """Variant loses EC1 but keeps EC2 (identical). The old positional pairing
    compared canonical EC1 against the variant's EC2 (non-homologous → near
    zero). Homology pairing scores EC2↔EC2 (10 identical residues) and penalises
    only the lost EC1: 10 identical / max(14, 10) = 10/14 ≈ 71.4%."""
    var_seq = "WWWW" + "FGHIKLMNPQ" + "YYYY" + "SSS"
    var_topo = "MMMM" + "OOOOOOOOOO" + "MMMM" + "III"
    res = compute_ecd_identity(
        human_topology=_CANON_TOPO,
        human_sequence=_CANON_SEQ,
        paralog_topology=var_topo,
        paralog_sequence=var_seq,
    )
    assert res.ecd_pct_identity is not None
    assert round(res.ecd_pct_identity, 1) == 71.4  # 10/14
    # Neither the old mispaired near-zero, nor a false 100% (EC1 loss penalised).
    assert 50.0 < res.ecd_pct_identity < 100.0


def test_identical_variant_is_100_percent() -> None:
    res = compute_ecd_identity(
        human_topology=_CANON_TOPO,
        human_sequence=_CANON_SEQ,
        paralog_topology=_CANON_TOPO,
        paralog_sequence=_CANON_SEQ,
    )
    assert round(res.ecd_pct_identity, 1) == 100.0
    assert round(res.ecd_pct_similarity, 1) == 100.0


def test_gained_ecd_residues_penalised_by_max_denominator() -> None:
    """A variant identical across the canonical ECD but carrying EXTRA
    extracellular residues (a gained loop) reads < 100%: numerator is bounded by
    the canonical ECD (14 matches) while the denominator is max(14, 24) = 24 →
    14/24 ≈ 58.3%."""
    # Prepend a 10-residue extracellular loop (+ a flanking TM so it's a real
    # loop) ahead of the otherwise-identical canonical body.
    var_seq = "ACDEFGHIKL" + "PPPP" + _CANON_SEQ
    var_topo = "OOOOOOOOOO" + "MMMM" + _CANON_TOPO
    res = compute_ecd_identity(
        human_topology=_CANON_TOPO,
        human_sequence=_CANON_SEQ,
        paralog_topology=var_topo,
        paralog_sequence=var_seq,
    )
    assert res.ecd_pct_identity is not None
    assert res.ecd_pct_identity < 100.0
    assert round(res.ecd_pct_identity, 1) == round(14 / 24 * 100, 1)


def test_no_ecd_either_side_is_none() -> None:
    glob_seq = "MKNLLLLVVVVKKK"
    glob_topo = "IIIMMMMMMMMIII"
    res = compute_ecd_identity(
        human_topology=glob_topo,
        human_sequence=glob_seq,
        paralog_topology=glob_topo,
        paralog_sequence=glob_seq,
    )
    assert res.ecd_pct_identity is None
    assert res.ecd_pct_similarity is None
