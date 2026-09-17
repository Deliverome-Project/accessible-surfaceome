"""Measure representative antibody interfaces; retain failures as unknown coverage.

SAbDab defines antibody/antigen chain pairs, SIFTS maps target residues to
UniProt, and deposited experimental coordinates supply <=5 A heavy-atom contacts.
One representative per target is attempted, so this is a coverage lower bound,
not a complete antibody catalogue or a count of independent validations.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import numpy as np
from Bio.PDB.MMCIF2Dict import MMCIF2Dict
from Bio.PDB.kdtrees import KDTree  # ty: ignore[unresolved-import]  # Compiled extension.

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data/external/binding_site_audit"


def download(path: Path, url: str) -> bytes:
    if path.exists():
        return path.read_bytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            response = httpx.get(url, timeout=120, follow_redirects=True)
            response.raise_for_status()
            path.write_bytes(response.content)
            return response.content
        except httpx.HTTPError:
            if attempt == 2:
                raise
            time.sleep(2**attempt)
    raise RuntimeError(url)


def select_complexes() -> list[dict]:
    cohort = {
        r["uniprot_acc"]
        for r in csv.DictReader(
            (ROOT / "data/analysis/binder_coverage/gene_coverage.tsv").open(),
            delimiter="\t",
        )
    }
    mapping = defaultdict(set)
    with gzip.open(CACHE / "sifts.csv.gz", "rt") as handle:
        next(handle)
        for row in csv.DictReader(handle):
            if row["SP_PRIMARY"] in cohort:
                mapping[row["PDB"], row["CHAIN"]].add(row["SP_PRIMARY"])
    matches = []
    for row in csv.DictReader((CACHE / "sabdab_summary.txt").open()):
        pdb = row["PDB"].removeprefix("pdb_0000")
        if row["method"] not in {"XRAY", "ELECTRON_MICROSCOPY", "NMR"}:
            continue
        for chain in row["antigen_chain"].split("|"):
            for acc in mapping[pdb, chain]:
                matches.append(
                    dict(row, uniprot_acc=acc, pdb_id=pdb, target_chain=chain)
                )
    return matches


def residue_mapping(xml: bytes, accession: str) -> dict[tuple[str, str], int]:
    root = ET.fromstring(xml)
    mapping = {}
    for residue in root.findall(".//{*}residue"):
        refs = residue.findall("{*}crossRefDb")
        pdb = [r for r in refs if r.get("dbSource") == "PDB"]
        uni = [
            r
            for r in refs
            if r.get("dbSource") == "UniProt" and r.get("dbAccessionId") == accession
        ]
        if len(pdb) == len(uni) == 1:
            mapping[pdb[0].get("dbChainId", ""), pdb[0].get("dbResNum", "")] = int(
                uni[0].attrib["dbResNum"]
            )
    return mapping


def contacts(
    cif: dict, target_chain: str, antibody_chains: set[str], mapping: dict
) -> list[int]:
    targets, partners, positions = [], [], []
    model = cif["_atom_site.pdbx_PDB_model_num"][0]
    for i, chain in enumerate(cif["_atom_site.auth_asym_id"]):
        if cif["_atom_site.pdbx_PDB_model_num"][i] != model:
            continue
        if cif["_atom_site.type_symbol"][i] in {"H", "D"}:
            continue
        if cif["_atom_site.group_PDB"][i] != "ATOM":
            continue
        if float(cif["_atom_site.occupancy"][i]) <= 0:
            continue
        if chain != target_chain and chain not in antibody_chains:
            continue
        xyz = [float(cif[f"_atom_site.Cartn_{axis}"][i]) for axis in "xyz"]
        if chain in antibody_chains:
            partners.append(xyz)
        elif chain == target_chain:
            insertion = cif["_atom_site.pdbx_PDB_ins_code"][i]
            number = cif["_atom_site.auth_seq_id"][i] + (
                insertion if insertion not in {"?", "."} else ""
            )
            position = mapping.get((chain, number))
            if position:
                targets.append(xyz)
                positions.append(position)
    if not targets or not partners:
        return []
    tree = KDTree(np.array(partners, dtype=float))
    return sorted(
        {
            p
            for p, point in zip(positions, targets, strict=True)
            if tree.search(np.array(point, dtype=float), 5.0)
        }
    )


def audit(row: dict) -> dict:
    acc, pdb = row["uniprot_acc"], row["pdb_id"]
    result_path = CACHE / "antibody_contacts" / f"{acc}.json"
    if result_path.exists():
        cached = json.loads(result_path.read_text())
        if cached["pdb_id"] == pdb or cached["status"] == "mapped_contacts":
            return cached
    result = {
        k: row[k]
        for k in [
            "uniprot_acc",
            "pdb_id",
            "target_chain",
            "SABDAB_ID",
            "INSTANCE",
            "Hchain",
            "Lchain",
            "method",
            "resolution",
            "compound",
            "type",
        ]
    }
    result["sequence_sha256"] = hashlib.sha256(
        (row["VH"] + "|" + row["VL"]).encode()
    ).hexdigest()
    try:
        data = download(
            CACHE / "coordinates" / f"{pdb}.cif",
            f"https://www.ebi.ac.uk/pdbe/entry-files/download/{pdb}.cif",
        )
        xml = download(
            CACHE / "sifts_xml" / f"{pdb}.xml.gz",
            f"https://ftp.ebi.ac.uk/pub/databases/msd/sifts/xml/{pdb}.xml.gz",
        )
        cif = MMCIF2Dict(io.StringIO(data.decode()))
        mapping = residue_mapping(gzip.decompress(xml), acc)
        chains = {row["Hchain"], row["Lchain"]} - {"NA", row["target_chain"]}
        result["positions"] = contacts(cif, row["target_chain"], chains, mapping)
        result["status"] = (
            "mapped_contacts" if result["positions"] else "no_mapped_contacts"
        )
    except Exception as exc:
        result.update(status="error", error=str(exc))
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result))
    attempts = CACHE / "antibody_attempts"
    attempts.mkdir(exist_ok=True)
    (attempts / f"{acc}_{pdb}.json").write_text(json.dumps(result))
    return result


def main() -> None:
    matches = select_complexes()
    (CACHE / "sabdab_matched.json").write_text(json.dumps(matches))
    selected = defaultdict(list)

    def rank(row: dict) -> tuple:
        try:
            resolution = float(row["resolution"])
        except ValueError:
            resolution = 100.0
        return (
            row["method"] != "XRAY",
            resolution,
            row["INSTANCE"],
            row["target_chain"],
        )

    for row in sorted(matches, key=rank):
        choices = selected[row["uniprot_acc"]]
        if row["pdb_id"] not in {r["pdb_id"] for r in choices} and len(choices) < 3:
            choices.append(row)
    print(
        f"SAbDab: {len(matches)} mapped chain pairs; {len(selected)} targets",
        flush=True,
    )

    def attempt(choices: list[dict]) -> dict:
        for row in choices:
            result = audit(row)
            if result["status"] == "mapped_contacts":
                return result
        return result

    with ThreadPoolExecutor(max_workers=3) as pool:
        for i, result in enumerate(pool.map(attempt, selected.values()), 1):
            if i % 20 == 0:
                print(f"Contacts {i}/{len(selected)} {result['status']}", flush=True)
    # The pilot's two literature-curated examples have deposited complexes.
    # Resolve binder chains from the deposited entity name, then recompute the
    # observed contacts instead of reusing the paper's design-hotspot residues.
    examples = csv.DictReader(
        (ROOT / "data/analysis/binder_coverage/literature_examples.tsv").open(),
        delimiter="\t",
    )
    for example in examples:
        pdb, acc = example["pdb_id"].lower(), example["uniprot_acc"]
        data = download(
            CACHE / "coordinates" / f"{pdb}.cif",
            f"https://www.ebi.ac.uk/pdbe/entry-files/download/{pdb}.cif",
        )
        xml = download(
            CACHE / "sifts_xml" / f"{pdb}.xml.gz",
            f"https://ftp.ebi.ac.uk/pub/databases/msd/sifts/xml/{pdb}.xml.gz",
        )
        cif = MMCIF2Dict(io.StringIO(data.decode()))
        names = dict(
            zip(cif["_entity.id"], cif["_entity.pdbx_description"], strict=True)
        )
        chains = {
            chain
            for entity, strands in zip(
                cif["_entity_poly.entity_id"],
                cif["_entity_poly.pdbx_strand_id"],
                strict=True,
            )
            if names[entity].lower() == example["binder_name"].lower()
            for chain in strands.split(",")
        }
        if not chains:
            raise ValueError(f"No exact deposited binder name: {pdb}")
        mapping = residue_mapping(gzip.decompress(xml), acc)
        positions = sorted(
            set().union(
                *(
                    set(contacts(cif, chain, chains, mapping))
                    for chain in {c for c, _ in mapping}
                )
            )
        )
        result = dict(
            example,
            positions=positions,
            status="mapped_contacts" if positions else "no_mapped_contacts",
        )
        folder = CACHE / "minibinder_contacts"
        folder.mkdir(exist_ok=True)
        (folder / f"{pdb}.json").write_text(json.dumps(result))


if __name__ == "__main__":
    main()
