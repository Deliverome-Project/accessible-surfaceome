import hashlib
import json
import sqlite3

import pytest

from accessible_surfaceome.cloud.gpi_predictions import publish, validate_prediction


class SQLiteClient:
    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row

    def query(self, sql, params=None):
        cursor = self.connection.execute(sql, params or [])
        return [dict(row) for row in cursor.fetchall()]


def prediction():
    seq = "MAAAA"
    return {
        "run_id": "run1",
        "record_id": "input1",
        "prediction_number": 1,
        "tool_version": "NetGPI-1.1",
        "job_id": "service-job",
        "sequence": seq,
        "sequence_sha256": hashlib.sha256(seq.encode()).hexdigest(),
        "sequence_resolution": "exact_input",
        "sequence_length": 5,
        "prediction": "GPI-Anchored",
        "likelihood_text": "0.500",
        "omega_position": 3,
        "omega_residue": "A",
        "raw_line": "input1\t5\tGPI-Anchored\t3\t0.500\tA",
        "source_uri": "processed://run/raw.txt",
        "source_sha256": "a" * 64,
        "raw_header": "# NetGPI 1.1 short output",
        "import_code_sha": "b" * 40,
        "members_json": "[]",
    }


def test_append_is_idempotent_and_keeps_curation_independent():
    client = SQLiteClient()
    row = prediction()
    curation = {
        "source_sha256": "c" * 64,
        "record_number": 1,
        "source_kind": "literature_override",
        "gene_symbol": "GENE",
        "source_uri": "processed://curation.tsv",
        "import_code_sha": "b" * 40,
        "record_json": json.dumps(
            {"gpi_anchored": False, "reason": "recorded curator decision"}
        ),
    }
    publish(client, [row], [curation])
    publish(client, [row], [curation])
    assert client.query("SELECT COUNT(*) AS n FROM netgpi_prediction")[0]["n"] == 1
    assert (
        client.query("SELECT likelihood_text FROM netgpi_prediction")[0][
            "likelihood_text"
        ]
        == "0.500"
    )
    assert (
        json.loads(
            client.query("SELECT record_json FROM gpi_curation_record")[0][
                "record_json"
            ]
        )["gpi_anchored"]
        is False
    )


def test_reused_key_cannot_overwrite_prediction():
    client = SQLiteClient()
    row = prediction()
    publish(client, [row], [])
    changed = {
        **row,
        "likelihood_text": "0.501",
        "raw_line": row["raw_line"].replace("0.500", "0.501"),
    }
    with pytest.raises(ValueError, match="conflicts with input"):
        publish(client, [changed], [])
    assert (
        client.query("SELECT likelihood_text FROM netgpi_prediction")[0][
            "likelihood_text"
        ]
        == "0.500"
    )


def test_legacy_missing_input_is_explicit_and_not_guessed():
    row = {
        **prediction(),
        "sequence": None,
        "sequence_sha256": None,
        "sequence_resolution": "unresolved_legacy",
    }
    validate_prediction(row)
    with pytest.raises(ValueError, match="must remain unresolved"):
        validate_prediction({**row, "sequence_sha256": "a" * 64})


def test_exact_sequence_and_raw_numeric_value_are_verified():
    row = prediction()
    with pytest.raises(ValueError, match="checksum differs"):
        validate_prediction({**row, "sequence": "MAAAV"})
    with pytest.raises(ValueError, match="literal value"):
        validate_prediction({**row, "likelihood_text": "0.5"})
