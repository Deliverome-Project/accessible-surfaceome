"""Publishing the enrichment pass ADDITIVELY, beside the first pass.

The requirement is that a second literature pass never removes what the first
one published. That is not fastidiousness: the pool is not monotonic across
runs — 179 papers degraded to abstract-only across one 20-gene sweep, and
SLC6A3 consequently returned 7 sites then 3 — so a pass that found less than its
predecessor is the NORMAL case under transient upstream failure. If publishing
replaced rather than added, a publisher's 500 would delete four real published
sites.

Two mechanisms, both pinned here:

* the enrichment writes under its own provenance, and ``publish_tag_sites``
  scopes its stale-row cleanup to the provenances it speaks for;
* an enriched ``site_id`` carries the ``candidate_id`` and an ``-enr`` suffix, so
  it cannot collide with a ``-lit`` row even at the same junction — and two
  members of one gene cannot collide with each other, which matters because 45
  of the 518 genes have more than one member and 7 of those disagree about where
  the tag goes.
"""

from __future__ import annotations

import json
import sqlite3
from typing import cast

from accessible_surfaceome.cloud import tag_sites as TS
from accessible_surfaceome.cloud.d1_client import D1Client

ENRICHED = "literature_enriched"


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


def site(
    site_id: str,
    *,
    provenance: str,
    junction: int,
    candidate_id: str | None = None,
    position_frame: str | None = None,
    numbered_against: str | None = None,
    loop_run_position: str | None = None,
) -> dict:
    return {
        "site_id": site_id,
        "gene_symbol": "GENEX",
        "uniprot_acc": "P1",
        "provenance": provenance,
        "det_path": None,
        "site_kind": "internal",
        "insert_after_residue": junction,
        "residue_before": "T",
        "residue_after": "G",
        "residue_label": f"T{junction}",
        "topology_state": "O",
        "extracellular": True,
        "compartment": "extracellular",
        "tag_type": "HA",
        "evidence_type": "published tag insertion at this exact site",
        "confidence": "high",
        "rationale": "in the loop",
        "sources": [{"pmid": 1, "citation": "PMID 1", "claim": "a sentence"}],
        "candidate_id": candidate_id,
        "library": "l1" if candidate_id else None,
        "position_frame": position_frame,
        "numbered_against": numbered_against,
        "loop_run_position": loop_run_position,
    }


def file_of(*sites: dict) -> dict:
    return {
        "has_data": bool(sites),
        "gene_symbol": "GENEX",
        "uniprot_acc": "P1",
        "sites": list(sites),
    }


def published(db: _SqliteD1) -> dict[str, str]:
    return {
        r["site_id"]: r["provenance"]
        for r in db.query("SELECT site_id, provenance FROM tag_site_public;")
    }


def _publish(db, data, provenances=None):
    return TS.publish_tag_sites(
        data,
        tag_sites_version="test-1",
        client=cast(D1Client, db),
        provenances=provenances,
    )


# --------------------------------------------------------------------------
# the additive contract
# --------------------------------------------------------------------------


def test_an_enriched_publish_leaves_the_first_pass_untouched() -> None:
    db = _SqliteD1()
    _publish(db, file_of(site("GENEX-internal-10-lit", provenance="literature_retrieved", junction=10)))
    _publish(
        db,
        file_of(
            site(
                "GENEX-l1-p0001-internal-55-enr",
                provenance=ENRICHED,
                junction=55,
                candidate_id="l1-p0001",
            )
        ),
        provenances=[ENRICHED],
    )
    rows = published(db)
    assert rows == {
        "GENEX-internal-10-lit": "literature_retrieved",
        "GENEX-l1-p0001-internal-55-enr": ENRICHED,
    }


