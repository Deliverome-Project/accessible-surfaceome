"""Their methods give threshold (0.7) and min cluster size (200) but NOT the
DBSCAN eps. Sweep it and see which value best reproduces their published sites."""

import json
import glob
import sys
import collections as C
import numpy as np
from sklearn.cluster import DBSCAN

SB = json.load(open(sys.argv[1]))
T = {t["uniprot_acc"]: t for t in SB["topology"]}
TOPO = {
    "O": "extracellular",
    "I": "intracellular",
    "M": "membrane",
    "S": "signal_peptide",
    "B": "membrane",
}
pub = C.defaultdict(list)
for s in SB["sites"]:
    t = T.get(s["uniprot_acc"])
    prt = t["per_residue_topology"] if t else None
    a = int(s["anchor_residue"])
    pub[s["uniprot_acc"]].append(
        {
            "res": a,
            "area": float(s["area_a2"]),
            "topo": TOPO.get(prt[a - 1]) if prt and 1 <= a <= len(prt) else None,
        }
    )
data = []
for vf in sorted(glob.glob(f"{sys.argv[2]}/verts_*.npy")):
    acc = vf.split("verts_")[1][:-4].split("_")[0]
    data.append(
        (
            acc,
            np.load(vf),
            np.load(vf.replace("verts_", "scores_")),
            np.load(vf.replace("verts_", "vres_")),
        )
    )
print(
    f"{'eps':>5} {'minpts':>7} | {'ourSites':>9} {'theirSites':>11} | {'EC matched':>11} {'all matched':>12}"
)
print("-" * 66)
best = []
for eps in (1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0):
    for mp in (200,):
        tot_ours = tot_theirs = 0
        ec_hit = ec_tot = all_hit = all_tot = 0
        for acc, V, S_, R in data:
            keep = S_ >= 0.7
            if keep.sum() == 0:
                continue
            lab = DBSCAN(eps=eps, min_samples=5).fit_predict(V[keep])
            sizes = C.Counter(lab[lab >= 0])
            Rk = R[keep]
            sites = [
                sorted(set(int(x) for x in Rk[lab == k]))
                for k, n in sizes.items()
                if n >= mp
            ]
            tot_ours += len(sites)
            tot_theirs += len(pub[acc])
            for p in pub[acc]:
                inside = any(p["res"] in s for s in sites)
                all_tot += 1
                all_hit += inside
                if p["topo"] == "extracellular":
                    ec_tot += 1
                    ec_hit += inside
        print(
            f"{eps:5.1f} {mp:7d} | {tot_ours:9d} {tot_theirs:11d} | "
            f"{ec_hit:4d}/{ec_tot:<6d} {all_hit:5d}/{all_tot:<6d}"
        )
        best.append(
            (ec_hit / ec_tot if ec_tot else 0, -abs(tot_ours - tot_theirs), eps, mp)
        )
best.sort(reverse=True)
print(
    f"\nbest by (EC match rate, then closest site count): eps={best[0][2]}, min_pts={best[0][3]}"
)
