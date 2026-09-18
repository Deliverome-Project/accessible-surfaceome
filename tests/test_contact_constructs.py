"""Manual construct acceptance is exact-scoped, hash-pinned and non-destructive."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from accessible_surfaceome.binders.contact_constructs import (
    accepted_construct_updates,
    construct_fingerprint,
    equivalent_construct_groups,
    load_accepted_constructs,
)

ROOT = Path(__file__).resolve().parents[1]


def source_record(pdb):
    return {
        "target": "P12345",
        "partner": "Q12345",
        "pdb": pdb,
        "parent_accessions": ["Q12345"],
        "monomers": ["ALA", "CYS"],
        "mapped_spans": [["Q12345", 10, 11, 1, 2]],
        "internal_covalent_links": [],
        "chemistry_checked": True,
        "unresolved_chemistry": False,
        "status": "complete",
        "coordinate_sha256": "a" * 64,
        "mapping_sha256": "b" * 64,
    }


def snapshots(tmp_path):
    records = [source_record("1abc"), source_record("2abc")]
    raw = json.dumps({"records": records}).encode()
    suggestions = tmp_path / "suggestions.json"
    suggestions.write_bytes(raw)
    accepted = tmp_path / "accepted.json"
    acceptance = {
        "schema_version": 1,
        "suggestions_sha256": hashlib.sha256(raw).hexdigest(),
        "groups": [
            {
                "canonical_partner_label": "Reviewed two-residue construct",
                "construct_fingerprint": construct_fingerprint(records[0]),
                "identity_note": "Same deposited construct; preserve target context.",
                "members": [
                    {
                        k: r[k]
                        for k in (
                            "target",
                            "partner",
                            "pdb",
                            "coordinate_sha256",
                            "mapping_sha256",
                        )
                    }
                    for r in records
                ],
            }
        ],
    }
    accepted.write_text(json.dumps(acceptance))
    return accepted, suggestions


def rehash(accepted, suggestions):
    data = json.loads(accepted.read_text())
    data["suggestions_sha256"] = hashlib.sha256(suggestions.read_bytes()).hexdigest()
    accepted.write_text(json.dumps(data))


def test_exact_scope_returns_only_identity_updates_without_mutating_site(tmp_path):
    accepted, suggestions = snapshots(tmp_path)
    index = load_accepted_constructs(accepted, suggestions)
    site = {
        "partner": "Q12345",
        "pdb": "1abc",
        "positions": [42],
        "context": "non_extracellular:cytoplasmic",
        "category": "unclassified",
        "partner_label": "Old display label",
    }
    before = copy.deepcopy(site)
    updates = accepted_construct_updates(site, "P12345", index)
    assert set(updates) == {
        "canonical_partner_label",
        "construct_fingerprint",
        "identity_note",
    }
    assert site == before
    updates["identity_note"] = "Caller modified its copy"
    assert (
        index["P12345", "Q12345", "1abc"]["identity_note"] != updates["identity_note"]
    )
    for changed in (
        {"partner": "Other"},
        {"pdb": "3abc"},
        {"pdb": "1ABC"},
        {"partner": "123", "partner_label": "Q12345"},
    ):
        assert accepted_construct_updates({**site, **changed}, "P12345", index) == {}
    assert accepted_construct_updates(site, "Q99999", index) == {}


def test_suggestions_byte_hash_rejects_changed_snapshot(tmp_path):
    accepted, suggestions = snapshots(tmp_path)
    suggestions.write_bytes(suggestions.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        load_accepted_constructs(accepted, suggestions)


@pytest.mark.parametrize("field", ["coordinate_sha256", "mapping_sha256"])
def test_member_pins_still_reject_changes_after_top_level_rehash(tmp_path, field):
    accepted, suggestions = snapshots(tmp_path)
    data = json.loads(suggestions.read_text())
    data["records"][0][field] = "c" * 64
    suggestions.write_text(json.dumps(data))
    rehash(accepted, suggestions)
    with pytest.raises(ValueError, match=field + " mismatch"):
        load_accepted_constructs(accepted, suggestions)


@pytest.mark.parametrize(
    "change",
    ["sequence", "external_chemistry", "missing_links", "held", "missing", "duplicate"],
)
def test_changed_or_uncertain_members_fail_closed(tmp_path, change):
    accepted, suggestions = snapshots(tmp_path)
    data = json.loads(suggestions.read_text())
    first = data["records"][0]
    if change == "sequence":
        first["monomers"][0] = "GLY"
    elif change == "external_chemistry":
        first["unresolved_chemistry"] = True
    elif change == "missing_links":
        del first["internal_covalent_links"]
    elif change == "held":
        first["status"] = "held_chemistry"
    elif change == "missing":
        data["records"].pop(0)
    else:
        data["records"].append(first)
    suggestions.write_text(json.dumps(data))
    rehash(accepted, suggestions)
    with pytest.raises(ValueError):
        load_accepted_constructs(accepted, suggestions)


def test_duplicate_acceptance_and_new_unaccepted_equal_member(tmp_path):
    accepted, suggestions = snapshots(tmp_path)
    data = json.loads(suggestions.read_text())
    data["records"].append(source_record("3abc"))
    suggestions.write_text(json.dumps(data))
    rehash(accepted, suggestions)
    index = load_accepted_constructs(accepted, suggestions)
    assert (
        accepted_construct_updates(
            {"partner": "Q12345", "pdb": "3abc"}, "P12345", index
        )
        == {}
    )
    acceptance = json.loads(accepted.read_text())
    acceptance["groups"].append(acceptance["groups"][0])
    accepted.write_text(json.dumps(acceptance))
    with pytest.raises(ValueError, match="Duplicate"):
        load_accepted_constructs(accepted, suggestions)


def test_fingerprint_changes_for_chemical_monomer_or_span():
    first = source_record("1abc")
    second = source_record("2abc")
    assert len(equivalent_construct_groups([first, second])) == 1
    second["monomers"][1] = "CSO"
    assert equivalent_construct_groups([first, second]) == []
    second = source_record("2abc")
    second["mapped_spans"][0][1] = 9
    assert equivalent_construct_groups([first, second]) == []


def audit_module():
    spec = importlib.util.spec_from_file_location(
        "audit_contact_constructs", ROOT / "scripts/audit/audit_contact_constructs.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_absent_vs_partial_or_inconsistent_chemistry_category():
    module = audit_module()
    assert (
        module.rows({}, "_struct_conn.", ["conn_type_id", "ptnr1_label_asym_id"]) == []
    )
    with pytest.raises(module.IncompleteCategory):
        module.rows(
            {"_struct_conn.conn_type_id": ["disulf"]},
            "_struct_conn.",
            ["conn_type_id", "ptnr1_label_asym_id"],
        )
    with pytest.raises(module.IncompleteCategory):
        module.rows(
            {
                "_struct_conn.conn_type_id": ["disulf"],
                "_struct_conn.ptnr1_label_asym_id": ["A", "B"],
            },
            "_struct_conn.",
            ["conn_type_id", "ptnr1_label_asym_id"],
        )


def test_describe_holds_incomplete_chemistry(tmp_path, monkeypatch):
    module = audit_module()
    monkeypatch.setattr(module, "CACHE", tmp_path)
    (tmp_path / "1abc.cif").write_text("data_fixture\n")
    mapping = {"1abc": {"UniProt": {"Q12345": {"mappings": [{"entity_id": 1}]}}}}
    (tmp_path / "1abc-mapping.json").write_text(json.dumps(mapping))
    incomplete = {
        "_entity_poly_seq.entity_id": ["1"],
        "_entity_poly_seq.num": ["1"],
        "_entity_poly_seq.mon_id": ["CYS"],
        "_struct_asym.id": ["A"],
        "_struct_asym.entity_id": ["1"],
        "_struct_conn.conn_type_id": ["disulf"],
    }
    monkeypatch.setattr(module, "MMCIF2Dict", lambda _: incomplete)
    result = module.describe({"target": "P12345", "partner": "Q12345", "pdb": "1abc"})
    assert result["status"] == "held_chemistry"
    assert result["chemistry_checked"] is False
    assert construct_fingerprint(result) is None


def test_committed_acceptances_cover_only_three_reviewed_pairs():
    directory = ROOT / "data/analysis/deep_dive_binding_sites"
    accepted = directory / "accepted_constructs.json"
    index = load_accepted_constructs(
        accepted, directory / "contact_construct_suggestions.json"
    )
    assert set(index) == {
        ("O75581", "Q9H461", "21kr"),
        ("O75581", "Q9H461", "21ks"),
        ("P12830", "O60716", "3l6x"),
        ("P12830", "O60716", "3l6y"),
        ("P17693", "P16104", "2d31"),
        ("P17693", "P16104", "2dyp"),
    }
    assert len({v["construct_fingerprint"] for v in index.values()}) == 3
    assert (
        accepted_construct_updates(
            {"partner": "P16104", "pdb": "9rwi"}, "P17693", index
        )
        == {}
    )
