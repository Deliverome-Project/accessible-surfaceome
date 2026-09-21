#!/usr/bin/env python
"""Merge a cohort-scoped paralog release into the dominant one.

Why this exists: both the paralog and the topology version pickers punish a
parallel, cohort-scoped release — in opposite directions, so there is no upload
strategy that is safe under both. Uploading a backfill as its own
``paralog_version`` is the mistake, and it has now been made twice:

* topology — ``_latest_topology_version_for_cohort`` takes the NEWEST release,
  so a 148-gene release shadowed the 11k-row global one and every other gene
  resolved to a placeholder.
* paralogs — ``_latest_paralog_version`` took the newest by ``fetched_at``, so
  ``paralog_2026_09_20_rescue`` (1,066 pairs / 123 genes) shadowed
  ``paralog_topo_2026_05_16`` (91,103 pairs / 5,790 genes) and every deep dive
  saw paralogs for 2% of the cohort. An empty paralog list renders as "this
  protein has no paralogs" — a fabricated negative, not a visible gap.

The picker has since been changed to select on distinct-gene coverage
(``d1_deterministic._latest_paralog_version``), which stops a small release
shadowing a large one. But that fix makes the small release *unreachable*, so
its rows still have to be merged in. Hence: append to the live release, never
upload beside it.

Idempotent. ``INSERT OR IGNORE`` on the PK
``(paralog_version, human_ensembl_gene, paralog_ensembl_gene)``, so a gene the
dominant release already carries keeps its original rows and vintage. The
source rows are left in place — deleting them is a separate, optional cleanup.

Runs against BOTH D1s (public mirror + private agents DB) so they cannot drift.

Usage::

    # dry-run — report what would move
    uv run python scripts/cloud/merge_paralog_release.py \\
        --source paralog_2026_09_20_rescue --dest paralog_topo_2026_05_16

    # execute
    uv run python scripts/cloud/merge_paralog_release.py \\
        --source paralog_2026_09_20_rescue --dest paralog_topo_2026_05_16 --execute
"""

from __future__ import annotations

import argparse
import sys

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env

# Every column except the PK's version discriminator and the DEFAULT'd
# synced_at. Listed explicitly so a schema addition fails loudly here rather
# than silently dropping a column on the merged rows.
CARRIED_COLUMNS = (
    "human_hgnc_id",
    "human_ensembl_gene",
    "human_uniprot_acc",
    "human_gene_symbol",
    "paralog_hgnc_id",
    "paralog_ensembl_gene",
    "paralog_uniprot_acc",
    "paralog_gene_symbol",
    "family_id",
    "biomart_percent_identity",
    "ecd_pct_identity",
    "ecd_pct_similarity",
    "n_ecd_loops_compared",
    "rank_by_ecd_identity",
    "paralogy_type",
    "is_high_confidence",
    "compara_version",
)


def _columns_to_carry(d1: D1Client, label: str) -> tuple[str, ...]:
    """Reconcile CARRIED_COLUMNS against the live table, in both directions.

    Extra column in the table -> hard failure: a column this script does not
    list would be silently dropped, producing merged rows that look complete
    but carry a NULL where the source had data. That is the same
    missing-lookup-as-real-value bug the merge exists to clean up.

    Declared column absent from the table -> warn and skip it. The two D1s have
    drifted before (the private ``compara_paralog`` lacks ``ecd_pct_similarity``
    even though ``cloudflare/d1_schema.sql`` declares it), and a source row in
    that database cannot carry data in a column the database does not have — so
    dropping it from the statement loses nothing, whereas failing would leave
    the two databases inconsistent with each other.
    """
    cols = {r["name"] for r in d1.query("PRAGMA table_info(compara_paralog);", [])}
    unhandled = cols - set(CARRIED_COLUMNS) - {"paralog_version", "synced_at"}
    if unhandled:
        raise SystemExit(
            f"{label}: compara_paralog has column(s) {sorted(unhandled)} that "
            f"CARRIED_COLUMNS does not list — add them before merging, or the "
            f"merged rows silently lose that data."
        )
    missing = [c for c in CARRIED_COLUMNS if c not in cols]
    if missing:
        print(
            f"  WARNING {label}: table is missing declared column(s) "
            f"{missing} — schema drift vs cloudflare/*.sql. Merging without "
            f"them (no data is lost: the source rows cannot carry them either)."
        )
    return tuple(c for c in CARRIED_COLUMNS if c in cols)


