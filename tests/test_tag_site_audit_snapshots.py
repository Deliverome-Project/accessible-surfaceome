"""The literature audit cannot be undone by a snapshot sync.

Three things together close that hole: the 18 withdrawn ids are in
``tag_sites.retracted`` (so nothing re-emits them), the committed snapshots'
literature sites equal the served rows (so a sync changes nothing), and the
loader refuses to let an older-stamped publish overwrite or delete a
newer-stamped live row.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sqlite3
import sys
from typing import cast

import pytest

from accessible_surfaceome.cloud import tag_sites as TS
from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.paths import REPO_ROOT
from accessible_surfaceome.tag_sites.retracted import RETRACTED, drop_retracted

AUDIT_DIR = REPO_ROOT / "data" / "analysis" / "tag_site_corpus_audit"
SNAPSHOT_DIR = REPO_ROOT / "viewer" / "public" / "tag-sites"
WITHDRAWN = {"not_supported", "wrong_species_numbering", "terminal_misfiled"}

_spec = importlib.util.spec_from_file_location(
    "refresh_tag_site_lit_snapshots",
    REPO_ROOT / "scripts/refresh_tag_site_lit_snapshots.py",
)
assert _spec and _spec.loader
refresh = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = refresh
_spec.loader.exec_module(refresh)


def _audit() -> list[dict[str, str]]:
    with (AUDIT_DIR / "audit.tsv").open(newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _rows_after() -> list[dict]:
    return json.loads((AUDIT_DIR / "rows_after.json").read_text())


class _SqliteD1:
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


# --- 1. the withdrawn ids are retracted ----------------------------------------


def test_every_withdrawn_audit_row_is_retracted_under_its_accession():
    withdrawn = {
        (a["uniprot_acc"], a["site_id"]) for a in _audit() if a["verdict"] in WITHDRAWN
    }
    assert len(withdrawn) == 18
    assert withdrawn <= set(RETRACTED)
    for key in withdrawn:
        assert "PR 236" in RETRACTED[key] and "verdict" in RETRACTED[key]


def test_no_surviving_audit_row_is_retracted():
    survivors = {(r["uniprot_acc"], r["site_id"]) for r in _rows_after()}
    assert not survivors & set(RETRACTED)


def test_drop_retracted_removes_a_withdrawn_site_on_the_way_into_a_snapshot():
    sites = [
        {"site_id": "ABCC2-internal-163-lit", "uniprot_acc": "Q92887"},
        {"site_id": "ABCC2-terminal_n-4-lit", "uniprot_acc": "Q92887"},
    ]
    kept = drop_retracted(sites, uniprot_acc="Q92887")
    assert [s["site_id"] for s in kept] == ["ABCC2-terminal_n-4-lit"]


# --- 2. the snapshots equal the served rows -----------------------------------


def test_committed_snapshots_are_what_the_refresh_produces(tmp_path):
    """Regenerate into a temp copy and compare: the committed files must not
    have been hand-edited away from their inputs."""
    rows_after = _rows_after()
    genes = sorted({r["gene_symbol"] for r in rows_after})
    for g in genes:
        (tmp_path / f"{g}.json").write_text((SNAPSHOT_DIR / f"{g}.json").read_text())
    refresh.refresh_all(tmp_path)
    for g in genes:
        assert json.loads((tmp_path / f"{g}.json").read_text()) == json.loads(
            (SNAPSHOT_DIR / f"{g}.json").read_text()
        ), g


def test_snapshot_literature_sites_round_trip_to_the_audited_rows():
    """``flat_row`` over the snapshot gives back exactly the D1 row PR 459 wrote,
    version included, so a sync re-stamps nothing."""
    after = {r["site_id"]: r for r in _rows_after()}
    seen = 0
    for g in sorted({r["gene_symbol"] for r in after.values()}):
        data = json.loads((SNAPSHOT_DIR / f"{g}.json").read_text())
        for row in TS.rows_for_file(data, version="would-restamp", synced_at="x"):
            if row["site_id"] not in after:
                continue
            seen += 1
            expect = {**after[row["site_id"]], "synced_at": "x"}
            assert row == expect, row["site_id"]
    assert seen == len(after)


def test_snapshots_carry_the_genes_other_literature_rows_too():
    """A provenance-scoped sync deletes every literature row the file lacks, so
    the un-audited rows (terminal tags etc.) must be in the snapshot as well."""
    other = json.loads((AUDIT_DIR / "live_other_lit_rows.json").read_text())
    assert other, "fixture should hold the un-audited literature rows"
    for r in other:
        data = json.loads((SNAPSHOT_DIR / f"{r['gene_symbol']}.json").read_text())
        ids = {s["site_id"] for s in data["sites"]}
        assert r["site_id"] in ids, r["site_id"]


def test_no_snapshot_carries_a_withdrawn_id():
    withdrawn = {a["site_id"] for a in _audit() if a["verdict"] in WITHDRAWN}
    for path in SNAPSHOT_DIR.glob("*.json"):
        ids = {s["site_id"] for s in json.loads(path.read_text()).get("sites", [])}
        assert not ids & withdrawn, path.name


@pytest.mark.network
def test_dry_run_sync_of_the_snapshots_changes_nothing_live():
    """What a ``--provenance literature_retrieved`` sync of the audited genes'
    snapshots would write is exactly what public D1 serves."""
    from accessible_surfaceome.env import load_env

    load_env()
    genes = sorted({r["gene_symbol"] for r in _rows_after()})
    with D1Client.public() as d1:
        live: dict[str, dict] = {}
        for i in range(0, len(genes), 90):
            ch = genes[i : i + 90]
            marks = ", ".join("?" * len(ch))
            for r in d1.query(
                "SELECT * FROM tag_site_public WHERE provenance = 'literature_retrieved' "
                f"AND gene_symbol IN ({marks});",
                ch,
            ):
                live[r["site_id"]] = r
    would_write: dict[str, dict] = {}
    for g in genes:
        data = json.loads((SNAPSHOT_DIR / f"{g}.json").read_text())
        for row in TS.rows_for_file(data, version="dev", synced_at="x"):
            if row["provenance"] == "literature_retrieved":
                would_write[row["site_id"]] = row
    assert set(would_write) == set(live), "a sync would add or delete literature rows"
    for sid, row in would_write.items():
        assert row == {**live[sid], "synced_at": "x"}, sid


# --- 3. the loader will not downgrade a newer live row ------------------------


def _site(site_id: str, residue: int, version: str | None = None) -> dict:
    s = {
        "site_id": site_id,
        "gene_symbol": "GENEX",
        "uniprot_acc": "P00001",
        "provenance": "literature_retrieved",
        "site_kind": "internal",
        "insert_after_residue": residue,
        "residue_before": "A",
        "residue_after": "C",
        "residue_label": f"A{residue}",
        "extracellular": True,
        "compartment": "extracellular",
        "sources": [],
    }
    if version:
        s["tag_sites_version"] = version
    return s


def _file(*sites: dict) -> dict:
    return {"gene_symbol": "GENEX", "uniprot_acc": "P00001", "sites": list(sites)}


def test_version_date_parses_dated_stamps_only():
    assert str(TS.version_date("2026-11-05-lit-audit")) == "2026-11-05"
    assert str(TS.version_date("2026-10-11")) == "2026-10-11"
    assert TS.version_date("dev") is None
    assert TS.version_date("literature_enriched_v1") is None
    assert TS.version_date(None) is None


def test_a_site_keeps_its_own_version_and_takes_the_runs_when_it_has_none():
    with_own = TS.flat_row(
        _site("GENEX-internal-10-lit", 10, "2026-11-05-lit-audit"),
        gene_symbol="GENEX",
        uniprot_acc="P00001",
        version="dev",
        synced_at="x",
    )
    without = TS.flat_row(
        _site("GENEX-internal-11-lit", 11),
        gene_symbol="GENEX",
        uniprot_acc="P00001",
        version="dev",
        synced_at="x",
    )
    assert with_own["tag_sites_version"] == "2026-11-05-lit-audit"
    assert without["tag_sites_version"] == "dev"


def test_an_older_publish_neither_overwrites_nor_deletes_a_newer_live_row():
    db = cast(D1Client, _SqliteD1())
    # The audit wrote the corrected residue (105) and withdrew nothing else yet.
    TS.publish_tag_sites(
        _file(_site("GENEX-internal-101-lit", 105)),
        tag_sites_version="2026-11-05-lit-audit",
        client=db,
    )
    # An old snapshot: the wrong residue at the same id, plus a row the audit
    # never saw, stamped with the earlier sweep date.
    n = TS.publish_tag_sites(
        _file(
            _site("GENEX-internal-101-lit", 101), _site("GENEX-internal-200-lit", 200)
        ),
        tag_sites_version="2026-10-11",
        client=db,
    )
    rows = {r["site_id"]: r for r in db.query("SELECT * FROM tag_site_public;")}
    assert rows["GENEX-internal-101-lit"]["insert_after_residue"] == 105
    assert rows["GENEX-internal-101-lit"]["tag_sites_version"] == "2026-11-05-lit-audit"
    assert (
        rows["GENEX-internal-200-lit"]["insert_after_residue"] == 200
    )  # new rows still land
    assert n == 1


def test_an_older_publish_that_lacks_the_newer_row_does_not_delete_it():
    db = cast(D1Client, _SqliteD1())
    TS.publish_tag_sites(
        _file(_site("GENEX-internal-101-lit", 105)),
        tag_sites_version="2026-11-05-lit-audit",
        client=db,
    )
    TS.publish_tag_sites(
        _file(_site("GENEX-internal-200-lit", 200)),
        tag_sites_version="2026-10-11",
        client=db,
        provenances=["literature_retrieved"],
    )
    ids = {r["site_id"] for r in db.query("SELECT site_id FROM tag_site_public;")}
    assert ids == {"GENEX-internal-101-lit", "GENEX-internal-200-lit"}


def test_allow_downgrade_is_the_explicit_override():
    db = cast(D1Client, _SqliteD1())
    TS.publish_tag_sites(
        _file(_site("GENEX-internal-101-lit", 105)),
        tag_sites_version="2026-11-05-lit-audit",
        client=db,
    )
    TS.publish_tag_sites(
        _file(_site("GENEX-internal-101-lit", 101)),
        tag_sites_version="2026-10-11",
        client=db,
        allow_downgrade=True,
    )
    (row,) = db.query(
        "SELECT insert_after_residue, tag_sites_version FROM tag_site_public;"
    )
    assert (row["insert_after_residue"], row["tag_sites_version"]) == (
        101,
        "2026-10-11",
    )


def test_a_same_or_newer_publish_and_an_undated_one_are_not_blocked():
    db = cast(D1Client, _SqliteD1())
    TS.publish_tag_sites(
        _file(_site("GENEX-internal-101-lit", 105)),
        tag_sites_version="2026-11-05-lit-audit",
        client=db,
    )
    TS.publish_tag_sites(
        _file(_site("GENEX-internal-101-lit", 106)),
        tag_sites_version="2026-11-05-lit-audit",
        client=db,
    )
    (row,) = db.query("SELECT insert_after_residue FROM tag_site_public;")
    assert row["insert_after_residue"] == 106
    # "dev" has no date: no comparison, so it writes (the pre-existing behaviour).
    TS.publish_tag_sites(
        _file(_site("GENEX-internal-101-lit", 107)), tag_sites_version="dev", client=db
    )
    (row,) = db.query("SELECT insert_after_residue FROM tag_site_public;")
    assert row["insert_after_residue"] == 107


def test_the_snapshot_rows_themselves_protect_each_other_by_date():
    """A row carrying its own newer stamp in the file is compared by THAT stamp:
    a run version of 2026-10-11 does not protect the live 2026-11-05 row from a
    file row that is itself 2026-11-05 (it is the same correction)."""
    live = [
        {"site_id": "A", "tag_sites_version": "2026-11-05-lit-audit"},
        {"site_id": "B", "tag_sites_version": "2026-11-05-lit-audit"},
        {"site_id": "C", "tag_sites_version": "dev"},
    ]
    protected = TS.newer_live_rows(
        live, {"A": "2026-11-05-lit-audit", "B": "2026-10-11"}, "2026-10-11"
    )
    assert protected == {"B"}
