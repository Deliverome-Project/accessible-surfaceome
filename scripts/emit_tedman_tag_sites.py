"""Emit/merge Tedman screen_validated control sites into viewer/public/tag-sites/{SYMBOL}.json.

Canonical sites only (one per gene); per-isoform pins are added by a later task.

    uv run python scripts/emit_tedman_tag_sites.py --gene ADRB2   # one gene
    uv run python scripts/emit_tedman_tag_sites.py                # all in the TSV
"""
from __future__ import annotations

import argparse
import csv
import itertools
import logging

from accessible_surfaceome.paths import REPO_ROOT
from accessible_surfaceome.tag_sites.emit import emit_tag_sites_json
from accessible_surfaceome.tag_sites.tedman import build_control_sites_for_gene

log = logging.getLogger("emit_tedman")
TSV = REPO_ROOT / "data" / "tag_sites" / "tedman_gpcr_controls.tsv"
OUT = REPO_ROOT / "viewer" / "public" / "tag-sites"
SOURCES = [{
    "citation": ("Tedman et al., Efficient experimental characterization of the GPCRome "
                 "via deep receptor scanning, Nat Commun 2026 (bioRxiv 2025.09.19.677468, PMC12458215)"),
    "doi": "10.1038/s41467-026-76564-7",
    "pmid": None,
    "url": "https://doi.org/10.1038/s41467-026-76564-7",
    "claim": ("N-terminal HA epitope inserted per receptor; surface expression read out by HA "
              "immunostaining in a pooled GPCRome deep-receptor-scanning screen."),
}]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gene")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    rows = [r for r in csv.DictReader(TSV.open(), delimiter="\t")
            if r["verified"] == "true" and r["is_canonical"] == "true" and r["uniprot_acc"]]
    if args.gene:
        rows = [r for r in rows if r["gene_symbol"] == args.gene]
    rows.sort(key=lambda r: r["gene_symbol"])

    n = 0
    for symbol, grp in itertools.groupby(rows, key=lambda r: r["gene_symbol"]):
        grp = list(grp)
        sites = build_control_sites_for_gene(grp, sources=SOURCES)
        if not sites:
            continue
        emit_tag_sites_json(symbol, grp[0]["uniprot_acc"], sites, out_dir=OUT)
        n += 1
        if args.limit and n >= args.limit:
            break
    log.info("emitted %d genes -> %s", n, OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
