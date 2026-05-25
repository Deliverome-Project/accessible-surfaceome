"""Sync SURFACE-Bind summary JSON → public D1.

Reads ``data/external/surface_bind/surface_bind_summary.json``
(built by ``scripts/build_surface_bind_summary.py``) and UPSERTs
two tables in the ``surfaceome_public`` D1 database:

* ``surface_bind_protein`` — one row per UniProt acc with
  aggregates + classification + PDB list.
* ``surface_bind_site`` — one row per (acc, site_id) with per-site
  anchor / BSA / α-β seeds / hydrophobicity.

Run::

    uv run python scripts/sync_surface_bind_to_d1.py
    uv run python scripts/sync_surface_bind_to_d1.py --dry-run
    uv run python scripts/sync_surface_bind_to_d1.py --apply-schema  # one-shot

Idempotent on the primary keys: re-runs UPSERT in place.

Note: D1's HTTP API doesn't accept multi-statement batches, so this
script submits one statement per call (loop-chunked). ~2,700 protein
rows + ~5,000 site rows. With the default chunk-of-50 batching this
takes a couple of minutes against the production D1.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
SUMMARY_PATH = (
    REPO_ROOT / "data" / "external" / "surface_bind" / "surface_bind_summary.json"
)
SCHEMA_PATH = REPO_ROOT / "cloudflare" / "d1_public_schema.sql"

# Pin the SURFACE-Bind release tag so consumers can join on the
# version column and know which snapshot the data came from. Tracks
# the SURFACE-Bind GitHub repo's data-snapshot date.
SURFACEBIND_VERSION = "2024-08-09"


def _public_d1() -> D1Client:
    load_env()
    public_db_id = os.environ.get("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "").strip()
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    api_token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    missing = [
        name
        for name, value in [
            ("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", public_db_id),
            ("CLOUDFLARE_ACCOUNT_ID", account_id),
            ("CLOUDFLARE_API_TOKEN", api_token),
        ]
        if not value
    ]
    if missing:
        raise SystemExit(
            "Missing D1 env vars for public-mirror sync: " + ", ".join(missing)
        )
    return D1Client(
        D1Config(
            account_id=account_id,
            database_id=public_db_id,
            api_token=api_token,
        )
    )


def _strip_sql_comments(stmt: str) -> str:
    """Drop ``-- ...`` line comments from a SQL statement.

    D1's HTTP API parses statements strictly; leading comments inside
    a single statement payload trip the parser with
    ``"incomplete input"``. Strip them line-by-line before sending.
    """
    out_lines: list[str] = []
    for line in stmt.splitlines():
        # Strip ``-- ...`` to end-of-line. (Naive: doesn't handle
        # ``--`` inside string literals, but the schema doesn't have
        # any.)
        idx = line.find("--")
        if idx >= 0:
            line = line[:idx]
        if line.strip():
            out_lines.append(line)
    return "\n".join(out_lines).strip()


def _apply_schema(d1: D1Client) -> None:
    """Run the SURFACE-Bind CREATE TABLE / CREATE INDEX statements
    against public D1. Idempotent (uses IF NOT EXISTS)."""
    text = SCHEMA_PATH.read_text()
    # Pull only the SURFACE-Bind block — the rest of the schema may
    # have been applied separately.
    marker = "-- SURFACE-Bind (Marchand et al. 2026 PNAS"
    idx = text.find(marker)
    if idx < 0:
        raise SystemExit("could not find SURFACE-Bind section in d1_public_schema.sql")
    block = text[idx:]
    # Strip ``-- ...`` line comments FIRST, then split. Comments often
    # contain ``;`` themselves (e.g. ``-- PDB-chain ID; 'A' for most``)
    # which would shred a real CREATE TABLE in half if we split before
    # stripping.
    block = _strip_sql_comments(block)
    for raw_stmt in block.split(";"):
        stmt = raw_stmt.strip()
        if not stmt:
            continue
        logger.info("DDL: %s", " ".join(stmt.splitlines()[:1])[:100])
        d1.query(stmt + ";", [])


def _load_summary() -> dict[str, dict[str, Any]]:
    payload = json.loads(SUMMARY_PATH.read_text())
    payload.pop("__meta__", None)
    return payload


def _upsert_protein(
    d1: D1Client, acc: str, entry: dict[str, Any], *, dry_run: bool
) -> None:
    sql = (
        "INSERT INTO surface_bind_protein "
        "(uniprot_acc, chain, main_class, sub_class, protein_name, "
        " n_sites, n_seeds_alpha, n_seeds_beta, n_seeds_total, "
        " pdbs, surfacebind_version, synced_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now')) "
        "ON CONFLICT(uniprot_acc) DO UPDATE SET "
        " chain=excluded.chain, main_class=excluded.main_class, "
        " sub_class=excluded.sub_class, protein_name=excluded.protein_name, "
        " n_sites=excluded.n_sites, n_seeds_alpha=excluded.n_seeds_alpha, "
        " n_seeds_beta=excluded.n_seeds_beta, n_seeds_total=excluded.n_seeds_total, "
        " pdbs=excluded.pdbs, surfacebind_version=excluded.surfacebind_version, "
        " synced_at=datetime('now');"
    )
    params: list[Any] = [
        acc,
        entry.get("chain"),
        entry.get("main_class"),
        entry.get("sub_class"),
        entry.get("protein_name"),
        int(entry["n_sites"]),
        int(entry["n_seeds_alpha"]),
        int(entry["n_seeds_beta"]),
        int(entry["n_seeds_total"]),
        json.dumps(entry.get("pdbs", [])),
        SURFACEBIND_VERSION,
    ]
    if dry_run:
        return
    d1.query(sql, params)


def _upsert_sites(
    d1: D1Client, acc: str, sites: list[dict[str, Any]], *, dry_run: bool
) -> None:
    sql = (
        "INSERT INTO surface_bind_site "
        "(uniprot_acc, site_id, anchor_residue, area_a2, n_seeds_alpha, "
        " n_seeds_beta, hydrophobicity, surfacebind_version, synced_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now')) "
        "ON CONFLICT(uniprot_acc, site_id) DO UPDATE SET "
        " anchor_residue=excluded.anchor_residue, area_a2=excluded.area_a2, "
        " n_seeds_alpha=excluded.n_seeds_alpha, n_seeds_beta=excluded.n_seeds_beta, "
        " hydrophobicity=excluded.hydrophobicity, "
        " surfacebind_version=excluded.surfacebind_version, "
        " synced_at=datetime('now');"
    )
    for site in sites:
        params = [
            acc,
            int(site["site_id"]),
            int(site["anchor_residue"]),
            float(site["area_a2"]),
            int(site["n_seeds_alpha"]),
            int(site["n_seeds_beta"]),
            float(site["hydrophobicity"]),
            SURFACEBIND_VERSION,
        ]
        if dry_run:
            continue
        d1.query(sql, params)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Parse + count rows but don't UPSERT.",
    )
    ap.add_argument(
        "--apply-schema", action="store_true",
        help="Run the CREATE TABLE / INDEX statements first.",
    )
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    summary = _load_summary()
    n_proteins = len(summary)
    n_sites = sum(len(e.get("sites", [])) for e in summary.values())
    logger.info(
        "loaded %d UniProt entries (%d total sites) from %s",
        n_proteins, n_sites, SUMMARY_PATH.relative_to(REPO_ROOT),
    )

    if args.dry_run:
        logger.info("dry-run — no D1 writes")
        return 0

    with _public_d1() as d1:
        if args.apply_schema:
            logger.info("applying SURFACE-Bind schema to public D1")
            _apply_schema(d1)

        logger.info("upserting %d proteins + %d sites into public D1", n_proteins, n_sites)
        for i, (acc, entry) in enumerate(sorted(summary.items()), start=1):
            _upsert_protein(d1, acc, entry, dry_run=False)
            sites = entry.get("sites", [])
            if sites:
                _upsert_sites(d1, acc, sites, dry_run=False)
            if i % 100 == 0:
                logger.info("  ... %d / %d proteins", i, n_proteins)
        logger.info("done — %d proteins, %d sites synced", n_proteins, n_sites)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
