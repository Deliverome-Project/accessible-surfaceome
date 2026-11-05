"""Append-only NetGPI outputs and separate curated/ad hoc GPI records.

Raw decimal strings, record numbers, versions, source checksums and job IDs are
preserved. A legacy prediction whose original input is unavailable remains
explicitly unresolved; an accession or a matching length never proves sequence
identity. No caller in this module changes a gene's curated architecture call.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Protocol

PREDICTION_COLS = (
    "run_id",
    "record_id",
    "prediction_number",
    "tool_version",
    "job_id",
    "sequence_sha256",
    "sequence",
    "sequence_resolution",
    "sequence_length",
    "prediction",
    "likelihood_text",
    "omega_position",
    "omega_residue",
    "raw_line",
    "raw_header",
    "source_uri",
    "source_sha256",
    "import_code_sha",
    "members_json",
)
CURATION_COLS = (
    "source_sha256",
    "record_number",
    "source_kind",
    "gene_symbol",
    "source_uri",
    "import_code_sha",
    "record_json",
)
SCHEMA = Path(__file__).resolve().parents[3] / "cloudflare/d1_gpi_schema.sql"


class QueryClient(Protocol):
    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]: ...


def validate_prediction(row: dict[str, Any]) -> None:
    if set(row) != set(PREDICTION_COLS):
        raise ValueError("NetGPI record columns differ from the stored schema")
    raw = row["raw_line"].split("\t")
    if len(raw) != 6:
        raise ValueError("NetGPI short output must have six fields")
    if raw[0] != row["record_id"] or raw[2] != row["prediction"]:
        raise ValueError("prediction differs from its raw output")
    if raw[2] not in {"GPI-Anchored", "Not GPI-Anchored"}:
        raise ValueError("unknown NetGPI verdict")
    likelihood = float(row["likelihood_text"])
    if (
        not math.isfinite(likelihood)
        or not 0 <= likelihood <= 1
        or raw[4] != row["likelihood_text"]
    ):
        raise ValueError("likelihood must preserve the literal value in the raw output")
    if int(raw[1]) != row["sequence_length"]:
        raise ValueError("length differs from the raw output")
    omega = int(raw[3]) if raw[3].isdigit() else None
    if omega != row["omega_position"] or raw[5] != row["omega_residue"]:
        raise ValueError("omega site differs from the raw output")
    if int(row["prediction_number"]) < 1:
        raise ValueError("prediction numbers are one-based output row numbers")
    sequence = row["sequence"]
    if sequence is None:
        if (
            row["sequence_sha256"] is not None
            or row["sequence_resolution"] != "unresolved_legacy"
        ):
            raise ValueError("missing original sequence must remain unresolved")
    else:
        if len(sequence) != row["sequence_length"]:
            raise ValueError("input sequence differs from predicted length")
        if hashlib.sha256(sequence.encode()).hexdigest() != row["sequence_sha256"]:
            raise ValueError("input sequence checksum differs")
        if row["sequence_resolution"] != "exact_input":
            raise ValueError("resolved sequence requires exact original input")
    members = json.loads(row["members_json"])
    if not isinstance(members, list):
        raise ValueError("members must be a list of input identities")


def schema_statements() -> list[str]:
    text = "\n".join(line.split("--", 1)[0] for line in SCHEMA.read_text().splitlines())
    return [sql.strip() for sql in text.split(";") if sql.strip()]


def publish(
    client: QueryClient,
    predictions: list[dict[str, Any]],
    curation: list[dict[str, Any]],
) -> dict[str, int]:
    """Insert idempotently, then compare every stored value with the source record.

    Existing rows are never overwritten. Reusing a key with different source data
    raises an error, including when an earlier interrupted upload is resumed.
    """
    for row in predictions:
        validate_prediction(row)
    for row in curation:
        if set(row) != set(CURATION_COLS):
            raise ValueError("curation record columns differ from the stored schema")
        json.loads(row["record_json"])
    for statement in schema_statements():
        client.query(statement)
    for table, rows, columns, keys in (
        ("netgpi_prediction", predictions, PREDICTION_COLS, ("run_id", "record_id")),
        (
            "gpi_curation_record",
            curation,
            CURATION_COLS,
            ("source_sha256", "record_number"),
        ),
    ):
        # One bound JSON array per statement avoids D1's 100-parameter ceiling
        # while keeping each request small and reducing shared-account API calls.
        chunk_size = 50
        for start in range(0, len(rows), chunk_size):
            chunk = rows[start : start + chunk_size]
            sql = f"INSERT OR IGNORE INTO {table} ({', '.join(columns)}) SELECT "
            sql += ", ".join(f"json_extract(value, '$.{col}')" for col in columns)
            sql += " FROM json_each(?)"
            client.query(sql, [json.dumps(chunk, separators=(",", ":"))])
        # One read per run/source; do not issue one request per predicted protein.
        group_key = keys[0]
        for group in sorted({row[group_key] for row in rows}):
            existing = client.query(
                f"SELECT * FROM {table} WHERE {group_key} = ?", [group]
            )
            by_key = {tuple(row[k] for k in keys): row for row in existing}
            for row in (r for r in rows if r[group_key] == group):
                found = by_key.get(tuple(row[k] for k in keys))
                if found is None or any(found[col] != row[col] for col in columns):
                    raise ValueError(
                        f"stored {table} record conflicts with input: {tuple(row[k] for k in keys)}"
                    )
    return {
        "predictions_verified": len(predictions),
        "curation_records_verified": len(curation),
    }
