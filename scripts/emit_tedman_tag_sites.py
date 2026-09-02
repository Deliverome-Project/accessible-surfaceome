"""Emit/merge Tedman screen_validated control sites into viewer/public/tag-sites/{SYMBOL}.json.

Two passes:
  1. Canonical screen_validated sites (one per gene).
  2. Per-isoform control pins for alt-isoform Tedman rows, matched onto the
     Worker's UniProt isoform sequences by protein length (skip with
     --no-isoforms).

    uv run python scripts/emit_tedman_tag_sites.py --gene ADRB2   # one gene
    uv run python scripts/emit_tedman_tag_sites.py                # all in the TSV
"""
from __future__ import annotations

import argparse
import csv
import itertools
import logging

import httpx
import openpyxl

from accessible_surfaceome.paths import REPO_ROOT
from accessible_surfaceome.tag_sites.control import control_isoform_pin
from accessible_surfaceome.tag_sites.emit import emit_tag_sites_json
from accessible_surfaceome.tag_sites.tedman import (
    build_control_sites_for_gene,
    map_junction_to_canonical,
    match_isoform_by_length,
)

log = logging.getLogger("emit_tedman")
TSV = REPO_ROOT / "data" / "tag_sites" / "tedman_gpcr_controls.tsv"
OUT = REPO_ROOT / "viewer" / "public" / "tag-sites"
API_BASE = "https://api.deliverome.org/surfaceome"
MEDIA2 = REPO_ROOT / "data" / "external" / "tedman_gpcr_screen" / "tedman2025_gpcr_screen_media-2.xlsx"
SOURCES = [{
    "citation": ("Tedman et al., Efficient experimental characterization of the GPCRome "
                 "via deep receptor scanning, Nat Commun 2026 (bioRxiv 2025.09.19.677468, PMC12458215)"),
    "doi": "10.1038/s41467-026-76564-7",
    "pmid": None,
    "url": "https://doi.org/10.1038/s41467-026-76564-7",
    "claim": ("N-terminal HA epitope inserted per receptor; surface expression read out by HA "
              "immunostaining in a pooled GPCRome deep-receptor-scanning screen."),
}]


def _isoform_surface() -> dict[str, tuple]:
    """SYMBOL_ENST -> (length_aa:int, pme:float|None, pct_change:float|None,
    tedman_canonical_len:int|None) from the media-2 Isoforms sheet.

    Tedman's reported lengths are measured on the HA-tagged CONSTRUCT, not the
    natural UniProt protein — every length in the sheet (isoform AND that row's
    own "canonical length" echo) is inflated by the same per-gene amount (tag
    length + 0-1 linker residues; empirically ~9-10 for the HA tag used here,
    occasionally larger for signal-peptide receptors). The caller derives that
    per-gene offset as (tedman_canonical_len - <Worker's natural canonical
    length>) and subtracts it from `length_aa` before matching against UniProt
    isoform lengths, which are on the natural (untagged) scale."""
    wb = openpyxl.load_workbook(MEDIA2, read_only=True, data_only=True)
    ws = wb["Isoforms"]
    it = ws.iter_rows(values_only=True)
    hdr = list(next(it))
    ix = {n: i for i, n in enumerate(hdr)}
    out = {}
    for r in it:
        name = r[ix["Isoform Transcript"]]
        if not name:
            continue
        key = "_".join(str(name).split("_")[:2])
        out[key] = (
            r[ix["length (AA)"]], r[ix["Surface Expression"]], r[ix["% change in PME"]],
            r[ix["canonical length"]],
        )
    return out


def _fetch_record(symbol: str, client: httpx.Client) -> dict | None:
    try:
        res = client.get(f"{API_BASE}/v1/genes/{symbol}", timeout=30)
        if res.status_code != 200:
            return None
        return res.json()
    except Exception:  # noqa: BLE001
        return None


def emit_isoform_pins(alt_rows_by_gene: dict, iso_surface: dict) -> tuple[int, int, int]:
    """For each gene with alt-isoform Tedman rows, match each isoform to a UniProt
    isoform by protein length and emit a control pin on the isoform's own axis.
    Returns (genes_with_pins, pins_emitted, isoforms_unmatched)."""
    genes_with_pins = pins_emitted = unmatched = 0
    with httpx.Client() as client:
        for symbol, rows in sorted(alt_rows_by_gene.items()):
            rec = _fetch_record(symbol, client)
            if not rec:
                unmatched += len(rows)
                continue
            df = rec.get("deterministic_features") or {}
            iso_topos = [(i["isoform_id"], i.get("sequence") or "")
                         for i in (df.get("isoform_topologies") or []) if i.get("sequence")]
            if not iso_topos:
                unmatched += len(rows)
                continue
            canon_seq = ((df.get("canonical_topology") or {}).get("sequence")) or ""
            canonical_len = len(canon_seq) or None
            seq_by_id = dict(iso_topos)
            lens = [(iid, len(seq)) for iid, seq in iso_topos]
            acc = rows[0]["uniprot_acc"]
            pins = []
            for r in rows:
                m2 = iso_surface.get(f"{symbol}_{r['ensembl_transcript_id']}")
                if not m2 or m2[0] is None:
                    unmatched += 1
                    continue
                iso_len_raw = int(m2[0])
                tedman_canon_len = m2[3]
                offset = (
                    int(tedman_canon_len) - canonical_len
                    if tedman_canon_len is not None and canonical_len else 0
                )
                iso_len = iso_len_raw - offset
                iso_id = match_isoform_by_length(iso_len, lens, canonical_len=canonical_len)
                if not iso_id:
                    unmatched += 1
                    continue
                iso_seq = seq_by_id[iso_id]
                j = str(r.get("junction_after_residue", "")).strip()
                junction = int(j) if j not in ("", "None") else 0
                jm = map_junction_to_canonical(junction, iso_seq)
                isoform_residue = jm.insert_after_residue if jm.insert_after_residue else 1
                pme, pct = m2[1], m2[2]
                note = None
                if pme is not None:
                    note = f"Isoform surface expr {float(pme):.0f}"
                    if pct is not None:
                        note += f" ({float(pct):+.0f}% vs canonical)"
                pins.append(control_isoform_pin(
                    canonical_site_id=f"{symbol}-nterm-tedman", isoform_id=iso_id,
                    isoform_residue=isoform_residue, isoform_len=len(iso_seq),
                    canonical_residue=None, note=note,
                ))
            if pins:
                emit_tag_sites_json(symbol, acc, [], out_dir=OUT, isoform_pins=pins)
                genes_with_pins += 1
                pins_emitted += len(pins)
    return genes_with_pins, pins_emitted, unmatched


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gene")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-isoforms", action="store_true", help="skip the per-isoform control-pin pass")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    all_rows = list(csv.DictReader(TSV.open(), delimiter="\t"))

    rows = [r for r in all_rows
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

    if not args.no_isoforms:
        alt_rows = [r for r in all_rows
                    if r["is_canonical"] == "false" and r["verified"] == "true" and r["uniprot_acc"]]
        if args.gene:
            alt_rows = [r for r in alt_rows if r["gene_symbol"] == args.gene]
        alt_rows_by_gene: dict[str, list] = {}
        for r in alt_rows:
            alt_rows_by_gene.setdefault(r["gene_symbol"], []).append(r)

        iso_surface = _isoform_surface()
        genes_with_pins, pins_emitted, unmatched = emit_isoform_pins(alt_rows_by_gene, iso_surface)
        log.info(
            "isoform pins: %d genes, %d pins emitted, %d isoforms unmatched",
            genes_with_pins, pins_emitted, unmatched,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
