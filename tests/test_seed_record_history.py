"""``scripts/cloud/seed_record_history.py``: reading the tarball, the
resumable-seed guardrails, and the bulk D1 write + verification path.

Loaded via ``importlib.util.spec_from_file_location`` (the house pattern for
testing a standalone ``scripts/`` entry point — see
``tests/test_sweep_record_history.py``). Its
``from accessible_surfaceome... import ...`` statements still resolve
through the real package.

The D1 fake is an in-memory SQLite connection seeded with
``record_history.store.DDL`` (the same pattern ``test_record_history_
releases.py`` uses) rather than a param-recording mock: the whole point of
the bulk-insert rewrite is real ``INSERT ... ON CONFLICT DO NOTHING``
semantics, which only a real SQL engine exercises faithfully.
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


class _FailAfterNQueries:
    """Wraps a ``SqliteD1``, raising once a query count threshold is hit."""

    def __init__(self, inner: SqliteD1, fail_on_call: int) -> None:
        self._inner = inner
        self._fail_on_call = fail_on_call
        self._calls = 0

    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        self._calls += 1
        if self._calls == self._fail_on_call:
            raise RuntimeError("simulated transient D1 failure")
        return self._inner.query(sql, params)


def _existing_row(d1: SqliteD1, sym: str, json_hash: str, *, source: str = "seed:zenodo-1.0.0", revision: int = 1) -> None:
    d1.query(
        "INSERT INTO record_revision "
        "(gene_symbol, hgnc_id, revision, json_hash, evidence_hash, md_hash, "
        " published_at, source, schema_version, prompt_corpus_version) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        [sym, "HGNC:0000", revision, json_hash, None, None, "t", source, "2.14.2", "v9"],
    )


class FakeStore:
    def __init__(self, d1: SqliteD1 | None = None) -> None:
        self.d1 = d1 or SqliteD1()
        self.put_blob_calls: list[tuple[str, bool]] = []

    def __enter__(self) -> "FakeStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def put_blob(
        self, key: str, body: bytes, content_type: str, *, skip_head: bool = False
    ) -> None:
        self.put_blob_calls.append((key, skip_head))


class _FakeCloudRevisionStore:
    store: FakeStore | None = None

    @classmethod
    def from_env(cls) -> FakeStore:
        assert cls.store is not None
        return cls.store


def _run_execute(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tarball_records: list[dict[str, Any]],
    store_obj: FakeStore,
) -> None:
    tarball = _make_tarball(tmp_path, "seed.tar.gz", tarball_records)
    _FakeCloudRevisionStore.store = store_obj
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
    store_obj = FakeStore()
    created_release: dict[str, Any] = {}

    def fake_create_release(d1: object, **kwargs: Any) -> None:
        created_release.update(kwargs)

    monkeypatch.setattr(_mod, "create_release", fake_create_release)

    _run_execute(tmp_path, monkeypatch, tarball_records, store_obj)

    # Both records went through R2 with skip_head=True (content-addressed,
    # the bucket is assumed empty for these fresh keys).
    assert len(store_obj.put_blob_calls) == 2
    assert all(skip_head is True for _key, skip_head in store_obj.put_blob_calls)

    rows = store_obj.d1.query(
        "SELECT gene_symbol, revision, source, json_hash FROM record_revision "
        "ORDER BY gene_symbol"
    )
    assert [r["gene_symbol"] for r in rows] == ["CD63", "EGFR"]
    for r in rows:
        assert r["revision"] == 1
        assert r["source"] == _mod.SEED_SOURCE

    assert created_release["version"] == "1.0.0"
    assert created_release["zenodo_version_doi"] == "10.5281/zenodo.20805384"
    assert sorted(created_release["members"]) == [("CD63", 1), ("EGFR", 1)]
    assert "seeded 2 genes" in capsys.readouterr().out


def test_resume_only_writes_the_remaining_genes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tarball_records = [_record("EGFR", "HGNC:3236"), _record("CD63", "HGNC:1692")]
    egfr_hash = _mod.content_hash_record(tarball_records[0])
    store_obj = FakeStore()
    _existing_row(store_obj.d1, "EGFR", egfr_hash)
    created_release: dict[str, Any] = {}
    monkeypatch.setattr(
        _mod, "create_release", lambda d1, **kwargs: created_release.update(kwargs)
    )

    _run_execute(tmp_path, monkeypatch, tarball_records, store_obj)

    # Only CD63 (not already at revision 1) gets a fresh R2 write.
    assert store_obj.put_blob_calls == [
        (_mod.blob_key(_mod.content_hash_record(tarball_records[1]), "json"), True)
    ]
    rows = store_obj.d1.query("SELECT gene_symbol FROM record_revision ORDER BY gene_symbol")
    assert [r["gene_symbol"] for r in rows] == ["CD63", "EGFR"]
    # But the release still covers both genes.
    assert sorted(created_release["members"]) == [("CD63", 1), ("EGFR", 1)]


def test_refuses_when_a_publish_row_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tarball_records = [_record("EGFR", "HGNC:3236"), _record("CD63", "HGNC:1692")]
    egfr_hash = _mod.content_hash_record(tarball_records[0])
    store_obj = FakeStore()
    _existing_row(store_obj.d1, "EGFR", egfr_hash, source="publish")
    monkeypatch.setattr(
        _mod,
        "create_release",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("must not be reached")),
    )

    with pytest.raises(SystemExit, match="EGFR"):
        _run_execute(tmp_path, monkeypatch, tarball_records, store_obj)

    assert store_obj.put_blob_calls == []


def test_already_seeded_exits_0_with_no_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tarball_records = [_record("EGFR", "HGNC:3236"), _record("CD63", "HGNC:1692")]
    egfr_hash = _mod.content_hash_record(tarball_records[0])
    cd63_hash = _mod.content_hash_record(tarball_records[1])
    store_obj = FakeStore()
    _existing_row(store_obj.d1, "EGFR", egfr_hash)
    _existing_row(store_obj.d1, "CD63", cd63_hash)
    store_obj.d1.query(
        "INSERT INTO data_release (version, cut_at, n_genes) VALUES ('1.0.0', 't', 2)"
    )
    monkeypatch.setattr(
        _mod,
        "create_release",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("must not be reached")),
    )

    _run_execute(tmp_path, monkeypatch, tarball_records, store_obj)

    assert store_obj.put_blob_calls == []
    assert "already seeded" in capsys.readouterr().out


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


def test_bulk_insert_failure_propagates_before_release_is_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tarball_records = [_record(f"GENE{i}") for i in range(3)]
    inner = SqliteD1()
    # 1=existing-rows read, 2=data_release read, 3=the one bulk-insert batch
    # (3 genes fits in one SEED_ROWS_PER_INSERT batch) -> fail on call 3.
    store_obj = FakeStore(d1=_FailAfterNQueries(inner, fail_on_call=3))  # ty: ignore[invalid-argument-type]
    monkeypatch.setattr(
        _mod,
        "create_release",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("must not be reached")),
    )

    with pytest.raises(RuntimeError, match="simulated transient D1 failure"):
        _run_execute(tmp_path, monkeypatch, tarball_records, store_obj)
