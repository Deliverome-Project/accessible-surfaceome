"""Cache richer UniProt records, unrestricted PDBe interfaces and IntAct features."""

import argparse
import csv
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/external/structural_intact_extension"
OUT = ROOT / "data/analysis/deep_dive_binding_sites"
FIELDS = "accession,sequence,ft_topo_dom,ft_transmem,ft_signal,ft_chain,ft_propep,ft_lipid,cc_subcellular_location,xref_pdb,organism_id"


def fetch(job):
    path, url, params = job
    if path.exists():
        return {"file": str(path.relative_to(RAW)), "status": "cached"}
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            r = httpx.get(url, params=params, timeout=90, follow_redirects=True)
            if r.status_code not in {200, 404}:
                r.raise_for_status()
            data = {
                "url": str(r.url),
                "retrieved_at": datetime.now(UTC).isoformat(),
                "status": r.status_code,
                "data": r.json() if r.status_code == 200 else {},
            }
            path.write_text(json.dumps(data))
            return {"file": str(path.relative_to(RAW)), "status": r.status_code}
        except (httpx.HTTPError, ValueError) as error:
            if attempt == 2:
                return {
                    "file": str(path.relative_to(RAW)),
                    "status": "error",
                    "error": str(error),
                }
            time.sleep(2**attempt)
    raise RuntimeError("unreachable")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage", choices=["uniprot", "pdbe", "intact"])
    args = p.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    genes = list(
        csv.DictReader((OUT / "all_source_comparison_genes.tsv").open(), delimiter="\t")
    )
    accessions = sorted({g["uniprot_acc"] for g in genes})
    if args.stage == "intact":
        jobs = [
            ("bindings_regions.tsv", "psimitab/features/bindings_regions.tsv"),
            ("mutations.tsv", "psimitab/features/mutations.tsv"),
            ("mutation_details.tsv", "various/mutations.tsv"),
            ("intact_negative.txt", "psimitab/intact_negative.txt"),
        ]
        manifests = []
        for name, relative in jobs:
            path = RAW / name
            url = "https://ftp.ebi.ac.uk/pub/databases/intact/current/" + relative
            if not path.exists():
                temporary = path.with_suffix(".part")
                with httpx.stream(
                    "GET", url, timeout=180, follow_redirects=True
                ) as response:
                    response.raise_for_status()
                    headers = dict(response.headers)
                    with temporary.open("wb") as handle:
                        for block in response.iter_bytes():
                            handle.write(block)
                temporary.rename(path)
            else:
                headers = {}
            manifests.append(
                {
                    "file": name,
                    "url": url,
                    "headers": headers,
                    "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "checked_at": datetime.now(UTC).isoformat(),
                }
            )
            print("Downloaded", name, path.stat().st_size, flush=True)
        (RAW / "intact_download_manifest.json").write_text(
            json.dumps(manifests, indent=2)
        )
        return
    if args.stage == "uniprot":
        jobs = []
        for i in range(0, len(accessions), 50):
            batch = accessions[i : i + 50]
            jobs.append(
                (
                    RAW / "uniprot" / f"{i:05d}.json",
                    "https://rest.uniprot.org/uniprotkb/search",
                    {
                        "query": " OR ".join("accession:" + a for a in batch),
                        "format": "json",
                        "size": 100,
                        "fields": FIELDS,
                    },
                )
            )
    else:
        # Query every cohort accession. A UniProt PDB cross-reference is not a prerequisite.
        jobs = [
            (
                RAW / "interfaces" / f"{a}.json",
                f"https://www.ebi.ac.uk/pdbe/api/uniprot/interface_residues/{a}",
                None,
            )
            for a in accessions
        ]
    results = []
    with ThreadPoolExecutor(max_workers=6 if args.stage == "pdbe" else 3) as executor:
        for i, result in enumerate(executor.map(fetch, jobs), 1):
            results.append(result)
            if i % 100 == 0 or i == len(jobs):
                print(args.stage, i, "/", len(jobs), flush=True)
    (RAW / f"{args.stage}_retrieval.json").write_text(json.dumps(results, indent=2))
    print("Errors", sum(r["status"] == "error" for r in results), flush=True)


if __name__ == "__main__":
    main()
