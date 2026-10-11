"""Round-trips cloud/tag_sites.py against in-memory sqlite (D1 *is* sqlite), and
pins the DDL into the checked-in public schema file."""
import json
import sqlite3

from accessible_surfaceome.cloud import tag_sites as TS
from accessible_surfaceome.paths import REPO_ROOT
from typing import cast
from accessible_surfaceome.cloud.d1_client import D1Client

TFRC = REPO_ROOT / "viewer" / "public" / "tag-sites" / "TFRC.json"


class _SqliteD1:
    """Stand-in for D1Client that replays statements against in-memory sqlite."""

    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:")

    def query(self, sql, params=None):
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


def test_publish_round_trips_tfrc():
    data = json.loads(TFRC.read_text())
    db = _SqliteD1()
    n = TS.publish_tag_sites(data, tag_sites_version="test-1", client=cast(D1Client, db))
    assert n == len(data["sites"])

    rows = db.query("SELECT * FROM tag_site_public WHERE gene_symbol = 'TFRC';")
    assert len(rows) == n
    by_id = {r["site_id"]: r for r in rows}

    s = by_id["TFRC-surface_loop-291"]
    assert s["provenance"] == "deterministic_computed"
    assert s["det_path"] == "surface_loop"
    assert s["residue_label"] and s["residue_label"].endswith("291")
    assert s["residue_range"] and "-" in s["residue_range"]  # tolerant-feature span
    assert s["extracellular"] == 1
    assert isinstance(json.loads(s["sources_json"]), list)  # sources round-trip as JSON

    # Pick the literature row STRUCTURALLY. Pinning a site_id here ties the
    # test to whatever the agent last produced: this assertion named
    # "TFRC-internal-290-lit" and broke when a re-run returned a terminal_c
    # site at 760 instead. The contract is "a literature row carries that
    # provenance and no det_path", not "this exact junction exists".
    lits = [r for r in rows if r["provenance"] == "literature_retrieved"]
    assert lits, "TFRC should carry at least one literature site"
    for lit in lits:
        assert lit["det_path"] is None
        assert lit["site_id"].endswith("-lit")
    db.close()


def test_a_re_derivation_drops_stale_sites_of_the_SAME_provenance():
    """A re-derivation that drops a site must not strand a stale row — but the
    cleanup is scoped to the provenances the file speaks for.

    This used to assert replace-all: publish a 3-site subset, expect exactly 3
    rows. That behaviour deleted a gene's deterministic rows whenever a
    literature-only file was synced, which cost 40 live rows in public D1."""
    data = json.loads(TFRC.read_text())
    db = _SqliteD1()
    TS.publish_tag_sites(data, tag_sites_version="v1", client=cast(D1Client, db))

    det = [s for s in data["sites"] if s["provenance"] == "deterministic_computed"]
    lit = [s for s in data["sites"] if s["provenance"] == "literature_retrieved"]
    assert det and lit, "fixture needs both provenances to exercise the scoping"

    # Re-derive the DETERMINISTIC side only, dropping all but one of its sites.
    fewer = {**data, "sites": det[:1]}
    TS.publish_tag_sites(fewer, tag_sites_version="v2", client=cast(D1Client, db))

    rows = db.query("SELECT site_id, provenance, tag_sites_version FROM tag_site_public;")
    kept_det = [r for r in rows if r["provenance"] == "deterministic_computed"]
    kept_lit = [r for r in rows if r["provenance"] == "literature_retrieved"]
    assert len(kept_det) == 1, "stale deterministic rows should be removed"
    assert len(kept_lit) == len(lit), "the literature rows were not this file's to delete"
    assert all(r["tag_sites_version"] == "v2" for r in kept_det)


def test_ddl_registered_in_public_schema_file():
    text = (REPO_ROOT / "cloudflare" / "d1_public_schema.sql").read_text()
    assert "CREATE TABLE IF NOT EXISTS tag_site_public" in text
    assert "idx_tag_site_symbol" in text
    assert "idx_tag_site_provenance" in text
