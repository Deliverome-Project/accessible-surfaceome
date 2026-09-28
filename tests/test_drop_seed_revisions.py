"""``scripts/cloud/drop_seed_revisions.py`` against in-memory SQLite built
from ``record_history.store.DDL`` — same house pattern as
``tests/test_seed_record_history.py``.

Loaded via ``importlib.util.spec_from_file_location`` so the standalone
``scripts/`` entry point runs unmodified; its
``from accessible_surfaceome... import ...`` statements resolve through the
real package.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pytest

from accessible_surfaceome.cloud.record_history import store

_SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "cloud" / "drop_seed_revisions.py"
)
_spec = importlib.util.spec_from_file_location("drop_seed_revisions", _SCRIPT)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


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
        self.con.commit()
        return [dict(r) for r in cur.fetchall()]


class _FailOnceOnSql:
    """Wraps a ``SqliteD1``, raising the FIRST time a query whose SQL
    contains ``trigger`` is about to run (without executing it) —
    simulates a crash right after the previous statement committed.
    Every other query, including a retried one after the caller catches
    the failure, passes straight through to ``inner``."""

    def __init__(self, inner: SqliteD1, trigger: str) -> None:
        self._inner = inner
        self._trigger = trigger
        self._fired = False

    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        if not self._fired and self._trigger in sql:
            self._fired = True
            raise RuntimeError("simulated transient D1 failure")
        return self._inner.query(sql, params)


class FakeStore:
    def __init__(self, d1: SqliteD1) -> None:
        self.d1 = d1

    def __enter__(self) -> "FakeStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


class _FakeCloudRevisionStore:
    store: FakeStore | None = None

    @classmethod
    def from_env(cls) -> FakeStore:
        assert cls.store is not None
        return cls.store


def _insert_revision(
    d1: SqliteD1,
    sym: str,
    revision: int,
    *,
    source: str,
    json_hash: str | None = None,
    hgnc_id: str = "HGNC:0000",
    published_at: str = "2026-09-01T00:00:00Z",
) -> None:
    d1.query(
        "INSERT INTO record_revision "
        "(gene_symbol, hgnc_id, revision, json_hash, evidence_hash, md_hash, "
        " published_at, source, schema_version, prompt_corpus_version) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            sym,
            hgnc_id,
            revision,
            json_hash or f"{sym.lower()}-{revision}",
            None,
            None,
            published_at,
            source,
            "2.14.4",
            "v9",
        ],
    )


def _seed_fixture(d1: SqliteD1) -> None:
    """The state record history was actually in "hours ago" per the task
    background: a seed row for every seeded gene at revision 1, plus
    whatever the sweep/publish path has added since, and release 1.0.0
    pointing every seeded gene's revision 1 (the seed) as its member."""
    # S100A7A: seeded, then 3 more served revisions (4 total) -> after
    # migration: revisions 1,2,3 remain (shifted down from 2,3,4).
    _insert_revision(d1, "S100A7A", 1, source="seed:zenodo-1.0.0")
    _insert_revision(d1, "S100A7A", 2, source="sweep")
    _insert_revision(d1, "S100A7A", 3, source="sweep")
    _insert_revision(d1, "S100A7A", 4, source="publish")

    # CD63: seeded, then exactly one more served revision (2 total) ->
    # after migration: only revision 1 remains (shifted down from 2).
    _insert_revision(d1, "CD63", 1, source="seed:zenodo-1.0.0")
    _insert_revision(d1, "CD63", 2, source="sweep")

    # EGFR: never seeded (annotated after 2026-08-15) -> untouched.
    _insert_revision(d1, "EGFR", 1, source="sweep")
    _insert_revision(d1, "EGFR", 2, source="sweep")

    d1.query(
        "INSERT INTO data_release "
        "(version, cut_at, github_tag, zenodo_version_doi, n_genes, notes) "
        "VALUES (?, ?, NULL, ?, ?, ?)",
        [
            "1.0.0",
            "2026-08-15T00:00:00Z",
            "10.5281/zenodo.20805384",
            2,
            "Initial data deposit (Zenodo record 20805384); records as "
            "deposited, evidence inline, no Markdown.",
        ],
    )
    d1.query(
        "INSERT INTO data_release_member (version, gene_symbol, revision) "
        "VALUES ('1.0.0', 'S100A7A', 1), ('1.0.0', 'CD63', 1)"
    )


