"""Regression checks for false site assignments and coordinate interpretation."""

import importlib.util
from pathlib import Path


def load_script(name):
    path = Path(__file__).resolve().parents[1] / "scripts/audit" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_contacts = load_script("audit_antibody_contacts")
contacts, residue_mapping = _contacts.contacts, _contacts.residue_mapping
_summary = load_script("summarize_binding_sites")
mapped_iedb_positions, pdb_sites, topology = (
    _summary.mapped_iedb_positions,
    _summary.pdb_sites,
    _summary.topology,
)


def test_sites_do_not_mix_structures_or_predicted_annotations():
    item = {
        "residues": [
            {
                "indexType": "UNIPROT",
                "startIndex": 10,
                "endIndex": 10,
                "interactingPDBEntries": [{"pdbId": "aaaa"}],
                "allPDBEntries": ["bbbb"],
            },
            {
                "indexType": "UNIPROT",
                "startIndex": 20,
                "endIndex": 20,
                "interactingPDBEntries": [{"pdbId": "bbbb"}],
            },
            {
                "indexType": "PDB",
                "startIndex": 30,
                "endIndex": 30,
                "interactingPDBEntries": [{"pdbId": "aaaa"}],
            },
        ]
    }
    assert pdb_sites(item) == {"aaaa": [10], "bbbb": [20]}


def test_epitope_mapping_rejects_repeats_mutations_and_foreign_numbering():
    assert mapped_iedb_positions({"linear_sequence": "ACD"}, "MACDE") == [2, 3, 4]
    assert mapped_iedb_positions({"linear_sequence": "ACD"}, "ACDACD") == []
    assert mapped_iedb_positions({"structure_description": "A2, D4"}, "MACDE") == [2, 4]
    assert mapped_iedb_positions({"structure_description": "A1, D3"}, "MACDE") == []
    assert mapped_iedb_positions({"structure_description": "A2, E4"}, "MACDE") == []


def test_partial_extracellular_site_is_not_wholly_extracellular():
    protein = {
        "features": [
            {
                "type": "Topological domain",
                "description": "Extracellular",
                "location": {"start": {"value": 1}, "end": {"value": 10}},
            }
        ]
    }
    assert topology([1, 10], protein) == "extracellular"
    assert topology([10, 11], protein) == "mixed:extracellular;unknown"
    assert topology([], protein) == "unmapped"


def test_sifts_mapping_preserves_insertions_and_target_identity():
    xml = b"""<entry xmlns="http://www.ebi.ac.uk/pdbe/docs/sifts/eFamily.xsd"><residue>
    <crossRefDb dbSource="PDB" dbChainId="A" dbResNum="12A"/>
    <crossRefDb dbSource="UniProt" dbAccessionId="P00001" dbResNum="20"/>
    </residue></entry>"""
    assert residue_mapping(xml, "P00001") == {("A", "12A"): 20}
    assert residue_mapping(xml, "P00002") == {}


def test_contacts_ignore_hydrogen_other_models_and_unmapped_atoms():
    cif = {
        "_atom_site.auth_asym_id": ["A", "A", "H", "H", "H"],
        "_atom_site.pdbx_PDB_model_num": ["1", "1", "1", "1", "2"],
        "_atom_site.type_symbol": ["C", "C", "C", "H", "C"],
        "_atom_site.group_PDB": ["ATOM"] * 5,
        "_atom_site.occupancy": ["1"] * 5,
        "_atom_site.Cartn_x": ["0", "10", "4.9", "10", "10"],
        "_atom_site.Cartn_y": ["0"] * 5,
        "_atom_site.Cartn_z": ["0"] * 5,
        "_atom_site.pdbx_PDB_ins_code": ["?"] * 5,
        "_atom_site.auth_seq_id": ["1", "2", "1", "2", "3"],
    }
    assert contacts(cif, "A", {"H"}, {("A", "1"): 20, ("A", "2"): 21}) == [20]
