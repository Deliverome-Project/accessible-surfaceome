"""Bindome x SURFACE-Bind concordance, and Bindome's own target-side sites.

Bindome publishes 305,806 BindCraft designs but no target-side site list: its
`InterfaceResidues` column is the *binder* chain and every design ran the
`no_hotspot` protocol. The sites therefore have to be recovered from the
complex structures -- chain A/B contacts at 5 A heavy-atom -- which is what
this does, recording per-protein interface-residue counts, CA coordinates, and
each SURFACE-Bind anchor's distance to the nearest Bindome contact.

Two design points worth keeping:

* **One protein per call, one file per protein.** An earlier version appended
  to a single JSONL on the volume and committed per protein; concurrent
  appends lose writes.
* **Chain A is matched against every known sequence for the accession**, not
  just the canonical one. Bindome designs against a specific proteoform, and
  canonical-only matching dropped 36% of the expansion batch as `chain`
  failures.

Politeness, not compute, sets the pace: the CIFs are static files on an
academic server, so each worker sleeps ~1.1 s between fetches and the worker
count is deliberately small.

    uv run modal run --detach modal/bindome_concordance_app.py::driver
"""

from __future__ import annotations

import os

import modal

app = modal.App("bindome-concordance")
vol = modal.Volume.from_name("bindome-concordance")
image = modal.Image.debian_slim(python_version="3.11")
if modal.is_local():  # the image is built from the laptop; containers only re-import this file
    from accessible_surfaceome.trust_store import harden

    image = harden(image)  # drop the compromised eMudhra roots

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
TOPO = {
    "O": "extracellular",
    "I": "intracellular",
    "M": "membrane",
    "S": "signal_peptide",
    "B": "membrane",
}
UA = "accessible-surfaceome research bot (becca@deliverome.org)"


def _parse_cif(txt: str):
    """-> ({chain: {resnum: [(x,y,z,atom)]}}, {(chain,resnum): one-letter})"""
    import collections as C

    lines = txt.splitlines()
    i = next(
        n
        for n, ln in enumerate(lines)
        if ln.strip() == "loop_" and lines[n + 1].strip().startswith("_atom_site.")
    )
    cols, n = [], i + 1
    while lines[n].strip().startswith("_atom_site."):
        cols.append(lines[n].strip().split(".", 1)[1])
        n += 1
    ix = {c: k for k, c in enumerate(cols)}
    ck = ix.get("auth_asym_id", ix.get("label_asym_id"))
    rk = ix.get("auth_seq_id", ix["label_seq_id"])
    ch = C.defaultdict(lambda: C.defaultdict(list))
    comp = {}
    for ln in lines[n:]:
        if not ln.startswith(("ATOM", "HETATM")):
            break
        f = ln.split()
        if f[ix["type_symbol"]] == "H":
            continue
        c, rn = f[ck], int(f[rk])
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


@app.function(
    image=image,
    volumes={"/vol": vol},
    timeout=6 * 3600,
    retries=2,
    max_containers=int(os.environ.get("BINDOME_WORKERS", "4")),
)
def run_one(acc: str) -> dict:
    import collections as C
    import json
    import math
    import time
    import urllib.request

    seqs = json.load(open("/vol/seqs_multi.json"))
    meta = json.load(open("/vol/bindome_meta.json"))
    sb = json.load(open("/vol/sb.json"))
    topo = {t["uniprot_acc"]: t for t in sb["topology"]}
    anchors = C.defaultdict(list)
    for s in sb["sites"]:
        t = topo.get(s["uniprot_acc"])
        if not t:
            continue
        prt = t["per_residue_topology"]
        a = int(s["anchor_residue"])
        if 1 <= a <= len(prt):
            anchors[s["uniprot_acc"]].append(
                {
                    "res": a,
                    "topo": TOPO.get(prt[a - 1]),
                    "area": float(s["area_a2"]),
                    "hyd": float(s["hydrophobicity"]),
                    "sa": int(s["n_seeds_alpha"]),
                    "sb": int(s["n_seeds_beta"]),
                    "sid": int(s["site_id"]),
                }
            )

    def fetch(url, tries=3):
        for k in range(tries):
            try:
                r = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(r, timeout=120) as f:
                    return f.read()
            except Exception:
                if k == tries - 1:
                    return None
                time.sleep(5 * (k + 1))

    unis = seqs.get(acc) or []
    ancs = anchors.get(acc, [])
    models = (meta.get(acc, {}) or {}).get("metrics") or []
    best = {a["res"]: None for a in ancs}
    iface, CA = C.Counter(), {}
    used, fails = 0, C.Counter()
    for m in models:
        txt = fetch(m["model_url"])
        time.sleep(1.1)
        if txt is None:
            fails["fetch"] += 1
            continue
        try:
            ch, comp = _parse_cif(txt.decode("utf-8", "replace"))
        except Exception:
            fails["parse"] += 1
            continue
        # Identify the target chain by sequence. Ordering by atom count picks
        # the 90-residue binder whenever the target domain is smaller.
        cand = []
        for c in ch:
            rns = sorted(ch[c])
            sq = "".join(comp[(c, r)] for r in rns)
            for uni in unis:
                j = uni.find(sq)
                if j >= 0 and uni.count(sq) == 1:
                    cand.append((c, rns, j))
                    break
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
        "symbol": topo.get(acc, {}).get("gene_symbol"),
        "n_designs_used": used,
        "n_designs_listed": len(models),
        "fails": dict(fails),
        "anchors": [{**a, "dist": best[a["res"]]} for a in ancs],
        "iface": {str(k): v for k, v in iface.items()},
        "ca": {str(k): [round(x, 2) for x in v] for k, v in CA.items()} if used else {},
    }
    os.makedirs("/vol/records", exist_ok=True)
    with open(f"/vol/records/{acc}.json", "w") as fh:
        json.dump(rec, fh)
    vol.commit()
    return {k: v for k, v in rec.items() if k not in ("iface", "ca", "anchors")}


@app.function(volumes={"/vol": vol}, timeout=24 * 3600)
def driver():
    import json

    accs = json.load(open("/vol/shared.json"))["shared"]
    done = (
        {f[:-5] for f in os.listdir("/vol/records")}
        if os.path.isdir("/vol/records")
        else set()
    )
    todo = [a for a in accs if a not in done]
    print(f"bindome: {len(done)} done, {len(todo)} to go", flush=True)
    ok = err = 0
    for r in run_one.map(todo, order_outputs=False, return_exceptions=True):
        if isinstance(r, Exception):
            err += 1
        else:
            ok += 1
        if (ok + err) % 25 == 0:
            print(f"  {ok + err}/{len(todo)} ok={ok} err={err}", flush=True)
    print(f"DONE ok={ok} err={err}")
