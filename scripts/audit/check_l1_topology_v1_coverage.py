"""Can every L1 member get DeepTMHMM **v1** topology, matched by sequence hash?

The library's own `l1_topology_have.tsv` names `topo_2026_09_27_dtm2` and
`topo_2026_09_28_dtm2_ortho` for 2,539 of its 2,543 rows, and those are
DeepTMHMM **2** (`deeptmhmm2_predictor-0.1.0`). Every other topology row this
project serves is `deeptmhmm-1.0.24`, so following that file as written would
mix two predictors inside one dataset with nothing downstream flagging it.

This matches each member's construct sequence by SHA-256 against v1-only
releases, which also verifies the sequence rather than trusting a label.
Run it before building sweep inputs; 2,642/2,674 match.

    uv run python scripts/audit/check_l1_topology_v1_coverage.py
"""

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env
import argparse
import collections as C
import csv
import hashlib
import time

load_env()

_ap = argparse.ArgumentParser()
_ap.add_argument(
    "--s4e9-dir",
    required=True,
    help="path to analysis/sprint4/s4e9-orf-design-fg-panel",
)
W = _ap.parse_args().s4e9_dir
pay = [
    r
    for r in csv.DictReader(open(W + "/library_structure_payload.tsv"), delimiter="\t")
    if r["is_chosen"] == "1"
]
have = {
    r["candidate_id"]: r
    for r in csv.DictReader(open(W + "/l1_topology_have.tsv"), delimiter="\t")
}
gap = {
    r["candidate_id"]: r
    for r in csv.DictReader(open(W + "/l1_topology_gap.tsv"), delimiter="\t")
}
want = {}
for r in pay:
    cid = r["candidate_id"]
    src = have.get(cid) or gap.get(cid)
    if src and src.get("sha256"):
        want[cid] = {
            "sha": src["sha256"],
            "acc": r["uniprot_acc"],
            "species": r["species"],
            "named_cohort": (have.get(cid) or {}).get("cohort"),
            "named_version": (have.get(cid) or {}).get("topology_version"),
        }
print(f"chosen candidates with a sequence hash: {len(want)}/{len(pay)}")
V1 = (
    "topo_2026_05_16",
    "topo_2026_05_25",
    "topo_2026_09_rescue",
    "topo_2026_10_09_ortholog_repick",
    "topo_2026_10_11_ortholog_gap",
    "topo_2026_10_14_l1_designed",
)
accs = sorted({v["acc"] for v in want.values()})
by_sha = {}
with D1Client.public() as d1:
    for i in range(0, len(accs), 15):
        ch = accs[i : i + 15]
        q = (
            "SELECT uniprot_acc, uniprot_acc_full, cohort, topology_version, tool_version, sequence, "
            "per_residue_topology FROM topology_public WHERE topology_version IN ("
            + ",".join("?" * len(V1))
            + ") AND uniprot_acc IN ("
            + ",".join("?" * len(ch))
            + ");"
        )
        for r in d1.query(q, list(V1) + ch):
            if r.get("sequence"):
                by_sha.setdefault(
                    hashlib.sha256(r["sequence"].encode()).hexdigest(), []
                ).append(r)
        time.sleep(0.25)
    # the designed-ORF cohort is keyed differently; pull it whole
    for r in d1.query(
        "SELECT uniprot_acc, uniprot_acc_full, cohort, topology_version, tool_version, "
        "sequence, per_residue_topology FROM topology_public "
        "WHERE topology_version='topo_2026_10_14_l1_designed';",
        [],
    ):
        if r.get("sequence"):
            by_sha.setdefault(
                hashlib.sha256(r["sequence"].encode()).hexdigest(), []
            ).append(r)
print(f"v1 rows indexed by sequence hash: {len(by_sha)}")
hit = C.Counter()
miss = []
for cid, v in want.items():
    m = by_sha.get(v["sha"])
    if m:
        hit[m[0]["cohort"]] += 1
    else:
        miss.append((cid, v["acc"], v["species"], v["named_version"]))
print(f"\nMATCHED to a v1 row by exact sequence hash: {sum(hit.values())}/{len(want)}")
for k, n in hit.most_common():
    print(f"    {k:24s} {n}")
print(f"UNMATCHED: {len(miss)}")
print("  by species:", dict(C.Counter(m[2] for m in miss)))
print("  named version they'd have used:", dict(C.Counter(str(m[3]) for m in miss)))