def _assert_fully_migrated(d1: SqliteD1) -> None:
    # No seed rows anywhere.
    rows = d1.query(
        "SELECT COUNT(*) AS n FROM record_revision WHERE source = 'seed:zenodo-1.0.0'"
    )
    assert rows[0]["n"] == 0

    # S100A7A: 1,2,3 (shifted down from 2,3,4), sources preserved in order.
    s100 = d1.query(
        "SELECT revision, source FROM record_revision WHERE gene_symbol = 'S100A7A' "
        "ORDER BY revision"
    )
    assert [(r["revision"], r["source"]) for r in s100] == [
        (1, "sweep"),
        (2, "sweep"),
        (3, "publish"),
    ]

    # CD63: only revision 1 remains (shifted down from 2).
    cd63 = d1.query(
        "SELECT revision, source FROM record_revision WHERE gene_symbol = 'CD63' "
        "ORDER BY revision"
    )
    assert [(r["revision"], r["source"]) for r in cd63] == [(1, "sweep")]

    # EGFR (never seeded): untouched.
    egfr = d1.query(
        "SELECT revision, source FROM record_revision WHERE gene_symbol = 'EGFR' "
        "ORDER BY revision"
    )
    assert [(r["revision"], r["source"]) for r in egfr] == [(1, "sweep"), (2, "sweep")]

    # No 1.0.0 member rows.
    members = d1.query(
        "SELECT COUNT(*) AS n FROM data_release_member WHERE version = '1.0.0'"
    )
    assert members[0]["n"] == 0

    # 1.0.0 row intact: DOI preserved, archive_scope set, n_genes untouched.
    rel = d1.query(
        "SELECT zenodo_version_doi, n_genes, archive_scope, notes "
        "FROM data_release WHERE version = '1.0.0'"
    )[0]
    assert rel["zenodo_version_doi"] == "10.5281/zenodo.20805384"
    assert rel["n_genes"] == 2
    assert rel["archive_scope"] == "zenodo_only"
    assert "Zenodo deposit" in rel["notes"]

    # Every gene, seeded or not, is contiguous from 1 — the general
    # invariant the migration exists to restore.
    assert _mod.genes_needing_shift(d1) == {}


def _run_main(
    monkeypatch: pytest.MonkeyPatch, d1: Any, *, execute: bool
) -> None:
    _FakeCloudRevisionStore.store = FakeStore(d1)
    monkeypatch.setattr(_mod, "CloudRevisionStore", _FakeCloudRevisionStore)
    monkeypatch.setattr(_mod, "load_env", lambda: None)
    monkeypatch.setattr(_mod, "purge_paths", lambda *a, **kw: None)
    argv = ["drop_seed_revisions.py"]
    if execute:
        argv.append("--execute")
    monkeypatch.setattr(sys, "argv", argv)
    _mod.main()


def test_dry_run_writes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    d1 = SqliteD1()
    _seed_fixture(d1)

    _run_main(monkeypatch, d1, execute=False)

    # Untouched: the seed row is still there.
    rows = d1.query(
        "SELECT COUNT(*) AS n FROM record_revision WHERE source = 'seed:zenodo-1.0.0'"
    )
    assert rows[0]["n"] == 2
    members = d1.query(
        "SELECT COUNT(*) AS n FROM data_release_member WHERE version = '1.0.0'"
    )
    assert members[0]["n"] == 2


def test_execute_migrates_fully(monkeypatch: pytest.MonkeyPatch) -> None:
    d1 = SqliteD1()
    _seed_fixture(d1)

    _run_main(monkeypatch, d1, execute=True)

    _assert_fully_migrated(d1)


def test_execute_is_idempotent_on_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    d1 = SqliteD1()
    _seed_fixture(d1)

    _run_main(monkeypatch, d1, execute=True)
    _run_main(monkeypatch, d1, execute=True)  # replay: must be a safe no-op

    _assert_fully_migrated(d1)


def test_already_migrated_prints_and_exits_0_without_writes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    d1 = SqliteD1()
    _seed_fixture(d1)
    _run_main(monkeypatch, d1, execute=True)  # migrate for real once
    queries_before = len(d1.queries)

    _run_main(monkeypatch, d1, execute=True)

    assert "already migrated" in capsys.readouterr().out
    _assert_fully_migrated(d1)
    # Any number of read-only preflight queries is fine; no further writes.
    new_queries = [sql for sql, _params in d1.queries[queries_before:]]
    assert all(
        sql.strip().upper().startswith(("SELECT", "PRAGMA")) for sql in new_queries
    ), new_queries


