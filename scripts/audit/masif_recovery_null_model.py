"""Is our recovery of SURFACE-Bind anchors better than chance?

Null: our extracellular sites cover some fraction F of the protein's
extracellular residues. If site placement carried no information, a published
anchor would land inside with probability ~F. Compare observed hit rate to F.
"""

import collections as C
import glob
import json
import math
import random
import statistics as St

sb = json.load(open("/tmp/sb.json"))
T = {t["uniprot_acc"]: t for t in sb["topology"]}
TOPO = {
    "O": "extracellular",
    "I": "intracellular",
    "M": "membrane",
    "S": "signal_peptide",
    "B": "membrane",
}
pub = C.defaultdict(list)
for s in sb["sites"]:
    t = T.get(s["uniprot_acc"])
    prt = t["per_residue_topology"] if t else None
    a = int(s["anchor_residue"])
    if prt and 1 <= a <= len(prt) and TOPO.get(prt[a - 1]) == "extracellular":
        pub[s["uniprot_acc"]].append(a)
rows = [json.load(open(f)) for f in glob.glob("/tmp/l1s/sites/*.json")]
ok = {r["acc"]: r for r in rows if not r.get("error")}
val = [a for a in ok if a in pub and a in T]
random.seed(3)
hit = tot = 0
cov = []
null_hits = 0
null_tot = 0
prot_any = 0
for a in val:
    prt = T[a]["per_residue_topology"]
    ec_all = {i + 1 for i, c in enumerate(prt) if c == "O"}
    if not ec_all:
        continue
    covered = set()
    for s in ok[a]["sites"]:
        if s["topology"] == "extracellular":
            covered |= set(s["residues"])
    covered &= ec_all
    f = len(covered) / len(ec_all)
    cov.append(f)
    m = 0
    for p in pub[a]:
        tot += 1
        if p in covered:
            hit += 1
            m += 1
        # null: draw a random extracellular residue, same count
        for _ in range(50):
            null_tot += 1
            null_hits += random.choice(tuple(ec_all)) in covered
    prot_any += m > 0
print(f"validation proteins: {len(val)}   published EC anchors: {tot}")
print()
print(
    f"OBSERVED  anchor inside one of our EC sites : {hit}/{tot} = {100 * hit / tot:.1f}%"
)
print(
    f"NULL      random EC residue inside our sites: {100 * null_hits / null_tot:.1f}%"
)
print(
    f"  (our EC sites cover a median {100 * St.median(cov):.1f}% of each protein's ECD)"
)
print(f"ENRICHMENT: {(hit / tot) / (null_hits / null_tot):.2f}x")
print()
print(
    f"proteins where we recover >=1 of their anchors: {prot_any}/{len(val)} ({100 * prot_any / len(val):.0f}%)"
)
# binomial z vs null

p0 = null_hits / null_tot
z = (hit / tot - p0) / math.sqrt(p0 * (1 - p0) / tot)
print(
    f"z = {z:.1f}  (p {'<1e-10' if abs(z) > 6.5 else f'= {math.erfc(abs(z) / math.sqrt(2)):.2g}'})"
)
