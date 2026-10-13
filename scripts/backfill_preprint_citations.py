"""Give the "preprint" citations back their accession.

``to_viewer_sites`` used to publish ``{"citation": "preprint"}`` for any source
with no PMID, discarding the accession the pipeline had already resolved. The
result is a citation naming nothing: 25 refs across 24 genes whose only label is
the word "preprint", which no reader can look up and which the repo's citation
rule (a cited paper is one click from its source) forbids outright.

The accession survives in the private run archive — every ledger line carries
the ``source_id`` of the paper its quote came from — so this recovers it by
matching the published ``claim`` back to the ledger quote it was taken from. No
re-run, no model calls.

Writes the viewer records only; re-sync afterwards to publish them.

    uv run python scripts/backfill_preprint_citations.py            # dry run
    uv run python scripts/backfill_preprint_citations.py --execute
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from accessible_surfaceome.env import load_env

load_env()

from accessible_surfaceome.agents.tag_site.runner import _citation_label  # noqa: E402
from accessible_surfaceome.cloud.d1_client import D1Client  # noqa: E402
from accessible_surfaceome.tools._shared.normalize import (  # noqa: E402
    normalize_for_quote_matching,
)

ROOT = Path(__file__).resolve().parents[1]
VIEWER_DIR = ROOT / "viewer/public/tag-sites"
log = logging.getLogger("backfill_preprint")


def ledgers(genes: set[str]) -> dict[str, list[dict]]:
    """{gene: [{source_id, quote}, ...]} from the private archive, newest run."""
    with D1Client() as d1:
        rows = d1.query(
            "SELECT gene_symbol, ledger_json FROM tag_site_run "
            "WHERE gene_symbol <> '' ORDER BY created_at;",
            [],
        )
    out: dict[str, list[dict]] = {}
    for r in rows:
        if r["gene_symbol"] not in genes:
            continue
        try:
            out[r["gene_symbol"]] = json.loads(r["ledger_json"] or "[]")
        except Exception:  # noqa: BLE001
            continue
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # Which records carry an identifier-less citation.
    affected: dict[str, Path] = {}
    for path in sorted(VIEWER_DIR.glob("*.json")):
        rec = json.loads(path.read_text())
        for s in rec.get("sites") or []:
            if any(
                (src.get("citation") == "preprint") and not src.get("source_id")
                for src in (s.get("sources") or [])
            ):
                affected[rec.get("gene_symbol") or path.stem] = path
                break
    log.info("records with an unidentified citation: %d", len(affected))
    if not affected:
        return 0

    led = ledgers(set(affected))
    fixed = unmatched = 0
    for gene, path in affected.items():
        lines = led.get(gene) or []
        norm = [
            (normalize_for_quote_matching(ln.get("quote") or ""), ln.get("source_id"))
            for ln in lines
            if ln.get("quote") and ln.get("source_id")
        ]
        rec = json.loads(path.read_text())
        touched = False
        for s in rec.get("sites") or []:
            for src in s.get("sources") or []:
                if src.get("citation") != "preprint" or src.get("source_id"):
                    continue
                claim = normalize_for_quote_matching(src.get("claim") or "")
                sid = next(
                    (
                        acc
                        for q, acc in norm
                        # The published claim is the ledger quote, so either
                        # containment direction is a match; clipping differs.
                        if claim and q and (claim in q or q in claim)
                    ),
                    None,
                )
                if not sid:
                    unmatched += 1
                    log.warning(
                        "  %s: no ledger line matches the published claim", gene
                    )
                    continue
                src["source_id"] = sid
                src["citation"] = _citation_label(sid)
                fixed += 1
                touched = True
                log.info("  %-12s -> %s", gene, src["citation"])
        if touched and args.execute:
            path.write_text(json.dumps(rec, indent=2, default=str))

    log.info("recovered %d citation(s); %d unmatched", fixed, unmatched)
    if not args.execute:
        log.info("dry run — nothing written (pass --execute)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
