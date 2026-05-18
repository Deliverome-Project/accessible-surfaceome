"""Patch ``compara_ortholog_ecd`` rows to carry correct ortholog Ensembl gene
ID + gene symbol + Compara release-version string.

The producer in ``scripts/run_topology_sweep.py`` (``compute_ortholog_ecd_records``,
lines 1072-1073 of the pre-fix version) wrote UniProt entry names into the
``ortholog_ensembl_gene`` and ``ortholog_gene_symbol`` columns — e.g. ``SRC_MOUSE``
appears in *both* columns where the table is supposed to hold an Ensembl gene ID
(``ENSMUSG00000027646``) in the first and a gene symbol (``Src``) in the second.
A sibling bug set ``compara_release='Compara r112'`` while ``compara_ortholog.release_version``
uses ``ensembl_compara_2026_05_12``, breaking the schema-level FK.

Both bugs are pure metadata: the ECD identity values + ortholog UniProt accs are
correct. This script repairs the metadata in place by joining each ECD row
against its (human_ensembl_gene, species) match in ``compara_ortholog`` and
copying the correct fields over. Idempotent — re-runnable, safe to apply twice.

Updates both ``surfaceome_agents`` (private) and ``surfaceome_public`` D1
databases since they mirror each other.

Usage::

    uv run python scripts/fix_compara_ortholog_ecd_metadata.py --dry-run
    uv run python scripts/fix_compara_ortholog_ecd_metadata.py --execute
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

import httpx

from accessible_surfaceome.env import load_env

logger = logging.getLogger(__name__)

API_ROOT = "https://api.cloudflare.com/client/v4"

# Pin: every fresh row should reference this release; matches compara_ortholog.release_version.
CANONICAL_COMPARA_RELEASE = "ensembl_compara_2026_05_12"


def _query(client: httpx.Client, account_id: str, db_id: str, sql: str,
           params: list | None = None) -> list[dict]:
    r = client.post(
        f"{API_ROOT}/accounts/{account_id}/d1/database/{db_id}/query",
        json={"sql": sql, "params": params or []},
        timeout=120,
    )
    r.raise_for_status()
    payload = r.json()
    if not payload.get("success"):
        raise RuntimeError(f"D1 query failed: {payload}")
    return payload["result"][0]["results"]


def _summarize(client: httpx.Client, account_id: str, db_id: str, label: str) -> None:
    bad = _query(client, account_id, db_id,
                 "SELECT COUNT(*) AS n FROM compara_ortholog_ecd "
                 "WHERE ortholog_ensembl_gene NOT LIKE 'ENS%' OR compara_release != ?",
                 [CANONICAL_COMPARA_RELEASE])
    total = _query(client, account_id, db_id,
                   "SELECT COUNT(*) AS n FROM compara_ortholog_ecd", [])
    unmatched = _query(client, account_id, db_id,
                       "SELECT COUNT(*) AS n FROM compara_ortholog_ecd eo "
                       "WHERE NOT EXISTS ("
                       "  SELECT 1 FROM compara_ortholog co "
                       "  WHERE co.human_ensembl_gene = eo.human_ensembl_gene "
                       "    AND co.species = eo.species)", [])
    logger.info("[%s] total ecd rows = %d, bad-metadata rows = %d, unmatched in compara_ortholog = %d",
                label, total[0]["n"], bad[0]["n"], unmatched[0]["n"])


def _patch_one_db(client: httpx.Client, account_id: str, db_id: str,
                  label: str, *, dry_run: bool) -> None:
    _summarize(client, account_id, db_id, label + " (before)")

    if dry_run:
        # Sample the change set without writing
        sample = _query(client, account_id, db_id,
                        "SELECT eo.human_gene_symbol, eo.species, "
                        "eo.ortholog_ensembl_gene AS old_ensg, eo.ortholog_gene_symbol AS old_sym, "
                        "(SELECT co.ortholog_ensembl_gene FROM compara_ortholog co "
                        " WHERE co.human_ensembl_gene = eo.human_ensembl_gene "
                        "   AND co.species = eo.species LIMIT 1) AS new_ensg, "
                        "(SELECT co.ortholog_gene_symbol  FROM compara_ortholog co "
                        " WHERE co.human_ensembl_gene = eo.human_ensembl_gene "
                        "   AND co.species = eo.species LIMIT 1) AS new_sym "
                        "FROM compara_ortholog_ecd eo "
                        "WHERE eo.human_gene_symbol IN ('SRC','GPR75','EGFR','TP53') "
                        "ORDER BY eo.human_gene_symbol, eo.species", [])
        logger.info("[%s] dry-run sample (would update):", label)
        for r in sample:
            logger.info("  %-8s %-12s  %-20s → %-22s   %-20s → %s",
                        r["human_gene_symbol"], r["species"],
                        r["old_ensg"], r["new_ensg"], r["old_sym"], r["new_sym"])
        return

    # Repair ecd rows: pull correct (ortholog_ensembl_gene, ortholog_gene_symbol)
    # from compara_ortholog via (human_ensembl_gene, species), and pin the
    # compara_release to the canonical naming.
    logger.info("[%s] running UPDATE on compara_ortholog_ecd ...", label)
    _query(client, account_id, db_id,
           "UPDATE compara_ortholog_ecd "
           "SET ortholog_ensembl_gene = ("
           "      SELECT co.ortholog_ensembl_gene FROM compara_ortholog co "
           "      WHERE co.human_ensembl_gene = compara_ortholog_ecd.human_ensembl_gene "
           "        AND co.species = compara_ortholog_ecd.species LIMIT 1), "
           "    ortholog_gene_symbol = ("
           "      SELECT co.ortholog_gene_symbol FROM compara_ortholog co "
           "      WHERE co.human_ensembl_gene = compara_ortholog_ecd.human_ensembl_gene "
           "        AND co.species = compara_ortholog_ecd.species LIMIT 1), "
           "    compara_release = ? "
           "WHERE ortholog_ensembl_gene NOT LIKE 'ENS%' "
           "   OR compara_release != ?",
           [CANONICAL_COMPARA_RELEASE, CANONICAL_COMPARA_RELEASE])

    logger.info("[%s] running UPDATE on compara_ortholog_ecd_release ...", label)
    _query(client, account_id, db_id,
           "UPDATE compara_ortholog_ecd_release SET compara_release = ? "
           "WHERE compara_release != ?",
           [CANONICAL_COMPARA_RELEASE, CANONICAL_COMPARA_RELEASE])

    _summarize(client, account_id, db_id, label + " (after)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true",
                       help="Sample the change set without writing.")
    group.add_argument("--execute", action="store_true",
                       help="Apply UPDATE statements to both D1 DBs.")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_env()
    account_id = os.environ["CLOUDFLARE_ACCOUNT_ID"].strip()
    token = os.environ["CLOUDFLARE_API_TOKEN"].strip()
    public_id = os.environ["CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID"].strip()
    private_id = os.environ["CLOUDFLARE_D1_SURFACEOME_AGENTS_ID"].strip()

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    with httpx.Client(headers=headers) as client:
        # Private (agents) first — that's where new agent runs write; then public mirror.
        _patch_one_db(client, account_id, private_id, "private (agents)", dry_run=args.dry_run)
        _patch_one_db(client, account_id, public_id, "public (mirror)",   dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
