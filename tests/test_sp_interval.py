"""SP-proximal tag placement: Tedman's interval method, generalised to three predictors."""

from __future__ import annotations

import pytest

from accessible_surfaceome.tag_sites import sp_interval as S

DIS = [0.9] * 10 + [0.1] * 40        # disordered to residue 10, structured after
CASSETTE = "GGGGSHATAG"


def test_structure_onset_is_the_first_sustained_ordered_run():
    assert S.structure_onset(DIS, 0) == 11


def test_a_single_ordered_residue_does_not_start_the_fold():
    noisy = [0.9] * 5 + [0.1] + [0.9] * 5 + [0.1] * 40
    assert S.structure_onset(noisy, 0) == 12  # the run, not the blip at 6


def test_an_all_disordered_ectodomain_has_no_boundary():
    assert S.structure_onset([0.9] * 50, 0) is None


def test_interval_runs_from_the_cleavage_site_to_the_fold():
    iv = S.tag_interval(5, {"a": DIS})
    assert (iv.lo, iv.hi) == (5, 10)
    assert iv.positions == [5, 6, 7, 8, 9, 10]


def test_onset_is_the_median_so_one_outlier_cannot_collapse_the_interval():
    tracks = {"early": [0.1] * 50,                       # structured from the cleavage site
              "mid": DIS,                                 # says residue 11
              "late": [0.9] * 20 + [0.1] * 30}            # says residue 21
    iv = S.tag_interval(5, tracks)
    assert iv.hi == 10  # the median onset (11) - 1, not the earliest (6) or latest (21)
    # the scan starts at the cleavage site, so no onset can precede it
    assert iv.onsets == {"early": 6, "mid": 11, "late": 21}


def test_no_predictor_finds_a_boundary_falls_back_to_a_typical_width():
    iv = S.tag_interval(5, {"a": [0.9] * 50}, fallback_width=7)
    assert iv.width == 7
    assert all(v is None for v in iv.onsets.values())


def test_tagged_sequence_splices_after_the_named_residue():
    assert S.tagged_sequence("ABCDEF", 3, "xx") == "ABCxxDEF"
    assert S.tagged_sequence("ABCDEF", 0, "xx") == "xxABCDEF"
    with pytest.raises(ValueError):
        S.tagged_sequence("ABC", 9, "x")


def test_candidate_designs_cover_every_admissible_position():
    iv = S.tag_interval(2, {"a": [0.9] * 6 + [0.1] * 20})
    seq = "M" * 26
    designs = S.candidate_designs(seq, iv, CASSETTE)
    assert [p for p, _ in designs] == iv.positions
    assert all(len(s) == len(seq) + len(CASSETTE) for _, s in designs)


def test_scores_are_kept_per_tool_and_never_averaged_into_the_record():
    iv = S.tag_interval(2, {"a": DIS})
    got = S.score_positions(iv, {"a": DIS, "b": [0.5] * 50},
                            percentiles={"a": [80.0] * 50, "b": [20.0] * 50})
    assert set(got[0].scores) == {"a", "b"}
    assert got[0].scores["a"] != got[0].scores["b"]
    # consensus is computed on demand, and weighting changes the answer
    assert got[0].consensus() == pytest.approx(50.0)
    assert got[0].consensus({"a": 3.0, "b": 1.0}) == pytest.approx(65.0)


def test_reprediction_flags_a_moved_cleavage_site():
    r = S.compare_reprediction(10, cleavage_before=20, cleavage_after=24,
                               disorder_before={"a": [0.5] * 30}, disorder_after={"a": [0.5] * 40},
                               cassette_len=10)
    assert not r.ok and not r.cleavage_preserved


def test_reprediction_compares_disorder_only_upstream_of_the_insertion():
    before = [0.1] * 30
    after = [0.1] * 10 + [0.9] * 30        # everything downstream shifted by the tag
    r = S.compare_reprediction(10, 20, 20, {"a": before}, {"a": after}, cassette_len=10)
    assert r.ok
    assert r.disorder_shift["a"] == pytest.approx(0.0)  # upstream is untouched
