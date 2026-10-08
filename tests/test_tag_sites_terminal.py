"""Terminal + snorkel deterministic gate (pure-topology, no structure)."""
from accessible_surfaceome.tag_sites.run import (
    TERMINUS_MIN_DIST_A,
    _drop_near_terminus,
    derive_deterministic_sites,
)
from accessible_surfaceome.tag_sites.terminal import terminal_candidates


def _sig(seq, topo, plddt=None):
    return {"sequence": seq, "topology": topo, "plddt": plddt or {}}


def test_ecto_n_and_intracellular_c_gives_nterm_only_no_snorkel():
    # N-terminus IS extracellular -> the C-terminal snorkel is NOT emitted: a real
    # accessible terminus is always preferred over a snorkel fallback.
    out = terminal_candidates(_sig("A" * 10, {1: "O", 10: "I"}), gene_symbol="X", uniprot_acc="Q0")
    assert [s["site_kind"] for s in out] == ["terminal_n"]
    assert out[0]["det_path"] == "terminal"
    assert out[0]["insert_after_residue"] is None  # junction before residue 1
    assert out[0]["extracellular"] is True
    assert not any(s["det_path"] == "snorkel" for s in out)


def test_signal_peptide_gives_mature_nterm_no_snorkel():
    # EGFR-like: leading signal-peptide run ('S'), then extracellular ('O'), with an
    # intracellular C-terminus. The MATURE N-terminus (after cleavage) is the tag
    # site; because it is extracellular, no snorkel is emitted.
    topo = {i: "S" for i in range(1, 25)}          # signal peptide 1-24
    topo.update({i: "O" for i in range(25, 100)})  # extracellular ectodomain
    topo[100] = "I"                                # intracellular C-terminus
    seq = "".join("ACDEFGHIKLMNPQRSTVWY"[i % 20] for i in range(100))
    out = terminal_candidates(_sig(seq, topo), gene_symbol="X", uniprot_acc="Q0")
    assert [s["site_kind"] for s in out] == ["terminal_n"]
    n = out[0]
    assert n["det_path"] == "terminal"
    assert n["insert_after_residue"] == 24          # tag AFTER the cleavage site
    assert n["residue_before"] == seq[23]           # last signal residue
    assert n["residue_after"] == seq[24]            # first mature residue
    assert n["extracellular"] is True
    assert not any(s["det_path"] == "snorkel" for s in out)


def test_ecto_c_gives_direct_cterm_no_snorkel():
    out = terminal_candidates(_sig("A" * 10, {1: "I", 10: "O"}), gene_symbol="X", uniprot_acc="Q0")
    assert [s["site_kind"] for s in out] == ["terminal_c"]
    assert out[0]["det_path"] == "terminal"  # direct, not snorkel
    assert out[0]["extracellular"] is True


def test_both_termini_intracellular_gives_snorkel_fallback():
    # Neither terminus extracellular (and no signal peptide) -> the C-terminal
    # snorkel is the genuine last-resort fallback.
    out = terminal_candidates(_sig("A" * 10, {1: "I", 10: "I"}), gene_symbol="X", uniprot_acc="Q0")
    assert [s["site_kind"] for s in out] == ["terminal_c"]
    assert out[0]["det_path"] == "snorkel"
    assert out[0]["insert_after_residue"] == 10
    assert out[0]["extracellular"] is False
    assert out[0]["residue_label"] == "A10"


def test_both_termini_extracellular_no_snorkel():
    out = terminal_candidates(_sig("A" * 10, {1: "O", 10: "O"}), gene_symbol="X", uniprot_acc="Q0")
    paths = {s["det_path"] for s in out}
    kinds = {s["site_kind"] for s in out}
    assert paths == {"terminal"} and kinds == {"terminal_n", "terminal_c"}  # no snorkel


def test_unknown_cterm_topology_emits_no_snorkel():
    # sparse topology (C-term residue absent) -> we do NOT fabricate a snorkel.
    out = terminal_candidates(_sig("A" * 10, {1: "O"}), gene_symbol="X", uniprot_acc="Q0")
    assert [s["site_kind"] for s in out] == ["terminal_n"]


def test_run_orders_nterm_before_internal_no_snorkel_when_nterm_ec():
    # ecto N-term, an internal surface-loop site at 100, intracellular C-term.
    # N-term is EC, so no snorkel; terminal_n leads, internal preserved.
    seq = "A" * 200
    topo = {r: "O" for r in [1, 99, 100, 101, 102]}
    topo[200] = "I"
    sig = {
        "plddt": {100: 95.0}, "topology": topo, "rsa": {100: 0.55},
        "ss": {r: "C" for r in range(96, 105)},  # 9-aa host loop (>= MIN_LOOP_LEN)
        "feature_dist": {r: 25.0 for r in range(96, 105)},
        "gap_freq": {}, "conservation": {}, "sequence": seq,
    }
    sites = derive_deterministic_sites("X", "Q0", signals=sig)
    assert sites[0]["site_kind"] == "terminal_n"                 # N-term first
    assert any(s["det_path"] == "surface_loop" for s in sites)  # internal preserved
    assert not any(s["det_path"] == "snorkel" for s in sites)   # N-term EC -> no snorkel


