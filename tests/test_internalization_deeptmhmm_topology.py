from accessible_surfaceome.agents.internalization.deeptmhmm_topology import (
    deeptmhmm_record,
    summarize_deeptmhmm_topology,
)


def _rec(**over):
    base = {
        "uniprot_accession": "P00533",
        "uniprot_accession_full": "P00533",
        "deeptmhmm_label": "TM",
        "has_signal_peptide": 1,
        "signal_peptide_length": 24,
        "tm_helix_count": 1,
        "beta_strand_count": 0,
        "n_terminal_orientation": "extracellular",
        "c_terminal_orientation": "cytoplasmic",
        "ecd_length_residues": 621,
        "icd_length_residues": 543,
        "sequence": "M" * 1210,
    }
    base.update(over)
    return base


def test_summarize_reports_ec_sidedness_and_lengths():
    out = summarize_deeptmhmm_topology(_rec())
    assert "N-terminus extracellular" in out
    assert "C-terminus cytoplasmic" in out
    assert "extracellular 621 aa" in out
    assert "cytoplasmic 543 aa" in out
    assert "signal peptide 24 aa" in out
    assert "1 TM" in out


def test_summarize_omits_absent_features():
    out = summarize_deeptmhmm_topology(
        _rec(has_signal_peptide=0, tm_helix_count=0, deeptmhmm_label="GLOB")
    )
    assert "signal peptide" not in out
    assert "TM helix" not in out
    assert "N-terminus extracellular" in out


def test_record_direct_hit_by_isoform_accession():
    index = {"P00533-2": _rec(uniprot_accession_full="P00533-2", ecd_length_residues=1)}
    rec = deeptmhmm_record("P00533-2", is_canonical=False, index=index)
    assert rec is not None and rec["ecd_length_residues"] == 1


def test_canonical_falls_back_to_base_accession():
    index = {"P00533": _rec()}
    rec = deeptmhmm_record("P00533-1", is_canonical=True, index=index)
    assert rec is not None and rec["uniprot_accession"] == "P00533"


def test_alt_isoform_does_not_borrow_canonical_topology():
    # Only the canonical record (base key) is present; an alt isoform must miss
    # rather than be mislabeled with the canonical's topology.
    index = {"P00533": _rec()}
    assert deeptmhmm_record("P00533-7", is_canonical=False, index=index) is None
