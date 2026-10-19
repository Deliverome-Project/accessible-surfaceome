"""Removes already-published rows that ``tag_sites.retracted`` has withdrawn.

The code fix stops a retracted site being published again, but a row the table is
ALREADY serving needs deleting, and re-publishing the gene to get it is the wrong
tool: the two genes in the first retraction carry different ``tag_sites_version``
stamps (ACKR3 2026-10-08, MS4A1 2026-10-11), so one sync restamps six rows to
remove two and loses that provenance. This deletes exactly the withdrawn rows.

Driven entirely by ``RETRACTED`` so growing the list never means editing the
script, and idempotent so it is safe to re-run after the next entry lands.
"""
import importlib.util
import sqlite3
import sys
from pathlib import Path
from typing import cast

from accessible_surfaceome.cloud import tag_sites as TS
from accessible_surfaceome.cloud.d1_client import D1Client

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "delete_retracted_tag_sites", REPO / "scripts/cloud/delete_retracted_tag_sites.py"
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class _SqliteD1:
    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.statements: list[str] = []

    def query(self, sql, params=None):
        self.statements.append(sql)
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


def _seed(db: _SqliteD1, rows: list[tuple[str, str, str]]) -> None:
    """rows = (gene_symbol, uniprot_acc, site_id)."""
    TS.ensure_table(cast(D1Client, db))
    cols = ", ".join(TS._COLS)
    marks = ", ".join(["?"] * len(TS._COLS))
    for gene, acc, site_id in rows:
        row = TS.flat_row(
            {
                "site_id": site_id, "gene_symbol": gene, "uniprot_acc": acc,
                "provenance": "deterministic_computed", "site_kind": "internal",
                "extracellular": True,
            },
            gene_symbol=gene, uniprot_acc=acc, version="v", synced_at="s",
        )
        db.query(f"INSERT INTO tag_site_public ({cols}) VALUES ({marks});",
                 [row[c] for c in TS._COLS])
    db.statements.clear()


def _site_ids(db: _SqliteD1) -> set[str]:
    return {r["site_id"] for r in db.query("SELECT site_id FROM tag_site_public;")}


GOOD = ("MS4A1", "P11836", "MS4A1-surface_loop-161")
BAD_MS4A1 = ("MS4A1", "P11836", "MS4A1-surface_loop-171")
BAD_ACKR3 = ("ACKR3", "P25106", "ACKR3-surface_loop-35")


def test_dry_run_issues_no_delete():
    db = _SqliteD1()
    _seed(db, [GOOD, BAD_MS4A1, BAD_ACKR3])

    n = mod.delete_retracted(cast(D1Client, db), execute=False)

    assert n == 2, "it should still report the two rows it would remove"
    assert not any("DELETE" in s.upper() for s in db.statements)
    assert _site_ids(db) == {GOOD[2], BAD_MS4A1[2], BAD_ACKR3[2]}


def test_execute_deletes_exactly_the_retracted_rows():
    db = _SqliteD1()
    _seed(db, [GOOD, BAD_MS4A1, BAD_ACKR3])

    n = mod.delete_retracted(cast(D1Client, db), execute=True)

    assert n == 2
    assert _site_ids(db) == {GOOD[2]}


def test_a_second_run_is_a_no_op():
    """Idempotent, so it is safe to re-run when the next entry is added."""
    db = _SqliteD1()
    _seed(db, [GOOD, BAD_MS4A1])
    mod.delete_retracted(cast(D1Client, db), execute=True)

    assert mod.delete_retracted(cast(D1Client, db), execute=True) == 0
    assert _site_ids(db) == {GOOD[2]}


def test_it_is_driven_by_the_retraction_list(monkeypatch):
    """A new entry in RETRACTED is picked up with no edit here — which is the whole
    reason the list and the deleter are separate things."""
    db = _SqliteD1()
    extra = ("TFRC", "P02786", "TFRC-surface_loop-291")
    _seed(db, [GOOD, extra])
    monkeypatch.setitem(
        mod.RETRACTED, (extra[1], extra[2]), "withdrawn for the purposes of this test only"
    )

    assert mod.delete_retracted(cast(D1Client, db), execute=True) == 1
    assert _site_ids(db) == {GOOD[2]}


def test_it_will_not_delete_a_matching_site_id_on_another_protein():
    """The retraction key is (accession, site_id); a symbol-keyed delete would be
    the COX1 / WAS class of bug with the blast radius pointed at live rows."""
    db = _SqliteD1()
    impostor = ("MS4A1", "P99999", "MS4A1-surface_loop-171")
    _seed(db, [impostor])

    assert mod.delete_retracted(cast(D1Client, db), execute=True) == 0
    assert _site_ids(db) == {impostor[2]}
