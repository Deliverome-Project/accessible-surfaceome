from accessible_surfaceome.tag_sites.disorder import disorder_candidates


def _sig(plddt, topo, feat_dist, seq):
    return {
        "plddt": plddt, "topology": topo, "feature_dist": feat_dist,
        "conservation": {r: 0.2 for r in plddt}, "sequence": seq,
    }


def test_low_plddt_extracellular_run_becomes_a_site():
    rng = range(50, 56)  # 6-residue run
    sig = _sig({r: 55.0 for r in rng}, {r: "O" for r in rng},
               {r: 25.0 for r in rng}, "A" * 300)
    picks = disorder_candidates(sig, gene_symbol="X", uniprot_acc="Q0")
    assert len(picks) == 1 and picks[0]["det_path"] == "disorder"
    assert 50 <= picks[0]["insert_after_residue"] <= 55
    assert picks[0]["provenance"] == "deterministic_computed"


def test_short_run_and_intracellular_run_rejected():
    short = _sig({r: 55.0 for r in range(50, 53)}, {r: "O" for r in range(50, 53)},
                 {r: 25.0 for r in range(50, 53)}, "A" * 300)
    assert disorder_candidates(short, gene_symbol="X", uniprot_acc="Q0") == []
    ic = _sig({r: 55.0 for r in range(50, 56)}, {r: "I" for r in range(50, 56)},
              {r: 25.0 for r in range(50, 56)}, "A" * 300)
    assert disorder_candidates(ic, gene_symbol="X", uniprot_acc="Q0") == []


def test_feature_overlap_vetoes_run():
    rng = range(50, 56)
    sig = _sig({r: 55.0 for r in rng}, {r: "O" for r in rng},
               {r: 5.0 for r in rng}, "A" * 300)  # too close to a functional atom
    assert disorder_candidates(sig, gene_symbol="X", uniprot_acc="Q0") == []
