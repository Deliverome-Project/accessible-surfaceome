"""Build the L1 MaSIF run list + topology strings for the DeepTMHMM site filter.

Order matters: the 1,202 proteins with no SURFACE-Bind sites run FIRST (that is
the set that was actually asked for), then the 1,218 that already have published
sites, which double as the validation set.
"""

import json
import sys
import time
from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env

load_env()
l1 = json.load(open(sys.argv[1]))
with D1Client.public() as d1:
    sb_sites = {
        r["uniprot_acc"]
        for r in d1.query("SELECT DISTINCT uniprot_acc FROM surface_bind_site;", [])
    }
    ver = d1.query(
        "SELECT r.topology_version FROM topology_release r WHERE EXISTS (SELECT 1 FROM topology_public t "
        "WHERE t.topology_version=r.topology_version AND t.cohort='human_canonical') "
        "ORDER BY r.loaded_at DESC LIMIT 1;",
        [],
    )[0]["topology_version"]
    topo = {}
    for i in range(0, len(l1), 30):
        ch = l1[i : i + 30]
        q = (
            "SELECT uniprot_acc, protein_length, per_residue_topology, gene_symbol FROM topology_public "
            "WHERE topology_version=? AND cohort='human_canonical' AND is_canonical IN ('1',1) "
            "AND uniprot_acc IN (" + ",".join("?" * len(ch)) + ");"
        )
        for r in d1.query(q, [ver] + ch):
            topo[r["uniprot_acc"]] = {
                "len": int(r["protein_length"]),
                "prt": r["per_residue_topology"],
                "sym": r.get("gene_symbol"),
            }
        time.sleep(0.3)
new = [a for a in l1 if a not in sb_sites]
val = [a for a in l1 if a in sb_sites]
order = new + val
json.dump(
    {
        "order": order,
        "n_new": len(new),
        "n_validation": len(val),
        "topology": topo,
        "topology_version": ver,
    },
    open(sys.argv[2], "w"),
)
print(f"run list: {len(order)}  ({len(new)} new first, then {len(val)} validation)")
print(
    f"topology strings: {len(topo)}/{len(l1)}  (missing {len(l1) - len(topo)} -> site topology will be 'unknown')"
)
