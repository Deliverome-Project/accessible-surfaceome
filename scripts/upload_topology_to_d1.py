"""Upload topology JSONL records to the D1 ``topology_public`` mirror.

Reads one or more JSONL files (typically ``topology_records.jsonl`` from each
cohort produced by ``run_topology_sweep.py``) and writes to **both**:
  * ``surfaceome_agents`` (private)
  * ``surfaceome_public`` (public mirror at api.deliverome.org)

Schema match: the row shape comes from parse_3line() plus a few wrapping
columns the caller stamps in (topology_version, cohort, species, is_canonical,
gene_symbol, isoform_id, tool_version, retrieved_at). The script doesn't
re-derive those — they have to be present in the input records.

Idempotent on (topology_version, cohort, uniprot_acc_full) via INSERT OR IGNORE.

Usage::

    uv run python scripts/upload_topology_to_d1.py \\
        --topology-version topo_2026_05_16 \\
        --jsonl data/processed/topology_run_topo_2026_05_16/human_canonical/topology_records.jsonl \\
        --cohorts-present human_canonical
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

# D1 caps placeholders at ~100 per statement. 24 columns * 4 rows = 96 → batch 4.
BATCH_SIZE = 4
API_ROOT = "https://api.cloudflare.com/client/v4"

COLS = [
    "topology_version",
    "cohort",
    "hgnc_id",                # PR #30 stable-ID join key into gene_identifier
    "uniprot_acc",
    "uniprot_acc_full",
    "isoform_id",
    "gene_symbol",
    "species",
    "is_canonical",
    "sequence",
    "protein_length",
    "deeptmhmm_label",
    "tm_helix_count",
    "beta_strand_count",
    "n_terminal_orientation",
    "c_terminal_orientation",
    "signal_peptide_length",
    "ecd_length_residues",
    "icd_length_residues",
    "per_residue_topology",
    "predicted_surface_membrane",
    "predicted_secreted",
    "tool_version",
    "retrieved_at",
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
        raise SystemExit("No D1 targets configured (set agents and/or public DB ID)")
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
    """Project a JSONL record onto the COLS schema."""
    return [
        rec["topology_version"],
        rec["cohort"],
        rec.get("hgnc_id") or None,
        rec["uniprot_accession"],
        rec["uniprot_accession_full"],
        rec.get("isoform_id") or rec["uniprot_accession_full"],
        rec.get("gene_symbol") or "",
        rec.get("species", "human"),
        int(rec.get("is_canonical", 1)),
        rec["sequence"],
        int(rec["protein_length"]),
        rec["deeptmhmm_label"],
        int(rec["tm_helix_count"]),
        int(rec["beta_strand_count"]),
        rec["n_terminal_orientation"],
        rec["c_terminal_orientation"],
        int(rec["signal_peptide_length"]),
        int(rec["ecd_length_residues"]),
        int(rec["icd_length_residues"]),
        rec["per_residue_topology"],
        int(rec["predicted_surface_membrane"]),
        int(rec["predicted_secreted"]),
        rec.get("tool_version", "deeptmhmm-1.0.24"),
        rec["retrieved_at"],
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
            f"INSERT OR IGNORE INTO topology_public ({cols_sql}) "
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
    topology_version: str,
    n_rows: int,
    cohorts_present: str,
    deeptmhmm_version: str,
    attribution: str,
    license_url: str,
    source_run_dir: str,
    client: httpx.Client,
    dry_run: bool,
) -> None:
    if dry_run:
        logger.info("[DRY %s] release(topology_version=%s, n_rows=%d)", target.name, topology_version, n_rows)
        return
    _query(
        target,
        "INSERT INTO topology_release "
        "(topology_version, n_rows, cohorts_present, deeptmhmm_version, attribution, "
        " license_url, source_run_dir, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, NULL) "
        "ON CONFLICT (topology_version) DO UPDATE SET "
        "  n_rows = excluded.n_rows, "
        "  cohorts_present = excluded.cohorts_present, "
        "  deeptmhmm_version = excluded.deeptmhmm_version, "
        "  attribution = excluded.attribution, "
        "  license_url = excluded.license_url, "
        "  source_run_dir = excluded.source_run_dir",
        [topology_version, n_rows, cohorts_present, deeptmhmm_version,
         attribution, license_url, source_run_dir],
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
    ap.add_argument("--topology-version", required=True)
    ap.add_argument("--jsonl", type=Path, action="append", required=True,
                    help="JSONL input(s); pass multiple --jsonl for multi-cohort upload")
    ap.add_argument("--cohorts-present", required=True,
                    help="comma-separated cohort list to record in topology_release")
    ap.add_argument("--deeptmhmm-version", default="deeptmhmm-1.0.24")
    ap.add_argument("--attribution", default="DeepTMHMM 1.0.24 (DTU)")
    ap.add_argument("--license-url", default="https://dtu.biolib.com/DeepTMHMM/")
    ap.add_argument("--source-run-dir", default="")
    ap.add_argument("--public-only", action="store_true")
    ap.add_argument("--private-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = _load_jsonl(args.jsonl)
    logger.info("loaded %d JSONL rows from %d file(s)", len(rows), len(args.jsonl))

    # Stamp topology_version on every row so callers don't have to.
    for r in rows:
        r["topology_version"] = args.topology_version

    targets = _resolve_targets(public_only=args.public_only, private_only=args.private_only)
    logger.info("targets: %s", ", ".join(t.name for t in targets))

    with httpx.Client(timeout=120) as client:
        for target in targets:
            logger.info("uploading to %s", target.name)
            _upload_rows(target, rows, client=client, dry_run=args.dry_run)
            _upsert_release(
                target,
                topology_version=args.topology_version,
                n_rows=len(rows),
                cohorts_present=args.cohorts_present,
                deeptmhmm_version=args.deeptmhmm_version,
                attribution=args.attribution,
                license_url=args.license_url,
                source_run_dir=args.source_run_dir,
                client=client,
                dry_run=args.dry_run,
            )
    logger.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
