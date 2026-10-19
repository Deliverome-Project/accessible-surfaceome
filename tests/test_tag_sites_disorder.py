from accessible_surfaceome.tag_sites.disorder import disorder_candidates


def _sig(plddt, topo, feat_dist, seq, rsa=None):
    return {
        "plddt": plddt, "topology": topo, "feature_dist": feat_dist,
        "conservation": {r: 0.2 for r in plddt}, "sequence": seq,
        "rsa": rsa if rsa is not None else {r: 0.5 for r in plddt},
    }


def test_emits_exposed_sites_across_a_run_ranked_by_exposure():
    rng = range(50, 57)  # 7-residue low-pLDDT extracellular run
    rsa = {50: 0.1, 51: 0.1, 52: 0.2, 53: 0.2, 54: 0.4, 55: 0.9, 56: 0.5}
    sig = _sig({r: 55.0 for r in rng}, {r: "O" for r in rng},
               {r: 25.0 for r in rng}, "A" * 300, rsa=rsa)
    picks = disorder_candidates(sig, gene_symbol="X", uniprot_acc="Q0")
    residues = [p["insert_after_residue"] for p in picks]
    assert residues, "a >=4 low-pLDDT extracellular run must yield candidates"
    assert all(50 <= r <= 56 for r in residues)
    assert all(p["det_path"] == "disorder" for p in picks)
    assert all(p["provenance"] == "deterministic_computed" for p in picks)
    # exposure-ranked so NMS keeps the exposed peak: most-exposed residue (55) leads
    assert residues[0] == 55
    # every disorder site reports the tolerant FEATURE span (the low-pLDDT run 50-56)
    assert all(p["residue_range"] == "A50-A56" for p in picks)  # seq is all 'A'


def test_short_run_and_intracellular_run_rejected():
    short = _sig({r: 55.0 for r in range(50, 53)}, {r: "O" for r in range(50, 53)},
                 {r: 25.0 for r in range(50, 53)}, "A" * 300)
    assert disorder_candidates(short, gene_symbol="X", uniprot_acc="Q0") == []
    ic = _sig({r: 55.0 for r in range(50, 56)}, {r: "I" for r in range(50, 56)},
              {r: 25.0 for r in range(50, 56)}, "A" * 300)
    assert disorder_candidates(ic, gene_symbol="X", uniprot_acc="Q0") == []


def test_feature_veto_gates_insertion_points_without_fragmenting_run():
    rng = range(50, 56)
    # whole run within feature clearance -> no valid insertion point -> no sites
    allclose = _sig({r: 55.0 for r in rng}, {r: "O" for r in rng},
                    {r: 5.0 for r in rng}, "A" * 300)
    assert disorder_candidates(allclose, gene_symbol="X", uniprot_acc="Q0") == []
    # only some residues clear the feature veto: the run still qualifies (>=4), and ONLY the
    # feature-clear residues become candidates — the veto no longer fragments it.
    feat = {50: 5.0, 51: 5.0, 52: 25.0, 53: 5.0, 54: 25.0, 55: 5.0}
    part = _sig({r: 55.0 for r in rng}, {r: "O" for r in rng}, feat, "A" * 300)
    res = {p["insert_after_residue"] for p in disorder_candidates(part, gene_symbol="X", uniprot_acc="Q0")}
    assert res == {52, 54}
