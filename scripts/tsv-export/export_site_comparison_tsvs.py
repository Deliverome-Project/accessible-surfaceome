"""Export the MaSIF-site sweep and the Bindome concordance as flat TSVs.

Both result sets live only on Modal volumes, which sit outside this project's
provenance chain. These TSVs are the durable, reviewable copy: small enough to
commit un-LFS'd (a few MB), one row per site / per anchor, with the stable
identifiers the figure-input conventions require.

Deliberately NOT written to D1: the sweep is incomplete, ~184 library members
carry topology from the wrong isoform (see the report), and the MaSIF model
variant is unsettled. Publishing to the served tables should wait for those.

    uv run python scripts/tsv-export/export_site_comparison_tsvs.py \
        --masif-dir /path/to/sites --bindome /path/to/fullrun.jsonl --out data/processed/extracellular_site_comparison
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import time
from pathlib import Path

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env

MASIF_COLS = [
    "hgnc_id",
    "hgnc_symbol",
    "uniprot_acc",
    "ensembl_gene",
    "ncbi_gene_id",
    "site_id",
    "anchor_residue",
    "topology",
    "n_points",
    "n_residues",
    "mean_masif_score",
    "res_min",
    "res_max",
    "n_sites_protein",
    "n_sites_extracellular_protein",
    "frac_surface_above_0_7",
]
BINDOME_COLS = [
    "hgnc_id",
    "hgnc_symbol",
    "uniprot_acc",
    "ensembl_gene",
    "ncbi_gene_id",
    "surface_bind_site_id",
    "anchor_residue",
    "anchor_topology",
    "surface_bind_area_a2",
    "surface_bind_hydrophobicity",
    "surface_bind_seeds_alpha",
    "surface_bind_seeds_beta",
    "bindome_nearest_interface_angstrom",
    "bindome_designs_used",
    "bindome_interface_residues",
]


def stable_ids(accs: list[str]) -> dict[str, dict]:
    """hgnc_id / symbol / ensembl / ncbi for each accession, from the resolver cache."""
    out: dict[str, dict] = {}
    with D1Client.public() as d1:
        for i in range(0, len(accs), 30):
            chunk = accs[i : i + 30]
            q = (
                "SELECT uniprot_acc, hgnc_id, hgnc_symbol, ensembl_gene, ncbi_gene_id "
                "FROM gene_identifier_public WHERE uniprot_acc IN ("
                + ",".join("?" * len(chunk))
                + ");"
            )
            for r in d1.query(q, chunk):
                out[r["uniprot_acc"]] = r
            time.sleep(0.3)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--masif-dir", required=True)
    ap.add_argument("--bindome", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    load_env()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    masif = [json.load(open(f)) for f in glob.glob(f"{args.masif_dir}/*.json")]
    bind = [json.loads(ln) for ln in open(args.bindome)]
    accs = sorted({r["acc"] for r in masif} | {r["acc"] for r in bind})
    ids = stable_ids(accs)
    print(f"stable ids resolved: {len(ids)}/{len(accs)}")

    p = out / "masif_site_predictions.tsv"
    n = 0
    with open(p, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=MASIF_COLS, delimiter="\t")
        w.writeheader()
        for r in sorted(masif, key=lambda x: x["acc"]):
            if r.get("error"):
                continue
            g = ids.get(r["acc"], {})
            for i, s in enumerate(r.get("sites") or []):
                w.writerow(
                    {
                        "hgnc_id": g.get("hgnc_id"),
                        "hgnc_symbol": g.get("hgnc_symbol") or r.get("sym"),
                        "uniprot_acc": r["acc"],
                        "ensembl_gene": g.get("ensembl_gene"),
                        "ncbi_gene_id": g.get("ncbi_gene_id"),
                        "site_id": i,
                        "anchor_residue": s["anchor"],
                        "topology": s["topology"],
                        "n_points": s["n_pts"],
                        "n_residues": s["n_res"],
                        "mean_masif_score": s["mean_score"],
                        "res_min": s["res_min"],
                        "res_max": s["res_max"],
                        "n_sites_protein": r["n_sites"],
                        "n_sites_extracellular_protein": r["n_sites_extracellular"],
                        "frac_surface_above_0_7": r.get("frac_above_0.7"),
                    }
                )
                n += 1
    print(f"{p}: {n} site rows")

    p = out / "bindome_surface_bind_concordance.tsv"
    n = 0
    with open(p, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=BINDOME_COLS, delimiter="\t")
        w.writeheader()
        for r in sorted(bind, key=lambda x: x["acc"]):
            g = ids.get(r["acc"], {})
            for a in r.get("anchors") or []:
                w.writerow(
                    {
                        "hgnc_id": g.get("hgnc_id"),
                        "hgnc_symbol": g.get("hgnc_symbol") or r.get("symbol"),
                        "uniprot_acc": r["acc"],
                        "ensembl_gene": g.get("ensembl_gene"),
                        "ncbi_gene_id": g.get("ncbi_gene_id"),
                        "surface_bind_site_id": a["sid"],
                        "anchor_residue": a["res"],
                        "anchor_topology": a["topo"],
                        "surface_bind_area_a2": a["area"],
                        "surface_bind_hydrophobicity": a["hyd"],
                        "surface_bind_seeds_alpha": a["sa"],
                        "surface_bind_seeds_beta": a["sb"],
                        "bindome_nearest_interface_angstrom": (
                            round(a["dist"], 2) if a.get("dist") is not None else ""
                        ),
                        "bindome_designs_used": r["n_designs_used"],
                        "bindome_interface_residues": len(r.get("iface") or {}),
                    }
                )
                n += 1
    print(f"{p}: {n} anchor rows")


if __name__ == "__main__":
    main()
