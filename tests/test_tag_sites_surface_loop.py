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
