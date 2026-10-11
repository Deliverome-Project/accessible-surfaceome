"""Publish per-gene tag-site facts to public D1's ``tag_site_gene_public``.

Two things the site table cannot say, because it holds one row per SITE:

* **"we looked and found nothing."** A searched gene with no sites has no rows,
  so it is indistinguishable from an unsearched one. 1,106 of the first sweep's
  1,824 genes are that case, and a reader has no way to tell "no published tag
  site exists for this protein" from "not got to it yet".
* **the positions that are not surface sites** — tolerated but cytoplasmic, or
  function-abrogating. Captured into the private run archive and going nowhere
  a reader could reach them.

Also backfills ``literature_other_positions`` onto the viewer records. The
sweep ran before the driver wrote that field, so for already-run genes the only
copy is the private archive; this carries it across so the static record and the
published row agree.

    uv run python scripts/publish_tag_site_genes.py                # dry run
    uv run python scripts/publish_tag_site_genes.py --execute
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from accessible_surfaceome.env import load_env

load_env()

from accessible_surfaceome.cloud import tag_site_genes as G  # noqa: E402
from accessible_surfaceome.cloud.d1_client import D1Client  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
VIEWER_DIR = ROOT / "viewer/public/tag-sites"

log = logging.getLogger("publish_gene_rows")


def archive_facts() -> dict[str, dict]:
    """Latest private-archive run per gene: other_positions + n_papers.

    Latest wins, because a gene re-run under a newer prompt has a newer answer
    and the older row is history, not a competing claim."""
    with D1Client() as d1:
        rows = d1.query(
            "SELECT gene_symbol, other_positions_json, n_papers, created_at "
            "FROM tag_site_run WHERE gene_symbol <> '' ORDER BY created_at;",
            [],
        )
    out: dict[str, dict] = {}
    for r in rows:  # ascending, so the last write per gene is the newest
        try:
            others = json.loads(r.get("other_positions_json") or "[]")
        except Exception:  # noqa: BLE001
            others = []
        out[r["gene_symbol"]] = {"others": others, "n_papers": r.get("n_papers")}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--version", default="2026-10-11")
    ap.add_argument(
        "--skip",
        action="append",
        default=[],
        help="gene to leave alone (e.g. one being re-run right now)",
    )
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    facts = archive_facts()
    log.info("private archive: %d gene(s) with a run", len(facts))

    rows, backfilled, skipped_unrun = [], 0, 0
    for path in sorted(VIEWER_DIR.glob("*.json")):
        if path.stem in args.skip:
            continue
        rec = json.loads(path.read_text())
        f = facts.get(rec.get("gene_symbol") or path.stem, {})
        # Carry the archive's other_positions onto the record when it predates
        # the driver writing them.
        if "literature_other_positions" not in rec and f.get("others"):
            rec["literature_other_positions"] = f["others"]
            backfilled += 1
            if args.execute:
                path.write_text(json.dumps(rec, indent=2, default=str))
        row = G.row_for(rec, version=args.version, n_papers=f.get("n_papers"))
        if row is None:
            skipped_unrun += 1
            continue
        rows.append(row)

    searched_empty = sum(1 for r in rows if r["n_sites"] == 0)
    with_others = sum(1 for r in rows if r["n_other_positions"] > 0)
    log.info("gene rows to publish      : %d", len(rows))
    log.info("  searched, zero sites    : %d  (invisible until now)", searched_empty)
    log.info(
        "  carrying other_positions: %d (%d positions)",
        with_others,
        sum(r["n_other_positions"] for r in rows),
    )
    log.info("records backfilled        : %d", backfilled)
    log.info("skipped (never searched)  : %d", skipped_unrun)

    if not args.execute:
        log.info("dry run — nothing written (pass --execute)")
        return 0

    with D1Client.public() as d1:
        n = G.publish_gene_rows(rows, client=d1)
    log.info("published %d row(s) -> tag_site_gene_public", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
