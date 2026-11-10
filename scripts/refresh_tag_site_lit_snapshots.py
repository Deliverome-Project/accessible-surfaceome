"""Rewrite the literature sites of ``viewer/public/tag-sites/{SYMBOL}.json`` from
the audited rows, so a snapshot sync reproduces what the API serves.

The literature audit (deliverome-analysis PR 236; ``data/analysis/
tag_site_corpus_audit/``) corrected 178 ``literature_retrieved`` rows in public
D1 and withdrew 18. The committed snapshots never carried most literature rows
(a sweep publishes straight to D1), and the few they did carry were the
pre-audit ones. ``scripts/sync_tag_sites_to_d1.py --provenance
literature_retrieved`` is authoritative for that provenance, so a sync from the
old snapshots would put the old residues back and delete every literature row
the file lacks. This script makes the snapshots agree with the served table for
every audited gene:

* the audited and minted rows come from ``rows_after.json`` (the file PR 459
  wrote to D1), so snapshot and D1 cannot drift from each other;
* the gene's OTHER literature rows (terminal tags, un-audited internal rows)
  come from ``live_other_lit_rows.json``, captured from D1 with
  ``--fetch-live`` — without them a provenance-scoped sync would delete them;
* every row keeps its own ``tag_sites_version`` (``flat_row`` now honours it),
  so a sync re-stamps nothing;
* the 18 withdrawn ids are dropped by ``tag_sites.retracted`` on the way in.

Only the ``literature_retrieved`` sites of the audited genes are replaced;
deterministic and screen sites, ``isoform_pins``, ``ortholog_pins`` and the
per-gene search facts in the file are left as they were.

    uv run python scripts/refresh_tag_site_lit_snapshots.py --fetch-live   # once, needs D1
    uv run python scripts/refresh_tag_site_lit_snapshots.py               # rewrite snapshots

``tests/test_tag_site_audit_snapshots.py`` regenerates into a temp dir and
compares with the committed files, and (``--run-network``) checks that a dry-run
sync of the regenerated snapshots produces exactly the live rows.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from accessible_surfaceome.paths import REPO_ROOT
from accessible_surfaceome.tag_sites.retracted import drop_retracted

AUDIT_DIR = REPO_ROOT / "data" / "analysis" / "tag_site_corpus_audit"
ROWS_AFTER = AUDIT_DIR / "rows_after.json"
LIVE_OTHER = AUDIT_DIR / "live_other_lit_rows.json"
SNAPSHOT_DIR = REPO_ROOT / "viewer" / "public" / "tag-sites"

PROVENANCE = "literature_retrieved"
#: D1 columns that are not part of a snapshot site.
_NOT_IN_SNAPSHOT = {"synced_at"}


def site_from_row(row: dict[str, Any]) -> dict[str, Any]:
    """The inverse of :func:`accessible_surfaceome.cloud.tag_sites.flat_row`.

    ``sources_json`` becomes ``sources``; the 0/1 integers become booleans;
    ``synced_at`` is dropped; ``tag_sites_version`` is kept so the sync
    re-stamps nothing.
    """
    site: dict[str, Any] = {}
    for k, v in row.items():
        if k in _NOT_IN_SNAPSHOT:
            continue
        if k == "sources_json":
            site["sources"] = json.loads(v or "[]")
        elif k == "extracellular":
            site[k] = bool(v)
        elif k == "entailment_verified":
            site[k] = None if v is None else bool(v)
        else:
            site[k] = v
    return site


def literature_sites_by_gene(
    rows_after: list[dict[str, Any]], live_other: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """Every literature site each audited gene should carry, audited rows winning
    over the live capture on a shared ``site_id``."""
    genes = {r["gene_symbol"] for r in rows_after}
    by_gene: dict[str, dict[str, dict[str, Any]]] = {g: {} for g in genes}
    for r in live_other:
        if r["gene_symbol"] in by_gene and r["provenance"] == PROVENANCE:
            by_gene[r["gene_symbol"]][r["site_id"]] = site_from_row(r)
    for r in rows_after:
        by_gene[r["gene_symbol"]][r["site_id"]] = site_from_row(r)
    return {
        g: sorted(sites.values(), key=lambda s: s["site_id"])
        for g, sites in by_gene.items()
    }


def refresh_file(
    path: Path, gene: str, uniprot_acc: str, lit_sites: list[dict[str, Any]]
) -> dict[str, Any]:
    """Replace the file's ``literature_retrieved`` sites with ``lit_sites`` and
    return the payload written. Other sites and every other key survive."""
    payload: dict[str, Any] = (
        json.loads(path.read_text())
        if path.exists()
        else {
            "has_data": False,
            "gene_symbol": gene,
            "uniprot_acc": uniprot_acc,
            "sites": [],
        }
    )
    others = [s for s in payload.get("sites", []) if s.get("provenance") != PROVENANCE]
    merged = others + drop_retracted(lit_sites, uniprot_acc=uniprot_acc)
    merged.sort(key=lambda s: s["site_id"])
    payload["sites"] = merged
    payload["has_data"] = len(merged) > 0
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def refresh_all(out_dir: Path) -> dict[str, int]:
    rows_after = json.loads(ROWS_AFTER.read_text())
    live_other = json.loads(LIVE_OTHER.read_text())
    acc_of = {r["gene_symbol"]: r["uniprot_acc"] for r in rows_after}
    counts: dict[str, int] = {}
    for gene, sites in sorted(literature_sites_by_gene(rows_after, live_other).items()):
        payload = refresh_file(out_dir / f"{gene}.json", gene, acc_of[gene], sites)
        counts[gene] = sum(1 for s in payload["sites"] if s["provenance"] == PROVENANCE)
    return counts


def fetch_live_other() -> int:
    from accessible_surfaceome.cloud.d1_client import D1Client
    from accessible_surfaceome.env import load_env

    load_env()
    rows_after = json.loads(ROWS_AFTER.read_text())
    genes = sorted({r["gene_symbol"] for r in rows_after})
    audited = {r["site_id"] for r in rows_after}
    out: list[dict[str, Any]] = []
    with D1Client.public() as d1:
        for i in range(0, len(genes), 90):
            ch = genes[i : i + 90]
            marks = ", ".join("?" * len(ch))
            out += d1.query(
                f"SELECT * FROM tag_site_public WHERE provenance = ? AND gene_symbol IN ({marks}) "
                "ORDER BY gene_symbol, site_id;",
                [PROVENANCE, *ch],
            )
    other = [r for r in out if r["site_id"] not in audited]
    for r in other:
        r["synced_at"] = "<captured>"  # not a snapshot field; keep the file stable
    LIVE_OTHER.write_text(json.dumps(other, indent=1, sort_keys=True) + "\n")
    return len(other)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--fetch-live",
        action="store_true",
        help="capture the audited genes' other literature rows from D1, then exit",
    )
    ap.add_argument("--out-dir", type=Path, default=SNAPSHOT_DIR)
    args = ap.parse_args()
    if args.fetch_live:
        n = fetch_live_other()
        print(
            f"wrote {n} un-audited literature rows -> {LIVE_OTHER.relative_to(REPO_ROOT)}"
        )
        return 0
    counts = refresh_all(args.out_dir)
    print(
        f"refreshed {len(counts)} snapshot(s), {sum(counts.values())} literature site(s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
