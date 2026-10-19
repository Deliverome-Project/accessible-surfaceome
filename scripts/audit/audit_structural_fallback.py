"""Bounded coordinate fallback for extracellular proteins missed by PDBe aggregation.

Attempts up to three UniProt-linked experimental structures per target, ranked by
mapped target span. Results are structural candidates, not validated natural pairs.
"""

import argparse
import csv
import gc
import gzip
import io
import json
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from Bio.PDB.MMCIF2Dict import MMCIF2Dict
from Bio.PDB.kdtrees import KDTree  # ty: ignore[unresolved-import]  # Compiled extension.
from Bio.SeqUtils import seq1

from accessible_surfaceome.binders.site_context import EXOPLASMIC_CONTEXTS, site_context
from audit_antibody_contacts import download
from audit_structural_intact_extension import OUT, RAW, proteins
from summarize_binding_sites import pdb_sites


def plan():
    ps = proteins()
    jobs = []
    for g in csv.DictReader(
        (OUT / "all_source_comparison_genes.tsv").open(), delimiter="\t"
    ):
        acc = g["uniprot_acc"]
        p = ps.get(acc)
        if not p or g["identifier_status"] != "unique":
            continue
        path = RAW / "interfaces" / f"{acc}.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text())
        covered = False
        if (
            payload.get("status") != 404
            or g["all_experimental_ec_union_after_antibody_extension"] == "1"
        ):
            continue
        for partner in payload.get("data", {}).get(acc, {}).get("data", []):
            if partner.get("accession") == acc:
                continue
            if not re.fullmatch(
                r"[A-Z0-9]{6,10}(?:-\d+)?", partner.get("accession", "")
            ):
                continue
            if any(
                site_context(pos, p) in EXOPLASMIC_CONTEXTS
                for pos in pdb_sites(partner).values()
            ):
                covered = True
        if covered:
            continue
        candidates = []
        for x in p.get("uniProtKBCrossReferences", []):
            if x["database"] != "PDB":
                continue
            props = {v["key"]: v["value"] for v in x.get("properties", [])}
            spans = [
                (int(a), int(b))
                for a, b in re.findall(r"=(\d+)-(\d+)", props.get("Chains", ""))
            ]
            # Require at least one mature extracellular/secreted point in the linked span.
            eligible = 0
            for a, b in spans:
                for pos in range(a, min(b, len(p["sequence"]["value"])) + 1):
                    if site_context([pos], p) in EXOPLASMIC_CONTEXTS:
                        eligible += 1
            if eligible:
                candidates.append((eligible, x["id"].lower()))
        for _, pdb in sorted(candidates, key=lambda x: (-x[0], x[1]))[:3]:
            jobs.append(
                {
                    "uniprot_acc": acc,
                    "pdb_id": pdb,
                    "hgnc_id": g["hgnc_id"],
                    "hgnc_symbol": g["hgnc_symbol"],
                }
            )
    return jobs


def coordinate_contacts(cif, target, partner, mappings, canonical, atom_indices=None):
    points = []
    model = cif["_atom_site.pdbx_PDB_model_num"][0]
    targets = []
    indices = (
        range(len(cif["_atom_site.auth_asym_id"]))
        if atom_indices is None
        else atom_indices
    )
    for i in indices:
        chain = cif["_atom_site.auth_asym_id"][i]
        if (
            chain not in {target, partner}
            or cif["_atom_site.pdbx_PDB_model_num"][i] != model
        ):
            continue
        if (
            cif["_atom_site.group_PDB"][i] != "ATOM"
            or cif["_atom_site.type_symbol"][i] in {"H", "D"}
            or float(cif["_atom_site.occupancy"][i]) <= 0
        ):
            continue
        ins = cif["_atom_site.pdbx_PDB_ins_code"][i]
        native = cif["_atom_site.auth_seq_id"][i] + (
            ins if ins not in {".", "?"} else ""
        )
        xyz = [float(cif["_atom_site.Cartn_" + axis][i]) for axis in "xyz"]
        m = mappings.get((chain, native))
        if chain == partner:
            if m:
                points.append(xyz)
        else:
            targets.append((xyz, m, seq1(cif["_atom_site.auth_comp_id"][i])))
    if not points or not targets:
        return [], "no_contacts"
    tree = KDTree(np.array(points, dtype=float))
    positions = set()
    for xyz, m, aa in targets:
        if not tree.search(np.array(xyz, dtype=float), 5.0):
            continue
        if not m:
            return [], "unmapped_contact_residue"
        pos = m[1]
        if pos < 1 or pos > len(canonical) or canonical[pos - 1] != aa:
            return [], "noncanonical_contact_residue"
        positions.add(pos)
    return sorted(positions), "mapped" if positions else "no_contacts"


