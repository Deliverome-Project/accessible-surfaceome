import json
import sys
import time
import statistics as St
from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env

load_env()
l1 = json.load(open(sys.argv[1]))
print(f"L1 canonical human accessions: {len(l1)}")
with D1Client.public() as d1:
    sb_all = {
        r["uniprot_acc"]
        for r in d1.query("SELECT uniprot_acc FROM surface_bind_protein;", [])
    }
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
    L = {}
    for i in range(0, len(l1), 40):
        ch = l1[i : i + 40]
        q = (
            "SELECT uniprot_acc, protein_length FROM topology_public WHERE topology_version=? AND "
            "cohort='human_canonical' AND is_canonical IN ('1',1) AND uniprot_acc IN ("
            + ",".join("?" * len(ch))
            + ");"
        )
        for r in d1.query(q, [ver] + ch):
            L[r["uniprot_acc"]] = int(r["protein_length"])
        time.sleep(0.3)
need = [a for a in l1 if a not in sb_sites]
print(f"  already have SURFACE-Bind SITES : {len(l1) - len(need)}")
print(f"  listed in SURFACE-Bind, 0 sites : {len([a for a in need if a in sb_all])}")
print(
    f"  absent from SURFACE-Bind entirely: {len([a for a in need if a not in sb_all])}"
)
print(f"  ==> TO RUN (L1 minus existing SURFACE-Bind sites): {len(need)}")
print(
    f"\nlengths known for {len([a for a in need if a in L])}/{len(need)} (rest not in our topology table)"
)
M = [(125, 78.0), (235, 196.6), (252, 207.5), (459, 547.9), (1210, 619.8)]
xs = [m[0] for m in M]
ys = [m[1] for m in M]


def t_of(x):
    if x <= xs[0]:
        return ys[0] * x / xs[0]
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            f = (x - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] + f * (ys[i + 1] - ys[i])
    return ys[-1] * (x / xs[-1]) ** 0.5


known = [L[a] for a in need if a in L]
med = St.median(known)
secs = [t_of(L[a]) if a in L else t_of(med) for a in need]
tot = sum(secs)
print(
    f"length: median {med:.0f}  mean {sum(known) / len(known):.0f}  p90 {sorted(known)[int(0.9 * len(known))]}"
)
print(f"per-protein MaSIF: median {St.median(secs):.0f}s  mean {tot / len(secs):.0f}s")
print(f"\nTOTAL: {tot / 3600:.0f} core-hours ({tot:,.0f} s)")
for cpu, mem in ((2, 8), (4, 16)):
    c = tot * cpu * 0.0000131
    m = tot * mem * 0.00000222
    print(f"  cpu={cpu} mem={mem}GiB -> ${c:.0f} CPU + ${m:.0f} mem = ${c + m:.0f}")
for k in (50, 100, 200):
    print(f"  wall-clock @{k} concurrent: {tot / k / 3600:.1f} h")
json.dump(need, open(sys.argv[2], "w"))