def merge(d1: D1Client, label: str, source: str, dest: str, execute: bool) -> None:
    print(f"\n=== {label} ===")
    carried = _columns_to_carry(d1, label)
    for r in d1.query(
        "SELECT paralog_version v, COUNT(*) n, COUNT(DISTINCT human_ensembl_gene) g "
        "FROM compara_paralog WHERE paralog_version IN (?, ?) GROUP BY 1 "
        "ORDER BY g DESC;",
        [source, dest],
    ):
        print(f"  {r['v']:<34s} pairs={r['n']:>7,d}  genes={r['g']:>6,d}")

    src_genes = d1.query(
        "SELECT COUNT(DISTINCT human_ensembl_gene) n FROM compara_paralog "
        "WHERE paralog_version = ?;",
        [source],
    )[0]["n"]
    if not src_genes:
        print(f"  source {source!r} has no rows — nothing to merge.")
        return
    overlap = d1.query(
        "SELECT COUNT(DISTINCT s.human_ensembl_gene) n FROM compara_paralog s "
        "WHERE s.paralog_version = ? AND EXISTS ("
        "  SELECT 1 FROM compara_paralog d WHERE d.paralog_version = ? "
        "    AND d.human_ensembl_gene = s.human_ensembl_gene);",
        [source, dest],
    )[0]["n"]
    print(
        f"  {src_genes} source gene(s); {overlap} already in {dest} "
        f"(kept as-is), {src_genes - overlap} will move"
    )

    if not execute:
        print("  [dry-run] re-run with --execute")
        return

    cols = ", ".join(carried)
    d1.query(
        f"INSERT OR IGNORE INTO compara_paralog (paralog_version, {cols}) "
        f"SELECT ?, {cols} FROM compara_paralog WHERE paralog_version = ?;",
        [dest, source],
    )
    post = d1.query(
        "SELECT COUNT(*) n, COUNT(DISTINCT human_ensembl_gene) g "
        "FROM compara_paralog WHERE paralog_version = ?;",
        [dest],
    )[0]
    print(f"  merged -> {dest}: pairs={post['n']:,}  genes={post['g']:,}")
    d1.query(
        "UPDATE compara_paralog_release SET n_pairs = ?, n_human_genes = ?, "
        "notes = COALESCE(notes || ' | ', '') || ? WHERE paralog_version = ?;",
        [post["n"], post["g"], f"merged {source} into this release", dest],
    )
    print("  release row counts updated")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True, help="cohort release to fold in")
    ap.add_argument("--dest", required=True, help="dominant release to fold into")
    ap.add_argument("--execute", action="store_true", help="default is dry-run")
    args = ap.parse_args(argv)
    if args.source == args.dest:
        raise SystemExit("--source and --dest must differ")
    load_env()

    with D1Client(config=D1Config.from_env_public()) as d1:
        merge(d1, "PUBLIC (surfaceome_public)", args.source, args.dest, args.execute)
    with D1Client() as d1:
        merge(d1, "PRIVATE (surfaceome_agents)", args.source, args.dest, args.execute)

    if args.execute:
        print(
            "\nVerify the picker now resolves to the dominant release:\n"
            "  uv run python -c \"from accessible_surfaceome.agents.surfaceome_v1 "
            "import d1_deterministic as d; from accessible_surfaceome.env import "
            'load_env; load_env(); print(d._latest_paralog_version())"'
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