def test_terminus_filter_drops_internal_loops_hugging_an_ecto_terminus():
    # An internal loop spatially close (3D) to an extracellular terminus is
    # redundant with the terminal tag and is dropped; a distant one is kept.
    internal = [
        {"insert_after_residue": 100, "site_kind": "internal"},  # near the C-term
        {"insert_after_residue": 50, "site_kind": "internal"},   # far
    ]
    terms = [
        {"site_kind": "terminal_c", "det_path": "terminal", "insert_after_residue": 105},
    ]
    ca = {
        105: (0.0, 0.0, 0.0),                     # C-terminus anchor
        100: (0.0, 0.0, TERMINUS_MIN_DIST_A - 5),  # ~10 A from the terminus -> drop
        50: (0.0, 0.0, TERMINUS_MIN_DIST_A + 20),  # far -> keep
    }
    kept = _drop_near_terminus(internal, terms, {"ca": ca})
    assert [s["insert_after_residue"] for s in kept] == [50]


def test_terminus_filter_ignores_snorkel_and_missing_ca():
    internal = [{"insert_after_residue": 100, "site_kind": "internal"}]
    # a snorkel is intracellular (det_path 'snorkel') -> NOT a surface terminus,
    # so it never triggers the proximity drop.
    snork = [{"site_kind": "terminal_c", "det_path": "snorkel", "insert_after_residue": 105}]
    ca = {105: (0.0, 0.0, 0.0), 100: (0.0, 0.0, 1.0)}  # 1 A apart, but snorkel -> keep
    assert _drop_near_terminus(internal, snork, {"ca": ca}) == internal
    # no CA coords (unit-test signals) -> no-op, never drops.
    terms = [{"site_kind": "terminal_c", "det_path": "terminal", "insert_after_residue": 105}]
    assert _drop_near_terminus(internal, terms, {}) == internal


def test_run_orders_snorkel_last_when_no_ecto_terminus():
    # Both termini intracellular -> snorkel is the terminal fallback, ordered last.
    seq = "A" * 200
    topo = {r: "O" for r in [99, 100, 101, 102]}
    topo[1] = "I"
    topo[200] = "I"
    sig = {
        "plddt": {100: 95.0}, "topology": topo, "rsa": {100: 0.55},
        "ss": {r: "C" for r in range(96, 105)},  # 9-aa host loop (>= MIN_LOOP_LEN)
        "feature_dist": {r: 25.0 for r in range(96, 105)},
        "gap_freq": {}, "conservation": {}, "sequence": seq,
    }
    sites = derive_deterministic_sites("X", "Q0", signals=sig)
    assert sites[-1]["det_path"] == "snorkel"                    # snorkel last
    assert any(s["det_path"] == "surface_loop" for s in sites)  # internal preserved
    assert not any(s["site_kind"] == "terminal_n" for s in sites)  # no ecto N-term


# --- junction projection across numbering frames -------------------------------- #

from accessible_surfaceome.tag_sites.tedman import project_junction  # noqa: E402


def test_same_sequence_projects_unchanged():
    s = "MDLGKPMKSVLVVALLVIFQ"
    p = project_junction(s, s, 10)
    assert p.junction == 10 and p.offset == 0 and p.exact


def test_an_n_terminal_truncation_shifts_the_frame():
    # the real CCR7 case: the construct transcript lacks the canonical first 6 residues,
    # so its junction 23 is canonical residue 29. Comparing the raw integers made this
    # look like a signal-peptide disagreement.
    canonical = "MDLGKP" + "MKSVLVVALLVIFQVCLCQDEVTDDYIGDNTTVDYTLFESLCSKKD"
    construct = "MKSVLVVALLVIFQVCLCQDEVTDDYIGDNTTVDYTLFESLCSKKD"
    p = project_junction(construct, canonical, 23)
    assert p.junction == 29 and p.offset == 6 and not p.exact
    assert "offset +6" in p.note


def test_an_internal_insertion_shifts_only_downstream_positions():
    head = "ACDEFGHIKLMNPQRSTVWY"      # 20 aa, long enough to anchor
    tail = "WVTSRQPNMLKIHGFEDCAY"
    source = head + tail
    target = head + "CCCCCCCC" + tail   # 8 residues inserted between them
    assert project_junction(source, target, 10).junction == 10   # upstream: unchanged
    assert project_junction(source, target, 30).junction == 38   # downstream: +8


def test_a_junction_with_no_counterpart_is_not_guessed():
    p = project_junction("AAAAXXXX", "AAAA", 7)
    assert p.junction is None
    assert "do not share" in p.note


def test_identity_is_reported_so_a_bad_match_is_visible():
    p = project_junction("AAAACCCC", "AAAATTTT", 2)
    assert p.identity == 0.5


def test_a_short_coincidental_match_does_not_carry_a_coordinate():
    # the GABBR1 failure: the junction residue matches by chance while the surrounding
    # sequence does not, and a two-residue block mapped it 122 residues away.
    source = "QQQQQQQQQQHZZZZZZZZZZ"
    target = "WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWHYYYYYYYYYY"
    p = project_junction(source, target, 11)
    assert p.junction is None


def test_a_long_block_with_mismatched_flanks_is_refused():
    shared = "ACDEFGHIKLMNPQRSTVWY" * 2       # 40 identical residues
    source = "AAAA" + shared
    target = "BBBBBBBB" + shared
    # inside the block the flanks agree, so this one projects
    assert project_junction(source, target, 20).junction == 24
    # a junction in the non-shared head does not
    assert project_junction(source, target, 2).junction is None
