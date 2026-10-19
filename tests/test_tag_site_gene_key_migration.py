"""Re-keying ``tag_site_gene_public`` so a gene can carry more than one search.

The table's claim is "this gene was searched, under this prompt, on this date",
and presence of the row is what distinguishes "no published tag site exists" from
"we have not got to it yet" — 1,415 of its 2,370 rows are exactly that dated
zero. Its primary key is ``gene_symbol`` alone, so an enrichment run writing a
second search for the same gene would OVERWRITE the first and destroy the very
fact the table exists to preserve.

D1 cannot ``ALTER`` a primary key, so the migration is create-copy-verify-rename,
one statement per HTTP call.

The new key is ``(gene_symbol, candidate_id, run_series)``. ``candidate_id``
because the enrichment's unit is the library MEMBER and 45 of the 518
internal-site genes have more than one, 7 of them disagreeing about where the
tag goes; ``run_series`` because the two passes are different searches of the
same gene and both answers are worth keeping.

Existing rows migrate to ``candidate_id = ''`` — gene-level, no specific member —
and ``run_series = 'literature_v1'``. Empty string rather than NULL because a
NULL in a primary key does not compare equal to itself, so NULL-keyed rows would
silently multiply on every UPSERT.

ORDERING THIS MIGRATION DOES NOT FIX: the Worker reads this table with
``.first()`` and no ``ORDER BY``. While every gene still has exactly one row that
is deterministic, and the migration itself preserves that — but writing
enrichment rows before the Worker is taught to choose would make a gene answer
differently depending on which row came back. Migrate, then deploy the Worker,
then write.
"""

from __future__ import annotations

import sqlite3
from typing import cast

from accessible_surfaceome.cloud import tag_site_genes as TG
from accessible_surfaceome.cloud.d1_client import D1Client

LEGACY_DDL = """
CREATE TABLE tag_site_gene_public (
    gene_symbol          TEXT PRIMARY KEY,
    uniprot_acc          TEXT,
    searched_at          TEXT,
    prompt_sha           TEXT,
    prompt_version       TEXT,
    model                TEXT,
    schema_version       TEXT,
    n_papers             INTEGER,
    n_sites              INTEGER NOT NULL DEFAULT 0,
    n_other_positions    INTEGER NOT NULL DEFAULT 0,
    other_positions_json TEXT,
    notes                TEXT,
    tag_sites_version    TEXT,
    synced_at            TEXT
);
"""


class _SqliteD1:
    def __init__(self, swallow_prefix: str | None = None) -> None:
        self.conn = sqlite3.connect(":memory:")
        #: An explicit failure seam: statements starting with this prefix are
        #: silently dropped, which simulates a copy that loses rows. An
        #: attribute is used rather than reassigning the bound method, so the
        #: stub stays type-checkable.
        self.swallow_prefix = swallow_prefix
        self.swallowed = 0

    def query(self, sql, params=None):
        if self.swallow_prefix and sql.strip().upper().startswith(
            self.swallow_prefix.upper()
        ):
            self.swallowed += 1
            return []
        cur = self.conn.execute(sql, params or [])
        rows = (
            [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]
            if cur.description
            else []
        )
        self.conn.commit()
        return rows

    def close(self) -> None:
        self.conn.close()


def legacy_db(
    n_genes: int = 5, zeros: int = 3, swallow_prefix: str | None = None
) -> _SqliteD1:
    db = _SqliteD1(swallow_prefix=swallow_prefix)
    db.query(LEGACY_DDL)
    for i in range(n_genes):
        db.query(
            "INSERT INTO tag_site_gene_public (gene_symbol, uniprot_acc, "
            "searched_at, prompt_sha, prompt_version, n_papers, n_sites, "
            "n_other_positions, other_positions_json, notes, tag_sites_version, "
            "synced_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?);",
            [f"GENE{i}", f"P{i}", "2026-01-01", "sha-v1", "1.4.0", 70,
             0 if i < zeros else 2, 0, "[]", "", "v1", "2026-01-01"],
        )
    return db


def _run(db) -> dict:
    return TG.migrate_gene_key(cast(D1Client, db), execute=True)


# --------------------------------------------------------------------------
# the migration
# --------------------------------------------------------------------------


def test_every_row_survives_with_the_legacy_series_label() -> None:
    db = legacy_db()
    report = _run(db)
    assert report["copied"] == 5
    assert report["before"] == report["after"] == 5
    rows = db.query("SELECT * FROM tag_site_gene_public ORDER BY gene_symbol;")
    assert len(rows) == 5
    assert {r["run_series"] for r in rows} == {"literature_v1"}
    assert {r["candidate_id"] for r in rows} == {""}


def test_the_dated_zeros_survive_as_zeros() -> None:
    """The whole point of the table. A zero that loses its date has to be
    re-run before it can be trusted, so losing one costs a real literature
    search."""
    db = legacy_db(n_genes=5, zeros=3)
    _run(db)
    zeros = db.query("SELECT gene_symbol, prompt_sha, searched_at FROM "
                     "tag_site_gene_public WHERE n_sites = 0;")
    assert len(zeros) == 3
    for z in zeros:
        assert z["prompt_sha"] == "sha-v1"
        assert z["searched_at"] == "2026-01-01"


def test_the_old_table_is_kept_as_a_backup_not_dropped() -> None:
    """A rename is reversible while the old bytes still exist; a DROP is not."""
    db = legacy_db()
    _run(db)
    names = {
        r["name"]
        for r in db.query("SELECT name FROM sqlite_master WHERE type='table';")
    }
    assert "tag_site_gene_public" in names
    assert any(n.startswith("tag_site_gene_public_legacy") for n in names)


