"""``scripts/cloud/seed_record_history.py``: reading the tarball and the
refusal guardrails around the one-off seed write.

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
import sys
import tarfile
from pathlib import Path
from typing import Any

import pytest

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


class _FakeD1:
    def __init__(self, record_revision_rows: list[dict[str, Any]]) -> None:
        self._record_revision_rows = record_revision_rows
        self.queries: list[tuple[str, list[Any]]] = []

    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        self.queries.append((sql, params or []))
        if "FROM record_revision LIMIT 1" in sql:
            return self._record_revision_rows
        return []


class _FakeStore:
    def __init__(self, *, record_revision_rows: list[dict[str, Any]]) -> None:
        self.d1 = _FakeD1(record_revision_rows)
        self.put_blob_calls: list[str] = []
        self.insert_revision_calls: list[list[Any]] = []

    def __enter__(self) -> "_FakeStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def put_blob(self, key: str, body: bytes, content_type: str) -> None:
        self.put_blob_calls.append(key)

    def insert_revision(self, params: list[Any]) -> int:
        self.insert_revision_calls.append(params)
        return 1


class _FakeCloudRevisionStore:
    store: _FakeStore | None = None

    @classmethod
    def from_env(cls) -> _FakeStore:
        assert cls.store is not None
        return cls.store


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


def test_dry_run_refuses_duplicate_symbols_before_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tarball = _make_tarball(
        tmp_path, "dupes.tar.gz", [_record("EGFR"), _record("Egfr")]
    )
    monkeypatch.setattr(
        sys, "argv", ["seed_record_history.py", "--tarball", str(tarball)]
    )
    monkeypatch.setattr(
        _mod, "load_env", lambda: (_ for _ in ()).throw(AssertionError("must not run"))
    )

    with pytest.raises(SystemExit, match="duplicate symbol"):
        _mod.main()


def test_execute_refuses_when_record_revision_non_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tarball = _make_tarball(tmp_path, "seed.tar.gz", [_record("EGFR"), _record("CD63")])
    store = _FakeStore(record_revision_rows=[{"1": 1}])
    _FakeCloudRevisionStore.store = store
    monkeypatch.setattr(_mod, "CloudRevisionStore", _FakeCloudRevisionStore)
    monkeypatch.setattr(_mod, "load_env", lambda: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["seed_record_history.py", "--tarball", str(tarball), "--execute"],
    )

    with pytest.raises(SystemExit, match="record_revision is not empty"):
        _mod.main()


def test_no_r2_write_before_the_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tarball = _make_tarball(tmp_path, "seed.tar.gz", [_record("EGFR"), _record("CD63")])
    store = _FakeStore(record_revision_rows=[{"1": 1}])
    _FakeCloudRevisionStore.store = store
    monkeypatch.setattr(_mod, "CloudRevisionStore", _FakeCloudRevisionStore)
    monkeypatch.setattr(_mod, "load_env", lambda: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["seed_record_history.py", "--tarball", str(tarball), "--execute"],
    )

    with pytest.raises(SystemExit, match="record_revision is not empty"):
        _mod.main()

    assert store.put_blob_calls == []
    assert store.insert_revision_calls == []
