"""The Worker's topology release lookups (EXISTS form) match the old IN/DISTINCT form.

The old form, ``WHERE topology_version IN (SELECT DISTINCT topology_version FROM
topology_public WHERE cohort = …)``, read every row of the cohort (6k–23k rows,
three times per record) and made public D1 fragile under load. This pins the
rewritten queries to the same answers on a fixture with several releases.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

_WORKER = (
    Path(__file__).resolve().parents[1]
    / "cloudflare/workers/surfaceome_api/src/index.js"
)

_OLD = (
    "SELECT topology_version FROM topology_release WHERE topology_version IN ("
    "SELECT DISTINCT topology_version FROM topology_public WHERE cohort = ?"
    ") ORDER BY loaded_at DESC LIMIT 1"
)


def _worker_release_queries() -> dict[str, str]:
    src = _WORKER.read_text(encoding="utf-8")
    found = re.findall(
        r"`(SELECT r\.topology_version FROM topology_release r[\s\S]*?LIMIT 1)`", src
    )
    out = {}
    for sql in found:
        cohort = re.search(r"p\.cohort = '(\w+)'", sql)
        assert cohort, sql
        out[cohort.group(1)] = " ".join(sql.split())
    return out


def _fixture() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.executescript(
        """
        CREATE TABLE topology_release (topology_version TEXT PRIMARY KEY, loaded_at TEXT);
        CREATE TABLE topology_public (topology_version TEXT, cohort TEXT, uniprot_acc TEXT);
        CREATE INDEX idx_topology_public_cohort_version ON topology_public (cohort, topology_version);
        INSERT INTO topology_release VALUES
          ('topo_a', '2026-05-01'), ('topo_b', '2026-05-16'), ('topo_c', '2026-05-25'),
          ('topo_empty', '2026-06-01');
        INSERT INTO topology_public VALUES
          ('topo_a', 'human_canonical', 'P1'), ('topo_b', 'human_canonical', 'P1'),
          ('topo_b', 'human_canonical', 'P2'), ('topo_c', 'human_isoforms', 'P1-2'),
          ('topo_a', 'mouse_ortholog', 'Q1'), ('topo_b', 'mouse_ortholog', 'Q1');
        """
    )
    return con


def test_worker_has_the_three_release_lookups() -> None:
    assert set(_worker_release_queries()) == {
        "human_canonical",
        "human_isoforms",
        "mouse_ortholog",
    }


def test_exists_form_matches_old_form_for_every_cohort() -> None:
    con = _fixture()
    for cohort, sql in _worker_release_queries().items():
        new = con.execute(sql).fetchall()
        old = con.execute(_OLD, [cohort]).fetchall()
        assert new == old, cohort
    # A release that exists but has no rows for the cohort is never chosen.
    assert con.execute(_worker_release_queries()["human_canonical"]).fetchall() == [
        ("topo_b",)
    ]


def test_cohort_with_no_rows_returns_nothing() -> None:
    con = _fixture()
    sql = _worker_release_queries()["human_isoforms"].replace(
        "human_isoforms", "cyno_ortholog"
    )
    assert con.execute(sql).fetchall() == []
