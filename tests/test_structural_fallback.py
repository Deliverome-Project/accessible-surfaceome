import importlib.util
import sys
from pathlib import Path

scripts = Path(__file__).resolve().parents[1] / "scripts/audit"
sys.path.insert(0, str(scripts))
spec = importlib.util.spec_from_file_location(
    "audit_structural_fallback", scripts / "audit_structural_fallback.py"
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def cif():
    return {
        "_atom_site.auth_asym_id": ["A", "B", "A"],
        "_atom_site.pdbx_PDB_model_num": ["1"] * 3,
        "_atom_site.group_PDB": ["ATOM"] * 3,
        "_atom_site.type_symbol": ["C"] * 3,
        "_atom_site.occupancy": ["1"] * 3,
        "_atom_site.pdbx_PDB_ins_code": [".", ".", "A"],
        "_atom_site.auth_seq_id": ["10", "1", "10"],
        "_atom_site.auth_comp_id": ["ALA", "GLY", "CYS"],
        "_atom_site.Cartn_x": ["0", "4", "20"],
        "_atom_site.Cartn_y": ["0"] * 3,
        "_atom_site.Cartn_z": ["0"] * 3,
    }


def test_contact_mapping_identity_and_insertion():
    mapping = {
        ("A", "10"): ("Q00001", 1),
        ("A", "10A"): ("Q00001", 2),
        ("B", "1"): ("Q00002", 1),
    }
    assert module.coordinate_contacts(cif(), "A", "B", mapping, "AC") == ([1], "mapped")
    assert module.coordinate_contacts(cif(), "A", "B", mapping, "AC", [0, 2, 1]) == (
        [1],
        "mapped",
    )
    assert (
        module.coordinate_contacts(cif(), "A", "B", mapping, "GC")[1]
        == "noncanonical_contact_residue"
    )
    del mapping["A", "10"]
    assert (
        module.coordinate_contacts(cif(), "A", "B", mapping, "AC")[1]
        == "unmapped_contact_residue"
    )


def test_unmapped_partner_tag_cannot_create_site():
    assert (
        module.coordinate_contacts(cif(), "A", "B", {("A", "10"): ("Q00001", 1)}, "A")[
            1
        ]
        == "no_contacts"
    )
