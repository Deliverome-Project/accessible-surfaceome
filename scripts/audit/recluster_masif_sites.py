"""Re-cluster cached MaSIF surfaces under any parameters, with no inference.

The sweep persists per-vertex coordinates, scores and residue assignments to
the `masif-l1` volume (`verts/<name>.{v,s,r}.npy`, ~56 KB per protein). That
makes the clustering stage replayable: changing the DBSCAN radius, the
minimum cluster size or the MaSIF score threshold is a local loop over cached
arrays rather than a re-run of surface generation and the network.

Why it matters: the sweep originally ran DBSCAN(eps=3.0, min_samples=5),
which are not SURFACE-Bind's published values (eps=2.5, min_samples=2,
clusters strictly >200 -- their data.py:161 / analyze_dataset.py). Answering
"does that change the site count" should never have required re-running MaSIF.

    uv run --with scikit-learn python scripts/audit/recluster_masif_sites.py \
        --verts-dir <cached verts/> --eps 2.5 --min-samples 2 --min-points 200
"""

from __future__ import annotations

import argparse
import collections as C
import glob
import time

import numpy as np
from sklearn.cluster import DBSCAN


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verts-dir", required=True)
    ap.add_argument("--threshold", type=float, default=0.7)
    ap.add_argument("--eps", type=float, default=2.5)
    ap.add_argument("--min-samples", type=int, default=2)
    ap.add_argument("--min-points", type=int, default=200)
    ap.add_argument(
        "--strict",
        action="store_true",
        help="keep clusters with len > min_points (SURFACE-Bind's rule) rather than >=",
    )
    args = ap.parse_args()

    files = sorted(glob.glob(f"{args.verts_dir}/*.v.npy"))
    t0 = time.time()
    total = C.Counter()
    for vf in files:
        V = np.load(vf)
        S = np.load(vf.replace(".v.npy", ".s.npy"))
        keep = S >= args.threshold
        if keep.sum() < args.min_samples:
            total["no vertex above threshold"] += 1
            continue
        lab = DBSCAN(eps=args.eps, min_samples=args.min_samples).fit_predict(V[keep])
        sizes = C.Counter(lab[lab >= 0])
        n = sum(
            1
            for v in sizes.values()
            if (v > args.min_points if args.strict else v >= args.min_points)
        )
        total["sites"] += n
        total["proteins"] += 1
        if n:
            total["proteins with >=1 site"] += 1
    dt = time.time() - t0
    print(
        f"eps={args.eps} min_samples={args.min_samples} "
        f"min_points={args.min_points}{' (strict >)' if args.strict else ' (>=)'} "
        f"threshold={args.threshold}"
    )
    for k, v in total.most_common():
        print(f"    {k:28s} {v}")
    print(f"    {'elapsed':28s} {dt:.2f}s for {len(files)} proteins (no inference)")


if __name__ == "__main__":
    main()
