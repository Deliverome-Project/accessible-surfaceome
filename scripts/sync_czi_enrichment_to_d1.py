"""Sync per-gene CZI CellxGene enrichment summaries into D1.

Reads the JSON-per-gene snapshots produced by ``build_czi_enrichment.py``
(local path: ``/tmp/czi_enrichment/{SYMBOL}.json`` by default) and pushes
each row into BOTH the private ``surfaceome_agents`` D1 and the public
``surfaceome_public`` mirror, into the ``czi_cellxgene_enrichment`` table.

Schema lives in:
  * ``cloudflare/d1_schema.sql``         (private)
  * ``cloudflare/d1_public_schema.sql``  (public)

The Worker's ``/v1/genes/:symbol/cellxgene`` route reads from the public
mirror.

Usage::

    # Dry run — show what would be pushed (no D1 writes).
    uv run python scripts/sync_czi_enrichment_to_d1.py

    # Push to both private + public D1.
    uv run python scripts/sync_czi_enrichment_to_d1.py --execute

    # Push to ONLY the public mirror (skip private). Useful if the public
    # rows drifted and we just want to refresh the read path.
    uv run python scripts/sync_czi_enrichment_to_d1.py --execute --public-only

    # Custom snapshot dir or census version override.
    uv run python scripts/sync_czi_enrichment_to_d1.py \\
        --snapshot-dir /tmp/czi_enrichment --execute

Idempotent: PK ``(gene_symbol, schema_version, census_version)`` +
``INSERT OR REPLACE`` mean re-running this is safe. Concurrent HTTP POSTs
(``--workers``) keep the wall-clock under a few minutes for the full
~19k-gene set.

Cache-purge: this script does NOT purge the edge cache for each gene
(that would be ~19k purge calls per sync). The CellxGene endpoint is
served with the same long Cache-Control as the per-gene record endpoint,
but census versions only refresh quarterly; for the cadence of a fresh
Census release, the right move is to call the Cloudflare cache purge API
once with a wildcard pattern (or rely on the natural TTL) instead of
per-URL purging. Add a wildcard purge here if/when census refreshes
start happening on a faster cadence.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config, D1Error
from accessible_surfaceome.env import load_env

logger = logging.getLogger("sync_czi_enrichment")

DEFAULT_SNAPSHOT_DIR = Path("/tmp/czi_enrichment")
DEFAULT_SCHEMA_VERSION = "1.0"

DDL = [
    """\
CREATE TABLE IF NOT EXISTS czi_cellxgene_enrichment (
    gene_symbol         TEXT NOT NULL,
    hgnc_id             TEXT,
    ensembl_gene        TEXT,
    schema_version      TEXT NOT NULL,
    census_version      TEXT NOT NULL,
    enrichment_json     TEXT NOT NULL,
    computed_at         TEXT NOT NULL,
    synced_at           TEXT NOT NULL DEFAULT (datetime('now')),
    cell_family_class   TEXT,
    cell_family_top     TEXT,
    cell_family_tau     REAL,
    tissue_organ_class  TEXT,
    tissue_organ_top    TEXT,
    tissue_organ_tau    REAL,
    PRIMARY KEY (gene_symbol, schema_version, census_version)
);""",
    # Idempotent column-adds for tables already created without the
    # v2.1.5 denormalized columns. D1 / SQLite doesn't have ALTER
    # ADD COLUMN IF NOT EXISTS, so we wrap each in a try/except at
    # apply time (see _apply_ddl).
    "ALTER TABLE czi_cellxgene_enrichment ADD COLUMN cell_family_class TEXT;",
    "ALTER TABLE czi_cellxgene_enrichment ADD COLUMN cell_family_top TEXT;",
    "ALTER TABLE czi_cellxgene_enrichment ADD COLUMN cell_family_tau REAL;",
    "ALTER TABLE czi_cellxgene_enrichment ADD COLUMN tissue_organ_class TEXT;",
    "ALTER TABLE czi_cellxgene_enrichment ADD COLUMN tissue_organ_top TEXT;",
    "ALTER TABLE czi_cellxgene_enrichment ADD COLUMN tissue_organ_tau REAL;",
    "CREATE INDEX IF NOT EXISTS idx_czi_cellxgene_enrichment_hgnc ON czi_cellxgene_enrichment (hgnc_id);",
    "CREATE INDEX IF NOT EXISTS idx_czi_cellxgene_enrichment_ensembl ON czi_cellxgene_enrichment (ensembl_gene);",
    "CREATE INDEX IF NOT EXISTS idx_czi_cellxgene_enrichment_census ON czi_cellxgene_enrichment (census_version);",
    "CREATE INDEX IF NOT EXISTS idx_czi_cellxgene_cell_family_class ON czi_cellxgene_enrichment (cell_family_class);",
    "CREATE INDEX IF NOT EXISTS idx_czi_cellxgene_tissue_organ_class ON czi_cellxgene_enrichment (tissue_organ_class);",
]

UPSERT_SQL = """\
INSERT OR REPLACE INTO czi_cellxgene_enrichment
    (gene_symbol, hgnc_id, ensembl_gene, schema_version,
     census_version, enrichment_json, computed_at,
     cell_family_class, cell_family_top, cell_family_tau,
     tissue_organ_class, tissue_organ_top, tissue_organ_tau)
