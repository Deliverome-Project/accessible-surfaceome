"""Pure, conservative validation of deposited chemical contact coordinates.

Author chain/residue identifiers join coordinates to SIFTS. Canonical positions
are emitted only for exact accession and amino-acid identity matches. No network,
biological-assembly expansion, alternate-location selection, or identity curation
is performed here: all positive-occupancy heavy atoms in the first model count.
"""

import gzip
import hashlib
import io
import math
import xml.etree.ElementTree as ET
from collections import defaultdict

import numpy as np
from Bio.PDB.kdtrees import KDTree  # ty: ignore[unresolved-import]  # Compiled Biopython extension.
from Bio.PDB.MMCIF2Dict import MMCIF2Dict
from Bio.SeqUtils import seq1

METHOD = (
    "First model, positive occupancy, target-heavy-atom to ligand-heavy-atom "
    "distance <=5 A; SIFTS exact accession and canonical residue identity required."
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_hash(data: bytes, expected: str | None, label: str) -> str:
    """Hash original file bytes (including SIFTS gzip container), never decoded XML."""
    actual = sha256(data)
    if expected is not None and actual != expected:
        raise ValueError(f"{label} SHA256 mismatch: expected {expected}, got {actual}")
    return actual


def _sifts_mapping(data, accession):
    root = ET.fromstring(
        gzip.decompress(data) if data.startswith(b"\x1f\x8b") else data
    )
    candidates = defaultdict(set)
    chain_accessions = defaultdict(set)
    for residue in root.findall(".//{*}residue"):
        refs = residue.findall("{*}crossRefDb")
        pdb_refs = [r for r in refs if r.get("dbSource") == "PDB"]
        uniprot_refs = [r for r in refs if r.get("dbSource") == "UniProt"]
        for p in pdb_refs:
            chain, number = p.get("dbChainId"), p.get("dbResNum")
            if not chain:
                continue
            for u in uniprot_refs:
                acc = u.get("dbAccessionId")
                if not acc:
                    continue
                chain_accessions[chain].add(acc)
                if not number or number in {"null", ".", "?"}:
                    continue
                try:
                    position = int(u.get("dbResNum", ""))
                except ValueError:
                    position = 0
                # Multiple PDB references are ambiguous even if one happens to fit.
                candidates[chain, number].add((acc, position, len(pdb_refs)))
    target_chains = {
        c for c, accessions in chain_accessions.items() if accession in accessions
    }
    issues = []
    for chain in sorted(target_chains):
        if chain_accessions[chain] != {accession}:
            issues.append(
                {
                    "chain_id": chain,
                    "issue": "mixed_chain_accessions",
                    "accessions": sorted(chain_accessions[chain]),
                }
            )
    if not target_chains:
        issues.append({"issue": "target_accession_absent", "uniprot_acc": accession})
    mappings = {}
    for (chain, number), values in candidates.items():
        if chain not in target_chains:
            continue
        if len(values) != 1 or next(iter(values))[2] != 1:
            issues.append(
                {
                    "chain_id": chain,
                    "author_residue": number,
                    "issue": "ambiguous_sifts_mapping",
                }
            )
            continue
        acc, position, _ = next(iter(values))
        if acc == accession and chain_accessions[chain] == {accession}:
            mappings[chain, number] = position
    return (
        mappings,
        target_chains,
        {c: sorted(a) for c, a in sorted(chain_accessions.items())},
        issues,
    )


def validate_contacts(
    coordinate_bytes: bytes,
    sifts_bytes: bytes,
    *,
    uniprot_acc: str,
    canonical_sequence: str,
    ccd: str,
    cutoff: float = 5.0,
    expected_coordinate_sha256: str | None = None,
    expected_sifts_sha256: str | None = None,
    expected_canonical_sequence_sha256: str | None = None,
) -> dict:
    """Return contacts and explicit mapping failures for every deposited CCD instance.

    Failed mappings never contribute canonical positions. Callers accepting an
    instance must reject both top-level and per-instance mapping issues. Sequence
    hash covers the supplied uppercase, whitespace-free amino-acid string.
    """
    if (
        not uniprot_acc
        or not ccd
        or not canonical_sequence
        or not canonical_sequence.isalpha()
        or canonical_sequence != canonical_sequence.upper()
    ):
        raise ValueError(
            "Require a stable accession, CCD and uppercase canonical sequence without whitespace"
        )
    if not math.isfinite(cutoff) or cutoff <= 0:
        raise ValueError("Contact cutoff must be positive and finite")
    hashes = {
        "coordinate_sha256": verify_hash(
            coordinate_bytes, expected_coordinate_sha256, "coordinate"
        ),
        "sifts_sha256": verify_hash(sifts_bytes, expected_sifts_sha256, "SIFTS"),
        "canonical_sequence_sha256": verify_hash(
            canonical_sequence.encode("ascii"),
            expected_canonical_sequence_sha256,
            "canonical sequence",
        ),
    }
    maps, target_chains, chain_accessions, issues = _sifts_mapping(
        sifts_bytes, uniprot_acc
    )
    cif = MMCIF2Dict(io.StringIO(coordinate_bytes.decode("utf-8")))
    keys = [
        "auth_asym_id",
        "auth_seq_id",
        "auth_comp_id",
        "pdbx_PDB_ins_code",
        "pdbx_PDB_model_num",
        "type_symbol",
        "occupancy",
        "group_PDB",
        "Cartn_x",
        "Cartn_y",
        "Cartn_z",
    ]
    columns = {key: cif["_atom_site." + key] for key in keys}
    if not columns["auth_asym_id"] or len({len(v) for v in columns.values()}) != 1:
        raise ValueError("Empty or inconsistent atom_site columns")
    model = columns["pdbx_PDB_model_num"][0]
    columns["label_seq_id"] = cif.get(
        "_atom_site.label_seq_id", ["."] * len(columns["auth_asym_id"])
    )
    keys.append("label_seq_id")
    ligands, targets = defaultdict(list), []
    for values in zip(*(columns[k] for k in keys), strict=True):
        atom = dict(zip(keys, values, strict=True))
        if atom["pdbx_PDB_model_num"] != model or atom["type_symbol"].upper() in {
            "H",
            "D",
        }:
            continue
        occupancy = float(atom["occupancy"])
        if not math.isfinite(occupancy):
            raise ValueError("Non-finite atom occupancy")
        if occupancy <= 0:
            continue
        point = [float(atom["Cartn_" + a]) for a in "xyz"]
        if not all(math.isfinite(v) for v in point):
            raise ValueError("Non-finite atom coordinate")
        chain, number, comp = (
            atom["auth_asym_id"],
            atom["auth_seq_id"],
            atom["auth_comp_id"],
        )
        insertion = atom["pdbx_PDB_ins_code"]
        if insertion not in {".", "?"}:
            number += insertion
        if comp == ccd:
            ligands[chain, number].append(point)
        elif chain in target_chains and (
            atom["group_PDB"] == "ATOM" or atom["label_seq_id"] not in {".", "?"}
        ):
            targets.append((chain, number, comp, point))
    instances = []
    for (ligand_chain, ligand_number), points in sorted(ligands.items()):
        tree = KDTree(np.asarray(points, dtype=float))
        residues, bad = {}, {}
        for chain, number, comp, point in targets:
            if not tree.search(np.asarray(point, dtype=float), cutoff):
                continue
            position = maps.get((chain, number))
            issue = None
            if position is None:
                issue = "unmapped_contact_residue"
            elif not 1 <= position <= len(canonical_sequence):
                issue = "canonical_position_out_of_range"
            elif seq1(comp) == "X" or seq1(comp) != canonical_sequence[position - 1]:
                issue = "canonical_residue_mismatch"
            if issue:
                bad[chain, number, comp] = {
                    "chain_id": chain,
                    "author_residue": number,
                    "residue_name": comp,
                    "canonical_position": position,
                    "issue": issue,
                }
                continue
            residues[chain, number, comp] = position
        provenance = []
        for chain in sorted({c for c, _, _ in residues}):
            local = [
                {"author_residue": n, "residue_name": comp, "canonical_position": pos}
                for (c, n, comp), pos in sorted(residues.items())
                if c == chain
            ]
            provenance.append(
                {
                    "chain_id": chain,
                    "positions": sorted({v["canonical_position"] for v in local}),
                    "contact_residues": local,
                }
            )
        instances.append(
            {
                "ligand_instance": [ligand_chain, ligand_number],
                "positions": sorted(set(residues.values())),
                "target_chains": provenance,
                "mapping_issues": [bad[k] for k in sorted(bad)],
            }
        )
    return {
        "uniprot_acc": uniprot_acc,
        "ccd": ccd,
        **hashes,
        "first_model": model,
        "cutoff_angstrom": cutoff,
        "method": METHOD if cutoff == 5 else METHOD.replace("<=5 A", f"<={cutoff:g} A"),
        "chain_accessions": chain_accessions,
        "mapping_issues": issues,
        "instances": instances,
    }


def validate_reviewed_instance(record: dict, result: dict) -> list[str]:
    """Return acceptance failures without mutating the reviewed record or positions."""
    failures = []
    for field in ("coordinate_sha256", "sifts_sha256"):
        if not record.get(field):
            failures.append(field + "_missing")
    if record.get("mapping_issues"):
        failures.append("reviewed_record_has_mapping_issues")
    if (
        record["uniprot_acc"] != result["uniprot_acc"]
        or record["partner"] != "CCD:" + result["ccd"]
    ):
        failures.append("target_or_ccd_mismatch")
    for field in ("coordinate_sha256", "sifts_sha256", "canonical_sequence_sha256"):
        if field in record and record[field] != result[field]:
            failures.append(field + "_mismatch")
    if result["cutoff_angstrom"] != 5.0:
        failures.append("review_requires_5_angstrom_cutoff")
    if result["mapping_issues"]:
        failures.append("target_mapping_issues")
    matching = [
        i
        for i in result["instances"]
        if i["ligand_instance"] == list(record["ligand_instance"])
    ]
    if len(matching) != 1:
        return failures + ["ligand_instance_missing_or_ambiguous"]
    instance = matching[0]
    if instance["mapping_issues"]:
        failures.append("contact_mapping_issues")
    expected = record["positions"]
    if isinstance(expected, str):
        expected = [int(p) for p in expected.split(",") if p]
    if not expected or sorted(set(expected)) != instance["positions"]:
        failures.append("reviewed_positions_mismatch")
    return failures
