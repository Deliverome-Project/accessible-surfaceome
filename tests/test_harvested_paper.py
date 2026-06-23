"""Tests for the harvested_paper table + writer.

Covers:
- ``ensure_schema`` emits the expected DDL statements
- ``publish_harvested_papers`` writes one ``INSERT OR REPLACE`` per paper
  and threads all the natural-key + denormalized fields through
- The schema in ``cloudflare/d1_schema.sql`` matches the in-module DDL
  (so the wrangler-applied schema and the Python-applied schema can't
  drift)
"""

from __future__ import annotations

import httpx

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.cloud.harvested_paper import (
    HarvestedPaper,
    _SCHEMA_SQL,
    _bucket_from_triage_action,
    _split_paper_id,
    ensure_schema,
    harvested_papers_from_dual,
    publish_harvested_papers,
)


def _mock_transport(default_ok_responses: int = 20) -> tuple[httpx.MockTransport, list]:
    """Mock transport that records every request body and returns OK."""
    recorded: list = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json
        recorded.append(_json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={
            "success": True,
            "result": [{"results": [], "success": True}],
            "errors": [],
            "messages": [],
        })

    return httpx.MockTransport(handler), recorded


def _make_client(transport: httpx.MockTransport) -> D1Client:
    cfg = D1Config(account_id="acct", database_id="db", api_token="tok")
    client = D1Client(cfg)
    client._client.close()
    client._client = httpx.Client(transport=transport, headers=client._headers)
    return client


def test_ensure_schema_emits_create_table_and_indexes() -> None:
    transport, recorded = _mock_transport()
    with _make_client(transport) as client:
        ensure_schema(d1=client)
    statements = [r["sql"] for r in recorded]
    # One CREATE TABLE statement, four CREATE INDEX statements (gene, run,
    # source, bucket) — matches _SCHEMA_SQL length.
    assert len(statements) == len(_SCHEMA_SQL)
    assert any("CREATE TABLE IF NOT EXISTS harvested_paper" in s for s in statements)
    for idx_col in ("idx_harvested_paper_gene", "idx_harvested_paper_run",
                    "idx_harvested_paper_source", "idx_harvested_paper_bucket"):
        assert any(idx_col in s for s in statements), f"missing index {idx_col}"


def test_publish_harvested_papers_threads_all_fields() -> None:
    transport, recorded = _mock_transport()
    papers = [
        HarvestedPaper(
            run_id="sweep_2026",
            gene_symbol="CD20",
            paper_id="PMID:12345",
            source="europepmc_ppr",
            axis_label="surface_method",
            bucket="pmc",
            body_source="pmc_xml",
            doi="10.1101/2026.01.01",
            pmid=12345,
            pmc_id=None,
            year=2026,
            title="CD20 in B cells",
        ),
        HarvestedPaper(
            run_id="sweep_2026",
            gene_symbol="CD20",
            paper_id="DOI:10.48550/arxiv.2510.17752",
            source="openalex",
            axis_label=None,
            bucket="datacite_oa_repo",
            body_source="datacite_pdf",
            doi="10.48550/arxiv.2510.17752",
            pmid=None,
            pmc_id=None,
            year=2025,
            title=None,
        ),
    ]
    with _make_client(transport) as client:
        n = publish_harvested_papers(papers, d1=client)
    assert n == 2
    assert len(recorded) == 2
    # Each call uses INSERT OR REPLACE with all 13 placeholders bound.
    for body, paper in zip(recorded, papers, strict=True):
        sql = body["sql"]
        params = body["params"]
        assert "INSERT OR REPLACE INTO harvested_paper" in sql
        assert len(params) == 13  # 12 column values + created_at timestamp
        # First 3 params are the natural key, in order.
        assert params[0] == paper.run_id
        assert params[1] == paper.gene_symbol
        assert params[2] == paper.paper_id
        assert params[3] == paper.source
        assert params[4] == paper.axis_label
        assert params[5] == paper.bucket
        assert params[6] == paper.body_source


