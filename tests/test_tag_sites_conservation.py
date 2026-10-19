from accessible_surfaceome.tag_sites.signals import ortholog_conservation


def test_all_identical_orthologs_are_fully_conserved():
    human = "ACDEFGHIKL"
    out = ortholog_conservation(human, [human, human])
    # every human residue (1-indexed) is identical in both orthologs
    assert all(out["conservation"][r] == 1.0 for r in range(1, len(human) + 1))
    assert all(out["gap_freq"][r] == 0.0 for r in range(1, len(human) + 1))


def test_substitution_lowers_conservation_at_that_position():
    human = "ACDEFGHIKL"
    #                ^ position 5 (F) substituted in one ortholog
    orth_sub = "ACDEYGHIKL"
    out = ortholog_conservation(human, [human, orth_sub])
    assert out["conservation"][5] == 0.5  # 1 of 2 orthologs identical at pos 5
    assert out["conservation"][1] == 1.0  # unchanged elsewhere


def test_empty_ortholog_set_is_neutral():
    human = "ACDEFG"
    out = ortholog_conservation(human, [])
    # no evidence → neutral conservation (0.0, so it never blocks) + no gaps
    assert out["conservation"][1] == 0.0
    assert out["gap_freq"][1] == 0.0
