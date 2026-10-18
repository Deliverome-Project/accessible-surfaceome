"""The enrichment pass's resume set, read from public D1.

A member-keyed pass needs a member-keyed skip set, and the only durable record
of "we searched this member" is ``tag_site_gene_public`` — the site table says
nothing about a search that found nothing, which is the majority case.

The repo rule for any pipeline that persists an LLM record (CLAUDE.md) is that
resume is **sha-aware**: a row written under a DIFFERENT ``prompt_sha`` is stale
and must be re-run, never skipped. Skipping on presence alone is how a prompt
edit ships without re-running the rows it invalidated.
"""

from __future__ import annotations

import sqlite3
from typing import cast

from accessible_surfaceome.cloud import tag_site_genes as TG
from accessible_surfaceome.cloud.d1_client import D1Client

SHA_NOW = "a" * 64
SHA_OLD = "b" * 64
SERIES = "literature_enriched_v1"


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


def db(*rows: dict) -> _SqliteD1:
    """A migrated (composite-key) table holding ``rows``."""
    d = _SqliteD1()
    d.query(TG.DDL)
    base = {
        "uniprot_acc": "P0", "searched_at": "2026-10-18", "prompt_version": "2.0.0",
        "model": "m", "schema_version": "1.1.0", "n_papers": 300, "n_sites": 1,
        "n_other_positions": 0, "other_positions_json": "[]", "notes": "",
        "tag_sites_version": SERIES, "synced_at": "2026-10-18",
    }
    TG.publish_gene_rows([{**base, **r} for r in rows], client=cast(D1Client, d))
    return d


def searched(d: _SqliteD1, *, series: str = SERIES, sha: str = SHA_NOW):
    return TG.searched_members(cast(D1Client, d), run_series=series, prompt_sha=sha)


def test_a_member_searched_under_this_prompt_is_skippable() -> None:
    d = db({"gene_symbol": "KCNN2", "candidate_id": "l1-p1037",
            "run_series": SERIES, "prompt_sha": SHA_NOW})
    assert searched(d) == {("KCNN2", "l1-p1037")}


def test_a_row_written_under_a_different_prompt_is_stale_and_must_rerun() -> None:
    """The sha-aware half. A prompt edit has to re-reach the rows it
    invalidated, and silence here is what lets it ship without doing so."""
    d = db({"gene_symbol": "KCNN2", "candidate_id": "l1-p1037",
            "run_series": SERIES, "prompt_sha": SHA_OLD})
    assert searched(d) == set()


def test_the_first_passs_rows_do_not_mask_the_enrichment() -> None:
    """Both passes are real searches of the same gene under the same prompt;
    the series is what separates them. Ignoring it would make the enrichment
    skip every gene the first pass already covered — i.e. all of them."""
    d = db({"gene_symbol": "KCNN2", "candidate_id": "l1-p1037",
            "run_series": "literature_v1", "prompt_sha": SHA_NOW})
    assert searched(d) == set()


def test_a_gene_level_row_does_not_mask_a_member() -> None:
    """Pre-migration rows carry ``candidate_id = ''``. A member's search is a
    different claim about a different construct, so the empty id must not
    satisfy it."""
    d = db({"gene_symbol": "KCNN2", "candidate_id": "",
            "run_series": SERIES, "prompt_sha": SHA_NOW})
    assert ("KCNN2", "l1-p1037") not in searched(d)


def test_a_dated_zero_counts_as_searched() -> None:
    """The reason this table exists. A member the pass ran and found nothing in
    is DONE — re-running it buys the same empty answer for the same money."""
    d = db({"gene_symbol": "ABCA8", "candidate_id": "l1-p0001",
            "run_series": SERIES, "prompt_sha": SHA_NOW, "n_sites": 0})
    assert searched(d) == {("ABCA8", "l1-p0001")}


def test_several_members_of_one_gene_are_tracked_apart() -> None:
    """45 of the 518 genes have more than one internal-site member, so a
    gene-keyed skip set would strand the second one."""
    d = db(
        {"gene_symbol": "KCNN2", "candidate_id": "l1-p1037",
         "run_series": SERIES, "prompt_sha": SHA_NOW},
        {"gene_symbol": "KCNN2", "candidate_id": "l1-p2461",
         "run_series": SERIES, "prompt_sha": SHA_OLD},
    )
    assert searched(d) == {("KCNN2", "l1-p1037")}


# --------------------------------------------------------------------------
# the write half: a resume is vacuous unless the pass records its search
# --------------------------------------------------------------------------


def _enriched_record(n_sites: int = 1) -> dict:
    return {
        "gene_symbol": "KCNN2",
        "candidate_id": "l1-p1037",
        "run_series": SERIES,
        "uniprot_acc": "P70604",
        "generated_at": "2026-10-18T00:00:00Z",
        "prompt_sha": SHA_NOW,
        "prompt_version": "2.0.0",
        "model": "claude-opus-5",
        "schema_version": "1.1.0",
        "literature_other_positions": [],
        "literature_notes": "",
        "sites": [
            {"provenance": "literature_enriched", "position": 458 + i}
            for i in range(n_sites)
        ],
    }


def test_row_for_counts_sites_of_the_provenance_it_is_asked_about() -> None:
    """``row_for`` counts ``literature_retrieved`` by default, which is the
    first pass's provenance. The enrichment publishes ``literature_enriched``,
    so without being told it would record every enriched member as a zero — a
    dated zero that is simply false, and the one value nothing downstream can
    tell apart from a real empty search."""
    row = TG.row_for(
        _enriched_record(n_sites=2), version=SERIES, provenance="literature_enriched"
    )
    assert row is not None
    assert row["n_sites"] == 2


def test_a_member_that_found_nothing_still_gets_a_dated_row() -> None:
    """~80% of these members have no published loop insertion. If the pass does
    not record that, every resume re-runs them and the sweep never converges."""
    row = TG.row_for(
        _enriched_record(n_sites=0), version=SERIES, provenance="literature_enriched"
    )
    assert row is not None
    assert row["n_sites"] == 0
    assert row["prompt_sha"] == SHA_NOW
    assert row["searched_at"] == "2026-10-18T00:00:00Z"


def test_the_row_carries_the_member_and_the_series() -> None:
    row = TG.row_for(_enriched_record(), version=SERIES,
                     provenance="literature_enriched")
    assert row is not None
    assert (row["candidate_id"], row["run_series"]) == ("l1-p1037", SERIES)


def test_a_published_row_is_what_the_resume_then_skips() -> None:
    """The two halves closing on each other — the only test here that would
    catch a write and a read that each look right but disagree on a key."""
    row = TG.row_for(_enriched_record(n_sites=0), version=SERIES,
                     provenance="literature_enriched")
    assert row is not None
    d = _SqliteD1()
    d.query(TG.DDL)
    TG.publish_gene_rows([row], client=cast(D1Client, d))
    assert searched(d) == {("KCNN2", "l1-p1037")}
