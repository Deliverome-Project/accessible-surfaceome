"""Sweep inputs for the L1 MaSIF run, read from the library's own manifests.

Supersedes build_l1_masif_inputs.py, which derived everything from a UniProt
accession and was wrong three ways: it pulled canonical-only topology (so an
isoform construct was filtered against the wrong sequence), it always fetched
the AlphaFold DB model (so members whose AFDB entry is a different proteoform
were scored as the wrong protein), and it filtered to human canonical
accessions (so every mouse and cyno member was silently dropped).

The library already answers all three, keyed on candidate_id rather than
accession -- which is the right key, since the ColabFold corrections are
deliberately filed under the candidate so a correction cannot land in the same
slot as the thing it corrects:

  library_structure_payload.tsv  one `is_chosen=1` row per member, giving
                                 either an AlphaFold `model_url` or an R2
                                 `r2_key`, proteoform-matched to the ORF.
  library_topology_index.tsv     the matching topology row, every one
                                 `topology_tool = deeptmhmm_v1`.

    uv run python scripts/audit/build_l1_masif_inputs_v2.py \
        --s4e9-dir <.../s4e9-orf-design-fg-panel> --out l1_inputs_v2.json
"""

from __future__ import annotations

import argparse
import collections as C
import csv
import json
import time

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env

R2_BUCKET = "surfaceome-structures"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--s4e9-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--library", default="l1")
    args = ap.parse_args()
    load_env()

    pay = [
        r
        for r in csv.DictReader(
            open(f"{args.s4e9_dir}/library_structure_payload.tsv"), delimiter="\t"
        )
        if r["is_chosen"] == "1"
    ]
    idx = {
        r["candidate_id"]: r
        for r in csv.DictReader(
            open(f"{args.s4e9_dir}/library_topology_index.tsv"), delimiter="\t"
        )
        if r["library"] == args.library
    }
    members = [r for r in pay if r["candidate_id"] in idx]
    print(f"{args.library} members with a chosen structure: {len(members)}")
    print("  structure source:", dict(C.Counter(r["source"] for r in members)))
    print("  proteoform:", dict(C.Counter(r["proteoform_match"] for r in members)))
    tools = C.Counter(idx[r["candidate_id"]]["topology_tool"] for r in members)
    print("  topology tool:", dict(tools))
    if set(tools) != {"deeptmhmm_v1"}:
        raise SystemExit(
            f"refusing to build: topology must be deeptmhmm_v1 only, got {dict(tools)}"
        )

    # Pull the per-residue strings for exactly the (version, cohort, acc) rows
    # the index names -- not "whatever is newest for this accession".
    want: dict[tuple[str, str, str], None] = {}
    for r in members:
        t = idx[r["candidate_id"]]
        want[(t["topology_version"], t["topology_cohort"], t["topology_acc"])] = None
    print(f"  distinct topology rows to pull: {len(want)}")
    prt: dict[tuple[str, str, str], str] = {}
    by_vc: dict[tuple[str, str], list[str]] = C.defaultdict(list)
    for v, c, a in want:
        by_vc[(v, c)].append(a)
    with D1Client.public() as d1:
        for (v, c), accs in by_vc.items():
            for i in range(0, len(accs), 25):
                chunk = accs[i : i + 25]
                # Match on uniprot_acc_full, not uniprot_acc. The index names
                # isoform-suffixed accessions (P21439-2) for the human_isoforms
                # cohort and candidate ids (l1-p0031) for library_designed_orf,
                # where `uniprot_acc` is a bare "l1". Keying on the base column
                # silently drops both -- 362 of 2,699 members on the first run.
                q = (
                    "SELECT uniprot_acc_full, per_residue_topology "
                    "FROM topology_public WHERE topology_version=? AND cohort=? "
                    "AND uniprot_acc_full IN (" + ",".join("?" * len(chunk)) + ");"
                )
                for row in d1.query(q, [v, c] + chunk):
                    prt[(v, c, row["uniprot_acc_full"])] = row["per_residue_topology"]
                time.sleep(0.25)

    out = {}
    miss = 0
    for r in members:
        t = idx[r["candidate_id"]]
        key = (t["topology_version"], t["topology_cohort"], t["topology_acc"])
        p = prt.get(key)
        if not p:
            miss += 1
            continue
        out[r["candidate_id"]] = {
            "acc": r["uniprot_acc"],
            "sym": r["gene_symbol"],
            "species": r["species"],
            "source": r["source"],
            "model_url": r["model_url"] or None,
            "r2_bucket": R2_BUCKET if r["r2_key"] else None,
            "r2_key": r["r2_key"] or None,
            "prt": p,
            "topology_version": t["topology_version"],
            "topology_cohort": t["topology_cohort"],
            "topology_acc": t["topology_acc"],
        }
    print(f"  built {len(out)} members ({miss} dropped: topology row not found)")
    json.dump({"members": out}, open(args.out, "w"))


if __name__ == "__main__":
    main()
