"""Add the topology + paralog tables to both D1 databases.

Creates four tables (each in both surfaceome_agents and surfaceome_public):
  * topology_public          — per-isoform DeepTMHMM topology + sequence
  * topology_release         — release pointer for topology
  * compara_paralog          — Ensembl Compara within-species paralogs
  * compara_paralog_release  — release pointer for paralogs

All statements are CREATE TABLE / CREATE INDEX IF NOT EXISTS, so this is
idempotent. Pattern mirrors scripts/d1_migrate_add_confidence.py.

Usage::

    uv run python scripts/d1_migrate_add_topology_paralogs.py --apply

Without --apply this is a dry run (prints SQL it would execute, but does
not hit the API). Requires CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_API_TOKEN +
CLOUDFLARE_D1_SURFACEOME_AGENTS_ID + CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID in
.env (see .env.example).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any

import httpx

from accessible_surfaceome.env import load_env

logger = logging.getLogger(__name__)

API_ROOT = "https://api.cloudflare.com/client/v4"

# Each statement is single-statement; D1's /query endpoint takes one
# {sql, params} per POST.
STATEMENTS: list[tuple[str, str]] = [
    (
        "topology_public",
        """
        CREATE TABLE IF NOT EXISTS topology_public (
            topology_version           TEXT NOT NULL,
            cohort                     TEXT NOT NULL,
            hgnc_id                    TEXT,
            uniprot_acc                TEXT NOT NULL,
            uniprot_acc_full           TEXT NOT NULL,
            isoform_id                 TEXT NOT NULL,
            gene_symbol                TEXT,
            species                    TEXT NOT NULL,
            is_canonical               INTEGER NOT NULL,
            sequence                   TEXT NOT NULL,
            protein_length             INTEGER NOT NULL,
            deeptmhmm_label            TEXT NOT NULL,
            tm_helix_count             INTEGER NOT NULL,
            beta_strand_count          INTEGER NOT NULL,
            n_terminal_orientation     TEXT NOT NULL,
            c_terminal_orientation     TEXT NOT NULL,
            signal_peptide_length      INTEGER NOT NULL,
            ecd_length_residues        INTEGER NOT NULL,
            icd_length_residues        INTEGER NOT NULL,
            per_residue_topology       TEXT NOT NULL,
            predicted_surface_membrane INTEGER NOT NULL,
            predicted_secreted         INTEGER NOT NULL,
            tool_version               TEXT NOT NULL,
            retrieved_at               TEXT NOT NULL,
            synced_at                  TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (topology_version, cohort, uniprot_acc_full)
        )
        """,
    ),
    (
        "idx_topology_public_hgnc",
        "CREATE INDEX IF NOT EXISTS idx_topology_public_hgnc ON topology_public (hgnc_id)",
    ),
    (
        "idx_topology_public_gene",
        "CREATE INDEX IF NOT EXISTS idx_topology_public_gene ON topology_public (gene_symbol)",
    ),
    (
        "idx_topology_public_uniprot",
        "CREATE INDEX IF NOT EXISTS idx_topology_public_uniprot ON topology_public (uniprot_acc)",
    ),
    (
        "idx_topology_public_canonical",
        "CREATE INDEX IF NOT EXISTS idx_topology_public_canonical "
        "ON topology_public (topology_version, cohort, is_canonical)",
    ),
    (
        "topology_release",
        """
        CREATE TABLE IF NOT EXISTS topology_release (
            topology_version    TEXT PRIMARY KEY,
            n_rows              INTEGER NOT NULL,
            cohorts_present     TEXT NOT NULL,
            deeptmhmm_version   TEXT NOT NULL,
            attribution         TEXT,
            license_url         TEXT,
            loaded_at           TEXT NOT NULL DEFAULT (datetime('now')),
            source_run_dir      TEXT,
            notes               TEXT
        )
        """,
    ),
    (
        "compara_paralog",
        """
        CREATE TABLE IF NOT EXISTS compara_paralog (
            paralog_version          TEXT NOT NULL,
            human_hgnc_id            TEXT,
            human_ensembl_gene       TEXT NOT NULL,
            human_uniprot_acc        TEXT,
            human_gene_symbol        TEXT,
            paralog_hgnc_id          TEXT,
            paralog_ensembl_gene     TEXT NOT NULL,
            paralog_uniprot_acc      TEXT,
            paralog_gene_symbol      TEXT,
            family_id                TEXT,
            biomart_percent_identity REAL,
            ecd_pct_identity         REAL,
            n_ecd_loops_compared     INTEGER,
            rank_by_ecd_identity     INTEGER,
            paralogy_type            TEXT,
            is_high_confidence       INTEGER NOT NULL,
            compara_version          TEXT NOT NULL,
            synced_at                TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (paralog_version, human_ensembl_gene, paralog_ensembl_gene)
        )
        """,
    ),
    (
        "idx_compara_paralog_human_hgnc",
        "CREATE INDEX IF NOT EXISTS idx_compara_paralog_human_hgnc "
        "ON compara_paralog (human_hgnc_id)",
    ),
    (
        "idx_compara_paralog_human_uniprot",
        "CREATE INDEX IF NOT EXISTS idx_compara_paralog_human_uniprot "
        "ON compara_paralog (human_uniprot_acc)",
    ),
    (
        "idx_compara_paralog_human_symbol",
        "CREATE INDEX IF NOT EXISTS idx_compara_paralog_human_symbol "
        "ON compara_paralog (human_gene_symbol)",
    ),
    (
        "idx_compara_paralog_version_human",
        "CREATE INDEX IF NOT EXISTS idx_compara_paralog_version_human "
        "ON compara_paralog (paralog_version, human_ensembl_gene)",
    ),
    (
        "compara_paralog_release",
        """
        CREATE TABLE IF NOT EXISTS compara_paralog_release (
            paralog_version    TEXT PRIMARY KEY,
            compara_release    TEXT NOT NULL,
            n_pairs            INTEGER NOT NULL,
            n_human_genes      INTEGER NOT NULL,
            fetched_at         TEXT NOT NULL DEFAULT (datetime('now')),
            source_url         TEXT,
            notes              TEXT
        )
        """,
    ),
]


@dataclass(frozen=True)
class D1Target:
    name: str
    account_id: str
    database_id: str
    api_token: str

    @property
    def url(self) -> str:
        return f"{API_ROOT}/accounts/{self.account_id}/d1/database/{self.database_id}/query"


def _resolve_targets() -> list[D1Target]:
    """Return one target per configured D1 DB. At least one of agents/public required."""
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    agents_db = os.environ.get("CLOUDFLARE_D1_SURFACEOME_AGENTS_ID", "").strip()
    public_db = os.environ.get("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "").strip()

    missing: list[str] = []
    if not account:
        missing.append("CLOUDFLARE_ACCOUNT_ID")
    if not token:
        missing.append("CLOUDFLARE_API_TOKEN")
    if missing:
        raise SystemExit(
            "Missing env vars: " + ", ".join(missing) + ". See .env.example."
        )

    targets: list[D1Target] = []
    if agents_db:
        targets.append(D1Target("surfaceome_agents", account, agents_db, token))
    else:
        logger.warning(
            "CLOUDFLARE_D1_SURFACEOME_AGENTS_ID not set — skipping private DB migration"
        )
    if public_db:
        targets.append(D1Target("surfaceome_public", account, public_db, token))
    else:
        logger.warning(
            "CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID not set — skipping public mirror migration. "
            "Apply manually via: wrangler d1 execute surfaceome_public --remote "
            "--file=cloudflare/d1_public_schema.sql"
        )
    if not targets:
        raise SystemExit("No D1 DBs configured in env")
    return targets


def _query(target: D1Target, sql: str, *, client: httpx.Client) -> Any:
    resp = client.post(
        target.url,
        json={"sql": sql},
        headers={"Authorization": f"Bearer {target.api_token}"},
        timeout=60,
    )
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"D1 error ({target.name}): {data}")
    return data.get("result")


def main() -> int:
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Actually execute the migrations. Without this flag the script "
             "prints the SQL it would execute and exits.",
    )
    args = ap.parse_args()

    targets = _resolve_targets()
    logger.info("targets: %s", ", ".join(f"{t.name}={t.database_id[:8]}…" for t in targets))
    logger.info("%d migration statements per target", len(STATEMENTS))

    if not args.apply:
        logger.info("--apply NOT set; printing statements and exiting (dry run)")
        for name, sql in STATEMENTS:
            print(f"\n-- {name} --")
            print(sql.strip())
        return 0

    with httpx.Client(timeout=60) as client:
        for target in targets:
            logger.info("applying to %s (%s)", target.name, target.database_id[:8])
            _ensure_columns(target, client=client)
            for name, sql in STATEMENTS:
                _query(target, sql.strip(), client=client)
                logger.info("  ✓ %s", name)
    logger.info("done — both DBs have topology_public + compara_paralog + release pointers")
    return 0


def _table_columns(target: D1Target, table: str, *, client: httpx.Client) -> set[str]:
    """Return the set of column names on ``table`` via PRAGMA. Empty set if
    the table doesn't exist yet (CREATE TABLE will run after this)."""
    url = target.url
    resp = client.post(
        url,
        json={"sql": f"PRAGMA table_info({table})"},
        headers={"Authorization": f"Bearer {target.api_token}"},
        timeout=60,
    )
    data = resp.json()
    if not data.get("success"):
        return set()
    result = data.get("result") or []
    if isinstance(result, dict):
        result = [result]
    cols: set[str] = set()
    for r in result:
        for row in r.get("results") or []:
            name = row.get("name")
            if name:
                cols.add(str(name))
    return cols


