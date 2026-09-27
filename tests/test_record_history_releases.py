"""Release rows, member batching, DOI immutability, and the export tarball."""

from __future__ import annotations

import json
import sqlite3
import tarfile
from pathlib import Path

import pytest

from accessible_surfaceome.cloud.record_history import releases as rel
from accessible_surfaceome.cloud.record_history.store import DDL


class SqliteD1:
    """D1Client stand-in backed by in-memory SQLite (same SQL dialect)."""

    def __init__(self) -> None:
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        for s in DDL:
            self.con.execute(s)
        self.con.execute("CREATE TABLE surface_annotation (gene_symbol TEXT)")

    def query(self, sql: str, params: list | None = None) -> list[dict]:
        cur = self.con.execute(sql, params or [])
        return [dict(r) for r in cur.fetchall()]


def _rev(d1: SqliteD1, sym: str, n: int, j: str) -> None:
    d1.query(
        "INSERT INTO record_revision VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            sym,
            f"HGNC:{sym}",
            n,
            j,
            None,
            None,
            "2026-09-27T00:00:00Z",
            "sweep",
            "2.14.4",
            "2.50.2",
        ],
    )


def test_latest_members_only_live_genes_and_latest_revision() -> None:
    d1 = SqliteD1()
    _rev(d1, "A", 1, "a1")
    _rev(d1, "A", 2, "a2")
    _rev(d1, "GONE", 1, "g1")
    d1.query("INSERT INTO surface_annotation VALUES ('A')")
    assert rel.latest_members(d1) == [("A", 2)]


def test_create_release_batches_members_and_refuses_duplicates() -> None:
    d1 = SqliteD1()
    members = [(f"G{i}", 1) for i in range(70)]  # > one 33-row batch
    rel.create_release(
        d1,
        version="1.3.0",
        cut_at="2026-09-27T00:00:00Z",
        github_tag="v1.3.0",
        zenodo_version_doi=None,
        notes=None,
        members=members,
    )
    assert d1.query("SELECT n_genes FROM data_release")[0]["n_genes"] == 70
    assert d1.query("SELECT count(*) AS n FROM data_release_member")[0]["n"] == 70
    with pytest.raises(rel.ReleaseExistsError):
        rel.create_release(
            d1,
            version="1.3.0",
            cut_at="x",
            github_tag=None,
            zenodo_version_doi=None,
            notes=None,
            members=members,
        )


def test_member_batch_fits_d1_parameter_cap() -> None:
    assert rel.MEMBER_ROWS_PER_INSERT * 3 <= 100


def test_set_doi_only_once() -> None:
    d1 = SqliteD1()
    rel.create_release(
        d1,
        version="1.3.0",
        cut_at="t",
        github_tag=None,
        zenodo_version_doi=None,
        notes=None,
        members=[("A", 1)],
    )
    rel.set_zenodo_doi(d1, "1.3.0", "10.5281/zenodo.1")
    with pytest.raises(rel.ReleaseError):
        rel.set_zenodo_doi(d1, "1.3.0", "10.5281/zenodo.2")


def test_export_release_writes_parts_and_manifest(tmp_path: Path) -> None:
    d1 = SqliteD1()
    d1.query(
        "INSERT INTO record_revision VALUES (?,?,?,?,?,?,?,?,?,?)",
        ["A", "HGNC:1", 1, "j", "e", "m", "t", "sweep", "2.14.4", "2.50.2"],
    )
    rel.create_release(
        d1,
        version="1.3.0",
        cut_at="t",
        github_tag=None,
        zenodo_version_doi=None,
        notes=None,
        members=[("A", 1)],
    )
    blobs = {
        "records/sha256/j.json": b'{"r":1}',
        "records/sha256/e.json": b'{"e":1}',
        "records/sha256/m.md": b"# A",
    }
    out = rel.export_release(d1, "1.3.0", tmp_path, get_blob=blobs.__getitem__)
    assert out.name == "deep_dives_1.3.0.tar.gz"
    with tarfile.open(out) as tf:
        names = sorted(tf.getnames())
        manifest = tf.extractfile("manifest.tsv").read().decode()
        record = json.loads(tf.extractfile("genes/A.json").read())
    assert names == [
        "genes/A.evidence.json",
        "genes/A.json",
        "genes/A.md",
        "manifest.tsv",
    ]
    assert manifest.splitlines()[1] == "A\tHGNC:1\t1\tj\te\tm"
    assert record == {"r": 1}
