"""``scripts/cloud/seed_record_history.py``: retired.

The script's write path (build the S3 client, hash + bulk-insert revision-1
rows, cut release 1.0.0 over them) was removed — record history now holds
only states the API actually served, and the Zenodo deposit was never
itself served through the Worker. ``main()`` refuses immediately; any
``seed:zenodo-1.0.0`` rows already landed in D1 from an earlier run are
cleaned up by ``scripts/cloud/drop_seed_revisions.py`` instead (see
``tests/test_drop_seed_revisions.py``).

The pure helper functions below it (tarball parsing, the resumable-seed
guardrails, the bulk-insert SQL shape) are left importable as a record of
how 1.0.0 was originally seeded, and are still exercised here so they don't
silently bit-rot into something that would mislead a future reader tracing
that history.

Loaded via ``importlib.util.spec_from_file_location`` (the house pattern for
testing a standalone ``scripts/`` entry point — see
``tests/test_sweep_record_history.py``). Its
``from accessible_surfaceome... import ...`` statements still resolve
through the real package.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sqlite3
import sys
import tarfile
from pathlib import Path
from typing import Any

import pytest

from accessible_surfaceome.cloud.record_history import store

_SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "cloud" / "seed_record_history.py"
)
_spec = importlib.util.spec_from_file_location("seed_record_history", _SCRIPT)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def _record(symbol: str, hgnc_id: str = "HGNC:0000") -> dict[str, Any]:
    return {
        "gene": {"hgnc_symbol": symbol, "hgnc_id": hgnc_id},
        "schema_version": "2.14.2",
        "prompt_corpus_version": "v9",
    }


def _make_tarball(tmp_path: Path, name: str, records: list[dict[str, Any]]) -> Path:
    out = tmp_path / name
    with tarfile.open(out, "w:gz") as tf:
        for rec in records:
            raw = json.dumps(rec).encode("utf-8")
            info = tarfile.TarInfo(f"genes/{rec['gene']['hgnc_symbol']}.json")
            info.size = len(raw)
            tf.addfile(info, io.BytesIO(raw))
    return out


class SqliteD1:
    """D1Client stand-in backed by in-memory SQLite (same SQL dialect)."""

    def __init__(self) -> None:
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        for s in store.DDL:
            self.con.execute(s)
        self.queries: list[tuple[str, list[Any]]] = []

    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        self.queries.append((sql, list(params or [])))
        cur = self.con.execute(sql, params or [])
        return [dict(r) for r in cur.fetchall()]


def _existing_row(
    d1: SqliteD1, sym: str, json_hash: str, *, source: str = "seed:zenodo-1.0.0", revision: int = 1
) -> None:
    d1.query(
        "INSERT INTO record_revision "
        "(gene_symbol, hgnc_id, revision, json_hash, evidence_hash, md_hash, "
        " published_at, source, schema_version, prompt_corpus_version) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        [sym, "HGNC:0000", revision, json_hash, None, None, "t", source, "2.14.2", "v9"],
    )


def test_main_refuses_immediately(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Retired: `main()` must never reach the tarball / D1 / R2 write path,
    with or without `--execute`."""
    tarball = _make_tarball(tmp_path, "seed.tar.gz", [_record("EGFR")])
    monkeypatch.setattr(
        sys, "argv", ["seed_record_history.py", "--tarball", str(tarball), "--execute"]
    )

    with pytest.raises(SystemExit, match="retired"):
        _mod.main()


def test_main_refuses_without_execute_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tarball = _make_tarball(tmp_path, "seed.tar.gz", [_record("EGFR")])
    monkeypatch.setattr(
        sys, "argv", ["seed_record_history.py", "--tarball", str(tarball)]
    )

    with pytest.raises(SystemExit, match="drop_seed_revisions"):
        _mod.main()


def test_read_records_reads_tiny_tarball(tmp_path: Path) -> None:
    tarball = _make_tarball(
        tmp_path,
        "tiny.tar.gz",
        [_record("EGFR", "HGNC:3236"), _record("CD63", "HGNC:1692")],
    )

    records = _mod.read_records(tarball)

    assert [sym for sym, _raw, _rec in records] == ["CD63", "EGFR"]
    symbol, raw, rec = records[0]
    assert symbol == "CD63"
    assert json.loads(raw) == rec
    assert rec["gene"]["hgnc_id"] == "HGNC:1692"