def test_refuses_when_a_later_release_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    d1 = SqliteD1()
    _seed_fixture(d1)
    d1.query(
        "INSERT INTO data_release (version, cut_at, n_genes) VALUES ('1.3.0', 't', 3)"
    )

    with pytest.raises(SystemExit, match="1.3.0"):
        _run_main(monkeypatch, d1, execute=True)

    # Refused before any write.
    rows = d1.query(
        "SELECT COUNT(*) AS n FROM record_revision WHERE source = 'seed:zenodo-1.0.0'"
    )
    assert rows[0]["n"] == 2


def test_refuses_with_a_later_release_even_in_dry_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    d1 = SqliteD1()
    _seed_fixture(d1)
    d1.query(
        "INSERT INTO data_release (version, cut_at, n_genes) VALUES ('1.3.0', 't', 3)"
    )

    with pytest.raises(SystemExit, match="1.3.0"):
        _run_main(monkeypatch, d1, execute=False)


def test_resume_after_interruption_before_shifting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Crash right after both DELETEs (a)/(b) commit, before any shift
    UPDATE runs."""
    d1 = SqliteD1()
    _seed_fixture(d1)

    failing = _FailOnceOnSql(d1, "UPDATE record_revision SET revision =")
    _FakeCloudRevisionStore.store = FakeStore(failing)  # ty: ignore[invalid-argument-type]
    monkeypatch.setattr(_mod, "CloudRevisionStore", _FakeCloudRevisionStore)
    monkeypatch.setattr(_mod, "load_env", lambda: None)
    monkeypatch.setattr(_mod, "purge_paths", lambda *a, **kw: None)
    monkeypatch.setattr(sys, "argv", ["drop_seed_revisions.py", "--execute"])

    with pytest.raises(RuntimeError, match="simulated transient D1 failure"):
        _mod.main()

    # Confirm we really did interrupt mid-migration: both DELETEs landed
    # (seed rows gone, no 1.0.0 members) but genes still have a numbering
    # gap (not yet shifted).
    rows = d1.query(
        "SELECT COUNT(*) AS n FROM record_revision WHERE source = 'seed:zenodo-1.0.0'"
    )
    assert rows[0]["n"] == 0
    members = d1.query(
        "SELECT COUNT(*) AS n FROM data_release_member WHERE version = '1.0.0'"
    )
    assert members[0]["n"] == 0
    assert _mod.genes_needing_shift(d1) != {}

    # Resume: a fresh run against the same (now non-failing) connection
    # completes correctly.
    _run_main(monkeypatch, d1, execute=True)
    _assert_fully_migrated(d1)


def test_resume_after_interruption_mid_shift(monkeypatch: pytest.MonkeyPatch) -> None:
    """Manually apply only k=2 of the shift loop, then resume via main()."""
    d1 = SqliteD1()
    _seed_fixture(d1)

    d1.query("DELETE FROM data_release_member WHERE version = '1.0.0'")
    d1.query("DELETE FROM record_revision WHERE source = 'seed:zenodo-1.0.0'")
    # Apply only the k=2 step by hand (S100A7A: 2->1, CD63: 2->1).
    d1.query(
        "UPDATE record_revision SET revision = 1 "
        "WHERE revision = 2 AND gene_symbol IN ('S100A7A', 'CD63')"
    )
    # S100A7A is now 1,3,4 (a gap at 2); CD63 is fully done at just 1.
    gapped = _mod.genes_needing_shift(d1)
    assert set(gapped) == {"S100A7A"}

    _run_main(monkeypatch, d1, execute=True)

    _assert_fully_migrated(d1)


def test_ensure_archive_scope_column_is_idempotent() -> None:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    # A `data_release` table shaped like public D1's BEFORE this column
    # existed — CREATE TABLE IF NOT EXISTS from the current DDL would be a
    # no-op against a table like this, which is exactly why the ALTER path
    # is needed.
    con.execute(
        "CREATE TABLE data_release (version TEXT PRIMARY KEY, cut_at TEXT NOT NULL, "
        "github_tag TEXT, zenodo_version_doi TEXT, n_genes INTEGER NOT NULL, notes TEXT)"
    )

    class _Con:
        def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
            cur = con.execute(sql, params or [])
            con.commit()
            return [dict(r) for r in cur.fetchall()]

    d1 = _Con()
    _mod.ensure_archive_scope_column(d1)  # adds the column
    _mod.ensure_archive_scope_column(d1)  # already applied -> no-op, not an error

    cols = {r[1] for r in con.execute("PRAGMA table_info(data_release)").fetchall()}
    assert "archive_scope" in cols


def test_genes_needing_shift_ignores_ordinary_genes() -> None:
    d1 = SqliteD1()
    _insert_revision(d1, "EGFR", 1, source="sweep")
    _insert_revision(d1, "EGFR", 2, source="sweep")

    assert _mod.genes_needing_shift(d1) == {}
