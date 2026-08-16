from accessible_surfaceome.tag_sites.surface_loop import surface_loop_candidates


def _signals():
    # residue 100 = exposed ordered loop (should be picked);
    # residue 200 = buried helix (should be rejected).
    return {
        "topology": {100: "O", 200: "O"},
        "plddt": {100: 95.0, 200: 95.0},
        "rsa": {100: 0.55, 200: 0.02},
        "ss": {100: "C", 200: "H"},
        "gap_freq": {100: 0.30, 200: 0.00},
        "conservation": {100: 0.20, 200: 0.90},
        "feature_dist": {100: 25.0, 200: 25.0},  # Angstrom to nearest functional atom
        "sequence": "A" * 300,
    }


def test_gate_selects_exposed_ordered_loop_not_buried_helix():
    picks = surface_loop_candidates(_signals(), gene_symbol="X", uniprot_acc="Q00000")
    picked = {p["insert_after_residue"] for p in picks}
    assert 100 in picked
    assert 200 not in picked
    assert all(p["det_path"] == "surface_loop" for p in picks)
    assert all(p["provenance"] == "deterministic_computed" for p in picks)


def test_gate_rejects_intracellular_and_low_plddt():
    sig = _signals()
    sig["topology"][100] = "I"  # not extracellular anymore
    assert surface_loop_candidates(sig, gene_symbol="X", uniprot_acc="Q00000") == []

    sig2 = _signals()
    sig2["plddt"][100] = 40.0  # below the reliability gate → not a surface_loop candidate
    assert surface_loop_candidates(sig2, gene_symbol="X", uniprot_acc="Q00000") == []


def test_residues_carried_from_sequence():
    sig = _signals()
    sig["sequence"] = "M" + "K" * 99 + "P" + "G" * 199  # residue 100 = K, 101 = P
    picks = surface_loop_candidates(sig, gene_symbol="X", uniprot_acc="Q00000")
    site = next(p for p in picks if p["insert_after_residue"] == 100)
    assert site["residue_before"] == "K"
    assert site["residue_after"] == "P"


def test_residue_range_helper_and_loop_span():
    from accessible_surfaceome.tag_sites.model import residue_range
    from accessible_surfaceome.tag_sites.surface_loop import loop_span
    seq = "M" + "K" * 99 + "P" + "G" * 199   # 1=M, 2..100=K, 101=P, 102..=G
    assert residue_range(seq, 98, 105) == "K98-G105"
    assert residue_range(seq, 101, 101) is None   # single residue -> not a range
    assert residue_range(seq, None, 105) is None
    ss = {r: "C" for r in range(50, 65)}
    ss[49] = "H"
    ss[65] = "E"
    assert loop_span(ss, 57) == (50, 64)
    assert loop_span({100: "H"}, 100) is None


def test_loop_length_and_tag_fit():
    from accessible_surfaceome.tag_sites.surface_loop import loop_length, tag_fit
    # a 15-aa coil run bounded by helix/strand
    ss = {r: "C" for r in range(50, 65)}
    ss[45] = "H"
    ss[65] = "E"
    assert loop_length(ss, 57) == 15
    assert loop_length({100: "H"}, 100) == 0     # a helix residue is not a loop
    # Internal loops: ALFA (detection) + DogTag (loop-friendly covalent). SpyTag003
    # is a TERMINAL tag — a β-strand that can't complete SpyCatcher's sheet while
    # tethered both ends (Keeble 2022) — so it must NOT be recommended for a loop,
    # at ANY length. Length does not change the recommendation.
    assert tag_fit(15) == "ALFA, DogTag"
    assert tag_fit(5) == "ALFA, DogTag"
    assert "SpyTag003" not in tag_fit(15) and "SpyTag003" not in tag_fit(5)
