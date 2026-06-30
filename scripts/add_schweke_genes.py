#!/usr/bin/env python
"""Add specific genes to the Schweke homomer payload + D1, then (optionally)
ingest their PDBs to R2.

This is the *targeted* companion to ``build_schweke_d1_table.py``. The full
build re-intersects the Schweke refset against the whole candidate universe;
use this instead when a handful of genes newly enter the universe (e.g. a v3
re-add) and you want them live without rebuilding/repushing all ~1,205 rows.

It reuses the build script's helpers so a row added here is byte-identical to
what a full rebuild would produce: stable IDs from ``gene_identifier_public``,
``af_model_num`` from the refset, stoichiometry/complex from
``full_complex_index.tsv``, ``is_ecd_only`` from UniProt TM annotations, and
the canonical SHORT complex filename (figshare ``_model_0_rank_1`` stripped).

Steps: append new rows to ``schweke_d1_payload.tsv`` (idempotent — skips accs
already present) and UPSERT them into D1 ``schweke_homomer_public``. Then run
``ingest_schweke_pdbs_to_r2.py --execute`` (reads the payload) to push the new
PDBs to R2.

Usage::

    # dry-run — show the rows that would be added
    uv run python scripts/add_schweke_genes.py Q99720 Q9UBI4

    # append to payload + UPSERT to D1
    uv run python scripts/add_schweke_genes.py Q99720 Q9UBI4 --execute
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import build_schweke_d1_table as bd  # noqa: E402
from accessible_surfaceome.cloud.d1_client import D1Client  # noqa: E402
from accessible_surfaceome.env import load_env  # noqa: E402

_RANK = re.compile(r"_model_\d+_rank_\d+(?=\.pdb$)")
_PAYLOAD_COLS = [
    "universe_version", "hgnc_id", "uniprot_acc", "gene_symbol",
    "ensembl_gene", "ncbi_gene_id", "af_model_num", "stoichiometry",
    "has_higher_order_complex", "is_ecd_only", "dimer_pdb_filename",
    "complex_pdb_filename", "schweke_version",
]


def _build_entry(acc, refset, complex_index, stable, tm_cache, universe_version):
    if acc not in refset:
        raise SystemExit(f"{acc} is not in the Schweke refset — not a homomer")
    model_num = refset[acc]
    ce = complex_index.get(acc)
    if ce:
        stoich = ce["stoichiometry"]
        has_complex = 1
        complex_fn = _RANK.sub("", ce["pdb_filename"])
    else:
        stoich = 2
        has_complex = 0
        complex_fn = None
    s = stable.get(acc, {})
    return bd.SchwekeEntry(
        universe_version=universe_version,
        hgnc_id=s.get("hgnc_id"),
        uniprot_acc=acc,
        gene_symbol=s.get("gene_symbol"),
        ensembl_gene=s.get("ensembl_gene"),
        ncbi_gene_id=s.get("ncbi_gene_id"),
        af_model_num=model_num,
        stoichiometry=stoich,
        has_higher_order_complex=has_complex,
        is_ecd_only=bd._classify_ecd_only(acc, tm_cache),
        dimer_pdb_filename=f"{acc}_V1_{model_num}.pdb",
        complex_pdb_filename=complex_fn,
        schweke_version=bd.SCHWEKE_VERSION,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("accs", nargs="+", help="UniProt accessions to add")
    ap.add_argument("--execute", action="store_true", help="write payload + push D1 (default: dry-run)")
    ap.add_argument("--universe-version", default=bd.DEFAULT_UNIVERSE_VERSION)
    args = ap.parse_args()

    load_env()
    refset = bd._read_refset()
    complex_index = bd._read_complex_index()
    tm_cache = bd._load_tm_cache()
    with D1Client.public() as d1:
        stable = bd._query_gene_identifier(d1, args.accs)

    entries = [
        _build_entry(acc, refset, complex_index, stable, tm_cache, args.universe_version)
        for acc in args.accs
    ]
    bd._save_tm_cache(tm_cache)

    print(f"{'acc':9} {'gene':10} {'stoich':6} {'dimer':22} {'complex':26} ecd")
    for e in entries:
        print(
            f"{e.uniprot_acc:9} {e.gene_symbol or '?':10} c{e.stoichiometry:<5} "
            f"{e.dimer_pdb_filename:22} {e.complex_pdb_filename or '-':26} {e.is_ecd_only}"
        )

    if not args.execute:
        print("\n[dry-run] re-run with --execute to append to payload + UPSERT to D1.")
        return 0

    # 1) Append to payload (skip accs already present).
    existing = set()
    if bd.PAYLOAD_PATH.exists():
        with bd.PAYLOAD_PATH.open() as fh:
            existing = {r["uniprot_acc"] for r in csv.DictReader(fh, delimiter="\t")}
    to_add = [e for e in entries if e.uniprot_acc not in existing]
    if to_add:
        with bd.PAYLOAD_PATH.open("a", newline="") as fh:
            w = csv.writer(fh, delimiter="\t")
            for e in to_add:
                w.writerow([
                    e.universe_version, e.hgnc_id, e.uniprot_acc, e.gene_symbol,
                    e.ensembl_gene, e.ncbi_gene_id, e.af_model_num, e.stoichiometry,
                    e.has_higher_order_complex, e.is_ecd_only,
                    e.dimer_pdb_filename, e.complex_pdb_filename or "", e.schweke_version,
                ])
        print(f"\nappended {len(to_add)} row(s) to {bd.PAYLOAD_PATH.relative_to(REPO)}")
    else:
        print("\nall accs already in payload — no rows appended")

    # 2) UPSERT to D1 schweke_homomer_public (rows only — leave the release-row
    #    summary to the full build, which has the true intersection counts).
    sql = (
        "INSERT OR REPLACE INTO schweke_homomer_public ("
        "  universe_version, hgnc_id, uniprot_acc, gene_symbol,"
        "  ensembl_gene, ncbi_gene_id, af_model_num, stoichiometry,"
        "  has_higher_order_complex, is_ecd_only,"
        "  dimer_pdb_filename, complex_pdb_filename, schweke_version, synced_at"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?, datetime('now'));"
    )
    with D1Client.public() as d1:
        for e in entries:
            d1.query(sql, [
                e.universe_version, e.hgnc_id, e.uniprot_acc, e.gene_symbol,
                e.ensembl_gene, e.ncbi_gene_id, e.af_model_num, e.stoichiometry,
                e.has_higher_order_complex, e.is_ecd_only,
                e.dimer_pdb_filename, e.complex_pdb_filename, e.schweke_version,
            ])
    print(f"UPSERTed {len(entries)} row(s) into D1 schweke_homomer_public")
    print("\nnext: uv run --with remotezip python scripts/ingest_schweke_pdbs_to_r2.py --execute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
