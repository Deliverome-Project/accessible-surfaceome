"""Sync tag-sites JSON -> public D1's ``tag_site_public``.

Reads every ``viewer/public/tag-sites/{SYMBOL}.json`` (the deterministic +
literature pipelines' committed output) and UPSERTs one row per site via
:func:`accessible_surfaceome.cloud.tag_sites.publish_tag_sites` (idempotent;
replace-all per gene). Env comes from ``.env`` via ``load_env``
(``CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID`` etc.).

    uv run python scripts/sync_tag_sites_to_d1.py --dry-run
    uv run python scripts/sync_tag_sites_to_d1.py --version 2026-08-15
    uv run python scripts/sync_tag_sites_to_d1.py --gene TFRC --version 2026-08-15
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from accessible_surfaceome.cloud import tag_sites as tag_sites_d1
from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

log = logging.getLogger("sync_tag_sites")
TAG_SITES_DIR = REPO_ROOT / "viewer" / "public" / "tag-sites"


def _files(gene: str | None) -> list[Path]:
    files = sorted(TAG_SITES_DIR.glob("*.json"))
    return [f for f in files if f.stem == gene] if gene else files


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dry-run", action="store_true",
        help="parse + count the rows that WOULD be written; write nothing.",
    )
    ap.add_argument(
        "--version", default="dev",
        help="tag_sites_version stamp for these rows (e.g. a date).",
    )
    ap.add_argument("--gene", help="sync only this SYMBOL (default: all committed JSON).")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    files = _files(args.gene)
    if not files:
        log.warning("no tag-sites JSON found in %s", TAG_SITES_DIR)
        return 1

    if args.dry_run:
        total = 0
        for f in files:
            data = json.loads(f.read_text())
            rows = tag_sites_d1.rows_for_file(data, version=args.version, synced_at="(dry-run)")
            total += len(rows)
            log.info("%-12s %3d sites", data["gene_symbol"], len(rows))
        log.info("dry-run: %d gene(s), %d site row(s) — nothing written", len(files), total)
        return 0

    load_env()
    client = D1Client.public()
    try:
        tag_sites_d1.ensure_table(client)
        grand = 0
        for f in files:
            data = json.loads(f.read_text())
            n = tag_sites_d1.publish_tag_sites(
                data, tag_sites_version=args.version, client=client
            )
            grand += n
            log.info("synced %-12s %3d sites", data["gene_symbol"], n)
        log.info("done: %d gene(s), %d site row(s) -> tag_site_public", len(files), grand)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