def test_duplicate_symbols_case_insensitive_refused() -> None:
    records = [
        ("EGFR", b"{}", _record("EGFR")),
        ("egfr", b"{}", _record("egfr")),
    ]

    with pytest.raises(SystemExit, match="duplicate symbol"):
        _mod.check_unique_case_insensitive(records)


def test_refuse_on_stale_existing_rows_passes_for_own_shape() -> None:
    _mod.refuse_on_stale_existing_rows(
        [
            {
                "gene_symbol": "EGFR",
                "revision": 1,
                "json_hash": "h1",
                "source": "seed:zenodo-1.0.0",
            }
        ],
        expected_hash={"egfr": "h1"},
        tarball_symbols={"egfr"},
    )  # must not raise


def test_refuse_on_stale_existing_rows_flags_non_seed_source() -> None:
    with pytest.raises(SystemExit, match="EGFR"):
        _mod.refuse_on_stale_existing_rows(
            [{"gene_symbol": "EGFR", "revision": 1, "json_hash": "h1", "source": "publish"}],
            expected_hash={"egfr": "h1"},
            tarball_symbols={"egfr"},
        )


def test_refuse_on_stale_existing_rows_flags_hash_mismatch() -> None:
    with pytest.raises(SystemExit, match="EGFR"):
        _mod.refuse_on_stale_existing_rows(
            [
                {
                    "gene_symbol": "EGFR",
                    "revision": 1,
                    "json_hash": "wrong",
                    "source": "seed:zenodo-1.0.0",
                }
            ],
            expected_hash={"egfr": "h1"},
            tarball_symbols={"egfr"},
        )


def test_bulk_insert_seed_rows_batch_fits_d1_parameter_cap() -> None:
    assert _mod.SEED_ROWS_PER_INSERT * len(_mod.SEED_COLUMNS) <= 100


def test_bulk_insert_seed_rows_issues_one_statement_per_batch() -> None:
    d1 = SqliteD1()
    todo = [(f"GENE{i}", b"{}", _record(f"GENE{i}")) for i in range(25)]
    expected_hash = {sym.casefold(): f"hash{i}" for i, (sym, _r, _rec) in enumerate(todo)}

    _mod.bulk_insert_seed_rows(d1, todo, expected_hash=expected_hash)

    import math

    expected_batches = math.ceil(len(todo) / _mod.SEED_ROWS_PER_INSERT)
    assert len(d1.queries) == expected_batches
    rows = d1.query("SELECT count(*) AS n FROM record_revision")
    assert rows[0]["n"] == 25


def test_bulk_insert_seed_rows_on_conflict_is_idempotent() -> None:
    """A replayed batch (an at-least-once HTTP retry) must not duplicate rows."""
    d1 = SqliteD1()
    todo = [("EGFR", b"{}", _record("EGFR")), ("CD63", b"{}", _record("CD63"))]
    expected_hash = {"egfr": "h1", "cd63": "h2"}

    _mod.bulk_insert_seed_rows(d1, todo, expected_hash=expected_hash)
    _mod.bulk_insert_seed_rows(d1, todo, expected_hash=expected_hash)  # replay

    rows = d1.query("SELECT count(*) AS n FROM record_revision")
    assert rows[0]["n"] == 2


def test_verify_seeded_rows_passes_when_correct() -> None:
    d1 = SqliteD1()
    todo = [("EGFR", b"{}", _record("EGFR"))]
    expected_hash = {"egfr": "h1"}
    _mod.bulk_insert_seed_rows(d1, todo, expected_hash=expected_hash)

    _mod.verify_seeded_rows(
        d1, expected_hash=expected_hash, display_symbol={"egfr": "EGFR"}
    )  # must not raise


def test_verify_seeded_rows_raises_on_missing_symbol() -> None:
    d1 = SqliteD1()
    expected_hash = {"egfr": "h1"}

    with pytest.raises(SystemExit, match="EGFR.*missing"):
        _mod.verify_seeded_rows(
            d1, expected_hash=expected_hash, display_symbol={"egfr": "EGFR"}
        )


def test_verify_seeded_rows_raises_on_hash_mismatch() -> None:
    d1 = SqliteD1()
    _existing_row(d1, "EGFR", "wrong-hash")
    expected_hash = {"egfr": "h1"}

    with pytest.raises(SystemExit, match="EGFR.*mismatch"):
        _mod.verify_seeded_rows(
            d1, expected_hash=expected_hash, display_symbol={"egfr": "EGFR"}
        )
