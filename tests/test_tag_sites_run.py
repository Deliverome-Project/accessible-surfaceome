from accessible_surfaceome.tag_sites.run import derive_deterministic_sites


def test_combines_both_paths_disjoint_by_plddt():
    # residues 50-55: low pLDDT extracellular run  -> disorder site
    # residue 100: high pLDDT exposed loop         -> surface_loop site
    lo = range(50, 56)
    plddt = {r: 55.0 for r in lo}
    plddt[100] = 95.0
    topo = {r: "O" for r in list(lo) + [99, 100, 101, 102]}
    rsa = {100: 0.55}
    ss = {r: "C" for r in range(96, 105)}  # 9-aa host loop around residue 100 (>= MIN_LOOP_LEN)
    feat = {r: 25.0 for r in list(lo) + [99, 100, 101, 102]}
    sig = {
        "plddt": plddt, "topology": topo, "rsa": rsa, "ss": ss,
        "feature_dist": feat, "gap_freq": {}, "conservation": {}, "sequence": "A" * 200,
    }
    sites = derive_deterministic_sites("X", "Q0", signals=sig)
    paths = {s["det_path"] for s in sites}
    assert paths == {"disorder", "surface_loop"}
    residues = {s["insert_after_residue"] for s in sites}
    assert 100 in residues                       # the surface-loop nomination
    assert any(50 <= r <= 55 for r in residues)  # the disorder nomination
    # every site_id is unique (paths are namespaced)
    assert len({s["site_id"] for s in sites}) == len(sites)


def test_select_representatives_suppresses_adjacent_and_caps():
    from accessible_surfaceome.tag_sites.run import select_representatives
    # rank-ordered (best first): a dense run 100..109 plus a far site at 200
    ranked = [{"insert_after_residue": r} for r in range(100, 110)] + [{"insert_after_residue": 200}]
    kept = select_representatives(ranked, min_gap=8, max_sites=20)
    res = [s["insert_after_residue"] for s in kept]
    assert res == [100, 108, 200]        # NMS keeps best-ranked, ≥8 apart
    # cap respected
    assert len(select_representatives(ranked, min_gap=1, max_sites=3)) == 3
