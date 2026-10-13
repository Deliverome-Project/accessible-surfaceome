"""``scripts/cloud/drop_seed_revisions.py`` against in-memory SQLite built
from a column-less copy of ``record_history.store.DDL`` — matching public
D1's live schema before this script's ``ensure_archive_scope_column`` has
ever run (see ``_legacy_ddl``). Same house pattern as
``tests/test_seed_record_history.py``.

Loaded via ``importlib.util.spec_from_file_location`` so the standalone
``scripts/`` entry point runs unmodified; its
``from accessible_surfaceome... import ...`` statements resolve through the
real package.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sqlite3
import sys
import tempfile
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


def _legacy_ddl() -> list[str]:
    """``store.DDL`` with `archive_scope` stripped back out of
    ``data_release`` — derived from the real DDL (not hand-duplicated) so
    it can't drift from the current schema except in the one column this
    migration exists to add. This is what public D1's live table looks
    like before ``ensure_archive_scope_column`` has ever run against it.
    """
    out = []
    for stmt in store.DDL:
        if "CREATE TABLE IF NOT EXISTS data_release " in stmt:
            stmt = re.sub(r",\s*archive_scope\s+TEXT", "", stmt)
            assert "archive_scope" not in stmt
        out.append(stmt)
    return out


class SqliteD1:
    """D1Client stand-in backed by in-memory SQLite (same SQL dialect).

    Defaults to the column-less legacy DDL (see module docstring); pass
    ``ddl=store.DDL`` for a fixture that already has `archive_scope`.
    """

    def __init__(self, ddl: list[str] | None = None) -> None:
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        for s in ddl if ddl is not None else _legacy_ddl():
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


class _InjectOnceAfterSql:
    """Wraps a ``SqliteD1``; the FIRST time a query whose SQL contains
    ``trigger`` runs, immediately afterward (against the SAME connection)
    also runs ``inject_sql`` once — simulates a concurrent write (e.g. a
    publish landing a new revision) racing this migration mid-loop."""

    def __init__(
        self, inner: SqliteD1, trigger: str, inject_sql: str, inject_params: list[Any]
    ) -> None:
        self._inner = inner
        self._trigger = trigger
        self._inject_sql = inject_sql
        self._inject_params = inject_params
        self._fired = False

    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        result = self._inner.query(sql, params)
        if not self._fired and self._trigger in sql:
            self._fired = True
            self._inner.query(self._inject_sql, self._inject_params)
        return result


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

    # BRI3BP: ONLY ever had the seed row (never re-served) -> after
    # migration it has ZERO record_revision rows; the Worker's
    # /v1/genes/BRI3BP/revisions then 404s gene_not_annotated (not
    # exercised here — this test only covers the D1-side state).
    _insert_revision(d1, "BRI3BP", 1, source="seed:zenodo-1.0.0")

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
            3,
            "Initial data deposit (Zenodo record 20805384); records as "
            "deposited, evidence inline, no Markdown.",
        ],
    )
    d1.query(
        "INSERT INTO data_release_member (version, gene_symbol, revision) "
        "VALUES ('1.0.0', 'S100A7A', 1), ('1.0.0', 'CD63', 1), ('1.0.0', 'BRI3BP', 1)"
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

    # BRI3BP: nothing left — its only revision was the seed.
    bri3bp = d1.query(
        "SELECT COUNT(*) AS n FROM record_revision WHERE gene_symbol = 'BRI3BP'"
    )
    assert bri3bp[0]["n"] == 0

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
    assert rel["n_genes"] == 3
    assert rel["archive_scope"] == "zenodo_only"
    assert "Zenodo deposit" in rel["notes"]

    # Every gene, seeded or not, is contiguous from 1 — the general
    # invariant the migration exists to restore.
    assert _mod.genes_needing_shift(d1) == {}


def _run_main(
    monkeypatch: pytest.MonkeyPatch,
    d1: Any,
    *,
    execute: bool,
    backup: Path | None = None,
) -> Path | None:
    _FakeCloudRevisionStore.store = FakeStore(d1)
    monkeypatch.setattr(_mod, "CloudRevisionStore", _FakeCloudRevisionStore)
    monkeypatch.setattr(_mod, "load_env", lambda: None)
    monkeypatch.setattr(_mod, "purge_paths", lambda *a, **kw: None)
    argv = ["drop_seed_revisions.py"]
    if execute:
        if backup is None:
            backup = Path(tempfile.mkdtemp()) / "backup.jsonl"
        argv += ["--backup", str(backup), "--execute"]
    monkeypatch.setattr(sys, "argv", argv)
    _mod.main()
    return backup


# --- basic dry-run / execute / idempotency -----------------------------


def test_dry_run_writes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    d1 = SqliteD1()
    _seed_fixture(d1)

    _run_main(monkeypatch, d1, execute=False)

    # Untouched: the seed rows are still there, and the column was never
    # added (dry-run must not ALTER either).
    rows = d1.query(
        "SELECT COUNT(*) AS n FROM record_revision WHERE source = 'seed:zenodo-1.0.0'"
    )
    assert rows[0]["n"] == 3
    members = d1.query(
        "SELECT COUNT(*) AS n FROM data_release_member WHERE version = '1.0.0'"
    )
    assert members[0]["n"] == 3
    assert not _mod.has_archive_scope_column(d1)


def test_dry_run_reports_missing_column_without_crashing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    d1 = SqliteD1()  # legacy (column-less) by construction
    _seed_fixture(d1)

    _run_main(monkeypatch, d1, execute=False)

    assert "archive_scope column missing" in capsys.readouterr().out


def test_execute_migrates_fully_from_column_less_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    d1 = SqliteD1()
    _seed_fixture(d1)
    assert not _mod.has_archive_scope_column(d1)

    _run_main(monkeypatch, d1, execute=True)

    assert _mod.has_archive_scope_column(d1)
    _assert_fully_migrated(d1)


def test_execute_migrates_fully_when_column_already_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    d1 = SqliteD1(ddl=store.DDL)  # current schema: archive_scope already there
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

    # Refused before any write (not even the ALTER or the backup).
    rows = d1.query(
        "SELECT COUNT(*) AS n FROM record_revision WHERE source = 'seed:zenodo-1.0.0'"
    )
    assert rows[0]["n"] == 3
    assert not _mod.has_archive_scope_column(d1)


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


# --- --backup ------------------------------------------------------------


def test_backup_required_with_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["drop_seed_revisions.py", "--execute"])

    with pytest.raises(SystemExit, match="--backup"):
        _mod.main()


def test_backup_captures_pre_migration_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d1 = SqliteD1()
    _seed_fixture(d1)
    backup_path = tmp_path / "backup.jsonl"

    _run_main(monkeypatch, d1, execute=True, backup=backup_path)

    entries = [json.loads(line) for line in backup_path.read_text().splitlines()]
    record_rows = [e["row"] for e in entries if e["table"] == "record_revision"]
    # Old (pre-migration) numbering: S100A7A's seed row is still at
    # revision 1 in the backup even though the live table shifted it away.
    s100 = [r for r in record_rows if r["gene_symbol"] == "S100A7A"]
    assert len(s100) == 4  # seed + 3 served, all backed up
    seed_row = next(r for r in s100 if r["source"] == "seed:zenodo-1.0.0")
    assert seed_row["revision"] == 1
    bri3bp = [r for r in record_rows if r["gene_symbol"] == "BRI3BP"]
    assert len(bri3bp) == 1  # its only (now-deleted) row, captured before the DELETE

    member_rows = [e["row"] for e in entries if e["table"] == "data_release_member"]
    assert {r["gene_symbol"] for r in member_rows} == {"S100A7A", "CD63", "BRI3BP"}

    release_rows = [e["row"] for e in entries if e["table"] == "data_release"]
    assert len(release_rows) == 1
    assert release_rows[0]["version"] == "1.0.0"

    # Never-seeded EGFR isn't in the backup at all.
    assert not [r for r in record_rows if r["gene_symbol"] == "EGFR"]


def test_backup_write_failure_refuses_before_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d1 = SqliteD1()
    _seed_fixture(d1)
    blocker = tmp_path / "not_a_directory"
    blocker.write_text("x")
    backup_path = blocker / "backup.jsonl"  # parent is a FILE -> mkdir fails

    with pytest.raises(SystemExit, match="backup write"):
        _run_main(monkeypatch, d1, execute=True, backup=backup_path)

    rows = d1.query(
        "SELECT COUNT(*) AS n FROM record_revision WHERE source = 'seed:zenodo-1.0.0'"
    )
    assert rows[0]["n"] == 3


# --- resumability / concurrency (C1) --------------------------------------


def test_shift_revisions_down_replay_after_success_is_a_noop() -> None:
    """Direct unit test of the exact bug this fix addresses: replaying the
    shift after a gene has already fully migrated must not try to move its
    (now legitimate) row at revision 2 on top of its own revision 1 —
    which, unguarded, raised a UNIQUE constraint violation."""
    d1 = SqliteD1()
    _insert_revision(d1, "S100A7A", 2, source="sweep")
    _insert_revision(d1, "S100A7A", 3, source="sweep")
    _insert_revision(d1, "S100A7A", 4, source="publish")

    _mod.shift_revisions_down(d1)
    first = [
        r["revision"]
        for r in d1.query(
            "SELECT revision FROM record_revision WHERE gene_symbol = 'S100A7A' "
            "ORDER BY revision"
        )
    ]
    assert first == [1, 2, 3]

    _mod.shift_revisions_down(d1)  # replay directly — must not raise
    second = [
        r["revision"]
        for r in d1.query(
            "SELECT revision FROM record_revision WHERE gene_symbol = 'S100A7A' "
            "ORDER BY revision"
        )
    ]
    assert second == [1, 2, 3]


def test_resume_after_crash_between_k3_and_k4(monkeypatch: pytest.MonkeyPatch) -> None:
    """Manually reach "crashed after k=3, before k=4" (S100A7A ends at
    1,2,4 — a gap at 3) by applying the guarded shifts by hand, then let a
    fresh --execute resume and finish it."""
    d1 = SqliteD1()
    _seed_fixture(d1)

    d1.query("DELETE FROM data_release_member WHERE version = '1.0.0'")
    d1.query("DELETE FROM record_revision WHERE source = 'seed:zenodo-1.0.0'")
    # k=2: 2->1 for every affected gene.
    d1.query(
        "UPDATE record_revision SET revision = 1 WHERE revision = 2 "
        "AND gene_symbol IN ('S100A7A', 'CD63')"
    )
    # k=3: 3->2, only S100A7A has a row there.
    d1.query(
        "UPDATE record_revision SET revision = 2 WHERE revision = 3 "
        "AND gene_symbol = 'S100A7A'"
    )
    s100 = d1.query(
        "SELECT revision FROM record_revision WHERE gene_symbol = 'S100A7A' "
        "ORDER BY revision"
    )
    assert [r["revision"] for r in s100] == [1, 2, 4]

    _run_main(monkeypatch, d1, execute=True)

    _assert_fully_migrated(d1)


def test_concurrent_insert_mid_loop_converges_to_contiguous(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A publish landing S100A7A's revision 5 WHILE the first shift pass is
    running (injected right after the first UPDATE commits) leaves a gap
    a single fixed-`max` pass can't reach (1,2,3,5) — the bounded outer
    loop's next pass must still converge it to 1,2,3,4."""
    d1 = SqliteD1()
    _seed_fixture(d1)
    injecting = _InjectOnceAfterSql(
        d1,
        "UPDATE record_revision SET revision = ?",
        "INSERT INTO record_revision "
        "(gene_symbol, hgnc_id, revision, json_hash, evidence_hash, md_hash, "
        " published_at, source, schema_version, prompt_corpus_version) "
        "VALUES ('S100A7A', 'HGNC:0000', 5, 's100-5', NULL, NULL, "
        " '2026-09-28T12:00:00Z', 'publish', '2.14.4', 'v9')",
        [],
    )

    _run_main(monkeypatch, injecting, execute=True)

    s100 = d1.query(
        "SELECT revision, source FROM record_revision WHERE gene_symbol = 'S100A7A' "
        "ORDER BY revision"
    )
    assert [(r["revision"], r["source"]) for r in s100] == [
        (1, "sweep"),
        (2, "sweep"),
        (3, "publish"),
        (4, "publish"),
    ]
    assert _mod.genes_needing_shift(d1) == {}


def test_resume_after_interruption_before_shifting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Crash right after both DELETEs land, before any shift UPDATE runs."""
    d1 = SqliteD1()
    _seed_fixture(d1)

    failing = _FailOnceOnSql(d1, "UPDATE record_revision SET revision =")

    with pytest.raises(RuntimeError, match="simulated transient D1 failure"):
        _run_main(monkeypatch, failing, execute=True)

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


# --- schema helpers --------------------------------------------------------


def test_ensure_archive_scope_column_is_idempotent() -> None:
    d1 = SqliteD1()  # legacy, no archive_scope yet
    assert not _mod.has_archive_scope_column(d1)

    _mod.ensure_archive_scope_column(d1)
    assert _mod.has_archive_scope_column(d1)

    _mod.ensure_archive_scope_column(d1)  # already applied -> no-op, not an error
    assert _mod.has_archive_scope_column(d1)


def test_genes_needing_shift_ignores_ordinary_genes() -> None:
    d1 = SqliteD1()
    _insert_revision(d1, "EGFR", 1, source="sweep")
    _insert_revision(d1, "EGFR", 2, source="sweep")

    assert _mod.genes_needing_shift(d1) == {}
