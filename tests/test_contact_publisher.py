"""Release activation is gated by complete payload readback, including resume."""

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "publish_contacts", ROOT / "scripts/publish_contact_sites.py"
)
assert spec is not None and spec.loader is not None
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class Database:
    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")

    def query(self, sql, params):
        return [dict(row) for row in self.connection.execute(sql, params).fetchall()]


def bundle():
    return {
        "release_id": "contacts-test",
        "manifest": {"version": 1},
        "ligands": [{"ligand_id": "lig-test"}],
        "genes": [
            {
                "uniprot_acc": "P00533",
                "hgnc_id": "HGNC:3236",
                "all": [],
                "extracellular": [],
                "observations": [
                    {
                        "observation_id": "obs-test",
                        "ligand_id": "lig-test",
                        "positions": [1],
                        "source": "PDB/PDBe",
                        "context": "extracellular_explicit",
                    }
                ],
            }
        ],
    }


def test_publish_resume_and_activation():
    db = Database()
    data = bundle()
    publisher.publish(db, data)
    assert not db.query("SELECT * FROM contact_active_release", [])
    publisher.publish(db, data, make_active=True)
    assert db.query("SELECT count(*) AS n FROM contact_observation", [])[0]["n"] == 1
    assert (
        db.query("SELECT release_id FROM contact_active_release", [])[0]["release_id"]
        == data["release_id"]
    )
    with pytest.raises(ValueError, match="validated"):
        publisher.activate(db, "missing")


def test_corrupt_or_partial_release_cannot_activate():
    db = Database()
    data = bundle()
    publisher.publish(db, data, make_active=True)
    changed = json.loads(json.dumps(data))
    changed["release_id"] = "contacts-second"
    publisher.publish(db, changed)
    db.query(
        "UPDATE contact_release SET state='loading' WHERE release_id=?",
        [changed["release_id"]],
    )
    db.query(
        "UPDATE contact_observation SET observation_json='{}' WHERE release_id=?",
        [changed["release_id"]],
    )
    with pytest.raises(ValueError, match="Readback mismatch"):
        publisher.publish(db, changed, make_active=True)
    assert (
        db.query("SELECT release_id FROM contact_active_release", [])[0]["release_id"]
        == data["release_id"]
    )
    publisher.activate(db, data["release_id"])


def test_manifest_is_immutable():
    db = Database()
    data = bundle()
    publisher.publish(db, data)
    data["manifest"]["version"] = 2
    with pytest.raises(ValueError, match="manifest mismatch"):
        publisher.publish(db, data)