def test_publish_skips_when_empty_input() -> None:
    """No D1 round-trips when the input iterable is empty."""
    transport, recorded = _mock_transport()
    with _make_client(transport) as client:
        n = publish_harvested_papers([], d1=client)
    assert n == 0
    assert recorded == []


def test_schema_sql_matches_canonical_d1_schema() -> None:
    """The in-module ``_SCHEMA_SQL`` must declare the same harvested_paper
    table as ``cloudflare/d1_schema.sql``. Drift between the two would
    mean Python-applied bring-up and wrangler-applied bring-up produce
    different shapes — exactly the failure mode this test guards.
    """
    from pathlib import Path
    canonical = Path(
        __file__
    ).resolve().parents[1] / "cloudflare" / "d1_schema.sql"
    text = canonical.read_text()
    # Both must declare CREATE TABLE harvested_paper with the same columns.
    assert "CREATE TABLE IF NOT EXISTS harvested_paper" in text
    for col in (
        "run_id", "gene_symbol", "paper_id", "source", "axis_label",
        "bucket", "body_source", "doi", "pmid", "pmc_id", "year", "title",
    ):
        # Column must appear under the harvested_paper table block.
        idx = text.index("CREATE TABLE IF NOT EXISTS harvested_paper")
        end = text.index(");", idx)
        block = text[idx:end]
        assert col in block, f"column {col} missing from canonical schema"
    # Both must declare the same indexes.
    for idx_name in (
        "idx_harvested_paper_gene", "idx_harvested_paper_run",
        "idx_harvested_paper_source", "idx_harvested_paper_bucket",
    ):
        assert idx_name in text, f"index {idx_name} missing from canonical schema"


# ---------------------------------------------------------------------------
# _split_paper_id
# ---------------------------------------------------------------------------

def test_split_paper_id_recognizes_pmc_pmid_doi() -> None:
    assert _split_paper_id("PMC:PMC123") == (None, None, "PMC123")
    assert _split_paper_id("PMID:7") == (None, 7, None)
    assert _split_paper_id("DOI:10.48550/arxiv.X") == ("10.48550/arxiv.X", None, None)


def test_split_paper_id_handles_unknown_prefix_and_bad_pmid() -> None:
    # Unknown prefix → all None (still inserts with bare paper_id).
    assert _split_paper_id("FOO:bar") == (None, None, None)
    # PMID prefix but non-integer body → all None (don't crash).
    assert _split_paper_id("PMID:not-a-number") == (None, None, None)
    assert _split_paper_id("UNKNOWN") == (None, None, None)


# ---------------------------------------------------------------------------
# _bucket_from_triage_action
# ---------------------------------------------------------------------------

class _FakeAction:
    """Minimal stand-in for TriageAction so we don't pull the agent module
    in just to construct fixtures."""
    def __init__(self, decision: str, fetched_body: bool = False,
                 fetch_source: str | None = None) -> None:
        self.decision = decision
        self.fetched_body = fetched_body
        self.fetch_source = fetch_source


def test_bucket_from_triage_action_decision_outcomes() -> None:
    assert _bucket_from_triage_action(_FakeAction("discard")) == "discarded"
    assert _bucket_from_triage_action(_FakeAction("keep_abstract")) == "abstract_only"
    # worth_fetching but fetch fell back → fetch_failed (separate from no_oa)
    assert _bucket_from_triage_action(_FakeAction("worth_fetching", fetched_body=False)) == "fetch_failed"
    # worth_fetching + body → bucket reflects which tier produced it
    assert _bucket_from_triage_action(_FakeAction("worth_fetching", fetched_body=True, fetch_source="pmc_xml")) == "pmc"
    assert _bucket_from_triage_action(_FakeAction("worth_fetching", fetched_body=True, fetch_source="unpaywall_pdf")) == "unpaywall"
    assert _bucket_from_triage_action(_FakeAction("worth_fetching", fetched_body=True, fetch_source="datacite_pdf")) == "datacite_pdf"
    # Unknown source on a fetched body → still record success.
    assert _bucket_from_triage_action(_FakeAction("worth_fetching", fetched_body=True, fetch_source="future_tier")) == "fetched"
    # Unknown decision → None (caller writes NULL).
    assert _bucket_from_triage_action(_FakeAction("???")) is None