def run_pdb(job):
    pdb, targets = job
    try:
        cif_data = download(
            RAW / "coordinates" / f"{pdb}.cif",
            f"https://www.ebi.ac.uk/pdbe/entry-files/download/{pdb}.cif",
        )
        download(
            RAW / "sifts" / f"{pdb}.xml.gz",
            f"https://ftp.ebi.ac.uk/pub/databases/msd/sifts/xml/{pdb}.xml.gz",
        )
        cif = MMCIF2Dict(io.StringIO(cif_data.decode()))
        mappings = {}
        chains = {}
        # Streaming avoids materializing multi-gigabyte viral SIFTS trees.
        residue_stream = ET.iterparse(
            gzip.open(RAW / "sifts" / f"{pdb}.xml.gz", "rb"), events=("end",)
        )
        for _, residue in residue_stream:
            tag = residue.tag.rsplit("}", 1)[-1]
            if tag != "residue":
                if tag in {"listResidue", "segment", "entity"}:
                    residue.clear()
                continue
            refs = residue.findall("{*}crossRefDb")
            p = [x for x in refs if x.get("dbSource") == "PDB"]
            u = [x for x in refs if x.get("dbSource") == "UniProt"]
            if len(p) != 1 or len(u) != 1:
                residue.clear()
                continue
            chain = p[0].get("dbChainId")
            acc = u[0].get("dbAccessionId")
            num = int(u[0].attrib["dbResNum"])
            mappings[chain, p[0].get("dbResNum")] = (acc, num)
            chains.setdefault(chain, set()).add(acc)
            residue.clear()
        chain_atoms = {}
        for i, chain in enumerate(cif["_atom_site.auth_asym_id"]):
            chain_atoms.setdefault(chain, []).append(i)
        rows = []
        for target in targets:
            acc = target["uniprot_acc"]
            found = False
            for chain, ids in chains.items():
                if ids != {acc}:
                    continue
                for partner, pids in chains.items():
                    if partner == chain or len(pids) != 1 or acc in pids:
                        continue
                    found = True
                    pos, status = coordinate_contacts(
                        cif,
                        chain,
                        partner,
                        mappings,
                        PROTEINS[acc]["sequence"]["value"],
                        chain_atoms.get(chain, []) + chain_atoms.get(partner, []),
                    )
                    rows.append(
                        dict(
                            target,
                            target_chain=chain,
                            partner_chain=partner,
                            partner_accession=next(iter(pids)),
                            positions=pos,
                            status=status,
                        )
                    )
            if not found:
                rows.append(
                    dict(
                        target,
                        status="no_distinct_uniquely_mapped_partner",
                        positions=[],
                    )
                )
        return rows
    except Exception as error:
        return [
            dict(t, status="error", error=str(error), positions=[]) for t in targets
        ]


PROTEINS = {}


def main():
    global PROTEINS
    # These parsing trees are acyclic; avoid repeated whole-heap GC scans.
    gc.disable()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", action="store_true")
    args = p.parse_args()
    PROTEINS = proteins()
    jobs = plan()
    (RAW / "fallback_plan.json").write_text(json.dumps(jobs, indent=2))
    print(
        "Target genes",
        len({j["uniprot_acc"] for j in jobs}),
        "target-structures",
        len(jobs),
        "PDBs",
        len({j["pdb_id"] for j in jobs}),
        flush=True,
    )
    if not args.run:
        return
    grouped = {}
    for row in jobs:
        grouped.setdefault(row["pdb_id"], []).append(row)
    results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        for i, rows in enumerate(executor.map(run_pdb, grouped.items()), 1):
            results.extend(rows)
            if i % 10 == 0:
                print("Fallback", i, "/", len(grouped), flush=True)
    (RAW / "fallback_contacts.json").write_text(json.dumps(results, indent=2))
    from collections import Counter

    print(Counter(r["status"] for r in results), flush=True)


if __name__ == "__main__":
    main()
