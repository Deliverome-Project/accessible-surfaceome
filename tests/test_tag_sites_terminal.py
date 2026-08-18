"""Terminal + snorkel deterministic gate (pure-topology, no structure)."""
from accessible_surfaceome.tag_sites.run import derive_deterministic_sites
from accessible_surfaceome.tag_sites.terminal import terminal_candidates


def _sig(seq, topo, plddt=None):
    return {"sequence": seq, "topology": topo, "plddt": plddt or {}}


def test_ecto_n_and_intracellular_c_gives_nterm_and_snorkel():
    out = terminal_candidates(_sig("A" * 10, {1: "O", 10: "I"}), gene_symbol="X", uniprot_acc="Q0")
    by = {s["site_kind"]: s for s in out}
    assert set(by) == {"terminal_n", "terminal_c"}
    assert by["terminal_n"]["det_path"] == "terminal"
    assert by["terminal_n"]["insert_after_residue"] is None  # junction before residue 1
    assert by["terminal_n"]["extracellular"] is True
    # the intracellular C-terminus becomes a C-terminal SNORKEL
    assert by["terminal_c"]["det_path"] == "snorkel"
    assert by["terminal_c"]["insert_after_residue"] == 10
    assert by["terminal_c"]["extracellular"] is False
    assert by["terminal_c"]["residue_label"] == "A10"


def test_ecto_c_gives_direct_cterm_no_snorkel():
    out = terminal_candidates(_sig("A" * 10, {1: "I", 10: "O"}), gene_symbol="X", uniprot_acc="Q0")
    assert [s["site_kind"] for s in out] == ["terminal_c"]
    assert out[0]["det_path"] == "terminal"  # direct, not snorkel
    assert out[0]["extracellular"] is True


def test_both_termini_extracellular_no_snorkel():
    out = terminal_candidates(_sig("A" * 10, {1: "O", 10: "O"}), gene_symbol="X", uniprot_acc="Q0")
    paths = {s["det_path"] for s in out}
    kinds = {s["site_kind"] for s in out}
    assert paths == {"terminal"} and kinds == {"terminal_n", "terminal_c"}  # no snorkel


def test_unknown_cterm_topology_emits_no_snorkel():
    # sparse topology (C-term residue absent) -> we do NOT fabricate a snorkel.
    out = terminal_candidates(_sig("A" * 10, {1: "O"}), gene_symbol="X", uniprot_acc="Q0")
    assert [s["site_kind"] for s in out] == ["terminal_n"]


def test_run_orders_terminals_around_internal():
    # ecto N-term, an internal surface-loop site at 100, intracellular C-term.
    seq = "A" * 200
    topo = {r: "O" for r in [1, 99, 100, 101, 102]}
    topo[200] = "I"
    sig = {
        "plddt": {100: 95.0}, "topology": topo, "rsa": {100: 0.55}, "ss": {100: "C"},
        "feature_dist": {r: 25.0 for r in [99, 100, 101, 102]},
        "gap_freq": {}, "conservation": {}, "sequence": seq,
    }
    sites = derive_deterministic_sites("X", "Q0", signals=sig)
    assert sites[0]["site_kind"] == "terminal_n"          # N-term first
    assert sites[-1]["det_path"] == "snorkel"             # C-term snorkel last
    assert any(s["det_path"] == "surface_loop" for s in sites)  # internal preserved
