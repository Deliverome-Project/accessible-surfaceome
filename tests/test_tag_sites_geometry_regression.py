"""Regression against the sites the agent actually shipped for TMEM123 (Q8N131).

Three of the four published geometry defects are on this one gene, and all three
trace to the same root cause: the synthesis stage was handed a bare run-length
topology string and mis-counted the 26-residue signal peptide as 18, shifting
every boundary it derived. The real published output was:

    Q18  terminal_n  -- inside the signal peptide; the tag is cleaved off
    K155 internal    -- residue 155 is H, not K; the prose window pins 160
    I208 terminal_c  -- the C-terminal tail is cytoplasmic, not displayed

Sequence and topology are pinned verbatim from the public API record so this
runs offline.
"""
from accessible_surfaceome.agents.tag_site.geometry import apply_geometry_pass
from accessible_surfaceome.agents.tag_site.prompt import format_topology_landmarks
from accessible_surfaceome.agents.tag_site.schema import TagSiteProposal

SEQ = (
    "MGLGARGAWAALLLGTLQVLALLGAAHESAAMAASANIENSGLPHNSSANSTETLQHVPSDHTNETSNSTVKPPTSVAS"
    "DSSNTTVTTMKPTAASNTTTPGMVSTNMTSTTLKSTPKTTSVSQNTSQISTSTMTVTHNSSVTSAASSVTITTTMHSEA"
    "KKGSKFDTGSFVGGIVLTLGVLSILYIGCKMYYSRRGIRYRTIDEHDAII"
)
TOPO = "S" * 26 + "O" * 142 + "M" * 22 + "I" * 18
SP_END = 26  # UniProt Signal 1-26; DeepTMHMM agrees for this gene


def _shipped(**kw) -> TagSiteProposal:
    """A TagSiteProposal with the boilerplate filled in.

    Built with explicit kwargs (not a dict splat) so the field types survive:
    ``TagSiteProposal(**some_dict)`` collapses every value to ``int | str``."""
    return TagSiteProposal(
        rank=1, site_type="internal", insert_after_residue=155,
        residue_before="K", residue_after="G", topology_state="extracellular",
        tag_type="HA", evidence_type="published tag insertion at this exact site",
        position_evidence="inferred", evidence_detail="x",
        functional_or_expression_impact_measured="NOT MEASURED",
        rationale="", confidence="medium",
    ).model_copy(update=kw)


def _pass(sites):
    return apply_geometry_pass(sites, sequence=SEQ, topology=TOPO, sp_end=SP_END)


def test_fixture_matches_the_published_record():
    assert len(SEQ) == len(TOPO) == 208
    assert SEQ[154] == "H"          # the model claimed K155
    assert SEQ[154:166] == "HSEAKKGSKFDT"


def test_q18_is_repaired_to_the_real_cleavage_site():
    """Published as Q18 — eight residues inside the signal peptide."""
    s = _shipped(site_type="terminal_n", insert_after_residue=18,
                 residue_before="Q", residue_after="V")
    kept, rejected = _pass([s])
    assert not rejected
    assert kept[0].insert_after_residue == 26
    assert kept[0].residue_label == "A26"     # matches the deterministic path
    assert kept[0].position_repaired is True


def test_k155_is_repaired_to_the_junction_its_own_prose_pins():
    """Published as K155 with the correct window quoted in the rationale."""
    s = _shipped(
        insert_after_residue=155, residue_before="K", residue_after="G",
        rationale="The sequence context around position 155 (HSEAKK|GSKFDT) "
                  "represents a transition into a less-glycosylated linker.",
    )
    kept, rejected = _pass([s])
    assert not rejected
    assert kept[0].insert_after_residue == 160
    assert kept[0].residue_label == "K160"    # a site the deterministic path also finds
    assert kept[0].position_repaired is True


def test_i208_is_rejected_as_a_cytoplasmic_terminus():
    """Published as terminal_c on a tail that is not surface-displayed."""
    s = _shipped(site_type="terminal_c", insert_after_residue=208,
                 residue_before="I", residue_after="")
    kept, rejected = _pass([s])
    assert not kept
    assert "intracellular" in rejected[0][1]


def test_landmarks_state_the_boundaries_the_model_mis_derived():
    """The prevention half. From the raw string the model reported 'signal
    peptide 1-18 (18 consecutive S residues), ecto 19-170, TM 171-192'. Every
    one of those was wrong; the landmarks hand it the real spans instead."""
    out = format_topology_landmarks(TOPO, sp_end=SP_END)
    assert "SIGNAL PEPTIDE: 1-26" in out
    assert "EXTRACELLULAR: 27-168" in out
    assert "TRANSMEMBRANE: 169-190" in out
    assert "INTRACELLULAR: 191-208" in out
    assert "MATURE N-TERMINUS: 27" in out
    for wrong in ("1-18", "19-170", "171-192"):
        assert wrong not in out
