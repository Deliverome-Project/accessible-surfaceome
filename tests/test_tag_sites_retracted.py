"""Row-level retraction of two published internal sites that three independent
analyses rejected.

Both were published via ``surface_loop`` and both are wrong about the same thing
-- a disulfide closure -- for two different reasons:

* **MS4A1 N171** (P11836) sits four residues inside the C167-C183 bond. The bond
  IS annotated and the residue is ~12.9 A from both cysteines, so the 10 A
  ``feature_dist`` veto passes it legitimately: ``hazard_residues`` reduces a bond
  to its two cysteine positions and cannot express enclosure. The closure spans 16
  residues and the published cassette is 51 aa.
* **ACKR3 P35** (P25106) measures 3.81 A from C287's SG and 4.54 A from C34's SG.
  That bond is formed in the AlphaFold model at 2.03 A but is NOT annotated in
  UniProt, so the distance veto never saw it and reported 12.1 A of clearance.

Why a retraction list and not a gate change: the enclosure veto proper is
``insert_aa >= span`` (``features.insert_exceeds_closure``), which depends on the
cargo and so cannot be a static boolean on a site record, and the run-length
definition it would need is still being settled. Landing two definitions is what
this avoids. This suppresses the two rows the measurements name and nothing else,
on both published surfaces, so the window closes now.

Enclosure on its own is deliberately NOT retracted: a published-corpus pass over
176 internal sites found 27 strictly inside a span, 12 of them functionally
validated, at a HIGHER enclosure rate than among display-only sites.
"""
import json
import sqlite3
from typing import cast

from accessible_surfaceome.cloud import tag_sites as TS
from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.paths import REPO_ROOT
from accessible_surfaceome.tag_sites.emit import emit_tag_sites_json

TAG_SITES_DIR = REPO_ROOT / "viewer" / "public" / "tag-sites"

# (uniprot_acc, site_id) — keyed on the ACCESSION, never the bare symbol, per the
# repo's gene-identifier rule: a symbol silently resolves to the wrong protein for
# ~0.2% of human genes, and a retraction that misfires suppresses a good site.
MS4A1_BAD = ("P11836", "MS4A1-surface_loop-171")
ACKR3_BAD = ("P25106", "ACKR3-surface_loop-35")


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


def _file(symbol: str) -> dict:
    return json.loads((TAG_SITES_DIR / f"{symbol}.json").read_text())


def _site(site_id: str, *, gene: str, acc: str, provenance: str = "deterministic_computed") -> dict:
    return {
        "site_id": site_id,
        "gene_symbol": gene,
        "uniprot_acc": acc,
        "provenance": provenance,
        "det_path": "surface_loop",
        "site_kind": "internal",
        "insert_after_residue": 171,
        "extracellular": True,
    }


# ---------------------------------------------------------------- D1 publish side


def test_the_retracted_ms4a1_site_is_not_published_to_d1():
    """``rows_for_file`` is the only place a gene's JSON becomes published rows --
    both the dry-run count and the real publish go through it."""
    rows = TS.rows_for_file(_file("MS4A1"), version="t", synced_at="t")
    assert MS4A1_BAD[1] not in {r["site_id"] for r in rows}


def test_the_retracted_ackr3_site_is_not_published_to_d1():
    rows = TS.rows_for_file(_file("ACKR3"), version="t", synced_at="t")
    assert ACKR3_BAD[1] not in {r["site_id"] for r in rows}


def test_the_sibling_loop_site_of_the_same_gene_still_publishes():
    """The retraction is row-level: MS4A1's other surface_loop site is untouched,
    and so is every other provenance on ACKR3."""
    ms4a1 = {r["site_id"] for r in TS.rows_for_file(_file("MS4A1"), version="t", synced_at="t")}
    assert "MS4A1-surface_loop-161" in ms4a1
    assert "MS4A1-snorkel-c" in ms4a1

    ackr3 = {r["site_id"] for r in TS.rows_for_file(_file("ACKR3"), version="t", synced_at="t")}
    assert {"ACKR3-terminal-n", "ACKR3-disorder-9", "ACKR3-disorder-18"} <= ackr3
    assert "ACKR3-nterm-tedman" in ackr3  # screen_validated, a different pipeline


def test_publishing_deletes_a_retracted_row_already_in_the_table():
    """The point of the exercise: a row the table ALREADY serves has to go away.
    ``publish_tag_sites`` scopes its stale-row delete to the provenances it speaks
    for and keeps only the site_ids it is writing, so a retracted id is cleaned up."""
    db = _SqliteD1()
    TS.ensure_table(cast(D1Client, db))
    stale = TS.flat_row(
        _site(MS4A1_BAD[1], gene="MS4A1", acc="P11836"),
        gene_symbol="MS4A1", uniprot_acc="P11836", version="old", synced_at="old",
    )
    cols = ", ".join(TS._COLS)
    db.query(
        f"INSERT INTO tag_site_public ({cols}) VALUES ({', '.join(['?'] * len(TS._COLS))});",
        [stale[c] for c in TS._COLS],
    )
    assert db.query("SELECT site_id FROM tag_site_public;")  # the bad row is in there

    TS.publish_tag_sites(_file("MS4A1"), tag_sites_version="t", client=cast(D1Client, db))

    served = {r["site_id"] for r in db.query("SELECT site_id FROM tag_site_public;")}
    assert MS4A1_BAD[1] not in served
    assert "MS4A1-surface_loop-161" in served