def test_a_count_mismatch_aborts_before_the_rename() -> None:
    """Verify-then-rename. If the copy lost rows, the live table must be left
    exactly as it was rather than replaced by a short one."""
    # Swallow the INSERT..SELECT so the copy comes out empty.
    db = legacy_db(swallow_prefix="INSERT INTO TAG_SITE_GENE_PUBLIC_V2")
    report = TG.migrate_gene_key(cast(D1Client, db), execute=True)
    assert db.swallowed == 1
    assert report["aborted"] is True
    # The live table is untouched and still legacy-keyed.
    cols = {c["name"] for c in db.query("PRAGMA table_info(tag_site_gene_public);")}
    assert "candidate_id" not in cols
    assert len(db.query("SELECT * FROM tag_site_gene_public;")) == 5


def test_a_dry_run_changes_nothing() -> None:
    db = legacy_db()
    report = TG.migrate_gene_key(cast(D1Client, db), execute=False)
    assert report["executed"] is False
    assert report["before"] == 5
    cols = {c["name"] for c in db.query("PRAGMA table_info(tag_site_gene_public);")}
    assert "candidate_id" not in cols


def test_the_migration_is_idempotent() -> None:
    """Re-running after a success must be a no-op, not a second rename that
    buries the real table behind two backups."""
    db = legacy_db()
    _run(db)
    report = _run(db)
    assert report["already_migrated"] is True
    assert len(db.query("SELECT * FROM tag_site_gene_public;")) == 5


# --------------------------------------------------------------------------
# what the new key buys
# --------------------------------------------------------------------------


def test_two_searches_of_one_gene_now_coexist() -> None:
    db = legacy_db(n_genes=1, zeros=0)
    _run(db)
    TG.publish_gene_rows(
        [
            {
                "gene_symbol": "GENE0", "candidate_id": "l1-p0001",
                "run_series": "literature_enriched_v1", "uniprot_acc": "P0",
                "searched_at": "2026-10-15", "prompt_sha": "sha-v2",
                "prompt_version": "2.0.0", "model": "m", "schema_version": "1.1.0",
                "n_papers": 300, "n_sites": 1, "n_other_positions": 0,
                "other_positions_json": "[]", "notes": "", "tag_sites_version": "v2",
                "synced_at": "2026-10-15",
            }
        ],
        client=cast(D1Client, db),
    )
    rows = db.query("SELECT run_series, candidate_id, n_sites FROM "
                    "tag_site_gene_public ORDER BY run_series;")
    assert len(rows) == 2
    assert [r["run_series"] for r in rows] == [
        "literature_enriched_v1", "literature_v1",
    ]


def test_two_members_of_one_gene_are_two_searches() -> None:
    """45 of the 518 genes have several internal-site members. Each is its own
    search of its own construct, and 7 of those pairs disagree about where the
    tag can go."""
    db = legacy_db(n_genes=1, zeros=0)
    _run(db)
    base = {
        "gene_symbol": "GENE0", "run_series": "literature_enriched_v1",
        "uniprot_acc": "P0", "searched_at": "2026-10-15", "prompt_sha": "sha-v2",
        "prompt_version": "2.0.0", "model": "m", "schema_version": "1.1.0",
        "n_papers": 300, "n_other_positions": 0, "other_positions_json": "[]",
        "notes": "", "tag_sites_version": "v2", "synced_at": "2026-10-15",
    }
    TG.publish_gene_rows(
        [
            {**base, "candidate_id": "l1-p0001", "n_sites": 1},
            {**base, "candidate_id": "l1-p2461", "n_sites": 0},
        ],
        client=cast(D1Client, db),
    )
    rows = db.query("SELECT candidate_id, n_sites FROM tag_site_gene_public "
                    "WHERE run_series = 'literature_enriched_v1' "
                    "ORDER BY candidate_id;")
    assert [(r["candidate_id"], r["n_sites"]) for r in rows] == [
        ("l1-p0001", 1), ("l1-p2461", 0),
    ]


def test_republishing_one_member_is_still_an_upsert() -> None:
    """Idempotence has to survive the wider key, or a re-run multiplies rows."""
    db = legacy_db(n_genes=1, zeros=0)
    _run(db)
    row = {
        "gene_symbol": "GENE0", "candidate_id": "l1-p0001",
        "run_series": "literature_enriched_v1", "uniprot_acc": "P0",
        "searched_at": "2026-10-15", "prompt_sha": "sha-v2",
        "prompt_version": "2.0.0", "model": "m", "schema_version": "1.1.0",
        "n_papers": 300, "n_sites": 1, "n_other_positions": 0,
        "other_positions_json": "[]", "notes": "", "tag_sites_version": "v2",
        "synced_at": "2026-10-15",
    }
    TG.publish_gene_rows([row], client=cast(D1Client, db))
    TG.publish_gene_rows([{**row, "n_sites": 3}], client=cast(D1Client, db))
    rows = db.query("SELECT n_sites FROM tag_site_gene_public "
                    "WHERE candidate_id = 'l1-p0001';")
    assert [r["n_sites"] for r in rows] == [3]


def test_the_new_columns_are_in_both_schema_files() -> None:
    from accessible_surfaceome.paths import REPO_ROOT

    for rel in ("cloudflare/d1_public_schema.sql", "cloudflare/d1_tag_sites_schema.sql"):
        text = (REPO_ROOT / rel).read_text()
        # Absent is a FAILURE, not a skip. The table was live and in neither
        # schema file, and a test that skipped on absence is exactly how that
        # survived — the same drift the site table had for five columns.
        assert "tag_site_gene_public" in text, rel
        assert "run_series" in text, rel
        assert "candidate_id" in text, rel
        assert "PRIMARY KEY (gene_symbol, candidate_id, run_series)" in text, rel
