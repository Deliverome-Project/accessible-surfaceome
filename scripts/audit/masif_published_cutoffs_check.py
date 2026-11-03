"""Their published code (data.py / analyze_dataset.py) vs the parameters I guessed."""

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
    if prt and 1 <= a <= len(prt) and TOPO.get(prt[a - 1]) == "extracellular":
        pub[s["uniprot_acc"]].append({"res": a, "area": float(s["area_a2"])})

CONFIGS = [
    ("MINE      eps=3.0 min_samples=5 >=200", 3.0, 5, 200, False),
    ("THEIRS    eps=2.5 min_samples=2  >200", 2.5, 2, 200, True),
    ("theirs-eps only   2.5 / 5  >=200", 2.5, 5, 200, False),
    ("theirs-minsamp    3.0 / 2  >=200", 3.0, 2, 200, False),
]
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
print(f"{'config':40s} {'sites':>6s} {'ECsites':>8s} {'recovered':>10s}")
print("-" * 70)
for name, eps, ms, minpts, strict in CONFIGS:
    tot_sites = tot_ec = hit = tot = 0
    for acc, V, S_, R in data:
        prt = T[acc]["per_residue_topology"]
        keep = S_ >= 0.7
        if keep.sum() < ms:
            continue
        lab = DBSCAN(eps=eps, min_samples=ms).fit_predict(V[keep])
        Rk = R[keep]
        ec_res = set()
        for k, n in C.Counter(lab[lab >= 0]).items():
            if (n > minpts) if strict else (n >= minpts):
                res = sorted(set(int(x) for x in Rk[lab == k]))
                tot_sites += 1
                c = C.Counter(TOPO.get(prt[x - 1]) for x in res if 1 <= x <= len(prt))
                if c and c.most_common(1)[0][0] == "extracellular":
                    tot_ec += 1
                    ec_res |= set(res)
        for p in pub.get(acc, []):
            tot += 1
            hit += p["res"] in ec_res
    print(
        f"{name:40s} {tot_sites:6d} {tot_ec:8d} {hit:4d}/{tot:<5d} ({100 * hit / tot if tot else 0:3.0f}%)"
    )
