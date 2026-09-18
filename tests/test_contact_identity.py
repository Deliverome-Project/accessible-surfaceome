"""Prevent alias collisions and unsupported construct equivalence."""

from accessible_surfaceome.binders.contact_constructs import (
    construct_fingerprint,
    equivalent_construct_groups,
)
from accessible_surfaceome.binders.contact_identity import (
    annotate_identities,
    contact_identity,
)


def site(**extra):
    return dict(
        source="AACDB",
        partner="VHH6",
        pdb="5fuc",
        positions=[10, 20],
        reference="https://www.rcsb.org/structure/5FUC",
        **extra,
    )


def test_reviewed_clone_alias_is_target_scoped():
    record = site(canonical_partner_label="VHH6", review_date="2026-09-18")
    assert contact_identity(record, "P08887") != contact_identity(record, "Q9NZQ7")
    assert contact_identity(record, "P08887") == contact_identity(
        dict(record, pdb="other", source="IEDB"), "P08887"
    )


def test_generic_peptide_never_becomes_a_global_ligand():
    record = dict(site(), partner="peptide")
    assert contact_identity(record, "P08887") != contact_identity(record, "Q9NZQ7")
    assert contact_identity(record, "P08887") != contact_identity(
        dict(record, pdb="8aok"), "P08887"
    )
    assert contact_identity(record, "P08887") != contact_identity(
        dict(record, positions=[30, 40]), "P08887"
    )


def test_ccd_identity_is_shared_without_using_display_names():
    record = dict(site(), partner="CCD:CLR", partner_label="Cholesterol")
    other = dict(record, partner_label="CHOLESTEROL", pdb="7tby")
    assert contact_identity(record, "P08887") == contact_identity(other, "O95477")


def test_ambiguous_display_names_are_disambiguated_without_changing_source():
    records = [
        dict(site(), partner="peptide"),
        dict(site(), partner="peptide", pdb="8aok"),
    ]
    annotate_identities({"P08887": {"sites": records}})
    assert records[0]["identity_display_label"] != records[1]["identity_display_label"]
    assert all(record["partner"] == "peptide" for record in records)


def test_construct_equivalence_requires_chemistry_and_mapping_not_footprint():
    record = dict(
        parent_accessions=["P01137"],
        monomers=["ALA", "GLY"],
        mapped_spans=[["P01137", 2, 3, 1, 2]],
        internal_covalent_links=[],
        chemistry_checked=True,
        unresolved_chemistry=False,
    )
    same = dict(record, pdb="other", positions=[900, 901])
    assert len(equivalent_construct_groups([record, same])) == 1
    for difference in [
        dict(monomers=["ALA", "MSE"]),
        dict(mapped_spans=[["P01137", 3, 4, 1, 2]]),
        dict(unresolved_chemistry=True),
        dict(chemistry_checked=False),
        dict(internal_covalent_links=["modified terminus"]),
    ]:
        assert construct_fingerprint(record) != construct_fingerprint(
            dict(record, **difference)
        )


def test_stable_parent_and_receptor_groups_do_not_claim_construct_identity():
    record = dict(site(), partner="P01133")
    assert contact_identity(record, "P00533")[1] == "protein_parent_group"
    record = dict(site(), source="IEDB", partner="123")
    assert contact_identity(record, "P00533") == contact_identity(
        dict(record, positions=[99]), "P00533"
    )
    assert contact_identity(record, "P00533")[1] == "source_receptor_group"


def test_source_clone_groups_stay_target_scoped():
    record = site()
    assert contact_identity(record, "P00533") == contact_identity(
        dict(record, pdb="9abc"), "P00533"
    )
    assert contact_identity(record, "P00533") != contact_identity(record, "Q9NZQ7")
