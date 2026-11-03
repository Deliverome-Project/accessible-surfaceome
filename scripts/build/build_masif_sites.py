"""Flatten the MaSIF-site sweep into one row per site, for D1 and the viewer.

Sites come from our own re-run of SURFACE-Bind's method on the L1 library --
MaSIF-site at their published cutoffs (score >= 0.7, DBSCAN eps=2.5
min_samples=2, clusters strictly > 200 points), over the structure the library
says is actually being ordered.

Two residue frames are carried deliberately. `anchor_residue` is numbered
against the MODEL, which is what MaSIF emits; `anchor_ordered` is numbered
against the ORDERED protein, which is what the topology string and the
construct use. For the 25 `contained` members they differ by up to 134, and
collapsing them to one column would make the next reader guess which.

    uv run python scripts/build/build_masif_sites.py \
        --sites <sites_v2/> --inputs <l1_inputs.json> --out data/external/masif/masif_sites.tsv
"""

from __future__ import annotations

import argparse
import collections as C
import csv
import glob
import json

COLS = [
    "candidate_id",
    "uniprot_acc",
    "gene_symbol",
    "species",
    "site_id",
    "anchor_residue",
    "anchor_ordered",
    "residue_offset",
    "compartment",
    "n_points",
    "n_residues",
    "mean_masif_score",
    "res_min",
    "res_max",
    "residues",
    "structure_source",
    "topology_version",
    "topology_cohort",
    "sequence_sha256",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", required=True)
    ap.add_argument("--inputs", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    members = json.load(open(args.inputs))["members"]
    recs = [json.load(open(f)) for f in glob.glob(f"{args.sites}/*.json")]
    ok = [r for r in recs if not r.get("error")]
    stat: C.Counter[str] = C.Counter()
    n = 0
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, delimiter="\t", lineterminator="\n")
        w.writeheader()
        for r in sorted(ok, key=lambda x: x["candidate_id"]):
            info = members.get(r["candidate_id"], {})
            for i, s in enumerate(
                sorted(r.get("sites") or [], key=lambda x: -x["n_pts"])
            ):
                w.writerow(
                    {
                        "candidate_id": r["candidate_id"],
                        "uniprot_acc": r.get("acc"),
                        "gene_symbol": r.get("sym") or "",
                        "species": r.get("species") or "",
                        "site_id": i,
                        "anchor_residue": s["anchor"],
                        "anchor_ordered": s.get("anchor_ordered", s["anchor"]),
                        "residue_offset": s.get("residue_offset", 0),
                        "compartment": s["topology"],
                        "n_points": s["n_pts"],
                        "n_residues": s["n_res"],
                        "mean_masif_score": s["mean_score"],
                        "res_min": s["res_min"],
                        "res_max": s["res_max"],
                        "residues": ",".join(str(x) for x in s["residues"]),
                        "structure_source": r.get("structure_source")
                        or info.get("source")
                        or "",
                        "topology_version": r.get("topology_version") or "",
                        "topology_cohort": r.get("topology_cohort") or "",
                        "sequence_sha256": r.get("sequence_sha256")
                        or info.get("sequence_sha256")
                        or "",
                    }
                )
                stat[s["topology"]] += 1
                n += 1
            stat["proteins"] += 1
    print(f"{args.out}: {n} sites over {stat['proteins']} members")
    for k, v in stat.most_common():
        if k != "proteins":
            print(f"    {k:18s} {v}")


if __name__ == "__main__":
    main()
