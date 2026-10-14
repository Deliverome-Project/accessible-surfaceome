"""MaSIF-site sweep over the L1 library, reproducing SURFACE-Bind's published
pipeline (score>=0.7 -> DBSCAN -> clusters >=200 points) and then applying the
cohort's DeepTMHMM topology filter, which their own published set lacks.

Resumable: one JSONL line per protein, volume committed after each. The 1,202
proteins with no SURFACE-Bind sites run first; the 1,218 that already have
published sites follow and serve as the validation set.
"""

import modal
from pathlib import Path

image = modal.Image.from_dockerfile(
    str(Path(__file__).parent / "masif" / "Dockerfile")
).pip_install("scikit-learn==1.5.2")
app = modal.App("masif-l1-sweep")
vol = modal.Volume.from_name("masif-l1")

EXTRACT = r"""
import sys, json, glob
import numpy as np
name = sys.argv[1]
ply = glob.glob("data_preparation/01-benchmark_surfaces/%s.ply" % name)
pred = (glob.glob("output/all_feat_3l/pred_data/pred_%s.npy" % name)
        or glob.glob("output/**/pred_%s.npy" % name))
pdb = (glob.glob("data_preparation/01-benchmark_pdbs/%s.pdb" % name)
       or glob.glob("data_preparation/00-raw_pdbs/%s.pdb" % name.split("_")[0]))
if not (ply and pred and pdb):
    json.dump({"error": "missing outputs"}, open("/tmp/ext.json", "w")); sys.exit(0)
import pymesh
verts = np.asarray(pymesh.load_mesh(ply[0]).vertices)
scores = np.load(pred[0]).ravel()
n = min(len(verts), len(scores)); verts, scores = verts[:n], scores[:n]
xyz, rid = [], []
for line in open(pdb[0]):
    if line.startswith("ATOM"):
        try:
            xyz.append([float(line[30:38]), float(line[38:46]), float(line[46:54])]); rid.append(int(line[22:26]))
        except ValueError: pass
xyz = np.asarray(xyz); rid = np.asarray(rid)
best = np.zeros(n, dtype=np.int64)
for i in range(0, n, 2000):
    best[i:i+2000] = ((verts[i:i+2000, None, :] - xyz[None, :, :]) ** 2).sum(-1).argmin(1)
np.save("/tmp/v.npy", verts.astype(np.float32))
np.save("/tmp/s.npy", scores.astype(np.float32))
np.save("/tmp/r.npy", rid[best].astype(np.int32))
json.dump({"n_verts": int(n)}, open("/tmp/ext.json", "w"))
"""


