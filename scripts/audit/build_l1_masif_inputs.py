"""Sweep inputs for the L1 MaSIF run, from the single merged library manifest.

Supersedes both earlier builders. The first derived everything from a UniProt
accession, which cannot name a proteoform. The second joined
library_structure_payload.tsv to library_topology_index.tsv, which could
disagree about what a member was -- 39 members carried another organism's
topology, and MICA's structure and topology described different proteins.

`library_manifest_l1.tsv` is one row per member with the ordering identity,
the chosen structure and the matched topology under distinct `structure_*` and
`topology_*` names, so a conflict is unrepresentable rather than merely
detectable. The length is asserted against the translated designed CDS at
build time on the producing side, which catches a stale length without needing
two files to disagree.

Two columns do the work this script used to do by hand:

* `structure_offset` -- MaSIF numbers residues against the MODEL, while the
  topology string covers the ORDERED protein. For the 25 `contained` members
  they differ by this much (up to 134), and reading them unshifted silently
  relabels which side of the membrane a site sits on.
* `sequence_sha256` -- the version columns say which run produced a string;
  the hash says which protein it was about. The designed CDS lives on S3 with
  no version pinned to the committed tables, so an overwrite changes their
  meaning without touching any version field.

    uv run python scripts/audit/build_l1_masif_inputs.py \
        --manifest <.../library_manifest_l1.tsv> --out l1_inputs.json
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
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--allow-conflict",
        action="store_true",
        help="build even where a member's topology is from another species",
    )
    args = ap.parse_args()
    load_env()

    rows = list(csv.DictReader(open(args.manifest), delimiter="\t"))
    print(f"manifest rows: {len(rows)}")
    print("  species:", dict(C.Counter(r["species"] for r in rows)))
    print("  structure source:", dict(C.Counter(r["structure_source"] for r in rows)))
    print(
        "  proteoform:", dict(C.Counter(r["structure_proteoform_match"] for r in rows))
    )

    tools = {r["topology_tool"] for r in rows if r["topology_tool"]}
    if tools != {"deeptmhmm_v1"}:
        raise SystemExit(
            f"refusing to build: topology must be deeptmhmm_v1 only, got {tools}"
        )

    cross = [
        r["candidate_id"]
        for r in rows
        # Plain equality on purpose. The manifest used to spell cynomolgus two
        # ways, so this needed normalising and reported 92 false conflicts;
        # that is now folded at the source (323c0c2). Normalising here again
        # would re-hide exactly the defect this column exists to expose.
        if r["topology_species"] and r["species"] != r["topology_species"]
    ]
    if cross:
        print(f"  cross-species topology: {len(cross)} -> {cross[:5]}")
        if not args.allow_conflict:
            raise SystemExit(
                "refusing to build: a member's topology is from another species"
            )

    usable = [r for r in rows if r["structure_source"] and r["topology_acc"]]
    print(f"  usable (chosen structure + topology): {len(usable)}/{len(rows)}")

    want = {
        (r["topology_version"], r["topology_cohort"], r["topology_acc"]) for r in usable
    }
    by_vc: dict[tuple[str, str], list[str]] = C.defaultdict(list)
    for v, c, a in want:
        by_vc[(v, c)].append(a)
    prt: dict[tuple[str, str, str], str] = {}
    with D1Client.public() as d1:
        for (v, c), accs in by_vc.items():
            for i in range(0, len(accs), 25):
                chunk = accs[i : i + 25]
                q = (
                    "SELECT uniprot_acc_full, per_residue_topology FROM topology_public "
                    "WHERE topology_version=? AND cohort=? AND uniprot_acc_full IN ("
                    + ",".join("?" * len(chunk))
                    + ");"
                )
                for row in d1.query(q, [v, c] + chunk):
                    prt[(v, c, row["uniprot_acc_full"])] = row["per_residue_topology"]
                time.sleep(0.25)

    out, miss = {}, 0
    for r in usable:
        p = prt.get((r["topology_version"], r["topology_cohort"], r["topology_acc"]))
        if not p:
            miss += 1
            continue
        out[r["candidate_id"]] = {
            "acc": r["structure_acc"] or r["topology_acc"],
            "sym": r["gene_symbol"],
            "species": r["species"],
            "source": r["structure_source"],
            "model_url": r["structure_model_url"] or None,
            "r2_bucket": R2_BUCKET if r["structure_r2_key"] else None,
            "r2_key": r["structure_r2_key"] or None,
            "prt": p,
            "residue_offset": int(r["structure_offset"] or 0),
            "ordered_length_aa": int(r["ordered_length_aa"] or 0),
            "proteoform_match": r["structure_proteoform_match"],
            "topology_version": r["topology_version"],
            "topology_cohort": r["topology_cohort"],
            "topology_acc": r["topology_acc"],
            "sequence_sha256": r["sequence_sha256"] or None,
        }
    print(f"  built {len(out)} members ({miss} dropped: topology row not found)")
    json.dump({"members": out}, open(args.out, "w"))


if __name__ == "__main__":
    main()
