"""Repair historical PMC/None links using the cited DOI; never rerun an analysis.

Dry-run by default. --execute saves the original rows to --backup before
compare-and-swap updates and targeted cache invalidation. Optionally restrict
the repair with --hgnc-id (the stable identifier, not a gene symbol).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.cloud.internalization import _purge_internalization_cache
from accessible_surfaceome.env import load_env


def repair_record(record: dict) -> int:
    changed = 0
    for evidence in (record.get("literature") or {}).get("sources", []):
        for span in evidence.get("spans", []):
            source = span.get("source") or {}
            if source.get("url") != "https://www.ncbi.nlm.nih.gov/pmc/articles/None/":
                continue
            sid = source.get("source_id", "")
            if not sid.startswith("DOI:") or not re.fullmatch(r"10\.\d{4,9}/\S+", sid[4:]):
                raise ValueError(f"Cannot repair a missing PMC link without a DOI: {sid}")
            source["url"] = f"https://doi.org/{sid[4:]}"
            changed += 1
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--hgnc-id")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    if args.execute and not args.backup:
        parser.error("--execute requires --backup for the original rows")
    load_env()
    sql = "SELECT hgnc_id, gene_symbol, schema_version, record_json FROM surface_internalization WHERE record_json LIKE ?"
    params = ["%pmc/articles/None/%"]
    if args.hgnc_id:
        sql += " AND hgnc_id = ?"
        params.append(args.hgnc_id)
    with D1Client(D1Config.from_env_public()) as db:
        rows = db.query(sql, params)
        repairs = []
        for row in rows:
            record = json.loads(row["record_json"])
            count = repair_record(record)
            if count:
                repairs.append((row, json.dumps(record, ensure_ascii=False), count))
        print(f"{len(repairs)} records, {sum(r[2] for r in repairs)} source URLs")
        if not args.execute:
            return
        # Exclusive creation avoids overwriting a previous recovery copy.
        with args.backup.open("x") as out:
            json.dump(rows, out, ensure_ascii=False)
        for row, updated, count in repairs:
            changed = db.query(
                "UPDATE surface_internalization SET record_json = ?, updated_at = datetime('now') "
                "WHERE hgnc_id = ? AND schema_version = ? AND record_json = ? RETURNING gene_symbol",
                [updated, row["hgnc_id"], row["schema_version"], row["record_json"]],
            )
            if not changed:
                raise RuntimeError(f"Record changed concurrently: {row['hgnc_id']}")
            _purge_internalization_cache(row["gene_symbol"])
            print(f"{row['hgnc_id']} ({row['gene_symbol']}): repaired {count} source URLs")


if __name__ == "__main__":
    main()
