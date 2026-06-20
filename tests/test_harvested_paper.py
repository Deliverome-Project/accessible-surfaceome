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

from typing import Any

import httpx
import pytest

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.cloud.harvested_paper import (
    HarvestedPaper,
    _SCHEMA_SQL,
    ensure_schema,
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