VALUES (?, ?, ?, ?, ?, ?, ?,  ?, ?, ?,  ?, ?, ?);
"""


@dataclass(frozen=True)
class Row:
    gene_symbol: str
    hgnc_id: str | None
    ensembl_gene: str | None
    schema_version: str
    census_version: str
    enrichment_json: str
    computed_at: str
    # v2.1.5+ denormalized chip-facing columns.
    cell_family_class: str | None
    cell_family_top: str | None  # pipe-separated top 1-3 entity labels
    cell_family_tau: float | None
    tissue_organ_class: str | None
    tissue_organ_top: str | None
    tissue_organ_tau: float | None

    @classmethod
    def from_snapshot(cls, path: Path) -> Row | None:
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("skip %s: %s", path.name, e)
            return None
        sym = payload.get("gene_symbol")
        if not sym:
            logger.warning("skip %s: no gene_symbol", path.name)
            return None
        # Extract chip-facing columns from v2.1.4+ records. Older records
        # leave them None; the DB columns are nullable.
        cf = payload.get("cell_family_enrichment") or {}
        to = payload.get("tissue_organ_enrichment") or {}
        return cls(
            gene_symbol=str(sym),
            hgnc_id=payload.get("hgnc_id"),
            ensembl_gene=payload.get("ensembl_gene"),
            schema_version=str(payload.get("schema_version", DEFAULT_SCHEMA_VERSION)),
            census_version=str(payload.get("census_version", "")),
            enrichment_json=json.dumps(payload, separators=(",", ":")),
            computed_at=str(payload.get("computed_at") or _utc_now()),
            cell_family_class=cf.get("class"),
            cell_family_top="|".join((cf.get("family_labels") or [])[:3]) or None,
            cell_family_tau=cf.get("tau"),
            tissue_organ_class=to.get("class"),
            tissue_organ_top="|".join((to.get("organ_labels") or [])[:3]) or None,
            tissue_organ_tau=to.get("tau"),
        )

    def params(self) -> list[object]:
        return [
            self.gene_symbol,
            self.hgnc_id,
            self.ensembl_gene,
            self.schema_version,
            self.census_version,
            self.enrichment_json,
            self.computed_at,
            self.cell_family_class,
            self.cell_family_top,
            self.cell_family_tau,
            self.tissue_organ_class,
            self.tissue_organ_top,
            self.tissue_organ_tau,
        ]


def _utc_now() -> str:
    # Avoid datetime.now() in libraries that participate in
    # cache-replay tooling; this script is one-shot so it's fine.
    import datetime as dt
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def _apply_ddl(client: D1Client, *, label: str) -> None:
    for stmt in DDL:
        try:
            client.query(stmt, [])
        except D1Error as e:
            # ALTER TABLE ADD COLUMN fails on D1 / SQLite when the
            # column already exists. Treat that as a no-op; everything
            # else is a real DDL failure.
            msg = str(e).lower()
            if stmt.lstrip().upper().startswith("ALTER TABLE") and (
                "duplicate column" in msg or "already exists" in msg
            ):
                continue
            logger.error("[%s] DDL failed: %s\nstatement: %s", label, e, stmt)
            raise


def _push_one(client: D1Client, row: Row) -> tuple[str, bool, str | None]:
    try:
        # Delete any older schema_version rows for this gene FIRST. The
        # table's primary key is (gene_symbol, schema_version, census_version),
        # so a schema bump on the build script inserts a new row instead
        # of replacing — leaving 11 rows per gene after 11 schema bumps.
        # The Worker's catalog endpoint LEFT JOIN then fans out N×11 rows.
        # Cleaning up stale schemas at push time prevents this drift from
        # accumulating again.
        client.query(
            "DELETE FROM czi_cellxgene_enrichment "
            "WHERE gene_symbol = ? AND schema_version != ?;",
            [row.gene_symbol, row.schema_version],
        )
        client.query(UPSERT_SQL, row.params())
        return row.gene_symbol, True, None
    except D1Error as e:
        return row.gene_symbol, False, str(e)


def _push_all(
    config: D1Config,
    rows: list[Row],
    *,
    workers: int,
    label: str,
    dry_run: bool,
) -> tuple[int, int]:
    if dry_run:
        logger.info("[%s] dry-run: would push %d rows", label, len(rows))
        return len(rows), 0

    ok = 0
    fail = 0
    started = time.time()

    def _worker(row: Row) -> tuple[str, bool, str | None]:
        with D1Client(config) as client:
            return _push_one(client, row)

    # Parallel HTTP POSTs. D1's HTTP API is single-statement-per-call so
    # the only way to keep wall-clock sane on 19k rows is concurrent
    # requests. Each thread owns its own httpx.Client (no shared state),
    # so the pool size is the natural concurrency limit.
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_worker, r) for r in rows]
        for i, fut in enumerate(concurrent.futures.as_completed(futures), start=1):
            sym, succeeded, err = fut.result()
            if succeeded:
                ok += 1
            else:
                fail += 1
                if fail <= 10:
                    logger.warning("[%s] %s FAILED: %s", label, sym, err)
            if i % 500 == 0:
                elapsed = time.time() - started
                rate = i / elapsed if elapsed > 0 else 0
                logger.info(
                    "[%s] %d/%d (%.1f rows/s, ok=%d fail=%d)",
                    label, i, len(rows), rate, ok, fail,
                )

    elapsed = time.time() - started
    logger.info(
        "[%s] done: %d ok, %d fail in %.1fs", label, ok, fail, elapsed
    )
    return ok, fail


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    load_env()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=DEFAULT_SNAPSHOT_DIR,
        help="Directory of per-gene JSON files. Default: /tmp/czi_enrichment",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually push to D1. Default: dry-run.",
    )
    parser.add_argument(
        "--public-only",
        action="store_true",
        help="Skip the private DB push (refresh public mirror only).",
    )
    parser.add_argument(
        "--private-only",
        action="store_true",
        help="Skip the public DB push (private only — for debugging).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=16,
        help="Concurrent HTTP POSTs to D1. Default: 16.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process only the first N snapshots (0 = all). For testing.",
    )
    args = parser.parse_args()

    snapshot_dir: Path = args.snapshot_dir
    if not snapshot_dir.is_dir():
        logger.error("snapshot dir does not exist: %s", snapshot_dir)
        return 2

    snapshots = sorted(snapshot_dir.glob("*.json"))
    if args.limit > 0:
        snapshots = snapshots[: args.limit]
    if not snapshots:
        logger.error("no JSON snapshots found in %s", snapshot_dir)
        return 2
    logger.info("found %d snapshots in %s", len(snapshots), snapshot_dir)

    rows: list[Row] = []
    for path in snapshots:
        r = Row.from_snapshot(path)
        if r is not None:
            rows.append(r)
    logger.info("loaded %d rows", len(rows))

    if not rows:
        logger.error("no usable rows; aborting")
        return 2

    dry_run = not args.execute

    # Apply DDL first so the table exists. Idempotent (CREATE TABLE IF NOT
    # EXISTS / CREATE INDEX IF NOT EXISTS).
    targets = []
    if not args.public_only:
        targets.append(("private", D1Config.from_env))
    if not args.private_only:
        targets.append(("public", D1Config.from_env_public))

    if not targets:
        logger.error("both --public-only and --private-only set; nothing to do")
        return 2

    for label, cfg_fn in targets:
        try:
            cfg = cfg_fn()
        except D1Error as e:
            logger.warning("[%s] D1 config unavailable, skipping: %s", label, e)
            continue
        if not dry_run:
            logger.info("[%s] applying DDL", label)
            with D1Client(cfg) as client:
                _apply_ddl(client, label=label)
        _push_all(cfg, rows, workers=args.workers, label=label, dry_run=dry_run)

    if dry_run:
        logger.info("dry-run complete; re-run with --execute to push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