def test_a_gene_whose_whole_provenance_is_retracted_still_clears_its_rows():
    """Scope has to be read from what the FILE claims, not from what survives the
    filter. Inferring it from the filtered rows would make a fully-retracted
    provenance infer an empty scope -- no DELETE -- and the stale row would be
    served forever, which is the exact failure this change exists to fix."""
    db = _SqliteD1()
    TS.ensure_table(cast(D1Client, db))
    stale = TS.flat_row(
        _site(MS4A1_BAD[1], gene="MS4A1", acc="P11836"),
        gene_symbol="MS4A1", uniprot_acc="P11836", version="old", synced_at="old",
    )
    cols = ", ".join(TS._COLS)
    db.query(
        f"INSERT INTO tag_site_public ({cols}) VALUES ({', '.join(['?'] * len(TS._COLS))});",
        [stale[c] for c in TS._COLS],
    )

    only_retracted = {
        "gene_symbol": "MS4A1",
        "uniprot_acc": "P11836",
        "sites": [_site(MS4A1_BAD[1], gene="MS4A1", acc="P11836")],
    }
    TS.publish_tag_sites(only_retracted, tag_sites_version="t", client=cast(D1Client, db))

    assert db.query("SELECT site_id FROM tag_site_public;") == []


# ------------------------------------------------------------------- JSON side


def test_the_json_writer_drops_a_retracted_site():
    """The viewer falls back to the static ``/tag-sites/{SYMBOL}.json`` asset when
    the Worker is unreachable, so suppressing in D1 alone would keep serving it."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        out = emit_tag_sites_json(
            "MS4A1", "P11836",
            [_site(MS4A1_BAD[1], gene="MS4A1", acc="P11836"),
             _site("MS4A1-surface_loop-161", gene="MS4A1", acc="P11836")],
            out_dir=tmp,
        )
        assert {s["site_id"] for s in out["sites"]} == {"MS4A1-surface_loop-161"}


def test_the_json_writer_drops_a_retracted_site_already_on_disk():
    """``emit_tag_sites_json`` MERGES with the existing file, so a retracted site
    sitting in a committed file has to be dropped on the way out too -- otherwise
    any unrelated re-run would carry it straight back."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        emit_tag_sites_json(
            "ACKR3", "P25106",
            [_site("ACKR3-disorder-9", gene="ACKR3", acc="P25106")],
            out_dir=tmp,
        )
        # simulate the committed file still carrying the bad site
        path = f"{tmp}/ACKR3.json"
        data = json.loads(open(path).read())
        data["sites"].append(_site(ACKR3_BAD[1], gene="ACKR3", acc="P25106"))
        open(path, "w").write(json.dumps(data))

        out = emit_tag_sites_json(
            "ACKR3", "P25106",
            [_site("ACKR3-disorder-18", gene="ACKR3", acc="P25106")],
            out_dir=tmp,
        )
        assert ACKR3_BAD[1] not in {s["site_id"] for s in out["sites"]}


def test_the_committed_json_no_longer_carries_the_retracted_sites():
    """The code fix stops them being re-published; this pins the DATA fix, so the
    static asset in the tree is clean without waiting for a regeneration."""
    assert MS4A1_BAD[1] not in {s["site_id"] for s in _file("MS4A1")["sites"]}
    assert ACKR3_BAD[1] not in {s["site_id"] for s in _file("ACKR3")["sites"]}


# --------------------------------------------------------------- the list itself


def test_every_retraction_names_an_accession_and_a_reason():
    from accessible_surfaceome.tag_sites import retracted as R

    assert R.RETRACTED, "the list is the record of why a row went away; never empty"
    for (acc, site_id), reason in R.RETRACTED.items():
        assert acc.startswith(("P", "Q", "O", "A")), f"{acc} is not an accession"
        assert site_id and len(reason.split()) >= 15, f"{site_id} needs a real reason"


def test_a_retraction_does_not_fire_on_a_different_protein():
    """Keyed on the accession, so the same site_id under another protein survives.
    Bare symbols misroute ~0.2% of human genes (the COX1 / WAS class)."""
    from accessible_surfaceome.tag_sites import retracted as R

    assert R.is_retracted(uniprot_acc="P11836", site_id=MS4A1_BAD[1])
    assert not R.is_retracted(uniprot_acc="P99999", site_id=MS4A1_BAD[1])
    assert not R.is_retracted(uniprot_acc="P11836", site_id="MS4A1-surface_loop-161")