# (column_name, sqlite_type) pairs to add when missing. SQLite's
# ``ADD COLUMN`` doesn't support ``IF NOT EXISTS``, so we PRAGMA-check first.
TOPOLOGY_NEW_COLUMNS: list[tuple[str, str]] = [
    ("hgnc_id", "TEXT"),
]
COMPARA_PARALOG_NEW_COLUMNS: list[tuple[str, str]] = [
    ("human_hgnc_id", "TEXT"),
    ("paralog_hgnc_id", "TEXT"),
]


def _ensure_columns(target: D1Target, *, client: httpx.Client) -> None:
    """ALTER TABLE ADD COLUMN for the v0.5 stable-ID columns when missing.

    Runs before the CREATE TABLE statements so the new columns exist on
    pre-v0.5 schemas (where the table already existed without hgnc_id).
    On fresh databases this is a no-op — PRAGMA returns empty, no ALTER
    runs, then the CREATE TABLE creates the full schema.
    """
    for table, new_cols in [
        ("topology_public", TOPOLOGY_NEW_COLUMNS),
        ("compara_paralog", COMPARA_PARALOG_NEW_COLUMNS),
    ]:
        existing = _table_columns(target, table, client=client)
        if not existing:
            continue  # Table doesn't exist yet; CREATE TABLE will handle it.
        for col, typ in new_cols:
            if col in existing:
                continue
            logger.info("  + ALTER TABLE %s ADD COLUMN %s %s", table, col, typ)
            _query(target, f"ALTER TABLE {table} ADD COLUMN {col} {typ}", client=client)


if __name__ == "__main__":
    sys.exit(main())
