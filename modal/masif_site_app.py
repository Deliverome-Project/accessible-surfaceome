"""MaSIF-site sweep over the L1 library, reproducing SURFACE-Bind's published
pipeline (score>=0.7 -> DBSCAN -> clusters >=200 points) and then applying the
cohort's DeepTMHMM topology filter, which their own published set lacks.

Resumable: one JSONL line per protein, volume committed after each. The 1,202
proteins with no SURFACE-Bind sites run first; the 1,218 that already have
published sites follow and serve as the validation set.
"""

import os

import modal
from pathlib import Path

image = modal.Image.from_dockerfile(str(Path(__file__).parent / "masif" / "Dockerfile"))
if modal.is_local():  # the image is built from the laptop; containers only re-import this file
    from accessible_surfaceome.trust_store import harden

    image = harden(image)  # drop the compromised eMudhra roots
app = modal.App("masif-l1-sweep")
vol = modal.Volume.from_name("masif-l1")

EXTRACT = r"""
import sys, json, glob, os
import numpy as np
name = sys.argv[1]
# candidate_id, so the cached vertices are filed under the same key the
# sweep writes its sites under.
cid = sys.argv[2]
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
# Persist them. Clustering parameters are the one thing most likely to be
# revisited -- SURFACE-Bind's published DBSCAN(eps=2.5, min_samples=2) versus
# anything else -- and without the vertices that means re-running MaSIF
# inference for every protein just to re-cluster. 56 KB each, ~131 MB for the
# whole library, so no future clustering question costs inference again.
os.makedirs("/vol/verts", exist_ok=True)
np.save("/vol/verts/%s.v.npy" % cid, verts.astype(np.float32))
np.save("/vol/verts/%s.s.npy" % cid, scores.astype(np.float32))
np.save("/vol/verts/%s.r.npy" % cid, rid[best].astype(np.int32))
json.dump({"n_verts": int(n)}, open("/tmp/ext.json", "w"))
"""


@app.function(
    image=image,
    timeout=5400,
    cpu=2.0,
    memory=8192,
    volumes={"/vol": vol},
    max_containers=int(os.environ.get("MASIF_MAX_CONTAINERS", "35")),
    retries=1,
)
def run_one(cid: str):
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
    meta = json.load(open("/vol/l1_inputs_v4.json"))
    info = meta["members"][cid]
    acc = info["acc"]
    UA = "accessible-surfaceome research bot (becca@deliverome.org)"
    wd = "/masif/data/masif_site"
    os.makedirs("/vol/sites_v2", exist_ok=True)

    def _write(r):
        with open(f"/vol/sites_v2/{cid}.json", "w") as f:
            json.dump(r, f)
        vol.commit()

    rec = {
        "candidate_id": cid,
        "acc": acc,
        "sym": info.get("sym"),
        "species": info.get("species"),
        "structure_source": info.get("source"),
        "topology_version": info.get("topology_version"),
        "topology_cohort": info.get("topology_cohort"),
        "sequence_sha256": info.get("sequence_sha256"),
    }
    t0 = time.time()
    os.makedirs("/tmp/p", exist_ok=True)
    pdb = f"/tmp/p/{acc}.pdb"
    # The library decides which structure is the protein actually being
    # ordered: an AlphaFold DB model when its proteoform matches the ORF, and
    # otherwise a ColabFold model built from the designed CDS, staged on the
    # volume. Never re-derive this from the accession -- that is what scored
    # the wrong proteoform for 270 members.
    if info.get("r2_key"):
        src = f"/vol/colabfold/{cid}.pdb"
        if not os.path.exists(src):
            rec["error"] = f"missing_colabfold: {src}"
            _write(rec)
            return rec
        import shutil

        shutil.copyfile(src, pdb)
    else:
        try:
            r = urllib.request.Request(info["model_url"], headers={"User-Agent": UA})
            open(pdb, "wb").write(urllib.request.urlopen(r, timeout=180).read())
        except Exception as e:
            rec["error"] = f"no_alphafold: {e}"
            _write(rec)
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
    rc3, l3 = sh(f"python /tmp/extract.py {name} {cid}", t=2400)
    rec["rc"] = [rc1, rc2, rc3]
    try:
        V = np.load("/tmp/v.npy")
        S_ = np.load("/tmp/s.npy")
        R = np.load("/tmp/r.npy")
    except Exception:
        rec["error"] = "extract_failed"
        rec["log"] = (l1 + l2 + l3)[-400:]
        _write(rec)
        return rec
    keep = S_ >= 0.7
    rec["n_verts"] = int(len(V))
    rec["frac_above_0.7"] = round(float(keep.mean()), 3)
    sites = []
    if keep.sum() >= 5:
        # SURFACE-Bind's own published parameters (their data.py:161).
        lab = DBSCAN(eps=2.5, min_samples=2).fit_predict(V[keep])
        Vk, Rk, Sk = V[keep], R[keep], S_[keep]
        import collections as C

        for k, npts in C.Counter(lab[lab >= 0]).items():
            if npts <= 200:  # theirs keeps `len(cluster) > 200`
                continue
            m = lab == k
            cen = Vk[m].mean(0)
            anchor = int(Rk[m][np.argmin(((Vk[m] - cen) ** 2).sum(1))])
            res = sorted(set(int(x) for x in Rk[m]))
            prt = info.get("prt")
            # MaSIF numbers residues against the MODEL. For a `contained`
            # member the ordered protein is a subsequence of that model, so the
            # topology string starts `offset` residues in: model residue x is
            # topology position x - offset. Reading them unshifted is wrong by
            # up to 134 residues and walks off the end of the string entirely
            # for the tail of a long site. Residues outside the ordered span
            # are not part of the construct and are dropped rather than guessed.
            off = int(info.get("residue_offset") or 0)
            ordered = int(info.get("ordered_length_aa") or 0) or (
                len(prt) if prt else 0
            )
            res = [x for x in res if 1 <= x - off <= ordered]
            if not res:
                continue
            tc = C.Counter(
                TOPO.get(prt[x - off - 1])
                for x in res
                if prt and 1 <= x - off <= len(prt)
            )
            sites.append(
                {
                    "n_pts": int(npts),
                    "anchor": anchor,
                    # positions in the ORDERED protein, so they line up with the
                    # topology string and with anything keyed on the construct
                    "anchor_ordered": anchor - off,
                    "residue_offset": off,
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
    _write(rec)
    return {k: v for k, v in rec.items() if k != "sites"}


@app.function(volumes={"/vol": vol}, timeout=24 * 3600)
def driver():
    import json
    import os

    meta = json.load(open("/vol/l1_inputs_v4.json"))
    done = (
        {f[:-5] for f in os.listdir("/vol/sites_v2")}
        if os.path.isdir("/vol/sites_v2")
        else set()
    )
    todo = [c for c in sorted(meta["members"]) if c not in done]
    print(f"L1 sweep v2: {len(done)} done, {len(todo)} to go", flush=True)
    ok = err = 0
    for r in run_one.map(todo, order_outputs=False, return_exceptions=True):
        if isinstance(r, Exception) or (isinstance(r, dict) and r.get("error")):
            err += 1
        else:
            ok += 1
        if (ok + err) % 25 == 0:
            print(f"  {ok + err}/{len(todo)}  ok={ok} err={err}", flush=True)
    print(f"DONE ok={ok} err={err}")
