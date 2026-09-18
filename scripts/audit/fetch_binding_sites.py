"""Cache experimental site sources for the stable-ID binder cohort (no model calls)."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data/external/binding_site_audit"


def fetch(name: str, url: str, params: dict | None = None) -> dict:
    path = CACHE / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        saved = json.loads(path.read_text())
        if saved["status"] in (200, 404):
            return saved
    result: dict[str, Any] = {}
    for attempt in range(3):
        try:
            response = httpx.get(
                url,
                params=params,
                timeout=90,
                follow_redirects=True,
                headers={
                    "User-Agent": "accessible-surfaceome binding-site coverage audit"
                },
            )
            result = dict(
                url=str(response.url),
                status=response.status_code,
                retrieved_at=datetime.now(UTC).isoformat(),
            )
            if response.status_code == 200:
                result["data"] = response.json()
                break
            if response.status_code == 404:
                result["data"] = {}
                break
            result["error"] = response.text[:300]
        except (httpx.HTTPError, ValueError) as exc:
            result = dict(
                url=url,
                status=0,
                error=str(exc),
                retrieved_at=datetime.now(UTC).isoformat(),
            )
        time.sleep(2 ** (attempt + 1))
    path.write_text(json.dumps(result))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source", choices=["bulk", "pdbe", "iedb", "uniprot", "natural", "compounds"]
    )
    parser.add_argument("--deep-dives", action="store_true")
    args = parser.parse_args()
    cohort_path = ROOT / (
        "data/analysis/deep_dive_binding_sites/cohort.tsv"
        if args.deep_dives
        else "data/analysis/binder_coverage/gene_coverage.tsv"
    )
    prior_path = ROOT / (
        "data/analysis/deep_dive_binding_sites/prior_observations.tsv.gz"
        if args.deep_dives
        else "data/analysis/binder_coverage/observations.tsv.gz"
    )
    if args.source == "bulk":
        urls = {
            "sabdab_summary.txt": "https://sabdab.opig.stats.ox.ac.uk/api/download/all-summary",
            "sifts.csv.gz": "https://ftp.ebi.ac.uk/pub/databases/msd/sifts/flatfiles/csv/pdb_chain_uniprot.csv.gz",
        }
        CACHE.mkdir(parents=True, exist_ok=True)
        manifest = []
        for name, url in urls.items():
            path = CACHE / name
            if not path.exists():
                response = httpx.get(url, timeout=180, follow_redirects=True)
                response.raise_for_status()
                path.write_bytes(response.content)
            manifest.append(
                dict(
                    path=name,
                    url=url,
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    retrieved_at=datetime.fromtimestamp(
                        path.stat().st_mtime, UTC
                    ).isoformat(),
                )
            )
        (CACHE / "bulk_sources.json").write_text(json.dumps(manifest, indent=2))
        return
    cohort = list(
        csv.DictReader(
            cohort_path.open(),
            delimiter="\t",
        )
    )
    accessions = sorted({row["uniprot_acc"] for row in cohort if row["uniprot_acc"]})
    if args.source == "compounds":
        ids = set()
        for path in (CACHE / "ligands").glob("*.json"):
            result = json.loads(path.read_text())
            for protein in result.get("data", {}).values():
                ids.update(item["accession"] for item in protein.get("data", []))
        cached_ids = {
            ccd
            for path in (CACHE / "compounds").glob("*.json")
            for ccd in json.loads(path.read_text()).get("data", {})
        }
        ordered = sorted(ids - cached_ids)
        for i in range(0, len(ordered), 100):
            fetch(
                f"compounds/batch_{hashlib.sha256(','.join(ordered[i : i + 100]).encode()).hexdigest()[:16]}",
                "https://www.ebi.ac.uk/pdbe/api/pdb/compound/summary/"
                + ",".join(ordered[i : i + 100]),
            )
            print(f"Compounds {min(i + 100, len(ordered))}/{len(ordered)}", flush=True)
        return
    if args.source == "natural":
        with gzip.open(prior_path, "rt") as handle:
            accessions = sorted(
                {
                    r["uniprot_acc"]
                    for r in csv.DictReader(handle, delimiter="\t")
                    if r["source"] == "gtopdb" and r["endogenous"] == "true"
                }
            )
    if args.source in {"pdbe", "natural"}:

        def protein(acc: str) -> tuple[str, int]:
            folder, endpoint = (
                ("ligands", "ligand_sites")
                if args.source == "pdbe"
                else ("interfaces", "interface_residues")
            )
            result = fetch(
                f"{folder}/{acc}",
                f"https://www.ebi.ac.uk/pdbe/api/uniprot/{endpoint}/{acc}",
            )
            time.sleep(0.1)
            return acc, result["status"]

        with ThreadPoolExecutor(max_workers=6) as pool:
            for i, result in enumerate(pool.map(protein, accessions), 1):
                if i % 100 == 0:
                    print(f"PDBe {i}/{len(accessions)} {result}", flush=True)
    elif args.source == "iedb":
        # Assay-level records avoid false joins between an antigen's antibodies
        # and epitopes that were tested in unrelated experiments.
        offset = 0
        while True:
            result = fetch(
                f"iedb/bcell_{offset}",
                "https://query-api.iedb.org/bcell_search",
                {
                    "parent_source_antigen_source_org_iri": "eq.NCBITaxon:9606",
                    "order": "bcell_id.asc",
                    "limit": "500",
                    "offset": str(offset),
                },
            )
            if result["status"] != 200:
                raise RuntimeError(result)
            count = len(result["data"])
            print(f"IEDB {offset}+{count}", flush=True)
            if count < 500:
                break
            offset += count
    else:
        cached_ids = {
            r["primaryAccession"]
            for p in (CACHE / "uniprot").glob("*.json")
            for r in json.loads(p.read_text()).get("data", {}).get("results", [])
        }
        accessions = sorted(set(accessions) - cached_ids)
        for i in range(0, len(accessions), 100):
            batch = accessions[i : i + 100]
            result = fetch(
                f"uniprot/batch_{hashlib.sha256(','.join(batch).encode()).hexdigest()[:16]}",
                "https://rest.uniprot.org/uniprotkb/search",
                {
                    "query": " OR ".join(f"accession:{acc}" for acc in batch),
                    "format": "json",
                    "size": "500",
                    "fields": "accession,ft_topo_dom,ft_transmem,sequence",
                },
            )
            if result["status"] != 200:
                raise RuntimeError(result)
            print(f"UniProt {i + len(batch)}/{len(accessions)}", flush=True)
    manifest = [
        {
            "path": str(p.relative_to(CACHE)),
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        }
        for p in sorted(CACHE.rglob("*.json"))
    ]
    (CACHE / f"{args.source}_manifest.txt").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
