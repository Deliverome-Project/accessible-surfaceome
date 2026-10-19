"""Discrete Bindome binding sites, derived from the BindCraft design interfaces.

Bindome publishes no target-side site list -- ``InterfaceResidues`` in its
metrics is the *binder* chain, and every design ran ``no_hotspot``. So a site
has to be recovered from where the designs actually land: pool the target
residues contacted across a protein's designs, keep the ones contacted by a
meaningful share of them, and cluster those in 3D.

Input is the concordance run (``modal/bindome_concordance_app.py``), which
already records per-protein interface-residue counts and CA coordinates.

Each site is labelled with the compartment its anchor sits in, using the same
DeepTMHMM per-residue string the SURFACE-Bind sites are labelled with, so the
viewer can show both sources on one axis.

    uv run python scripts/build/build_bindome_sites.py \
        --concordance fullrun.jsonl --out data/external/bindome/bindome_sites.tsv
"""

from __future__ import annotations

import argparse
import collections as C
import csv
import json
import math
import time

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env

TOPO = {
    "O": "extracellular",
    "I": "intracellular",
    "M": "membrane",
    "S": "signal_peptide",
    "B": "membrane",
}
# A residue counts as part of a site when at least this share of the protein's
# parsed designs contact it -- below that it is a stray contact from one design.
MIN_DESIGN_FRACTION = 0.20
# Single-linkage radius on CA coordinates, and the smallest cluster we keep.
LINK_ANGSTROM = 8.0
MIN_RESIDUES = 5

COLS = [
    "uniprot_acc",
    "gene_symbol",
    "site_id",
    "anchor_residue",
    "compartment",
    "n_residues",
    "n_designs_supporting",
    "n_designs_total",
    "mean_design_fraction",
    "residues",
]


def cluster(residues: list[int], ca: dict[int, list[float]]) -> list[set[int]]:
    """Single-linkage clusters of residues whose CA atoms are within LINK_ANGSTROM."""
    todo = {r for r in residues if r in ca}
    out: list[set[int]] = []
    while todo:
        seed = todo.pop()
        group, frontier = {seed}, [seed]
        while frontier:
            x = frontier.pop()
            near = {r for r in todo if math.dist(ca[x], ca[r]) <= LINK_ANGSTROM}
            todo -= near
            group |= near
            frontier += list(near)
        out.append(group)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--concordance", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--topology-version", default="topo_2026_05_16")
    args = ap.parse_args()
    load_env()

    rows = [json.loads(ln) for ln in open(args.concordance)]
    accs = sorted({r["acc"] for r in rows})
    prt: dict[str, str] = {}
    with D1Client.public() as d1:
        for i in range(0, len(accs), 30):
            chunk = accs[i : i + 30]
            q = (
                "SELECT uniprot_acc, per_residue_topology FROM topology_public "
                "WHERE topology_version=? AND cohort='human_canonical' "
                "AND is_canonical IN ('1',1) AND uniprot_acc IN ("
                + ",".join("?" * len(chunk))
                + ");"
            )
            for r in d1.query(q, [args.topology_version] + chunk):
                prt[r["uniprot_acc"]] = r["per_residue_topology"]
            time.sleep(0.3)

    n_sites = 0
    stat: C.Counter[str] = C.Counter()
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, delimiter="\t", lineterminator="\n")
        w.writeheader()
        for rec in sorted(rows, key=lambda x: x["acc"]):
            iface = {int(k): int(v) for k, v in (rec.get("iface") or {}).items()}
            ca = {int(k): v for k, v in (rec.get("ca") or {}).items()}
            n_designs = rec.get("n_designs_used") or 0
            if not iface or not ca or not n_designs:
                stat["no interface data"] += 1
                continue
            floor = max(1, int(MIN_DESIGN_FRACTION * n_designs))
            core = [r for r, n in iface.items() if n >= floor]
            groups = [g for g in cluster(core, ca) if len(g) >= MIN_RESIDUES]
            if not groups:
                stat["no cluster above the floor"] += 1
                continue
            topo = prt.get(rec["acc"])
            for sid, g in enumerate(sorted(groups, key=lambda s: -len(s))):
                pts = [ca[r] for r in g]
                cen = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
                anchor = min(g, key=lambda r: math.dist(ca[r], cen))
                comp = (
                    TOPO.get(topo[anchor - 1])
                    if topo and 1 <= anchor <= len(topo)
                    else "unknown"
                )
                res = sorted(g)
                w.writerow(
                    {
                        "uniprot_acc": rec["acc"],
                        "gene_symbol": rec.get("symbol") or "",
                        "site_id": sid,
                        "anchor_residue": anchor,
                        "compartment": comp,
                        "n_residues": len(res),
                        "n_designs_supporting": max(iface[r] for r in g),
                        "n_designs_total": n_designs,
                        "mean_design_fraction": round(
                            sum(iface[r] for r in g) / len(g) / n_designs, 3
                        ),
                        "residues": ",".join(str(r) for r in res),
                    }
                )
                n_sites += 1
                stat[comp] += 1
            stat["proteins with sites"] += 1
    print(f"{args.out}: {n_sites} sites")
    for k, v in stat.most_common():
        print(f"    {k:28s} {v}")


if __name__ == "__main__":
    main()
