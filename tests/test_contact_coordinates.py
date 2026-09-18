"""Synthetic deposited-coordinate fixtures; these tests never access the network."""

import gzip
import importlib.util
import json
from pathlib import Path

import pytest

from accessible_surfaceome.binders.contact_coordinates import (
    sha256,
    validate_contacts,
    validate_reviewed_instance,
)

ACC = "P12345"


def cif(atoms):
    columns = "group_PDB type_symbol auth_comp_id auth_asym_id auth_seq_id pdbx_PDB_ins_code pdbx_PDB_model_num occupancy Cartn_x Cartn_y Cartn_z".split()
    return (
        "data_test\nloop_\n"
        + "\n".join("_atom_site." + c for c in columns)
        + "\n"
        + "\n".join(" ".join(map(str, a)) for a in atoms)
        + "\n#\n"
    ).encode()


def atom(
    chain="A",
    number="1",
    comp="ALA",
    x=0,
    element="C",
    occupancy=1,
    model=1,
    insertion="?",
    group="ATOM",
):
    return (group, element, comp, chain, number, insertion, model, occupancy, x, 0, 0)


def ligand(chain="L", number="100", x=0, **kwargs):
    return atom(chain=chain, number=number, comp="LIG", x=x, group="HETATM", **kwargs)


def sifts(rows):
    residues = []
    for chain, number, acc, pos in rows:
        residues.append(
            f'<residue><crossRefDb dbSource="PDB" dbChainId="{chain}" dbResNum="{number}"/><crossRefDb dbSource="UniProt" dbAccessionId="{acc}" dbResNum="{pos}"/></residue>'
        )
    return gzip.compress(
        (
            '<entry xmlns="http://www.ebi.ac.uk/pdbe/docs/sifts/eFamily.xsd">'
            + "".join(residues)
            + "</entry>"
        ).encode(),
        mtime=0,
    )


def run(atoms, rows=None, sequence="AAAA", **kwargs):
    return validate_contacts(
        cif(atoms),
        sifts(rows or [("A", "1", ACC, 1)]),
        uniprot_acc=ACC,
        canonical_sequence=sequence,
        ccd="LIG",
        **kwargs,
    )


def record(result, positions="1", instance=None):
    return {
        "uniprot_acc": ACC,
        "partner": "CCD:LIG",
        "ligand_instance": instance or ["L", "100"],
        "positions": positions,
        **{
            k: result[k]
            for k in ("coordinate_sha256", "sifts_sha256", "canonical_sequence_sha256")
        },
    }


def test_boundary_first_model_occupancy_and_heavy_atoms():
    atoms = [
        ligand(),
        atom(x=5),
        atom(number="2", x=5.00001),
        atom(number="3", x=1, element="H"),
        atom(number="4", x=1, element="D"),
        atom(number="5", x=1, occupancy=0),
        atom(number="6", x=1, occupancy=-1),
        atom(number="7", x=1, model=2),
    ]
    result = run(
        atoms, [("A", str(i), ACC, i) for i in range(1, 8)], sequence="AAAAAAA"
    )
    assert result["instances"][0]["positions"] == [1]
    assert validate_reviewed_instance(record(result), result) == []
    assert result["first_model"] == "1"


def test_ligand_filtering_and_positive_partial_occupancy():
    result = run(
        [
            ligand(x=100),
            ligand(x=0, element="H"),
            ligand(x=0, occupancy=0),
            ligand(x=0, model=2),
            atom(),
        ]
    )
    assert result["instances"][0]["positions"] == []
    assert run([ligand(occupancy=0.1), atom(occupancy=0.5)])["instances"][0][
        "positions"
    ] == [1]


def test_insertion_codes_multiple_target_chains_and_instances():
    result = run(
        [
            ligand(),
            ligand(chain="M", number="101", x=20),
            atom(number="10", insertion="A"),
            atom(chain="B", number="8", x=4),
            atom(chain="B", number="9", x=20),
        ],
        [("A", "10A", ACC, 2), ("B", "8", ACC, 3), ("B", "9", ACC, 4)],
    )
    first, second = result["instances"]
    assert first["positions"] == [2, 3]
    assert [(c["chain_id"], c["positions"]) for c in first["target_chains"]] == [
        ("A", [2]),
        ("B", [3]),
    ]
    assert first["target_chains"][0]["contact_residues"][0]["author_residue"] == "10A"
    assert second["positions"] == [4]


@pytest.mark.parametrize(
    "rows,comp,expected",
    [
        ([("A", "1", ACC, 0)], "ALA", "canonical_position_out_of_range"),
        ([("A", "1", ACC, 99)], "ALA", "canonical_position_out_of_range"),
        ([("A", "1", ACC, 1)], "GLY", "canonical_residue_mismatch"),
        ([("A", "1", ACC, 1)], "UNK", "canonical_residue_mismatch"),
        ([("A", "2", ACC, 1)], "ALA", "unmapped_contact_residue"),
    ],
)
def test_bad_contact_mappings_fail_closed(rows, comp, expected):
    result = run([ligand(), atom(comp=comp)], rows)
    assert result["instances"][0]["positions"] == []
    assert result["instances"][0]["mapping_issues"][0]["issue"] == expected
    assert "contact_mapping_issues" in validate_reviewed_instance(
        record(result), result
    )


def test_chimeric_chain_is_rejected_even_if_foreign_segment_is_distant():
    result = run(
        [ligand(), atom(), atom(number="2", x=100)],
        [("A", "1", ACC, 1), ("A", "2", "Q99999", 1)],
    )
    assert result["mapping_issues"][0]["issue"] == "mixed_chain_accessions"
    assert result["instances"][0]["positions"] == []
    assert "target_mapping_issues" in validate_reviewed_instance(record(result), result)