@app.function(
    image=image,
    timeout=5400,
    cpu=2.0,
    memory=8192,
    volumes={"/vol": vol},
    max_containers=100,
    retries=1,
)
def run_one(acc: str):
    import subprocess
    import os
    import urllib.request
    import json
    import time
    import numpy as np
    from sklearn.cluster import DBSCAN

    TOPO = {
        "O": "extracellular",
        "I": "intracellular",
        "M": "membrane",
        "S": "signal_peptide",
        "B": "membrane",
    }
    meta = json.load(open("/vol/l1_inputs.json"))
    info = meta["topology"].get(acc) or {}
    UA = "accessible-surfaceome research bot (becca@deliverome.org)"
    wd = "/masif/data/masif_site"
    rec = {"acc": acc, "sym": info.get("sym")}
    t0 = time.time()
    os.makedirs("/tmp/p", exist_ok=True)
    pdb = f"/tmp/p/{acc}.pdb"
    try:
        r = urllib.request.Request(
            f"https://alphafold.ebi.ac.uk/files/AF-{acc}-F1-model_v6.pdb",
            headers={"User-Agent": UA},
        )
        open(pdb, "wb").write(urllib.request.urlopen(r, timeout=180).read())
    except Exception as e:
        rec["error"] = f"no_alphafold: {e}"
        with open("/vol/l1_sites.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
        vol.commit()
        return rec
    env = dict(os.environ, PATH="/masifbin:" + os.environ["PATH"])

    def sh(c, t=4500):
        p = subprocess.run(
            c,
            shell=True,
            cwd=wd,
            env=env,
            capture_output=True,
            text=True,
            executable="/bin/bash",
            timeout=t,
        )
        return p.returncode, (p.stdout + p.stderr)[-400:]

    name = f"{acc}_A"
    rc1, l1 = sh(f"./data_prepare_one.sh --file {pdb} {name}")
    rc2, l2 = sh(f"./predict_site.sh {name}")
    open("/tmp/extract.py", "w").write(EXTRACT)
    rc3, l3 = sh(f"python /tmp/extract.py {name}", t=2400)
    rec["rc"] = [rc1, rc2, rc3]
    try:
        V = np.load("/tmp/v.npy")
        S_ = np.load("/tmp/s.npy")
        R = np.load("/tmp/r.npy")
    except Exception:
        rec["error"] = "extract_failed"
        rec["log"] = (l1 + l2 + l3)[-400:]
        with open("/vol/l1_sites.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
        vol.commit()
        return rec
    keep = S_ >= 0.7
    rec["n_verts"] = int(len(V))
    rec["frac_above_0.7"] = round(float(keep.mean()), 3)
    sites = []
    if keep.sum() >= 5:
        lab = DBSCAN(eps=3.0, min_samples=5).fit_predict(V[keep])
        Vk, Rk, Sk = V[keep], R[keep], S_[keep]
        import collections as C

        for k, npts in C.Counter(lab[lab >= 0]).items():
            if npts < 200:
                continue
            m = lab == k
            cen = Vk[m].mean(0)
            anchor = int(Rk[m][np.argmin(((Vk[m] - cen) ** 2).sum(1))])
            res = sorted(set(int(x) for x in Rk[m]))
            prt = info.get("prt")
            tc = C.Counter(
                TOPO.get(prt[x - 1]) for x in res if prt and 1 <= x <= len(prt)
            )
            sites.append(
                {
                    "n_pts": int(npts),
                    "anchor": anchor,
                    "mean_score": round(float(Sk[m].mean()), 3),
                    "n_res": len(res),
                    "res_min": res[0],
                    "res_max": res[-1],
                    "residues": res,
                    "topology": (tc.most_common(1)[0][0] if tc else "unknown"),
                }
            )
    sites.sort(key=lambda s: -s["n_pts"])
    rec["sites"] = sites
    rec["n_sites"] = len(sites)
    rec["n_sites_extracellular"] = sum(
        1 for s in sites if s["topology"] == "extracellular"
    )
    rec["secs"] = round(time.time() - t0, 1)
    with open("/vol/l1_sites.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    vol.commit()
    return {k: v for k, v in rec.items() if k != "sites"}


@app.function(volumes={"/vol": vol}, timeout=24 * 3600)
def driver():
    import json
    import os

    meta = json.load(open("/vol/l1_inputs.json"))
    done = set()
    if os.path.exists("/vol/l1_sites.jsonl"):
        for ln in open("/vol/l1_sites.jsonl"):
            try:
                done.add(json.loads(ln)["acc"])
            except Exception:
                pass
    todo = [a for a in meta["order"] if a not in done]
    print(
        f"L1 sweep: {len(done)} done, {len(todo)} to go "
        f"({meta['n_new']} new-first, {meta['n_validation']} validation)",
        flush=True,
    )
    ok = err = 0
    for r in run_one.map(todo, order_outputs=False, return_exceptions=True):
        if isinstance(r, Exception) or (isinstance(r, dict) and r.get("error")):
            err += 1
        else:
            ok += 1
        if (ok + err) % 25 == 0:
            print(f"  {ok + err}/{len(todo)}  ok={ok} err={err}", flush=True)
    print(f"DONE ok={ok} err={err}")
