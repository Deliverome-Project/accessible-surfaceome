"""Upload paralog records (with computed ECD identity) to the D1 ``compara_paralog`` mirror.

Reads a JSONL file produced by ``run_topology_sweep.py`` (which combines
``ensembl_compara_paralogs.py`` output with locally-computed ``ecd_pct_identity``).
Writes to both ``surfaceome_agents`` and ``surfaceome_public``.

Idempotent on (paralog_version, human_ensembl_gene, paralog_ensembl_gene)
via INSERT OR IGNORE.

Usage::

    uv run python scripts/upload_paralogs_to_d1.py \\
        --paralog-version paralog_2026_05_16 \\
        --compara-release "ensembl_compara_2026_06_01" \\
        --jsonl data/processed/topology_run_topo_2026_05_16/paralog_records.jsonl

Note: legacy D1 rows carry the historical label ``"Compara r112"`` — that
string was a hard-coded default that never got bumped as Ensembl bumped
releases (real biology on those rows is r115-era). New uploads should use
the dated-snapshot convention matching the ortholog side.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from accessible_surfaceome.env import load_env

logger = logging.getLogger(__name__)

# 17 columns * 5 rows = 85 placeholders, under D1's 100 cap.
BATCH_SIZE = 5
API_ROOT = "https://api.cloudflare.com/client/v4"

COLS = [
    "paralog_version",
    "human_hgnc_id",          # PR #30 stable-ID join key
    "human_ensembl_gene",
    "human_uniprot_acc",
    "human_gene_symbol",
    "paralog_hgnc_id",        # PR #30 stable-ID join key for the paralog
    "paralog_ensembl_gene",
    "paralog_uniprot_acc",
    "paralog_gene_symbol",
    "family_id",
    "biomart_percent_identity",
    "ecd_pct_identity",
    "n_ecd_loops_compared",
    "rank_by_ecd_identity",
    "paralogy_type",
    "is_high_confidence",
    "compara_version",
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


def _resolve_targets(*, public_only: bool, private_only: bool) -> list[D1Target]:
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    agents = os.environ.get("CLOUDFLARE_D1_SURFACEOME_AGENTS_ID", "").strip()
    public = os.environ.get("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "").strip()
    if not account or not token:
        raise SystemExit("Missing CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN")

    targets: list[D1Target] = []
    if not public_only and agents:
        targets.append(D1Target("surfaceome_agents", account, agents, token))
    if not private_only and public:
        targets.append(D1Target("surfaceome_public", account, public, token))
    if not targets:
        raise SystemExit("No D1 targets configured")
    return targets


def _query(target: D1Target, sql: str, params: list[Any], *, client: httpx.Client) -> None:
    resp = client.post(
        target.url,
        json={"sql": sql, "params": params},
        headers={"Authorization": f"Bearer {target.api_token}"},
        timeout=120,
    )
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"D1 error ({target.name}): {data}")


def _row_to_params(rec: dict[str, Any]) -> list[Any]:
    return [
        rec["paralog_version"],
        rec.get("human_hgnc_id"),
        rec["human_ensembl_gene"],
        rec.get("human_uniprot_acc"),
        rec.get("human_gene_symbol"),
        rec.get("paralog_hgnc_id"),
        rec["paralog_ensembl_gene"],
        rec.get("paralog_uniprot_acc"),
        rec.get("paralog_gene_symbol"),
        rec.get("family_id"),
        rec.get("biomart_percent_identity"),
        rec.get("ecd_pct_identity"),
        rec.get("n_ecd_loops_compared"),
        rec.get("rank_by_ecd_identity"),
        rec.get("paralogy_type"),
        int(rec.get("is_high_confidence", 0)),
        # Required — no silent fallback to "Compara r112" (that string was a
        # hard-coded default that never got bumped as Ensembl bumped releases;
        # legacy rows carry it but new uploads must not perpetuate the lie).
        rec["compara_version"],
    ]


def _upload_rows(
    target: D1Target,
    rows: list[dict[str, Any]],
    *,
    client: httpx.Client,
    dry_run: bool,
) -> None:
    if not rows:
        return
    placeholders_one = "(" + ", ".join(["?"] * len(COLS)) + ")"
    cols_sql = ", ".join(COLS)
    total = len(rows)
    for start in range(0, total, BATCH_SIZE):
        chunk = rows[start : start + BATCH_SIZE]
        sql = (
            f"INSERT OR IGNORE INTO compara_paralog ({cols_sql}) "
            f"VALUES {', '.join([placeholders_one] * len(chunk))}"
        )
        params: list[Any] = []
        for rec in chunk:
            params.extend(_row_to_params(rec))
        if dry_run:
            logger.info(
                "[DRY %s] rows %d..%d (n=%d, %d params)",
                target.name, start, start + len(chunk) - 1, len(chunk), len(params),
            )
            continue
        _query(target, sql, params, client=client)
        if (start // BATCH_SIZE) % 50 == 0:
            logger.info("  %s: rows %d..%d done", target.name, start, start + len(chunk) - 1)


def _upsert_release(
    target: D1Target,
    *,
    paralog_version: str,
    compara_release: str,
    n_pairs: int,
    n_human_genes: int,
    source_url: str,
    notes: str | None,
    client: httpx.Client,
    dry_run: bool,
) -> None:
    if dry_run:
        logger.info(
            "[DRY %s] release(paralog_version=%s, n_pairs=%d)", target.name, paralog_version, n_pairs,
        )
        return
    _query(
        target,
        "INSERT INTO compara_paralog_release "
        "(paralog_version, compara_release, n_pairs, n_human_genes, source_url, notes) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (paralog_version) DO UPDATE SET "
        "  compara_release = excluded.compara_release, "
        "  n_pairs = excluded.n_pairs, "
        "  n_human_genes = excluded.n_human_genes, "
        "  source_url = excluded.source_url, "
        "  notes = excluded.notes",
        [paralog_version, compara_release, n_pairs, n_human_genes, source_url, notes],
        client=client,
    )


def _load_jsonl(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in paths:
        if not p.exists():
            raise SystemExit(f"JSONL not found: {p}")
        with p.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def main() -> int:
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--paralog-version", required=True)
    ap.add_argument(
        "--compara-release",
        required=True,
        help="Compara release label — used as an FK into D1's compara_release "
        "table. Preferred shape: dated snapshot tag (e.g. "
        "'ensembl_compara_2026_06_01'), matching the ortholog side's "
        "convention. Legacy rows carry the historical 'Compara r112' "
        "string; do not reuse it for new uploads.",
    )
    ap.add_argument("--jsonl", type=Path, action="append", required=True)
    ap.add_argument("--source-url", default="https://www.ensembl.org/biomart/martservice")
    ap.add_argument(
        "--notes",
        default="",
        help="Free-text / JSON written to compara_paralog_release.notes (provenance).",
    )
    ap.add_argument("--public-only", action="store_true")
    ap.add_argument("--private-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = _load_jsonl(args.jsonl)
    for r in rows:
        r["paralog_version"] = args.paralog_version
        r.setdefault("compara_version", args.compara_release)
    n_human_genes = len({r["human_ensembl_gene"] for r in rows})
    logger.info("loaded %d paralog rows covering %d human genes", len(rows), n_human_genes)

    targets = _resolve_targets(public_only=args.public_only, private_only=args.private_only)
    logger.info("targets: %s", ", ".join(t.name for t in targets))

    with httpx.Client(timeout=120) as client:
        for target in targets:
            logger.info("uploading to %s", target.name)
            _upload_rows(target, rows, client=client, dry_run=args.dry_run)
            _upsert_release(
                target,
                paralog_version=args.paralog_version,
                compara_release=args.compara_release,
                n_pairs=len(rows),
                n_human_genes=n_human_genes,
                source_url=args.source_url,
                notes=(args.notes or None),
                client=client,
                dry_run=args.dry_run,
            )
    logger.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
