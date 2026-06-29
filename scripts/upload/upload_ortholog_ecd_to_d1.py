"""Upload ortholog ECD identity records to the ``compara_ortholog_ecd`` table.

Mirrors ``scripts/upload/upload_paralogs_to_d1.py`` but for the cross-species
human-vs-mouse/cyno ECD comparisons computed in
``run_topology_sweep.compute_ortholog_ecd_records``. Writes to both
``surfaceome_agents`` and ``surfaceome_public``.

Idempotent on (ortholog_ecd_version, human_hgnc_id, species,
ortholog_uniprot_acc) via INSERT OR IGNORE.

Usage::

    uv run python scripts/upload/upload_ortholog_ecd_to_d1.py \\
        --ortholog-ecd-version orthologecd_topo_2026_05_16 \\
        --compara-release "ensembl_compara_2026_05_12" \\
        --jsonl data/processed/topology_run_topo_2026_05_16/ortholog_ecd_records.jsonl
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

# 13 columns × 7 rows = 91 placeholders, under D1's 100 cap.
BATCH_SIZE = 7
API_ROOT = "https://api.cloudflare.com/client/v4"

COLS = [
    "ortholog_ecd_version",
    "human_hgnc_id",
    "human_uniprot_acc",
    "human_ensembl_gene",
    "human_gene_symbol",
    "species",
    "ortholog_uniprot_acc",
    "ortholog_ensembl_gene",
    "ortholog_gene_symbol",
    "biomart_percent_identity",
    "ecd_pct_identity",
    "n_ecd_loops_compared",
    "compara_release",
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
        rec["ortholog_ecd_version"],
        rec["human_hgnc_id"],
        rec.get("human_uniprot_acc"),
        rec.get("human_ensembl_gene"),
        rec.get("human_gene_symbol"),
        rec["species"],
        rec["ortholog_uniprot_acc"],
        rec.get("ortholog_ensembl_gene"),
        rec.get("ortholog_gene_symbol"),
        rec.get("biomart_percent_identity"),
        rec.get("ecd_pct_identity"),
        rec.get("n_ecd_loops_compared"),
        rec["compara_release"],
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
            f"INSERT OR IGNORE INTO compara_ortholog_ecd ({cols_sql}) "
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
    ortholog_ecd_version: str,
    compara_release: str,
    n_pairs: int,
    n_human_genes: int,
    n_species: int,
    notes: str | None,
    client: httpx.Client,
    dry_run: bool,
) -> None:
    if dry_run:
        logger.info(
            "[DRY %s] release(version=%s, pairs=%d)",
            target.name, ortholog_ecd_version, n_pairs,
        )
        return
    _query(
        target,
        "INSERT INTO compara_ortholog_ecd_release "
        "(ortholog_ecd_version, compara_release, n_pairs, n_human_genes, n_species, notes) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (ortholog_ecd_version) DO UPDATE SET "
        "  compara_release = excluded.compara_release, "
        "  n_pairs = excluded.n_pairs, "
        "  n_human_genes = excluded.n_human_genes, "
        "  n_species = excluded.n_species, "
        "  notes = excluded.notes",
        [ortholog_ecd_version, compara_release, n_pairs, n_human_genes, n_species, notes],
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
    ap.add_argument("--ortholog-ecd-version", required=True)
    ap.add_argument(
        "--compara-release",
        required=True,
        help="e.g. 'ensembl_compara_2026_05_12'",
    )
    ap.add_argument("--jsonl", type=Path, action="append", required=True)
    ap.add_argument(
        "--notes",
        default="",
        help="Free-text / JSON written to compara_ortholog_ecd_release.notes (provenance).",
    )
    ap.add_argument("--public-only", action="store_true")
    ap.add_argument("--private-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = _load_jsonl(args.jsonl)
    for r in rows:
        r["ortholog_ecd_version"] = args.ortholog_ecd_version
        r.setdefault("compara_release", args.compara_release)
    n_human_genes = len({r["human_hgnc_id"] for r in rows})
    n_species = len({r["species"] for r in rows})
    logger.info(
        "loaded %d ortholog-ECD rows covering %d human genes × %d species",
        len(rows), n_human_genes, n_species,
    )

    targets = _resolve_targets(public_only=args.public_only, private_only=args.private_only)
    logger.info("targets: %s", ", ".join(t.name for t in targets))

    with httpx.Client(timeout=120) as client:
        for target in targets:
            logger.info("uploading to %s", target.name)
            _upload_rows(target, rows, client=client, dry_run=args.dry_run)
            _upsert_release(
                target,
                ortholog_ecd_version=args.ortholog_ecd_version,
                compara_release=args.compara_release,
                n_pairs=len(rows),
                n_human_genes=n_human_genes,
                n_species=n_species,
                notes=(args.notes or None),
                client=client,
                dry_run=args.dry_run,
            )
    logger.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
