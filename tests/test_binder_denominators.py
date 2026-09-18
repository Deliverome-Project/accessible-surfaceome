import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/audit"))
from audit_binder_denominators import endpoint, location_class, resolve_component


def test_proxy_enzyme_is_not_the_ligand():
    complexes = {"Adenosine_byENZYME": {"other_desc": ""}}
    assert endpoint("Adenosine_byENZYME", complexes) == ("chemical", "Adenosine", ())


def test_complex_does_not_become_a_direct_protein_partner():
    complexes = {
        "receptor_complex": {
            "other_desc": "",
            **{
                f"uniprot_{i}": a
                for i, a in enumerate(["Q00001", "Q00002", "", "", ""], 1)
            },
        }
    }
    assert endpoint("receptor_complex", complexes) == (
        "complex",
        "receptor_complex",
        ("Q00001", "Q00002"),
    )


def test_approved_symbol_beats_colliding_synonyms_and_case():
    approved = {"PDCD1": "HGNC:8760", "KLK2": "HGNC:6363", "HK2": "HGNC:4923"}
    aliases = {"PD1": {"HGNC:8760", "HGNC:11138"}}
    assert resolve_component("PDCD1/PD1", approved, aliases) == (
        {"HGNC:8760"},
        "approved_symbol",
    )
    assert resolve_component("KLK2/hK2", approved, aliases) == (
        {"HGNC:6363"},
        "approved_symbol",
    )
    assert resolve_component("PD1", approved, aliases)[1] == "ambiguous_alias"


def test_species_and_complex_targets_are_not_direct_human_targets():
    approved = {"PDCD1": "HGNC:8760", "ITGB3": "HGNC:6156"}
    aliases = {"CD61": {"HGNC:6156"}}
    assert (
        resolve_component("PDCD1 (Canine)", approved, aliases)[1] == "nonhuman_target"
    )
    assert (
        resolve_component("ITGAVB3/CD61/VNR", approved, aliases)[1]
        == "complex_target_not_direct_subunit"
    )
    assert (
        resolve_component("CD3", approved, aliases)[1]
        == "complex_target_not_direct_subunit"
    )


def protein(*locations, molecule=None, features=()):
    return {
        "comments": [
            {
                "commentType": "SUBCELLULAR LOCATION",
                "molecule": molecule,
                "subcellularLocations": [{"location": {"value": x}} for x in locations],
            }
        ],
        "features": features,
    }


def test_location_is_gene_level_and_distinguishes_inference():
    assert location_class(protein("Lateral cell membrane")) == "membrane"
    assert (
        location_class(protein("Cell membrane", "Secreted", molecule="Isoform 1"))
        == "membrane_and_secreted"
    )
    assert (
        location_class(protein("Secreted", molecule="Mature peptide"))
        == "secreted_only"
    )
    assert location_class(protein("Nucleus")) == "other_or_uncertain"
    assert (
        location_class(protein("Endoplasmic reticulum membrane"))
        == "other_or_uncertain"
    )
    assert (
        location_class(
            protein(
                "Membrane",
                features=[
                    {"type": "Topological domain", "description": "Extracellular"}
                ],
            )
        )
        == "membrane_inferred"
    )
