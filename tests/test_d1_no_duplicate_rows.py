"""D1 invariant: at most one row per gene per (table, mirror) surface.

The catalog page's /v1/catalog endpoint LEFT JOINs candidate_universe_public
against czi_cellxgene_enrichment and surface_annotation on gene_symbol. If
the right side of either join has > 1 row per gene, the catalog row fans
out N× — which is exactly the bug that hit production on 2026-06-12
(11 schema_version rows per gene in czi_cellxgene_enrichment after 11
schema bumps, → catalog home page showing duplicated rows).

This test asserts the invariant directly against the live public D1.
Skips when CLOUDFLARE_API_TOKEN is unset (offline CI smoke); CI gets the
token from secrets and enforces the invariant.

The fix that should keep this test green: ``scripts/sync_czi_enrichment_to_d1.py``
issues a DELETE-where-schema_version-different before each per-gene
UPSERT (cf. _push_one), and ``accessible_surfaceome.cloud.surface_annotation.publish_record``
does the same via ``_existing_versions_for``.
"""

from __future__ import annotations

import os
from collections.abc import Iterable

import pytest

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env


def _public_cfg() -> D1Config:
    if not os.environ.get("CLOUDFLARE_API_TOKEN"):
        pytest.skip(
            "CLOUDFLARE_API_TOKEN not set — D1 invariant tests skipped in "
            "offline CI smoke. Run with .env loaded to enable."
        )
    db_id = os.environ.get("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID")
    if not db_id:
        pytest.skip(
            "CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID not set — cannot reach "
            "the public D1 to verify catalog-row invariants."
        )
    return D1Config(
        account_id=os.environ["CLOUDFLARE_ACCOUNT_ID"],
        api_token=os.environ["CLOUDFLARE_API_TOKEN"],
        database_id=db_id,
    )


def _fmt_dups(rows: Iterable[dict[str, str]], col: str = "gene_symbol") -> str:
    lines = [f"  {r[col]}: {r['n']} rows" for r in rows]
    return "\n".join(lines)


@pytest.fixture(scope="module", autouse=True)
def _load() -> None:
    load_env()


def test_czi_cellxgene_enrichment_one_row_per_gene() -> None:
    """Every gene in czi_cellxgene_enrichment should appear at most once.

    The PRIMARY KEY ``(gene_symbol, schema_version, census_version)``
    allows accumulation across schema bumps — without the cleanup-on-push
    in ``sync_czi_enrichment_to_d1._push_one`` this drifts silently and
    fans the catalog JOIN out N×.
    """
    cfg = _public_cfg()
    with D1Client(cfg) as d1:
        dups = d1.query(
            "SELECT gene_symbol, COUNT(*) as n FROM czi_cellxgene_enrichment "
            "GROUP BY gene_symbol HAVING COUNT(*) > 1 ORDER BY n DESC LIMIT 20;",
            [],
        )
    assert not dups, (
        "Found genes with > 1 row in czi_cellxgene_enrichment — the catalog "
        "JOIN will fan out N×. Either re-run sync_czi_enrichment_to_d1.py "
        "(it deletes stale schema_versions before each upsert) or DELETE the "
        "older schema_version rows manually:\n"
        + _fmt_dups(dups)
    )


def test_surface_annotation_one_row_per_gene() -> None:
    """Every gene in surface_annotation should appear at most once.

    publish_record_dict already enforces this by dropping older
    schema_versions before INSERT OR REPLACE; this test guards against
    a future regression in that helper.
    """
    cfg = _public_cfg()
    with D1Client(cfg) as d1:
        dups = d1.query(
            "SELECT gene_symbol, COUNT(*) as n FROM surface_annotation "
            "GROUP BY gene_symbol HAVING COUNT(*) > 1 ORDER BY n DESC LIMIT 20;",
            [],
        )
    assert not dups, (
        "Found genes with > 1 row in surface_annotation. Same fan-out risk "
        "as the czi_cellxgene_enrichment case. Check that publish_record_dict "
        "still calls _existing_versions_for and drops older rows.\n"
        + _fmt_dups(dups)
    )


def test_candidate_universe_one_row_per_gene_per_version() -> None:
    """Every (gene_symbol, universe_version) in candidate_universe_public
    appears at most once. Drift here would similarly fan out the catalog."""
    cfg = _public_cfg()
    with D1Client(cfg) as d1:
        dups = d1.query(
            "SELECT gene_symbol, universe_version, COUNT(*) as n "
            "FROM candidate_universe_public "
            "GROUP BY gene_symbol, universe_version "
            "HAVING COUNT(*) > 1 ORDER BY n DESC LIMIT 20;",
            [],
        )
    assert not dups, (
        "Found duplicate (gene_symbol, universe_version) in candidate_universe_public:\n"
        + "\n".join(f"  {r['gene_symbol']}@{r['universe_version']}: {r['n']} rows" for r in dups)
    )
