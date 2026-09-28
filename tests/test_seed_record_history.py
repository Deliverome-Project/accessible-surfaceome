"""``scripts/cloud/seed_record_history.py``: reading the tarball and the
resumable-seed guardrails.

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

from accessible_surfaceome.cloud.record_history.store import LatestRevision

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


def _existing_row(
    symbol: str,
    json_hash: str,
    *,
    revision: int = 1,
    source: str = "seed:zenodo-1.0.0",
) -> dict[str, Any]:
    return {
        "gene_symbol": symbol,
        "revision": revision,
        "json_hash": json_hash,
        "source": source,
    }


class _FakeD1:
    def __init__(
        self,
        *,
        record_revision_rows: list[dict[str, Any]] | None = None,
        data_release_rows: list[dict[str, Any]] | None = None,
    ) -> None:
        self._record_revision_rows = record_revision_rows or []
        self._data_release_rows = data_release_rows or []
        self.queries: list[tuple[str, list[Any]]] = []

    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        self.queries.append((sql, params or []))
        if "FROM record_revision" in sql:
            return self._record_revision_rows
        if "FROM data_release" in sql:
            return self._data_release_rows
        return []


class _FakeStore:
    def __init__(
        self,
        *,
        record_revision_rows: list[dict[str, Any]] | None = None,
        data_release_rows: list[dict[str, Any]] | None = None,
        insert_returns: dict[str, int | None] | None = None,
        latest_overrides: dict[str, LatestRevision] | None = None,
    ) -> None:
        self.d1 = _FakeD1(
            record_revision_rows=record_revision_rows,
            data_release_rows=data_release_rows,
        )
        self.put_blob_calls: list[str] = []
        self.insert_revision_calls: list[list[Any]] = []
        self._insert_returns = insert_returns or {}
        self._latest_overrides = latest_overrides or {}

    def __enter__(self) -> "_FakeStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def put_blob(self, key: str, body: bytes, content_type: str) -> None:
        self.put_blob_calls.append(key)

    def insert_revision(self, params: list[Any]) -> int | None:
        self.insert_revision_calls.append(params)
        sym = params[0]
        if sym in self._insert_returns:
            return self._insert_returns[sym]
        return 1

    def latest(self, symbol: str) -> LatestRevision | None:
        return self._latest_overrides.get(symbol)


class _FakeCloudRevisionStore:
    store: _FakeStore | None = None

    @classmethod
    def from_env(cls) -> _FakeStore:
        assert cls.store is not None
        return cls.store


def _run_execute(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tarball_records: list[dict[str, Any]],
    store: _FakeStore,
) -> None:
    tarball = _make_tarball(tmp_path, "seed.tar.gz", tarball_records)
    _FakeCloudRevisionStore.store = store
    monkeypatch.setattr(_mod, "CloudRevisionStore", _FakeCloudRevisionStore)
    monkeypatch.setattr(_mod, "load_env", lambda: None)
    monkeypatch.setattr(_mod, "purge_paths", lambda *a, **kw: None)
    monkeypatch.setattr(
        sys, "argv", ["seed_record_history.py", "--tarball", str(tarball), "--execute"]
    )
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


def test_dry_run_refuses_duplicate_symbols_before_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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


def test_happy_execute_path_writes_revision_1_and_creates_release_1_0_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tarball_records = [_record("EGFR", "HGNC:3236"), _record("CD63", "HGNC:1692")]
    store = _FakeStore()
    created_release: dict[str, Any] = {}

    def fake_create_release(d1: object, **kwargs: Any) -> None:
        created_release.update(kwargs)

    monkeypatch.setattr(_mod, "create_release", fake_create_release)

    _run_execute(tmp_path, monkeypatch, tarball_records, store)

    assert len(store.put_blob_calls) == 2
    assert len(store.insert_revision_calls) == 2
    for params in store.insert_revision_calls:
        sym, hgnc_id, json_hash, evidence_hash, md_hash, published_at, source, *_ = (
            params
        )
        assert evidence_hash is None
        assert md_hash is None
        assert published_at == _mod.SEED_AT
        assert source == _mod.SEED_SOURCE

    assert created_release["version"] == "1.0.0"
    assert created_release["zenodo_version_doi"] == "10.5281/zenodo.20805384"
    assert sorted(created_release["members"]) == [("CD63", 1), ("EGFR", 1)]
    assert "seeded 2 genes" in capsys.readouterr().out


def test_resume_only_writes_the_remaining_genes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tarball_records = [_record("EGFR", "HGNC:3236"), _record("CD63", "HGNC:1692")]
    egfr_hash = _mod.content_hash_record(tarball_records[0])
    store = _FakeStore(
        record_revision_rows=[_existing_row("EGFR", egfr_hash)],
    )
    created_release: dict[str, Any] = {}
    monkeypatch.setattr(
        _mod, "create_release", lambda d1, **kwargs: created_release.update(kwargs)
    )

    _run_execute(tmp_path, monkeypatch, tarball_records, store)

    # Only CD63 (not already at revision 1) gets written.
    assert len(store.put_blob_calls) == 1
    assert len(store.insert_revision_calls) == 1
    assert store.insert_revision_calls[0][0] == "CD63"
    # But the release still covers both genes.
    assert sorted(created_release["members"]) == [("CD63", 1), ("EGFR", 1)]


def test_refuses_when_a_publish_row_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tarball_records = [_record("EGFR", "HGNC:3236"), _record("CD63", "HGNC:1692")]
    egfr_hash = _mod.content_hash_record(tarball_records[0])
    store = _FakeStore(
        record_revision_rows=[_existing_row("EGFR", egfr_hash, source="publish")],
    )
    monkeypatch.setattr(
        _mod,
        "create_release",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("must not be reached")),
    )

    with pytest.raises(SystemExit, match="EGFR"):
        _run_execute(tmp_path, monkeypatch, tarball_records, store)

    assert store.put_blob_calls == []
    assert store.insert_revision_calls == []


def test_none_from_insert_accepted_when_latest_confirms_revision_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tarball_records = [_record("EGFR", "HGNC:3236")]
    egfr_hash = _mod.content_hash_record(tarball_records[0])
    store = _FakeStore(
        insert_returns={"EGFR": None},
        latest_overrides={
            "EGFR": LatestRevision(
                revision=1, json_hash=egfr_hash, evidence_hash=None, md_hash=None
            )
        },
    )
    created_release: dict[str, Any] = {}
    monkeypatch.setattr(
        _mod, "create_release", lambda d1, **kwargs: created_release.update(kwargs)
    )

    _run_execute(tmp_path, monkeypatch, tarball_records, store)

    assert created_release["members"] == [("EGFR", 1)]


def test_none_from_insert_raises_when_latest_does_not_confirm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tarball_records = [_record("EGFR", "HGNC:3236")]
    store = _FakeStore(
        insert_returns={"EGFR": None},
        latest_overrides={
            "EGFR": LatestRevision(
                revision=1,
                json_hash="some-other-hash",
                evidence_hash=None,
                md_hash=None,
            )
        },
    )
    monkeypatch.setattr(
        _mod,
        "create_release",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("must not be reached")),
    )

    with pytest.raises(RuntimeError, match="EGFR"):
        _run_execute(tmp_path, monkeypatch, tarball_records, store)


def test_already_seeded_exits_0_with_no_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tarball_records = [_record("EGFR", "HGNC:3236"), _record("CD63", "HGNC:1692")]
    egfr_hash = _mod.content_hash_record(tarball_records[0])
    cd63_hash = _mod.content_hash_record(tarball_records[1])
    store = _FakeStore(
        record_revision_rows=[
            _existing_row("EGFR", egfr_hash),
            _existing_row("CD63", cd63_hash),
        ],
        data_release_rows=[{"version": "1.0.0", "n_genes": 2}],
    )
    monkeypatch.setattr(
        _mod,
        "create_release",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("must not be reached")),
    )

    _run_execute(tmp_path, monkeypatch, tarball_records, store)

    assert store.put_blob_calls == []
    assert store.insert_revision_calls == []
    assert "already seeded" in capsys.readouterr().out


def test_stop_on_first_failure_skips_queued_inserts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tarball_records = [_record(f"GENE{i}") for i in range(6)]
    store = _FakeStore(insert_returns={"GENE0": 2})  # wrong revision -> raises

    with pytest.raises(RuntimeError, match="GENE0"):
        _run_execute(tmp_path, monkeypatch, tarball_records, store)

    # Every gene got its (idempotent) R2 put, but not every gene necessarily
    # reached insert_revision once the failure tripped the stop event.
    assert len(store.insert_revision_calls) <= len(tarball_records)
    assert any(p[0] == "GENE0" for p in store.insert_revision_calls)
