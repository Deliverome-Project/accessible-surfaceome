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

# Batch size for D1 inserts. Cloudflare D1 caps placeholders at ~100 per
# statement (tighter than SQLite's default 999); 11 columns/row × 8 rows
# = 88 placeholders stays under that ceiling.
BATCH_SIZE = 8


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


def _opt(row: dict[str, str], name: str) -> str | None:
    v = (row.get(name) or "").strip()
    return v or None


def _float(row: dict[str, str], name: str) -> float | None:
    v = _opt(row, name)
    try:
        return float(v) if v is not None else None
    except ValueError:
        return None


def _row_params(row: dict[str, str], release_version: str) -> list[object]:
    """Map one LONG-format CSV row to the compara_ortholog INSERT params."""
    is_high_conf = 1 if (row.get("is_high_confidence") or "").strip() in {"1", "true", "True"} else 0
    return [
        release_version,
        _opt(row, "human_ensembl_gene") or "",
        _opt(row, "human_uniprot_acc"),
        _opt(row, "human_gene_symbol"),
        _opt(row, "species") or "unknown",
        _opt(row, "ortholog_ensembl_gene") or "",
        _opt(row, "ortholog_uniprot_acc"),
        _opt(row, "ortholog_gene_symbol"),
        _opt(row, "orthology_type") or "unknown",
        _float(row, "percent_identity"),
        is_high_conf,
    ]


def _wide_to_long(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Convert the producer's WIDE CSV (one row per human gene with both
    mouse and cyno columns inline) into LONG rows the D1 schema expects.

    Yields one row per (human_ensembl_gene, species, ortholog) when the
    species pair was flagged high-confidence. Missing species are skipped.
    """
    out: list[dict[str, str]] = []
    for row in rows:
        human_eng = (row.get("query_ensembl_gene_id") or "").strip()
        if not human_eng:
            continue
        # Pick the first symbol from the semicolon-joined alias list.
        sym_field = (row.get("query_input_gene_symbols") or "").strip()
        human_sym = sym_field.split(";")[0].strip() if sym_field else ""
        for prefix, canonical in (("mouse", "mouse"), ("cyno", "cynomolgus")):
            has_hc = (row.get(f"{prefix}_has_one2one_high_confidence") or "").strip().lower()
            if has_hc not in {"1", "true", "yes", "y", "t"}:
                continue
            ortho_eng = (row.get(f"{prefix}_target_ensembl_gene_id") or "").strip()
            if not ortho_eng:
                continue
            out.append({
                "human_ensembl_gene": human_eng,
                "human_uniprot_acc": "",  # producer doesn't emit this
                "human_gene_symbol": human_sym,
                "species": canonical,
                "ortholog_ensembl_gene": ortho_eng,
                "ortholog_uniprot_acc": "",
                "ortholog_gene_symbol": (row.get(f"{prefix}_target_gene_symbol") or "").strip(),
                "orthology_type": (row.get(f"{prefix}_orthology_type") or "unknown").strip() or "unknown",
                "percent_identity": (row.get(f"{prefix}_target_percent_identity") or "").strip(),
                "is_high_confidence": "1",
            })
    return out


def upload(
    *, csv_path: Path, release_version: str, source_url: str | None = None,
    notes: str | None = None, dry_run: bool = False,
) -> int:
    """Upload one Compara CSV to D1. Returns the number of rows inserted
    (or staged, if dry_run)."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Compara CSV not found: {csv_path}")

    with csv_path.open() as fh:
        reader = csv.DictReader(fh)
        raw = list(reader)
    if not raw:
        logger.warning("Empty CSV at %s — nothing to upload", csv_path)
        return 0
    # Detect wide vs long format by sniffing for the producer's species-prefixed columns.
    is_wide = "mouse_target_ensembl_gene_id" in raw[0]
    long_rows = _wide_to_long(raw) if is_wide else raw
    if is_wide:
        logger.info("Converted %d wide CSV rows → %d long ortholog rows", len(raw), len(long_rows))
    rows = [_row_params(r, release_version) for r in long_rows]
    n = len(rows)
    logger.info("Loaded %d ortholog rows from %s", n, csv_path)

    if dry_run:
        logger.info("Dry run — not uploading. Would insert %d rows under release_version=%r", n, release_version)
        return n

    cols = (
        "release_version, human_ensembl_gene, human_uniprot_acc, "
        "human_gene_symbol, species, ortholog_ensembl_gene, "
        "ortholog_uniprot_acc, ortholog_gene_symbol, orthology_type, "
        "percent_identity, is_high_confidence"
    )
    one_row_placeholders = "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"

    with D1Client() as client:
        _intern_release(
            client, release_version=release_version, n_pairs=n,
            source_url=source_url, notes=notes,
        )
        # D1 rejected the batch-array endpoint variant we used previously;
        # use multi-row INSERT statements (one SQL per chunk, parameters
        # spliced in line). Each chunk gets one round-trip.
        for start in range(0, n, BATCH_SIZE):
            chunk = rows[start : start + BATCH_SIZE]
            placeholders = ", ".join(one_row_placeholders for _ in chunk)
            sql = f"INSERT OR IGNORE INTO compara_ortholog ({cols}) VALUES {placeholders}"
            flat_params: list[object] = [v for params in chunk for v in params]
            client.query(sql, flat_params)
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
