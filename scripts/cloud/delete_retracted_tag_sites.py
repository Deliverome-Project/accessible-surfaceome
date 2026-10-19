"""Delete already-published tag-site rows that have been withdrawn.

:mod:`accessible_surfaceome.tag_sites.retracted` stops a withdrawn site being
published again, on both surfaces. It cannot remove a row public D1 is ALREADY
serving, and re-publishing the gene to get it is the wrong tool: the genes in the
first retraction carry different ``tag_sites_version`` stamps (ACKR3 2026-10-08,
MS4A1 2026-10-11), so one sync restamps six rows to remove two and throws away
that provenance. This deletes exactly the withdrawn rows and touches nothing else.

Keyed on ``(uniprot_acc, site_id)``, never the symbol — a symbol-keyed delete
against live rows is the COX1 / WAS bug class with the blast radius pointed at
production. Driven entirely by ``RETRACTED``, so adding an entry never means
editing this file, and idempotent, so re-running after the next entry is safe.

Dry-run by default:

    uv run python scripts/cloud/delete_retracted_tag_sites.py
    uv run python scripts/cloud/delete_retracted_tag_sites.py --execute
"""

from __future__ import annotations

import argparse
import logging
import sys

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env
from accessible_surfaceome.tag_sites.retracted import RETRACTED, retraction_reason

log = logging.getLogger("delete_retracted_tag_sites")

_SELECT = "SELECT site_id FROM tag_site_public WHERE uniprot_acc = ? AND site_id = ?;"
_DELETE = "DELETE FROM tag_site_public WHERE uniprot_acc = ? AND site_id = ?;"


def retracted_rows_present(client: D1Client) -> list[tuple[str, str]]:
    """The withdrawn ``(uniprot_acc, site_id)`` pairs the table still holds.

    One statement per pair rather than one big ``IN`` — the list is tiny, and a
    per-pair probe is what lets the run report, and stay, idempotent.
    """
    present: list[tuple[str, str]] = []
    for acc, site_id in sorted(RETRACTED):
        if client.query(_SELECT, [acc, site_id]):
            present.append((acc, site_id))
    return present


def delete_retracted(client: D1Client, *, execute: bool) -> int:
    """Delete every withdrawn row still present; return how many were (or would be)
    removed. ``execute=False`` reports without issuing a DELETE."""
    targets = retracted_rows_present(client)
    for acc, site_id in targets:
        log.warning(
            "%s %s (%s): %s",
            "deleting" if execute else "would delete",
            site_id, acc, retraction_reason(uniprot_acc=acc, site_id=site_id),
        )
        if execute:
            client.query(_DELETE, [acc, site_id])
    return len(targets)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--execute", action="store_true",
                    help="actually delete (default: report only).")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_env()

    with D1Client.public() as d1:
        n = delete_retracted(d1, execute=args.execute)

    if not n:
        log.info("nothing to do — no retracted row is published.")
    elif args.execute:
        # No cache purge step: /v1/tag-sites/{symbol} returns json() without a ttl,
        # so it takes CACHE_TTL_SHORT (60 s). Per the repo's purge policy the
        # 60-second surfaces are deliberately left to self-heal.
        log.info("deleted %d retracted row(s); live within ~60 s (edge TTL).", n)
    else:
        log.info("%d retracted row(s) still published. Re-run with --execute.", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
