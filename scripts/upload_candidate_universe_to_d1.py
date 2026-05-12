"""Upload the candidate-universe TSV to the `surfaceome_public` D1 mirror.

The candidate universe is a flat merge artifact at
``data/processed/candidate_universe/candidate_universe.tsv`` — one row
per (UniProt, gene) pair across the seven public databases, with the
per-source ``*_surface_flag`` columns and a ``n_sources_surface``
union count.

This script ports those rows into
``surfaceome_public.candidate_universe_public`` so the public Worker
at ``api.deliverome.org/surfaceome/v1/catalog`` can serve the
genome-wide table the viewer's index page renders.

Idempotent on (universe_version, gene_symbol, uniprot_acc): existing
rows are skipped via ``INSERT OR IGNORE``. To re-load with corrected
data, pass a fresh ``--version`` (the viewer's Worker always picks
the latest ``candidate_universe_release`` row).

Usage::

    uv run python scripts/upload_candidate_universe_to_d1.py \\
        --tsv data/processed/candidate_universe/candidate_universe.tsv \\
        --version "cu_$(date -u +%Y_%m_%d)"

Requires the standard Cloudflare env vars (CLOUDFLARE_ACCOUNT_ID,
CLOUDFLARE_API_TOKEN) plus ``CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID``
pointing at the public mirror DB. See ``.env.example`` for the full
set and ``cloudflare/workers/surfaceome_api/wrangler.toml.example``
for where the Worker reads the same UUID from.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from accessible_surfaceome.env import load_env

logger = logging.getLogger(__name__)

# Cloudflare D1 caps SQL placeholders per statement at ~100. Each row has
# 11 cols, so 8 rows per batch (88 placeholders) is the safe ceiling.
BATCH_SIZE = 8

API_ROOT = "https://api.cloudflare.com/client/v4"

COLS = [
    "universe_version",
    "gene_symbol",
    "uniprot_acc",
    "n_sources_surface",
    "uniprot_surface_flag",
    "go_surface_flag",
    "surfy_surface_flag",
    "cspa_surface_flag",
    "hpa_surface_flag",
    "deeptmhmm_surface_flag",
    "compartments_surface_flag",
]


@dataclass(frozen=True)
class D1:
    account_id: str
    database_id: str
    api_token: str

    @property
    def url(self) -> str:
        return f"{API_ROOT}/accounts/{self.account_id}/d1/database/{self.database_id}/query"


def _from_env() -> D1:
    missing: list[str] = []
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    db = os.environ.get("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "").strip()
    if not acct:
        missing.append("CLOUDFLARE_ACCOUNT_ID")
    if not token:
        missing.append("CLOUDFLARE_API_TOKEN")
    if not db:
        missing.append("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID")
    if missing:
        raise SystemExit(
            "Missing env vars: " + ", ".join(missing)
            + ". Add them to your .env; see .env.example for the full list."
        )
    return D1(account_id=acct, database_id=db, api_token=token)


def _query(d1: D1, sql: str, params: list[Any] | None = None, *, client: httpx.Client) -> Any:
    body: dict[str, Any] = {"sql": sql}
    if params is not None:
        body["params"] = list(params)
    resp = client.post(
        d1.url,
        json=body,
        headers={"Authorization": f"Bearer {d1.api_token}"},
        timeout=60,
    )
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"D1 error: {data}")
    return data.get("result")


def _flag(row: dict[str, str], name: str) -> int:
    """Tolerant 0/1 coercion. Empty / NA / nan → 0."""
    v = (row.get(name) or "").strip()
    if not v or v in {"NA", "nan", "None"}:
        return 0
    try:
        return 1 if int(float(v)) else 0
    except ValueError:
        return 0


def _int(row: dict[str, str], name: str) -> int:
    v = (row.get(name) or "").strip()
    if not v:
        return 0
    try:
        return int(float(v))
    except ValueError:
        return 0


def _build_rows(tsv: Path, version: str) -> list[list[Any]]:
    out: list[list[Any]] = []
    skipped = 0
    with tsv.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            sym = (r.get("gene_symbol_resolved") or r.get("gene_symbol") or "").strip()
            uni = (r.get("uniprot_accession") or "").strip()
            if not sym or not uni:
                skipped += 1
                continue
            out.append([
                version,
                sym,
                uni,
                _int(r, "n_sources_surface"),
                _flag(r, "uniprot_surface_flag"),
                _flag(r, "go_surface_flag"),
                _flag(r, "surfy_surface_flag"),
                _flag(r, "cspa_surface_flag"),
                _flag(r, "hpa_surface_flag"),
                _flag(r, "deeptmhmm_surface_flag"),
                _flag(r, "compartments_surface_flag"),
            ])
    if skipped:
        logger.warning("skipped %d rows with empty gene/uniprot", skipped)
    return out


def _intern_release(
    d1: D1, *, version: str, n_rows: int, source_path: str, dry_run: bool, client: httpx.Client,
) -> None:
    if dry_run:
        logger.info("[DRY] candidate_universe_release(version=%s, n_rows=%d)", version, n_rows)
        return
    _query(
        d1,
        """
        INSERT INTO candidate_universe_release (universe_version, n_rows, source_path, notes)
        VALUES (?, ?, ?, NULL)
        ON CONFLICT (universe_version) DO UPDATE SET
            n_rows = excluded.n_rows,
            source_path = excluded.source_path
        """,
        [version, n_rows, source_path],
        client=client,
    )


def _upload_rows(d1: D1, rows: list[list[Any]], *, dry_run: bool, client: httpx.Client) -> None:
    if not rows:
        return
    placeholders_one = "(" + ", ".join(["?"] * len(COLS)) + ")"
    cols_sql = ", ".join(COLS)
    total = len(rows)
    for start in range(0, total, BATCH_SIZE):
        chunk = rows[start : start + BATCH_SIZE]
        sql = (
            f"INSERT OR IGNORE INTO candidate_universe_public ({cols_sql}) "
            f"VALUES {', '.join([placeholders_one] * len(chunk))}"
        )
        params = [v for row in chunk for v in row]
        if dry_run:
            logger.info("[DRY] rows %d..%d (n=%d, %d params)",
                        start, start + len(chunk) - 1, len(chunk), len(params))
            continue
        _query(d1, sql, params, client=client)
        logger.info("rows %d..%d (n=%d) done", start, start + len(chunk) - 1, len(chunk))


def main() -> int:
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--tsv",
        type=Path,
        default=Path("data/processed/candidate_universe/candidate_universe.tsv"),
        help="Path to the candidate-universe TSV (default: data/processed/candidate_universe/candidate_universe.tsv)",
    )
    ap.add_argument(
        "--version",
        required=True,
        help="universe_version stamp, e.g. cu_2026_05_12",
    )
    ap.add_argument("--dry-run", action="store_true", help="Print rows but don't write")
    args = ap.parse_args()

    if not args.tsv.exists():
        raise SystemExit(f"TSV not found: {args.tsv}")

    d1 = _from_env()
    logger.info("target DB: %s", d1.database_id)
    rows = _build_rows(args.tsv, args.version)
    logger.info("parsed %d rows from %s (version=%s)", len(rows), args.tsv, args.version)

    with httpx.Client(timeout=60) as client:
        _intern_release(
            d1,
            version=args.version,
            n_rows=len(rows),
            source_path=str(args.tsv),
            dry_run=args.dry_run,
            client=client,
        )
        _upload_rows(d1, rows, dry_run=args.dry_run, client=client)

    logger.info("done: %d rows → candidate_universe_public (version=%s)", len(rows), args.version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
