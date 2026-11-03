"""Full Bindome x SURFACE-Bind concordance over all 481 shared proteins.

Resumable: appends one JSON line per protein to OUT; on restart, skips
proteins already present. CIFs are parsed and DISCARDED (never stored),
so this costs bandwidth, not 10 GB of disk.
Chain assignment is by sequence match to the UniProt record (the
largest-chain heuristic picks the 90-residue binder on small domains).
"""

import json
import math
import os
import sys
import time
import urllib.request
import collections as C
from pathlib import Path

SB, SHARED, META, OUT = sys.argv[1:5]
UA = "accessible-surfaceome research bot (becca@deliverome.org)"
A3 = {
    "ALA": "A",
    "ARG": "R",
    "ASN": "N",
    "ASP": "D",
    "CYS": "C",
    "GLN": "Q",
    "GLU": "E",
    "GLY": "G",
    "HIS": "H",
    "ILE": "I",
    "LEU": "L",
    "LYS": "K",
    "MET": "M",
    "PHE": "F",
    "PRO": "P",
    "SER": "S",
    "THR": "T",
    "TRP": "W",
    "TYR": "Y",
    "VAL": "V",
    "MSE": "M",
}
d = json.load(open(SB))
T = {t["uniprot_acc"]: t for t in d["topology"]}
SEQ = json.load(open(str(Path(SHARED).parent / "seqs.json")))
meta = json.load(open(META))
m = {
    "O": "extracellular",
    "I": "intracellular",
    "M": "membrane",
    "S": "signal_peptide",
    "B": "membrane",
}
anc = C.defaultdict(list)
for s in d["sites"]:
    t = T.get(s["uniprot_acc"])
    if not t:
        continue
    p = t["per_residue_topology"]
    a = int(s["anchor_residue"])
    if 1 <= a <= len(p):
        anc[s["uniprot_acc"]].append(
            {
                "res": a,
                "topo": m.get(p[a - 1]),
                "area": float(s["area_a2"]),
                "hyd": float(s["hydrophobicity"]),
                "sa": int(s["n_seeds_alpha"]),
                "sb": int(s["n_seeds_beta"]),
                "sid": int(s["site_id"]),
            }
        )
done = set()
if os.path.exists(OUT):
    for ln in open(OUT):
        try:
            done.add(json.loads(ln)["acc"])
        except Exception:
            pass
todo = [
    a for a in sorted(json.load(open(SHARED))["shared"]) if a in SEQ and a not in done
]
print(f"resume: {len(done)} done, {len(todo)} to go", flush=True)


def fetch(url, tries=3):
    for i in range(tries):
        try:
            r = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(r, timeout=120) as f:
                return f.read()
        except Exception:
            if i == tries - 1:
                return None
            time.sleep(5 * (i + 1))


def parse(txt):
    lines = txt.splitlines()
    i = next(
        n
        for n, ln in enumerate(lines)
        if ln.strip() == "loop_" and lines[n + 1].strip().startswith("_atom_site.")
    )
    cols = []
    n = i + 1
    while lines[n].strip().startswith("_atom_site."):
        cols.append(lines[n].strip().split(".", 1)[1])
        n += 1
    ix = {c: k for k, c in enumerate(cols)}
    ck = ix.get("auth_asym_id", ix.get("label_asym_id"))
    rk = ix.get("auth_seq_id", ix["label_seq_id"])
    ch = C.defaultdict(lambda: C.defaultdict(list))
    comp = {}
    for line in lines[n:]:
        if not line.startswith(("ATOM", "HETATM")):
            break
        f = line.split()
        if f[ix["type_symbol"]] == "H":
            continue
        c = f[ck]
        rn = int(f[rk])
        ch[c][rn].append(
            (
                float(f[ix["Cartn_x"]]),
                float(f[ix["Cartn_y"]]),
                float(f[ix["Cartn_z"]]),
                f[ix["label_atom_id"]],
            )
        )
        comp[(c, rn)] = A3.get(f[ix["label_comp_id"]].upper(), "X")
    return ch, comp


t0 = time.time()
out = open(OUT, "a")
for pi, acc in enumerate(todo):
    uni = SEQ[acc]
    ancs = anc.get(acc, [])
    ms = (meta.get(acc, {}) or {}).get("metrics") or []
    best = {a["res"]: None for a in ancs}
    iface = C.Counter()
    CA = {}
    used = 0
    fails = C.Counter()
    for mm in ms:
        txt = fetch(mm["model_url"])
        time.sleep(0.9)
        if txt is None:
            fails["fetch"] += 1
            continue
        try:
            ch, comp = parse(txt.decode("utf-8", "replace"))
        except Exception:
            fails["parse"] += 1
            continue
        cand = []
        for c in ch:
            rns = sorted(ch[c])
            sq = "".join(comp[(c, r)] for r in rns)
            j = uni.find(sq)
            if j >= 0 and uni.count(sq) == 1:
                cand.append((c, rns, j))
        if len(cand) != 1:
            fails["chain"] += 1
            continue
        tc, rns, j = cand[0]
        others = [c for c in ch if c != tc]
        if not others:
            fails["nobinder"] += 1
            continue
        bc = max(others, key=lambda c: sum(len(v) for v in ch[c].values()))
        mp = {rn: j + k + 1 for k, rn in enumerate(rns)}
        inv = {v: k for k, v in mp.items()}
        ca = {}
        for rn in rns:
            c2 = next((p[:3] for p in ch[tc][rn] if p[3] == "CA"), None)
            if c2:
                ca[rn] = c2
                CA.setdefault(mp[rn], c2)
        bat = [(x, y, z) for r in ch[bc].values() for (x, y, z, _) in r]
        hit = set()
        for rn, ats in ch[tc].items():
            for x, y, z, _ in ats:
                if any(
                    (x - bx) ** 2 + (y - by) ** 2 + (z - bz) ** 2 <= 25.0
                    for (bx, by, bz) in bat
                ):
                    hit.add(rn)
                    break
        ifca = [ca[rn] for rn in hit if rn in ca]
        if not ifca:
            continue
        used += 1
        for rn in hit:
            if rn in mp:
                iface[mp[rn]] += 1
        for a in ancs:
            r = a["res"]
            if r not in inv or inv[r] not in ca:
                continue
            dm = min(math.dist(ca[inv[r]], c2) for c2 in ifca)
            if best[r] is None or dm < best[r]:
                best[r] = dm
    rec = {
        "acc": acc,
        "symbol": T.get(acc, {}).get("gene_symbol"),
        "n_designs_used": used,
        "n_designs_listed": len(ms),
        "fails": dict(fails),
        "anchors": [{**a, "dist": best[a["res"]]} for a in ancs],
        "iface": {str(k): v for k, v in iface.items()},
        "ca": {str(k): [round(x, 2) for x in v] for k, v in CA.items()} if used else {},
    }
    out.write(json.dumps(rec) + "\n")
    out.flush()
    el = time.time() - t0
    print(
        f"[{pi + 1}/{len(todo)}] {acc} {rec['symbol']} designs={used}/{len(ms)} "
        f"| elapsed {el / 60:.0f}m eta {el / (pi + 1) * (len(todo) - pi - 1) / 60:.0f}m",
        flush=True,
    )
out.close()
print("DONE")
