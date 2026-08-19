from accessible_surfaceome.agents.tag_site.normalize import (
    compartment_at, signal_peptide_end, topology_gate, apply_topology_gate,
)

# type-II (TFRC-like): N-term intracellular 1-67, TM 68-88, ectodomain 89-760
TYPE_II = "I" * 67 + "M" * 21 + "O" * 672
# type-I with signal peptide (ITGB1-like): SP 1-20, ecto 21-720, TM 721-743, cyto 744-798
TYPE_I_SP = "S" * 20 + "O" * 700 + "M" * 23 + "I" * 55


def _site(kind, res):
    return {"site_type": kind, "insert_after_residue": res}


def test_signal_peptide_and_compartment_helpers():
    assert signal_peptide_end(TYPE_I_SP) == 20
    assert signal_peptide_end(TYPE_II) == 0
    assert compartment_at(TYPE_II, 300) == "extracellular"
    assert compartment_at(TYPE_II, 1) == "intracellular"


def test_type_ii_rejects_terminal_n_keeps_internal_and_cterm():
    assert topology_gate(_site("terminal_n", None), TYPE_II)[0] is False   # N-term intracellular
    assert topology_gate(_site("internal", 300), TYPE_II)[0] is True       # ectodomain loop
    assert topology_gate(_site("terminal_c", 760), TYPE_II)[0] is True     # C-term extracellular


def test_signal_peptide_rules():
    assert topology_gate(_site("terminal_n", 10), TYPE_I_SP)[0] is False   # within SP -> cleaved
    assert topology_gate(_site("terminal_n", 21), TYPE_I_SP)[0] is True    # after SP, ecto
    assert topology_gate(_site("internal", 730), TYPE_I_SP)[0] is False    # in TM
    assert topology_gate(_site("internal", 760), TYPE_I_SP)[0] is False    # cytoplasmic


def test_apply_partitions_with_reasons():
    sites = [_site("internal", 300), _site("terminal_n", None)]
    kept, rejected = apply_topology_gate(sites, TYPE_II)
    assert len(kept) == 1 and len(rejected) == 1
    assert "intracellular" in rejected[0][1]
