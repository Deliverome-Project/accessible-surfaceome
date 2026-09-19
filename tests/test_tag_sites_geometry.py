"""Geometry verification + repair for literature tag-site proposals.

Fixture mirrors the real TMEM123 failure: a signal peptide the model
miscounted, and an internal site whose prose window pins a junction the
model's integer missed.
"""
from accessible_surfaceome.agents.tag_site.geometry import (
    check_residues,
    junction_from_prose,
    apply_geometry_pass,
    repair_proposal,
)
from accessible_surfaceome.agents.tag_site.schema import (
    TagSiteProposal,
)

#            1234567890A BCDEFGHIJKL MNOPQRSTUVW
SEQ = "MLLLLLLLLLA" + "HSEAKKGSKFDT" + "PPPPPPPP" + "VVVVVVVVVVVVVVVVVVVVVV" + "CCCCCCCC"
TOPO = "SSSSSSSSSSS" + "OOOOOOOOOOOO" + "OOOOOOOO" + "MMMMMMMMMMMMMMMMMMMMMM" + "IIIIIIII"
# SP 1-11 | extracellular 12-31 | TM 32-53 | intracellular 54-61
# HSEAKK = 12-17, GSKFDT = 18-23


def test_check_residues_accepts_a_matching_junction():
    assert check_residues(sequence=SEQ, residue=17, before="K", after="G") is None


def test_check_residues_reports_a_mismatched_residue_before():
    reason = check_residues(sequence=SEQ, residue=12, before="K", after="S")
    assert reason is not None
    assert "K12" in reason and "H12" in reason


def test_junction_from_prose_repins_a_pipe_delimited_window():
    """The real TMEM123 K155 defect: the model quoted the correct sequence
    window but wrote the window's START index instead of its junction."""
    prose = "The sequence context around position 12 (HSEAKK|GSKFDT) is a linker."
    assert junction_from_prose(prose, SEQ) == 17


def test_junction_from_prose_returns_none_without_a_window():
    assert junction_from_prose("near the juxtamembrane region, ranked low", SEQ) is None


def test_junction_from_prose_refuses_an_ambiguous_window():
    """A window occurring more than once cannot pin a junction."""
    repeated = "AAAACCCC" + "AAAACCCC"
    assert junction_from_prose("context (AAAA|CCCC) here", repeated) is None


def _proposal(**kw) -> TagSiteProposal:
    """A TagSiteProposal with the boilerplate filled in.

    Built with explicit kwargs (not a dict splat) so the field types survive:
    ``TagSiteProposal(**some_dict)`` collapses every value to ``int | str``."""
    return TagSiteProposal(
        rank=1, site_type="internal", insert_after_residue=12,
        residue_before="H", residue_after="S", topology_state="extracellular",
        tag_type="HA", evidence_type="published tag insertion at this exact site",
        position_evidence="validated", evidence_detail="x",
        functional_or_expression_impact_measured="NOT MEASURED",
        rationale="", confidence="medium",
    ).model_copy(update=kw)


def test_repair_snaps_a_terminal_n_to_the_signal_peptide_cleavage_site():
    """The real TMEM123 Q18 defect: the model miscounted the signal-peptide run,
    so its 'mature N-terminus' landed inside the peptide that gets cleaved."""
    s = _proposal(site_type="terminal_n", insert_after_residue=8,
                  residue_before="L", residue_after="L")
    assert repair_proposal(s, sequence=SEQ, sp_end=11) == "snap_signal_peptide"
    assert s.insert_after_residue == 11
    assert s.residue_before == "A" and s.residue_after == "H"
    assert s.residue_label == "A11"


def test_repair_repins_a_mismatched_site_from_its_prose_window():
    s = _proposal(insert_after_residue=12, residue_before="K", residue_after="G",
                  rationale="context (HSEAKK|GSKFDT) chosen for the linker")
    assert repair_proposal(s, sequence=SEQ, sp_end=11) == "prose_window"
    assert s.insert_after_residue == 17
    assert s.residue_before == "K" and s.residue_after == "G"


def test_repair_refuses_a_mismatched_site_with_no_recoverable_window():
    """The real ERBB2 V643 defect: a structurally-guessed position with nothing
    in the prose to re-pin it against. Unrepairable, and must stay that way."""
    s = _proposal(insert_after_residue=12, residue_before="V", residue_after="V",
                  rationale="near the juxtamembrane region; ranked low")
    assert repair_proposal(s, sequence=SEQ, sp_end=11) is None
    assert s.insert_after_residue == 12  # untouched


def test_repair_leaves_an_already_correct_site_alone():
    s = _proposal(insert_after_residue=17, residue_before="K", residue_after="G")
    assert repair_proposal(s, sequence=SEQ, sp_end=11) is None
    assert s.insert_after_residue == 17


def test_geometry_pass_keeps_a_verified_site_unflagged():
    kept, rejected = apply_geometry_pass(
        [_proposal(insert_after_residue=17, residue_before="K", residue_after="G")],
        sequence=SEQ, topology=TOPO, sp_end=11)
    assert len(kept) == 1 and not rejected
    assert kept[0].position_repaired is False


def test_geometry_pass_keeps_and_flags_a_repaired_site():
    kept, rejected = apply_geometry_pass(
        [_proposal(insert_after_residue=12, residue_before="K", residue_after="G",
                   rationale="context (HSEAKK|GSKFDT) linker")],
        sequence=SEQ, topology=TOPO, sp_end=11)
    assert len(kept) == 1 and not rejected
    assert kept[0].insert_after_residue == 17
    assert kept[0].position_repaired is True


def test_geometry_pass_rejects_an_unrepairable_residue_mismatch():
    kept, rejected = apply_geometry_pass(
        [_proposal(insert_after_residue=12, residue_before="V", residue_after="V",
                   rationale="near the juxtamembrane region")],
        sequence=SEQ, topology=TOPO, sp_end=11)
    assert not kept and len(rejected) == 1
    assert "V12" in rejected[0][1] and "H12" in rejected[0][1]


def test_geometry_pass_rejects_a_site_the_topology_gate_fails():
    """An internal site in the cytoplasmic tail — correct residues, wrong face."""
    kept, rejected = apply_geometry_pass(
        [_proposal(insert_after_residue=55, residue_before="C", residue_after="C")],
        sequence=SEQ, topology=TOPO, sp_end=11)
    assert not kept and len(rejected) == 1
    assert "intracellular" in rejected[0][1]


def test_geometry_pass_repairs_then_regates():
    """A repair must not smuggle a site past the topology gate: snap the
    terminal_n to the cleavage site, THEN check the mature terminus."""
    cyto_nterm = "I" * 11 + TOPO[11:]
    kept, rejected = apply_geometry_pass(
        [_proposal(site_type="terminal_n", insert_after_residue=8,
                   residue_before="L", residue_after="L")],
        sequence=SEQ, topology=cyto_nterm, sp_end=0)
    assert not kept and len(rejected) == 1
