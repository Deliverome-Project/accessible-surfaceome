"""Re-key public D1's ``tag_site_gene_public`` so a gene can carry more than one
search.

The table's primary key is ``gene_symbol`` alone. Presence of a row is the claim
"this gene was searched, under this prompt, on this date", and **1,415 of its
2,370 rows are dated zeros** — the thing that distinguishes "no published tag
site exists for this protein" from "we have not got to it yet". An enrichment
pass writing a second search for the same gene would overwrite the first and
destroy exactly that, and a zero which loses its date has to be re-run before it
can be trusted, so each one costs a real literature search to reproduce.

New key: ``(gene_symbol, candidate_id, run_series)``. ``candidate_id`` because
the enrichment's unit is the library MEMBER and 45 of the 518 internal-site
genes have more than one, 7 of those disagreeing about where the tag goes;
``run_series`` because the two passes are different searches and both answers
are worth keeping. Existing rows become ``candidate_id = ''`` (gene-level) and
``run_series = 'literature_v1'``.

D1 cannot ``ALTER`` a primary key, so this is create-copy-**verify**-rename, one
statement per HTTP call. The verify is the point: a copy that lost rows leaves
the live table exactly as it was rather than replacing it with a short one. The
pre-migration table is RENAMED, not dropped — a rename is reversible while the
old bytes still exist.

**ORDER OF OPERATIONS.** This migration leaves every gene with exactly one row,
so it is safe on its own. But the Worker reads this table with ``.first()`` and
no ``ORDER BY``, so once a gene has two rows the answer depends on which one
came back. Migrate, THEN teach the Worker to choose and deploy it, THEN write
enrichment rows. Writing before the Worker lands would make a gene answer
differently per request.

    uv run python scripts/cloud/migrate_tag_site_gene_key.py
    uv run python scripts/cloud/migrate_tag_site_gene_key.py --execute
"""

from __future__ import annotations

import argparse
import logging
import sys

from accessible_surfaceome.env import load_env

load_env()

from accessible_surfaceome.cloud.d1_client import D1Client  # noqa: E402
from accessible_surfaceome.cloud.tag_site_genes import migrate_gene_key  # noqa: E402

log = logging.getLogger("migrate_tag_site_gene_key")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true",
                    help="perform the migration (dry-run otherwise)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    with D1Client.public() as pub:
        before = pub.query(
            "SELECT COUNT(*) n, "
            "SUM(CASE WHEN n_sites = 0 THEN 1 ELSE 0 END) zeros, "
            "COUNT(DISTINCT prompt_sha) shas FROM tag_site_gene_public;",
            [],
        )[0]
        log.info("live table: %s rows, %s dated zeros, %s prompt sha(s)",
                 before["n"], before["zeros"], before["shas"])

        report = migrate_gene_key(pub, execute=args.execute)
        if report.get("already_migrated"):
            log.info("already migrated — %s rows, nothing to do", report["after"])
            return 0
        if not args.execute:
            log.info(
                "DRY RUN: would copy %s rows into a composite-key table as "
                "candidate_id='' / run_series='literature_v1', verify the count, "
                "then rename. Re-run with --execute.",
                report["before"],
            )
            return 0
        if report.get("aborted"):
            log.error("ABORTED: %s", report.get("reason"))
            return 1

        after = pub.query(
            "SELECT COUNT(*) n, "
            "SUM(CASE WHEN n_sites = 0 THEN 1 ELSE 0 END) zeros FROM "
            "tag_site_gene_public;",
            [],
        )[0]
        log.info("migrated: %s -> %s rows, zeros %s -> %s",
                 report["before"], after["n"], before["zeros"], after["zeros"])
        if after["n"] != before["n"] or after["zeros"] != before["zeros"]:
            log.error("POST-CHECK FAILED: row or zero count moved")
            return 1
        log.info("pre-migration table retained as "
                 "tag_site_gene_public_legacy_single_key")
        log.info("NEXT: teach the Worker to choose between rows and deploy it "
                 "BEFORE any enrichment gene row is written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
