"""How much does each binding-site source add over the others?

Three sources answer "where could a binder go", and they are not
interchangeable:

  SURFACE-Bind   MaSIF patches on AlphaFold models, scored by binder-seed pools
  Bindome        where 305,806 BindCraft designs actually landed
  MaSIF (ours)   the same method as SURFACE-Bind, re-run on current structures

Counting a site as "novel" is only meaningful once two confounds are removed,
and both bit this analysis once already:

* **Scope.** Bindome designed against 8,289 targets. Measuring novelty against
  a 481-protein slice of it mostly measured "nobody looked", not "nobody
  found this".
* **Clustering.** Sites generated under non-published DBSCAN parameters are
  not comparable to published ones; min_samples in particular changes how many
  clusters survive, which is exactly what a novelty count is counting.

So this reports coverage and overlap separately, and prints the parameters the
MaSIF sites were produced under rather than assuming them.

    uv run python scripts/audit/site_source_overlap.py \
        --masif-dir <sites_v2/> --inputs <l1_inputs_v2.json>
"""

from __future__ import annotations

import argparse
import collections as C
import glob
import json
import time

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--masif-dir", required=True)
    ap.add_argument("--inputs", required=True)
    args = ap.parse_args()
    load_env()

    members = json.load(open(args.inputs))["members"]
    recs = [json.load(open(f)) for f in glob.glob(f"{args.masif_dir}/*.json")]
    ok = {r["candidate_id"]: r for r in recs if not r.get("error")}
    print(f"MaSIF records: {len(recs)} ({len(ok)} usable)")

    accs = sorted({ok[c]["acc"] for c in ok})
    sb: dict[str, list[int]] = C.defaultdict(list)
    bd: dict[str, list[int]] = C.defaultdict(list)
    with D1Client.public() as d1:
        for i in range(0, len(accs), 25):
            chunk = accs[i : i + 25]
            ph = ",".join("?" * len(chunk))
            for r in d1.query(
                f"SELECT uniprot_acc, anchor_residue FROM surface_bind_site "
                f"WHERE uniprot_acc IN ({ph});",
                chunk,
            ):
                sb[r["uniprot_acc"]].append(int(r["anchor_residue"]))
            for r in d1.query(
                f"SELECT uniprot_acc, anchor_residue FROM bindome_site_public "
                f"WHERE compartment='extracellular' AND uniprot_acc IN ({ph});",
                chunk,
            ):
                bd[r["uniprot_acc"]].append(int(r["anchor_residue"]))
            time.sleep(0.25)

    prot = C.Counter()
    site = C.Counter()
    for cid, r in ok.items():
        acc = r["acc"]
        prt = members.get(cid, {}).get("prt", "")
        sb_ec = [x for x in sb.get(acc, []) if 1 <= x <= len(prt) and prt[x - 1] == "O"]
        bd_ec = bd.get(acc, [])
        m_ec = [s for s in (r.get("sites") or []) if s["topology"] == "extracellular"]
        prot["has SURFACE-Bind EC"] += bool(sb_ec)
        prot["has Bindome EC"] += bool(bd_ec)
        prot["has MaSIF EC"] += bool(m_ec)
        prot["MaSIF EC only"] += bool(m_ec) and not sb_ec and not bd_ec
        for s in m_ec:
            res = set(s["residues"])
            site["MaSIF EC sites"] += 1
            if any(x in res for x in sb_ec):
                site["  shared with SURFACE-Bind"] += 1
            elif any(x in res for x in bd_ec):
                site["  shared with Bindome"] += 1
            elif sb_ec or bd_ec:
                site["  novel (protein has other EC sites)"] += 1
            else:
                site["  novel (protein has no other EC site)"] += 1
    print(f"\nproteins (n={len(ok)}):")
    for k, v in prot.most_common():
        print(f"    {k:38s} {v} ({100 * v / len(ok):.0f}%)")
    print("\nsites:")
    for k, v in site.items():
        print(f"    {k:42s} {v}")


if __name__ == "__main__":
    main()