# ---------------------------------------------------------------------------
# harvested_papers_from_dual
# ---------------------------------------------------------------------------

class _FakeAct:
    def __init__(self, paper_id: str, decision: str, fetched_body: bool = False,
                 fetch_source: str | None = None, paper_year: int | None = None,
                 paper_title: str | None = None) -> None:
        self.paper_id = paper_id
        self.decision = decision
        self.fetched_body = fetched_body
        self.fetch_source = fetch_source
        self.paper_year = paper_year
        self.paper_title = paper_title


class _FakeFocus:
    def __init__(self, actions: list[_FakeAct]) -> None:
        self.triage_actions = actions


class _FakeDual:
    def __init__(self, a1: list[_FakeAct], a2: list[_FakeAct]) -> None:
        self.a1 = _FakeFocus(a1)
        self.a2 = _FakeFocus(a2)


def test_harvested_papers_from_dual_dedupes_a1_a2_overlap() -> None:
    """A2 re-sees most papers A1 fetched (shared HTTP cache). The
    converter must dedupe by paper_id, keeping the A1 row when present."""
    shared = _FakeAct("PMID:1", "worth_fetching", fetched_body=True,
                     fetch_source="pmc_xml", paper_year=2024,
                     paper_title="shared paper")
    a1_only = _FakeAct("PMID:2", "keep_abstract", paper_title="a1 only")
    a2_only = _FakeAct("DOI:10.48550/arxiv.X", "worth_fetching",
                      fetched_body=True, fetch_source="datacite_pdf",
                      paper_title="a2 only arxiv")
    dual = _FakeDual(a1=[shared, a1_only], a2=[shared, a2_only])

    rows = harvested_papers_from_dual(dual, run_id="r1", gene_symbol="GENE")
    assert len(rows) == 3
    by_id = {r.paper_id: r for r in rows}
    # Shared paper keeps its A1 source label
    assert by_id["PMID:1"].source == "deep_dive_v2_a1"
    assert by_id["PMID:1"].bucket == "pmc"
    assert by_id["PMID:1"].body_source == "pmc_xml"
    assert by_id["PMID:1"].pmid == 1
    # A1-only kept-abstract
    assert by_id["PMID:2"].source == "deep_dive_v2_a1"
    assert by_id["PMID:2"].bucket == "abstract_only"
    # A2-only DataCite arXiv flows through with paper_id parsing
    assert by_id["DOI:10.48550/arxiv.X"].source == "deep_dive_v2_a2"
    assert by_id["DOI:10.48550/arxiv.X"].bucket == "datacite_pdf"
    assert by_id["DOI:10.48550/arxiv.X"].doi == "10.48550/arxiv.X"


def test_harvested_papers_from_dual_empty_and_unknown() -> None:
    assert harvested_papers_from_dual(None, run_id="r", gene_symbol="G") == []
    # Dual present but no actions → empty.
    assert harvested_papers_from_dual(_FakeDual(a1=[], a2=[]), run_id="r", gene_symbol="G") == []
    # ``UNKNOWN`` paper_id (rare; shouldn't happen post the source_id fix
    # but guard anyway so a stale row doesn't poison the table).
    dual = _FakeDual(a1=[_FakeAct("UNKNOWN", "discard")], a2=[])
    assert harvested_papers_from_dual(dual, run_id="r", gene_symbol="G") == []
