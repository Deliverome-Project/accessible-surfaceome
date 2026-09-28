"""Release rows, member batching, DOI immutability, and the export tarball."""

from __future__ import annotations

import hashlib
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


class FlakySqliteD1(SqliteD1):
    """Raises exactly once, on the N-th ``query`` call.

    Simulates a transient D1 write failure partway through
    :func:`releases.create_release` — e.g. a network blip mid-batch — so
    the "partial failure leaves no release row, and a retry succeeds"
    contract can be exercised deterministically.
    """

    def __init__(self, fail_on_call: int) -> None:
        super().__init__()
        self._fail_on_call = fail_on_call
        self._calls = 0
        self._already_failed = False

    def query(self, sql: str, params: list | None = None) -> list[dict]:
        self._calls += 1
        if not self._already_failed and self._calls == self._fail_on_call:
            self._already_failed = True
            raise RuntimeError("simulated transient D1 failure")
        return super().query(sql, params)


def _member(tf: tarfile.TarFile, name: str) -> bytes:
    fh = tf.extractfile(name)
    assert fh is not None, f"{name} missing from export"
    return fh.read()


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


def test_latest_members_matches_case_insensitively() -> None:
    d1 = SqliteD1()
    _rev(d1, "C11orf24", 1, "h1")
    d1.query("INSERT INTO surface_annotation VALUES ('C11ORF24')")
    assert rel.latest_members(d1) == [("C11orf24", 1)]


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


def test_create_release_refuses_empty_members() -> None:
    d1 = SqliteD1()
    with pytest.raises(rel.ReleaseError):
        rel.create_release(
            d1,
            version="1.3.0",
            cut_at="t",
            github_tag=None,
            zenodo_version_doi=None,
            notes=None,
            members=[],
        )


def test_create_release_refuses_case_insensitive_duplicate_members() -> None:
    d1 = SqliteD1()
    with pytest.raises(rel.ReleaseError):
        rel.create_release(
            d1,
            version="1.3.0",
            cut_at="t",
            github_tag=None,
            zenodo_version_doi=None,
            notes=None,
            members=[("A", 1), ("a", 2)],
        )


def test_create_release_partial_failure_leaves_no_release_row_and_retry_succeeds() -> (
    None
):
    d1 = FlakySqliteD1(
        fail_on_call=4
    )  # 1=exists check 2=delete 3=batch1 4=batch2(fails)
    members = [(f"G{i}", 1) for i in range(40)]  # 2 batches: 33 + 7
    with pytest.raises(RuntimeError):
        rel.create_release(
            d1,
            version="1.3.0",
            cut_at="t",
            github_tag=None,
            zenodo_version_doi=None,
            notes=None,
            members=members,
        )
    assert d1.query("SELECT 1 FROM data_release WHERE version = ?", ["1.3.0"]) == []

    # Re-run on the same (now non-flaky) connection succeeds and lands
    # exactly the right rows, even though the failed attempt left 33
    # orphaned member rows behind.
    rel.create_release(
        d1,
        version="1.3.0",
        cut_at="t",
        github_tag=None,
        zenodo_version_doi=None,
        notes=None,
        members=members,
    )
    assert d1.query("SELECT n_genes FROM data_release")[0]["n_genes"] == 40
    assert d1.query("SELECT count(*) AS n FROM data_release_member")[0]["n"] == 40


def test_member_insert_is_idempotent_under_retry() -> None:
    d1 = SqliteD1()
    members = [("A", 1), ("B", 1)]
    rel.create_release(
        d1,
        version="1.3.0",
        cut_at="t",
        github_tag=None,
        zenodo_version_doi=None,
        notes=None,
        members=members,
    )
    # Simulate an at-least-once HTTP retry replaying the same member batch
    # after it actually already landed.
    d1.query(
        "INSERT INTO data_release_member (version, gene_symbol, revision) "
        "VALUES (?, ?, ?), (?, ?, ?) ON CONFLICT(version, gene_symbol) DO NOTHING",
        ["1.3.0", "A", 1, "1.3.0", "B", 1],
    )
    assert d1.query("SELECT count(*) AS n FROM data_release_member")[0]["n"] == 2


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


def test_set_doi_validates_format() -> None:
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
    with pytest.raises(rel.ReleaseError):
        rel.set_zenodo_doi(d1, "1.3.0", "not-a-doi")


def test_set_doi_no_such_release() -> None:
    d1 = SqliteD1()
    with pytest.raises(rel.ReleaseError):
        rel.set_zenodo_doi(d1, "9.9.9", "10.5281/zenodo.1")


def test_set_doi_retry_with_same_doi_is_idempotent() -> None:
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
    rel.set_zenodo_doi(d1, "1.3.0", "10.5281/zenodo.1")  # retried write, same DOI
    assert d1.query("SELECT zenodo_version_doi FROM data_release")[0][
        "zenodo_version_doi"
    ] == ("10.5281/zenodo.1")


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
        manifest = _member(tf, "manifest.tsv").decode()
        record = json.loads(_member(tf, "genes/A.json"))
    assert names == [
        "genes/A.evidence.json",
        "genes/A.json",
        "genes/A.md",
        "manifest.tsv",
    ]
    assert manifest.splitlines()[1] == "A\tHGNC:1\t1\tj\te\tm"
    assert record == {"r": 1}
    assert not (tmp_path / "deep_dives_1.3.0.tar.gz.partial").exists()


def test_export_release_is_byte_reproducible(tmp_path: Path) -> None:
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
    out1_dir, out2_dir = tmp_path / "one", tmp_path / "two"
    out1_dir.mkdir()
    out2_dir.mkdir()
    out1 = rel.export_release(d1, "1.3.0", out1_dir, get_blob=blobs.__getitem__)
    out2 = rel.export_release(d1, "1.3.0", out2_dir, get_blob=blobs.__getitem__)
    assert (
        hashlib.sha256(out1.read_bytes()).hexdigest()
        == hashlib.sha256(out2.read_bytes()).hexdigest()
    )


def test_export_release_missing_blob_leaves_no_partial_or_final(tmp_path: Path) -> None:
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

    def missing(_key: str) -> bytes:
        raise KeyError("blob not found")

    with pytest.raises(KeyError):
        rel.export_release(d1, "1.3.0", tmp_path, get_blob=missing)
    assert not (tmp_path / "deep_dives_1.3.0.tar.gz").exists()
    assert not (tmp_path / "deep_dives_1.3.0.tar.gz.partial").exists()


def test_export_release_rejects_unsafe_gene_symbol(tmp_path: Path) -> None:
    d1 = SqliteD1()
    d1.query(
        "INSERT INTO record_revision VALUES (?,?,?,?,?,?,?,?,?,?)",
        ["../evil", "HGNC:1", 1, "j", None, None, "t", "sweep", "2.14.4", "2.50.2"],
    )
    rel.create_release(
        d1,
        version="1.3.0",
        cut_at="t",
        github_tag=None,
        zenodo_version_doi=None,
        notes=None,
        members=[("../evil", 1)],
    )
    with pytest.raises(rel.ReleaseError):
        rel.export_release(d1, "1.3.0", tmp_path, get_blob=lambda _k: b"x")