def test_the_first_pass_republishing_leaves_the_enrichment_untouched() -> None:
    """Symmetry matters: the deterministic and literature lanes already write
    the same gene, and the enrichment is a third writer."""
    db = _SqliteD1()
    _publish(
        db,
        file_of(site("GENEX-l1-p0001-internal-55-enr", provenance=ENRICHED, junction=55,
                     candidate_id="l1-p0001")),
        provenances=[ENRICHED],
    )
    _publish(
        db,
        file_of(site("GENEX-internal-10-lit", provenance="literature_retrieved", junction=10)),
        provenances=["literature_retrieved"],
    )
    assert set(published(db)) == {
        "GENEX-l1-p0001-internal-55-enr",
        "GENEX-internal-10-lit",
    }


def test_an_enrichment_that_finds_nothing_clears_only_its_own_rows() -> None:
    """A pass must be able to retract its OWN previous answer — otherwise a site
    it no longer stands behind is published forever — without touching the other
    lanes. This is why ``provenances`` is passed explicitly: an empty site list
    infers an empty scope and would clear nothing at all."""
    db = _SqliteD1()
    _publish(db, file_of(
        site("GENEX-internal-10-lit", provenance="literature_retrieved", junction=10),
        site("GENEX-surface_loop-30", provenance="deterministic_computed", junction=30),
    ))
    _publish(db, file_of(site("GENEX-l1-p0001-internal-55-enr", provenance=ENRICHED,
                              junction=55, candidate_id="l1-p0001")),
             provenances=[ENRICHED])
    assert len(published(db)) == 3

    _publish(db, file_of(), provenances=[ENRICHED])
    rows = published(db)
    assert set(rows) == {"GENEX-internal-10-lit", "GENEX-surface_loop-30"}


# --------------------------------------------------------------------------
# site_id cannot collide
# --------------------------------------------------------------------------


def test_the_same_junction_in_both_passes_is_two_rows_not_an_overwrite() -> None:
    """The primary key is (uniprot_acc, site_id). Without the -enr suffix an
    enriched site at a junction the first pass already holds would INSERT OR
    REPLACE straight over it — deleting the first pass's evidence while looking
    like an addition."""
    db = _SqliteD1()
    _publish(db, file_of(site("GENEX-internal-10-lit", provenance="literature_retrieved", junction=10)))
    _publish(db, file_of(site("GENEX-l1-p0001-internal-10-enr", provenance=ENRICHED,
                              junction=10, candidate_id="l1-p0001")),
             provenances=[ENRICHED])
    rows = db.query("SELECT site_id, provenance FROM tag_site_public WHERE insert_after_residue = 10;")
    assert len(rows) == 2
    assert {r["provenance"] for r in rows} == {"literature_retrieved", ENRICHED}


def test_two_members_of_one_gene_at_one_junction_are_two_rows() -> None:
    """45 of the 518 genes have more than one internal-site member, and 7 of
    those have members that disagree about where the tag can go. A site_id
    without the candidate_id collapses them."""
    db = _SqliteD1()
    _publish(
        db,
        file_of(
            site("GENEX-l1-p0001-internal-55-enr", provenance=ENRICHED, junction=55,
                 candidate_id="l1-p0001"),
            site("GENEX-l1-p2461-internal-55-enr", provenance=ENRICHED, junction=55,
                 candidate_id="l1-p2461"),
        ),
        provenances=[ENRICHED],
    )
    rows = db.query("SELECT site_id, candidate_id FROM tag_site_public;")
    assert len(rows) == 2
    assert {r["candidate_id"] for r in rows} == {"l1-p0001", "l1-p2461"}


# --------------------------------------------------------------------------
# the new columns
# --------------------------------------------------------------------------


def test_the_provenance_columns_round_trip() -> None:
    """A published position is only auditable if the sequence it was numbered
    against, the frame it was read in, and the topology that makes it a loop all
    travel with it."""
    db = _SqliteD1()
    _publish(
        db,
        file_of(
            site(
                "GENEX-l1-p1037-internal-458-enr",
                provenance=ENRICHED,
                junction=458,
                candidate_id="l1-p1037",
                position_frame="canonical",
                numbered_against="a" * 64,
                loop_run_position="inter_tm",
            )
        ),
        provenances=[ENRICHED],
    )
    r = db.query("SELECT * FROM tag_site_public;")[0]
    assert r["candidate_id"] == "l1-p1037"
    assert r["library"] == "l1"
    assert r["position_frame"] == "canonical"
    assert r["numbered_against"] == "a" * 64
    assert r["loop_run_position"] == "inter_tm"
    assert json.loads(r["sources_json"])[0]["pmid"] == 1


