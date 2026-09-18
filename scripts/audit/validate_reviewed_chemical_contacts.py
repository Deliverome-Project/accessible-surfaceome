#!/usr/bin/env python3
"""Reproduce accepted chemical footprints from hash-pinned PDBe coordinates/SIFTS.

Writes a standalone validation ledger; never changes reviewed input or assets.
Use --offline with an existing cache for fully reproducible local validation.
"""

import argparse
import json
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

from accessible_surfaceome.binders.contact_coordinates import (
    sha256,
    validate_contacts,
    validate_reviewed_instance,
    verify_hash,
)

ROOT = Path(__file__).resolve().parents[2]


def cached_file(path: Path, url: str, expected: str, offline: bool) -> bytes:
    if not expected:
        raise ValueError(f"Missing required file hash for {path.name}")
    if path.exists():
        data = path.read_bytes()
        verify_hash(data, expected, path.name)
        return data
    if offline:
        raise ValueError(f"Offline cache miss: {path}")
    response = httpx.get(url, timeout=120, follow_redirects=True)
    response.raise_for_status()
    data = response.content
    verify_hash(data, expected, path.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    temporary.replace(path)
    return data


def canonical_sequences(directory: Path, accessions: set[str]) -> dict[str, str]:
    sequences = {}
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text())
        payload = data.get("data", data)
        records = payload.get(
            "results", [payload] if "primaryAccession" in payload else []
        )
        for protein in records:
            accession = protein.get("primaryAccession")
            if accession not in accessions:
                continue
            sequence = protein["sequence"]["value"]
            if accession in sequences and sequences[accession] != sequence:
                raise ValueError(
                    f"Conflicting cached canonical sequences for {accession}"
                )
            sequences[accession] = sequence
    return sequences


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--review",
        type=Path,
        default=ROOT
        / "data/analysis/deep_dive_binding_sites/reviewed_chemical_contacts.json",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=ROOT / "data/external/reviewed_chemical_contacts",
    )
    parser.add_argument(
        "--sequence-cache-dir",
        type=Path,
        default=ROOT / "data/external/structural_intact_extension/uniprot",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)
    if args.output.resolve() == args.review.resolve():
        parser.error("Validation ledger must not overwrite reviewed input")
    review_bytes = args.review.read_bytes()
    records = json.loads(review_bytes)["records"]
    ledger = {
        "schema_version": 1,
        "review_sha256": sha256(review_bytes),
        "validator_sha256": sha256(
            (
                ROOT / "src/accessible_surfaceome/binders/contact_coordinates.py"
            ).read_bytes()
        ),
        "records": [],
        "errors": [],
    }
    try:
        if not records:
            raise ValueError("Reviewed contact file contains no records")
        sequences = canonical_sequences(
            args.sequence_cache_dir, {r["uniprot_acc"] for r in records}
        )
        results = {}
        for index, record in enumerate(records):
            item = {
                "record_index": index,
                "uniprot_acc": record["uniprot_acc"],
                "pdb_id": record["pdb_id"],
                "partner": record["partner"],
                "ligand_instance": record["ligand_instance"],
            }
            try:
                accession, pdb, partner = (
                    record["uniprot_acc"],
                    record["pdb_id"].lower(),
                    record["partner"],
                )
                if not partner.startswith("CCD:") or not pdb.isalnum() or len(pdb) != 4:
                    raise ValueError(
                        "Expected exact CCD partner and four-character PDB identifier"
                    )
                sequence = sequences[accession]
                # Include pins in cache key so inconsistent reviewed hashes cannot be hidden.
                key = (
                    accession,
                    pdb,
                    partner,
                    record["coordinate_sha256"],
                    record["sifts_sha256"],
                    record.get("canonical_sequence_sha256"),
                )
                if key not in results:
                    coordinate = cached_file(
                        args.cache_dir / f"{pdb}.cif",
                        f"https://www.ebi.ac.uk/pdbe/entry-files/download/{pdb}.cif",
                        record["coordinate_sha256"],
                        args.offline,
                    )
                    sifts = cached_file(
                        args.cache_dir / f"{pdb}.xml.gz",
                        f"https://ftp.ebi.ac.uk/pub/databases/msd/sifts/xml/{pdb}.xml.gz",
                        record["sifts_sha256"],
                        args.offline,
                    )
                    results[key] = validate_contacts(
                        coordinate,
                        sifts,
                        uniprot_acc=accession,
                        canonical_sequence=sequence,
                        ccd=partner.removeprefix("CCD:"),
                        expected_coordinate_sha256=record["coordinate_sha256"],
                        expected_sifts_sha256=record["sifts_sha256"],
                        expected_canonical_sequence_sha256=record.get(
                            "canonical_sequence_sha256"
                        ),
                    )
                result = results[key]
                failures = validate_reviewed_instance(record, result)
                item.update(
                    status="failed" if failures else "verified",
                    failures=failures,
                    **{
                        k: result[k]
                        for k in (
                            "coordinate_sha256",
                            "sifts_sha256",
                            "canonical_sequence_sha256",
                            "method",
                            "first_model",
                            "chain_accessions",
                            "mapping_issues",
                        )
                    },
                )
                item["instance"] = next(
                    (
                        i
                        for i in result["instances"]
                        if i["ligand_instance"] == record["ligand_instance"]
                    ),
                    None,
                )
            except (
                ValueError,
                KeyError,
                OSError,
                ET.ParseError,
                httpx.HTTPError,
            ) as error:
                item.update(status="failed", failures=[str(error)])
            ledger["records"].append(item)
    except (ValueError, KeyError, OSError) as error:
        ledger["errors"].append(str(error))
    ledger["verified_count"] = sum(r["status"] == "verified" for r in ledger["records"])
    ledger["ok"] = not ledger["errors"] and ledger["verified_count"] == len(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(ledger, indent=2) + "\n")
    print(
        f"Verified {ledger['verified_count']}/{len(records)} reviewed chemical instances; ledger: {args.output}"
    )
    return 0 if ledger["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
