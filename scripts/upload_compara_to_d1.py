"""Upload an Ensembl Compara ortholog CSV to the surfaceome_agents D1 database.

Reads a refreshed Compara CSV (produced by
``python -m accessible_surfaceome.sources.ensembl_compara download``)
and inserts one ``compara_ortholog`` row per (human_ensembl_gene,
species, ortholog_ensembl_gene), stamped with a ``release_version``
that identifies this snapshot for later replay.

Idempotent on (release_version, human_ensembl_gene, species,
ortholog_ensembl_gene): existing rows are skipped via
``INSERT OR IGNORE``. To force a re-upload, use a fresh release_version
or DELETE the existing rows.

Usage::

    uv run python scripts/upload_compara_to_d1.py \\
        --release ensembl_compara_2026_05_11 \\
        --csv data/external/ensembl_compara_surfaceome_expressed/compara_mouse_cyno_one2one_highconf_by_ensembl_query.csv
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

from accessible_surfaceome.cloud.d1_client import D1Client, D1Error
from accessible_surfaceome.env import load_env

logger = logging.getLogger(__name__)

# Batch size for D1 inserts. D1's HTTP API caps single requests at ~100 KB;
# 200 ortholog rows × ~150 chars/row = ~30 KB, comfortably under the limit.
BATCH_SIZE = 200


def _intern_release(
    client: D1Client, *, release_version: str, n_pairs: int, source_url: str | None,
    notes: str | None,
) -> None:
    """Insert (or no-op-update) the compara_release row for this snapshot."""
    client.query(
        """
        INSERT INTO compara_release (release_version, n_pairs, source_url, notes)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (release_version) DO UPDATE SET
            n_pairs = excluded.n_pairs,
            source_url = COALESCE(excluded.source_url, compara_release.source_url),
            notes = COALESCE(excluded.notes, compara_release.notes)
        """,
        [release_version, n_pairs, source_url, notes],
    )


def _row_params(row: dict[str, str], release_version: str) -> list[object]:
    """Map a CSV row to the compara_ortholog INSERT parameter list."""
    def _opt(name: str) -> str | None:
        v = (row.get(name) or "").strip()
        return v or None

    def _float(name: str) -> float | None:
        v = _opt(name)
        try:
            return float(v) if v is not None else None
        except ValueError:
            return None

    is_high_conf = 1 if (row.get("is_high_confidence") or "").strip() in {"1", "true", "True"} else 0
    return [
        release_version,
        _opt("human_ensembl_gene") or "",
        _opt("human_uniprot_acc"),
        _opt("human_gene_symbol"),
        _opt("species") or "unknown",
        _opt("ortholog_ensembl_gene") or "",
        _opt("ortholog_uniprot_acc"),
        _opt("ortholog_gene_symbol"),
        _opt("orthology_type") or "unknown",
        _float("percent_identity"),
        is_high_conf,
    ]


def upload(
    *, csv_path: Path, release_version: str, source_url: str | None = None,
    notes: str | None = None, dry_run: bool = False,
) -> int:
    """Upload one Compara CSV to D1. Returns the number of rows inserted
    (or staged, if dry_run)."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Compara CSV not found: {csv_path}")

    rows: list[list[object]] = []
    with csv_path.open() as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(_row_params(row, release_version))
    n = len(rows)
    logger.info("Loaded %d ortholog rows from %s", n, csv_path)

    if dry_run:
        logger.info("Dry run — not uploading. Would insert %d rows under release_version=%r", n, release_version)
        return n

    insert_sql = """
        INSERT OR IGNORE INTO compara_ortholog (
            release_version, human_ensembl_gene, human_uniprot_acc,
            human_gene_symbol, species, ortholog_ensembl_gene,
            ortholog_uniprot_acc, ortholog_gene_symbol, orthology_type,
            percent_identity, is_high_confidence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    with D1Client() as client:
        _intern_release(
            client, release_version=release_version, n_pairs=n,
            source_url=source_url, notes=notes,
        )
        for start in range(0, n, BATCH_SIZE):
            chunk = rows[start : start + BATCH_SIZE]
            client.batch([(insert_sql, params) for params in chunk])
            logger.info("Uploaded rows %d..%d", start, start + len(chunk) - 1)
    return n


def main() -> int:
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--release", required=True,
        help="Release version label, e.g. ensembl_compara_2026_05_11",
    )
    ap.add_argument("--csv", required=True, type=Path, help="Path to the Compara CSV")
    ap.add_argument("--source-url", help="BioMart endpoint that produced the rows (optional)")
    ap.add_argument("--notes", help="Free-text refresh notes (optional)")
    ap.add_argument("--dry-run", action="store_true", help="Parse the CSV but don't write to D1")
    args = ap.parse_args()

    try:
        n = upload(
            csv_path=args.csv, release_version=args.release,
            source_url=args.source_url, notes=args.notes, dry_run=args.dry_run,
        )
    except D1Error as exc:
        logger.error("D1 upload failed: %s", exc)
        return 2
    logger.info("Done — %d rows for release_version=%r", n, args.release)
    return 0


if __name__ == "__main__":
    sys.exit(main())
