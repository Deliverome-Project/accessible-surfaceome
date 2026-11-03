"""`CREATE TABLE IF NOT EXISTS` is a no-op on a table that exists, so a new
column in the DDL never reaches a live database.

That is not hypothetical. `candidate_id`, `library`, `numbered_against` and
`loop_run_position` were added to the DDL and to the writer's column list when
the enrichment pass was built, and the live `tag_site_public` never got them:
the writer sent 37 columns at a table with 33. Every enrichment publish would
have failed on `no such column` — discovered only because a publish was about
to be run for money.

So `ensure_table` additively backfills. Additive only: it adds columns the DDL
declares and the table lacks, and it never drops, renames or retypes anything.
A column the table has and the DDL does not is left alone — that is how a
rollback or another writer's column survives.
"""

from __future__ import annotations

import sqlite3
from typing import cast

import pytest

from accessible_surfaceome.cloud import tag_sites as TS
from accessible_surfaceome.cloud.d1_client import D1Client

#: The pre-enrichment shape: the same table minus the five columns the
#: member-keyed pass writes. Reproduces the live drift exactly.
OLD_DDL = """
CREATE TABLE tag_site_public (
    gene_symbol TEXT NOT NULL,
    uniprot_acc TEXT NOT NULL,
    site_id     TEXT NOT NULL,
    provenance  TEXT NOT NULL,
    site_kind   TEXT NOT NULL,
    insert_after_residue INTEGER,
    extracellular INTEGER NOT NULL,
    sources_json TEXT,
    tag_sites_version TEXT NOT NULL,
    synced_at   TEXT NOT NULL
);
"""


class _SqliteD1:
    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.statements: list[str] = []

    def query(self, sql, params=None):
        self.statements.append(sql.strip())
        cur = self.conn.execute(sql, params or [])
        rows = (
            [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]
            if cur.description
            else []
        )
        self.conn.commit()
        return rows

    def columns(self) -> set[str]:
        return {
            r["name"]
            for r in self.query("PRAGMA table_info(tag_site_public);")
        }


def old_table() -> _SqliteD1:
    db = _SqliteD1()
    db.query(OLD_DDL)
    return db


def test_the_missing_columns_are_added() -> None:
    """The four that were live-missing, plus position_frame."""
    db = old_table()
    TS.ensure_table(cast(D1Client, db))
    cols = db.columns()
    for name in ("candidate_id", "library", "numbered_against",
                 "loop_run_position", "position_frame"):
        assert name in cols, f"{name} was not backfilled"


def test_every_column_the_writer_sends_exists_afterwards() -> None:
    """The invariant that actually matters: a publish sends `_COLS`, so each one
    has to be a real column or the INSERT fails on `no such column`."""
    db = old_table()
    TS.ensure_table(cast(D1Client, db))
    assert set(TS._COLS) <= db.columns()


def test_it_is_additive_and_never_drops() -> None:
    """A column the table has and the DDL does not is left alone, so a rollback
    or another writer's column is not destroyed."""
    db = old_table()
    db.query("ALTER TABLE tag_site_public ADD COLUMN someone_elses_column TEXT;")
    TS.ensure_table(cast(D1Client, db))
    assert "someone_elses_column" in db.columns()
    assert not any("DROP" in s.upper() for s in db.statements)


def test_existing_rows_survive_with_null_in_the_new_columns() -> None:
    """26,719 deterministic rows are in that table. ADD COLUMN backfills NULL,
    which is correct — those rows have no candidate_id — but losing them would
    not be."""
    db = old_table()
    db.query(
        "INSERT INTO tag_site_public (gene_symbol, uniprot_acc, site_id, "
        "provenance, site_kind, extracellular, tag_sites_version, synced_at) "
        "VALUES ('MS4A1','P11836','MS4A1-surface_loop-161',"
        "'deterministic_computed','internal',1,'v1','2026-10-19');"
    )
    TS.ensure_table(cast(D1Client, db))
    rows = db.query("SELECT gene_symbol, candidate_id FROM tag_site_public;")
    assert rows == [{"gene_symbol": "MS4A1", "candidate_id": None}]


def test_a_second_call_adds_nothing() -> None:
    """Idempotent: ALTER TABLE ADD COLUMN errors on a duplicate, so a re-run
    must not reissue it. `ensure_table` here is deliberately NOT memoised —
    every publish re-checks, which is what makes a live table self-heal."""
    db = old_table()
    TS.ensure_table(cast(D1Client, db))
    first = sum(1 for s in db.statements if "ADD COLUMN" in s.upper())
    TS.ensure_table(cast(D1Client, db))
    second = sum(1 for s in db.statements if "ADD COLUMN" in s.upper())
    assert first > 0, "nothing was backfilled on the first pass"
    assert second == first, "the second pass reissued an ALTER"


def test_a_fresh_table_needs_no_backfill() -> None:
    """The CREATE path already has every column, so the common case issues no
    ALTER at all."""
    db = _SqliteD1()
    TS.ensure_table(cast(D1Client, db))
    assert set(TS._COLS) <= db.columns()
    assert not any("ADD COLUMN" in s.upper() for s in db.statements)


def test_a_missing_NOT_NULL_column_refuses_rather_than_crashing() -> None:
    """SQLite cannot ADD COLUMN for NOT NULL without a default on a populated
    table — there is no value for the existing rows. That is a real migration
    (create-copy-verify-rename, as `migrate_gene_key` does), so the backfill
    says so instead of dying on a bare sqlite3.OperationalError or, worse,
    skipping and letting the INSERT fail later on `no such column`."""
    db = _SqliteD1()
    db.query("CREATE TABLE tag_site_public (gene_symbol TEXT NOT NULL);")
    db.query("INSERT INTO tag_site_public (gene_symbol) VALUES ('MS4A1');")
    with pytest.raises(RuntimeError, match="create-copy-verify-rename"):
        TS.ensure_table(cast(D1Client, db))
