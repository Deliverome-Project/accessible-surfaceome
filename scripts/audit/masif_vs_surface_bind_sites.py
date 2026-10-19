"""SURFACE-Bind's pipeline + the DeepTMHMM topology filter applied to OUR sites.

Their methods drop "sites located in TM domains"; we apply the stricter and
better-specified rule the cohort already carries -- a site is extracellular
only if the majority of its residues are 'O' in the DeepTMHMM string.
"""

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

print(
    "their pipeline (score>=0.7, DBSCAN eps=3, >=200 pts) + DeepTMHMM filter on OUR sites\n"
)
tot = C.Counter()
detail = []
for vf in sorted(glob.glob(f"{sys.argv[2]}/verts_*.npy")):
    acc = vf.split("verts_")[1][:-4].split("_")[0]
    V = np.load(vf)
    S_ = np.load(vf.replace("verts_", "scores_"))
    R = np.load(vf.replace("verts_", "vres_"))
    prt = T[acc]["per_residue_topology"]
    sym = T[acc].get("gene_symbol", acc)
    keep = S_ >= 0.7
    lab = DBSCAN(eps=3.0, min_samples=5).fit_predict(V[keep])
    Rk = R[keep]
    sizes = C.Counter(lab[lab >= 0])
    raw = [
        sorted(set(int(x) for x in Rk[lab == k])) for k, n in sizes.items() if n >= 200
    ]
    # classify each of OUR sites by the majority topology of its residues
    ours_ec = []
    for s in raw:
        cnt = C.Counter(TOPO.get(prt[r - 1]) for r in s if 1 <= r <= len(prt))
        if cnt and cnt.most_common(1)[0][0] == "extracellular":
            ours_ec.append(s)
    their_ec = [p for p in pub[acc] if p["topo"] == "extracellular"]
    matched = sum(any(p["res"] in s for s in ours_ec) for p in their_ec)
    tot["ours_raw"] += len(raw)
    tot["ours_ec"] += len(ours_ec)
    tot["theirs_all"] += len(pub[acc])
    tot["theirs_ec"] += len(their_ec)
    tot["matched"] += matched
    print(
        f"{sym:8s} our sites {len(raw)} -> {len(ours_ec)} extracellular | "
        f"their sites {len(pub[acc])} -> {len(their_ec)} extracellular | matched {matched}/{len(their_ec)}"
    )
    for p in their_ec:
        hit = any(p["res"] in s for s in ours_ec)
        print(
            f"            theirs res {p['res']:4d} ({p['area']:.0f} A2) -> {'MATCH' if hit else 'MISS'}"
        )
        detail.append((sym, p["res"], p["area"], hit))
print("\n" + "=" * 68)
print(
    f"OUR sites: {tot['ours_raw']} raw -> {tot['ours_ec']} extracellular after the topology filter"
)
print(f"THEIR sites: {tot['theirs_all']} published -> {tot['theirs_ec']} extracellular")
print(
    f"THEIR extracellular anchors recovered by us: {tot['matched']}/{tot['theirs_ec']}"
)
m = [a for _, _, a, h in detail if h]
u = [a for _, _, a, h in detail if not h]
if m:
    print(f"   matched areas  : {sorted((int(x) for x in m), reverse=True)}")
if u:
    print(f"   unmatched areas: {sorted((int(x) for x in u), reverse=True)}")
