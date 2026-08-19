"""Round-trips cloud/tag_sites.py against in-memory sqlite (D1 *is* sqlite), and
pins the DDL into the checked-in public schema file."""
import json
import sqlite3

from accessible_surfaceome.cloud import tag_sites as TS
from accessible_surfaceome.paths import REPO_ROOT

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
    n = TS.publish_tag_sites(data, tag_sites_version="test-1", client=db)
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

    lit = by_id["TFRC-internal-290-lit"]
    assert lit["provenance"] == "literature_retrieved"
    assert lit["det_path"] is None
    db.close()


def test_replace_all_per_gene_drops_stale_sites():
    data = json.loads(TFRC.read_text())
    db = _SqliteD1()
    TS.publish_tag_sites(data, tag_sites_version="v1", client=db)
    fewer = {**data, "sites": data["sites"][:3]}
    TS.publish_tag_sites(fewer, tag_sites_version="v2", client=db)

    rows = db.query("SELECT site_id, tag_sites_version FROM tag_site_public;")
    assert len(rows) == 3  # stale sites removed, not just upserted
    assert all(r["tag_sites_version"] == "v2" for r in rows)
    db.close()


def test_ddl_registered_in_public_schema_file():
    text = (REPO_ROOT / "cloudflare" / "d1_public_schema.sql").read_text()
    assert "CREATE TABLE IF NOT EXISTS tag_site_public" in text
    assert "idx_tag_site_symbol" in text
    assert "idx_tag_site_provenance" in text