def test_the_new_columns_are_registered_in_the_public_schema_file() -> None:
    """The schema files claim to be kept in sync with tag_sites.py's DDL and
    were silently five columns behind once already."""
    from accessible_surfaceome.paths import REPO_ROOT

    for rel in ("cloudflare/d1_public_schema.sql", "cloudflare/d1_tag_sites_schema.sql"):
        text = (REPO_ROOT / rel).read_text()
        for col in ("candidate_id", "library", "numbered_against",
                    "position_frame", "loop_run_position"):
            assert col in text, f"{col} missing from {rel}"


# --------------------------------------------------------------------------
# the enriched viewer shape, which is what produces those rows
# --------------------------------------------------------------------------


def _result_with_one_site(junction: int = 458):
    from accessible_surfaceome.agents.tag_site.schema import (
        TagSiteProposal,
        TagSiteResult,
    )

    return TagSiteResult(
        gene_symbol="GENEX",
        sites=[
            TagSiteProposal(
                rank=1, site_type="internal", insert_after_residue=junction,
                residue_before="A", residue_after="G",
                topology_state="extracellular", tag_type="HA",
                rationale="in the loop", confidence="high",
                evidence_type="published tag insertion at this exact site",
                validation_level="surface_and_function",
                position_evidence="validated", source_tier="paper",
                supporting_quote="inserted between aa 246 and 247",
                evidence_detail="surface biotinylation",
                functional_or_expression_impact_measured="retained",
            )
        ],
    )


def test_the_enriched_site_id_carries_the_member_and_the_enr_suffix() -> None:
    from accessible_surfaceome.agents.tag_site.runner import to_viewer_sites

    rows = to_viewer_sites(
        _result_with_one_site(),
        uniprot_acc="P1",
        provenance=ENRICHED,
        candidate_id="l1-p1037",
        library="l1",
        numbered_against="b" * 64,
    )
    assert len(rows) == 1
    r = rows[0]
    assert r["site_id"] == "GENEX-l1-p1037-internal-458-enr"
    assert r["provenance"] == ENRICHED
    assert r["candidate_id"] == "l1-p1037"
    assert r["numbered_against"] == "b" * 64


def test_the_default_shape_is_unchanged_for_the_first_pass() -> None:
    """The control path writes `literature_retrieved` rows whose ids the
    existing corpus already uses; changing them would orphan 1,094 rows."""
    from accessible_surfaceome.agents.tag_site.runner import to_viewer_sites

    r = to_viewer_sites(_result_with_one_site(10), uniprot_acc="P1")[0]
    assert r["site_id"] == "GENEX-internal-10-lit"
    assert r["provenance"] == "literature_retrieved"
    assert r["candidate_id"] is None


def test_loop_run_position_is_derived_from_the_topology_not_the_label() -> None:
    """site_kind says "internal" for both of these. Only the topology knows one
    is an inter-TM loop and the other an N-terminal tail."""
    from accessible_surfaceome.agents.tag_site.runner import to_viewer_sites

    loop_topo = "O" * 20 + "M" * 20 + "O" * 20 + "M" * 20 + "I" * 20
    tail_topo = "O" * 40 + "M" * 20 + "I" * 40

    in_loop = to_viewer_sites(
        _result_with_one_site(50), uniprot_acc="P1", provenance=ENRICHED,
        candidate_id="l1-p1", topology=loop_topo,
    )[0]
    assert in_loop["site_kind"] == "internal"
    assert in_loop["loop_run_position"] == "inter_tm"

    in_tail = to_viewer_sites(
        _result_with_one_site(5), uniprot_acc="P1", provenance=ENRICHED,
        candidate_id="l1-p1", topology=tail_topo,
    )[0]
    assert in_tail["site_kind"] == "internal"
    assert in_tail["loop_run_position"] == "n_terminal"
