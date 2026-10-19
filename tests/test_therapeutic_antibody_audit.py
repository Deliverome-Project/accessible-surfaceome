"""Guard therapeutic identity, native numbering and constant-domain exclusions."""

import runpy
import sys
from pathlib import Path
from unittest.mock import patch

AUDIT = Path(__file__).resolve().parents[1] / "scripts/audit"
with patch.object(sys, "path", [str(AUDIT), *sys.path]):
    module = runpy.run_path(str(AUDIT / "audit_therapeutic_antibodies.py"))


def test_exact_structure_matches_keep_chain_pair_and_arm():
    row = dict(Therapeutic="Example", HeavySequence="AAAA", LightSequence="CCCC")
    row.update(
        {
            "HeavySequence(ifbispec)": "DDDD",
            "LightSequence(ifbispec)": "na",
            "100% SI Structure": "1abc:HL:AB;2abc:C",
            "99% SI Structure": "3abc:HL",
        }
    )
    structures, sequences = module["therapeutic_lookup"]([row])
    assert structures["1abc", "H", "L"] == {("Example", 0)}
    assert structures["2abc", "C", ""] == {("Example", 1)}
    assert ("3abc", "H", "L") not in structures
    assert sequences["DDDD", ""] == {("Example", 1)}


def test_antibody_constant_domain_atoms_are_removed():
    cif = {
        "_entity_poly.pdbx_strand_id": ["H", "L", "A"],
        "_entity_poly.pdbx_seq_one_letter_code_can": ["VVVCCCC", "WWWCCCC", "TARGET"],
        "_atom_site.auth_asym_id": ["H", "H", "L", "L", "A"],
        "_atom_site.label_seq_id": ["1", "4", "2", "5", "1"],
    }
    row = dict(Hchain="H", Lchain="L", VH="VVV", VL="WWW", target_chain="A")
    filtered = module["variable_only_cif"](cif, row)
    assert filtered["_atom_site.auth_asym_id"] == ["H", "L", "A"]
    assert filtered["_atom_site.label_seq_id"] == ["1", "2", "1"]


def test_aacdb_dropped_insertion_codes_cannot_be_guessed():
    rows = [dict(antigen="A:ALA10", distance="4.0")]
    assert module["aacdb_positions"](rows, "A", {("A", "10"): 1}, "A") == [1]
    assert (
        module["aacdb_positions"](rows, "A", {("A", "10"): 1, ("A", "10A"): 2}, "AA")
        == []
    )
    assert module["aacdb_positions"](rows, "A", {("A", "10"): 1}, "G") == []


def test_aacdb_distance_matches_five_angstrom_audit_cutoff():
    rows = [dict(antigen="A:ALA10", distance="5.1")]
    assert module["aacdb_positions"](rows, "A", {("A", "10"): 1}, "A") == []


def test_sabdab_split_domains_resolve_to_original_chain_with_exact_sequence():
    cif = {
        "_entity_poly.pdbx_strand_id": ["A", "T"],
        "_entity_poly.pdbx_seq_one_letter_code_can": ["VVVGGWWW", "TARGET"],
        "_atom_site.auth_asym_id": ["A", "A", "A", "T"],
        "_atom_site.label_seq_id": ["1", "4", "6", "1"],
    }
    row = dict(
        Hchain="A1",
        Lchain="A2",
        VH="VVV",
        VL="WWW",
        target_chain="T",
        chainsharing_construct="SCFV",
    )
    filtered = module["variable_only_cif"](cif, row)
    assert filtered["_atom_site.auth_asym_id"] == ["A1", "A2", "T"]
    assert filtered["_atom_site.label_seq_id"] == ["1", "6", "1"]
    row["VH"] = "VVX"
    assert module["variable_only_cif"](cif, row) is None