def test_duplicate_conflicting_mapping_and_exact_accession():
    result = run([ligand(), atom()], [("A", "1", ACC, 1), ("A", "1", ACC, 2)])
    assert result["mapping_issues"][0]["issue"] == "ambiguous_sifts_mapping"
    isoform = run([ligand(), atom()], [("A", "1", ACC + "-2", 1)])
    assert isoform["mapping_issues"][0]["issue"] == "target_accession_absent"
    assert isoform["instances"][0]["positions"] == []


def test_other_accession_in_separate_chain_does_not_contaminate_target():
    result = run(
        [ligand(), atom(), atom(chain="B")],
        [("A", "1", ACC, 1), ("B", "1", "Q99999", 2)],
    )
    assert result["mapping_issues"] == []
    assert result["instances"][0]["positions"] == [1]
    assert [c["chain_id"] for c in result["instances"][0]["target_chains"]] == ["A"]


@pytest.mark.parametrize(
    "field",
    [
        "expected_coordinate_sha256",
        "expected_sifts_sha256",
        "expected_canonical_sequence_sha256",
    ],
)
def test_pin_mismatches_rejected(field):
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        run([ligand(), atom()], **{field: "0" * 64})


def test_reviewed_acceptance_requires_instance_positions_and_cutoff():
    result = run([ligand(), atom()])
    assert "reviewed_positions_mismatch" in validate_reviewed_instance(
        record(result, "2"), result
    )
    assert "ligand_instance_missing_or_ambiguous" in validate_reviewed_instance(
        record(result, instance=["Z", "2"]), result
    )
    result["cutoff_angstrom"] = 6
    assert "review_requires_5_angstrom_cutoff" in validate_reviewed_instance(
        record(result), result
    )


def test_cli_offline_writes_sequence_pin_and_fails_changed_cache(tmp_path, monkeypatch):
    module_path = (
        Path(__file__).resolve().parents[1]
        / "scripts/audit/validate_reviewed_chemical_contacts.py"
    )
    spec = importlib.util.spec_from_file_location(
        "validate_reviewed_chemical_contacts", module_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        module.httpx, "get", lambda *a, **k: pytest.fail("Network access forbidden")
    )
    coordinate = cif([ligand(), atom()])
    mapping = sifts([("A", "1", ACC, 1)])
    (tmp_path / "1abc.cif").write_bytes(coordinate)
    (tmp_path / "1abc.xml.gz").write_bytes(mapping)
    seqdir = tmp_path / "sequences"
    seqdir.mkdir()
    (seqdir / "cache.json").write_text(
        json.dumps(
            {
                "data": {
                    "results": [
                        {"primaryAccession": ACC, "sequence": {"value": "AAAA"}}
                    ]
                }
            }
        )
    )
    reviewed = {
        "uniprot_acc": ACC,
        "pdb_id": "1abc",
        "partner": "CCD:LIG",
        "positions": "1",
        "ligand_instance": ["L", "100"],
        "coordinate_sha256": sha256(coordinate),
        "sifts_sha256": sha256(mapping),
    }
    review = tmp_path / "review.json"
    review.write_text(json.dumps({"records": [reviewed]}))
    output = tmp_path / "validation.json"
    args = [
        "--review",
        str(review),
        "--cache-dir",
        str(tmp_path),
        "--sequence-cache-dir",
        str(seqdir),
        "--output",
        str(output),
        "--offline",
    ]
    assert module.main(args) == 0
    result = json.loads(output.read_text())
    assert result["records"][0]["canonical_sequence_sha256"] == sha256(b"AAAA")
    (tmp_path / "1abc.cif").write_bytes(coordinate + b"# changed\n")
    assert module.main(args) == 1
    assert (
        "SHA256 mismatch" in json.loads(output.read_text())["records"][0]["failures"][0]
    )
    assert json.loads(review.read_text())["records"][0] == reviewed


def test_unmodeled_sifts_null_residues_do_not_collide_but_count_for_purity():
    rows = [("A", "1", ACC, 1), ("A", "null", ACC, 2), ("A", "null", ACC, 3)]
    result = run([ligand(), atom()], rows)
    assert result["mapping_issues"] == []
    assert result["instances"][0]["positions"] == [1]
    rows.append(("A", "null", "Q99999", 1))
    assert (
        run([ligand(), atom()], rows)["mapping_issues"][0]["issue"]
        == "mixed_chain_accessions"
    )


def test_modified_polymer_hetatm_contact_is_not_silently_ignored():
    data = cif([ligand(), atom(comp="MSE", group="HETATM")]).decode()
    data = data.replace(
        "_atom_site.Cartn_z\n", "_atom_site.Cartn_z\n_atom_site.label_seq_id\n"
    )
    lines = data.splitlines()
    lines = [
        line + (" 1" if " MSE " in line else " .")
        if line.startswith("HETATM")
        else line
        for line in lines
    ]
    result = validate_contacts(
        "\n".join(lines).encode(),
        sifts([("A", "1", ACC, 1)]),
        uniprot_acc=ACC,
        canonical_sequence="M",
        ccd="LIG",
    )
    assert (
        result["instances"][0]["mapping_issues"][0]["issue"]
        == "canonical_residue_mismatch"
    )


def test_reviewed_file_pins_are_mandatory():
    result = run([ligand(), atom()])
    reviewed = record(result)
    del reviewed["coordinate_sha256"]
    assert "coordinate_sha256_missing" in validate_reviewed_instance(reviewed, result)
