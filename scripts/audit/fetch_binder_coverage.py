"""Cache public binder sources and compact public-D1 antibody metadata.

Existing files are reused unless --refresh is set. BioGRID's public table is
used because project 12 has no bulk ZIP. Raw files stay local; source URLs,
queries and checksums are recorded. No model calls or remote writes.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env
from accessible_surfaceome.sources._support.traceability import sha256_file, utc_now_iso
from accessible_surfaceome.tools._shared.http import USER_AGENT

ROOT = Path(__file__).resolve().parents[2]
URLS = {
    "gtop_interactions.txt": "https://www.guidetopharmacology.org/DATA/interactions.csv",
    "gtop_ligands.txt": "https://www.guidetopharmacology.org/DATA/ligands.csv",
    "thera.csv": "https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/static/downloads/TheraSAbDab_SeqStruc_OnlineDownload.csv",
}
QUERIES = {
    "identifiers.json": "SELECT hgnc_id,hgnc_symbol,uniprot_acc,ensembl_gene,ncbi_gene_id FROM gene_identifier_public",
    "annotations.json": "SELECT gene_symbol, uniprot_acc, json_extract(annotation_json, '$.gene') AS gene_json, json_extract(annotation_json, '$.surface_evidence.methods') AS methods_json, json_extract(annotation_json, '$.record_generated_at') AS record_generated_at FROM surface_annotation",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    output = ROOT / "data/external/binder_coverage"
    output.mkdir(parents=True, exist_ok=True)
    sources: dict[str, dict[str, Any]] = {}

    def fetch(name: str, url: str, data: dict[str, str] | None = None) -> str:
        path = output / name
        if args.refresh or not path.exists():
            for attempt in range(3):
                try:
                    with httpx.Client(
                        timeout=60,
                        headers={"User-Agent": USER_AGENT},
                        follow_redirects=True,
                    ) as client:
                        response = (
                            client.post(url, data=data) if data else client.get(url)
                        )
                        response.raise_for_status()
                        body = response.text
                        if name.endswith(".json"):
                            json.loads(body)
                        elif name.endswith(".html") and "<" not in body:
                            raise ValueError(f"Expected HTML from {url}")
                        elif name in URLS and "<!doctype html" in body[:100].lower():
                            raise ValueError(f"Expected data, received HTML from {url}")
                        path.write_text(body, encoding="utf-8")
                        break
                except (httpx.HTTPError, ValueError):
                    if attempt == 2:
                        raise
                    time.sleep(2**attempt)
        sources[name] = dict(
            url=url,
            method="POST" if data else "GET",
            parameters=data or {},
            sha256=sha256_file(path),
            retrieved_file_mtime=path.stat().st_mtime,
        )
        return path.read_text()

    for name, url in URLS.items():
        fetch(name, url)
    if args.refresh or any(not (output / name).exists() for name in QUERIES):
        load_env()
        with D1Client(D1Config.from_env_public()) as d1:
            for name, query in QUERIES.items():
                if args.refresh or not (output / name).exists():
                    (output / name).write_text(json.dumps(d1.query(query, [])))
    for name, query in QUERIES.items():
        sources[name] = dict(
            source="surfaceome_public D1",
            sql=query,
            sha256=sha256_file(output / name),
            retrieved_file_mtime=(output / name).stat().st_mtime,
        )

    url = "https://thebiogrid.org/scripts/datatableTools.php"
    headers = json.loads(
        fetch(
            "biogrid_header.json",
            url,
            {
                "expData": json.dumps(
                    {"tool": "serverSideHeader", "type": "project", "projectID": "12"}
                )
            },
        )
    )
    columns = [dict(column, search={"value": "", "regex": False}) for column in headers]
    proteins = []
    start = 0
    while True:
        params = {
            "tool": "serverSideRows",
            "type": "project",
            "projectID": "12",
            "draw": 1,
            "start": start,
            "length": 500,
            "search": {"value": "", "regex": False},
            "order": [{"column": 0, "dir": "asc"}],
            "columns": columns,
            "checkedBoxes": {},
        }
        page = json.loads(
            fetch(f"biogrid_{start}.json", url, {"expData": json.dumps(params)})
        )
        proteins.extend(page["data"])
        if len(proteins) >= page["recordsFiltered"]:
            break
        if not page["data"]:
            raise ValueError("BioGRID pagination stopped early")
        start += 500
    for path in output.glob("biogrid_[0-9]*.json"):
        if int(path.stem.split("_")[-1]) > start:
            path.unlink()
    identifiers = []
    for row in proteins:
        match = re.search(r"data-id='(\d+)'", row[5])
        if not match:
            raise ValueError("Missing BioGRID synthetic protein ID")
        identifiers.append(match[1])

    def detail(identifier: str) -> str:
        time.sleep(0.3)
        return fetch(
            f"biogrid_detail_{identifier}.html",
            "https://thebiogrid.org/scripts/displaySyntheticInteractionsTable.php",
            {"id": identifier, "type": "synthetic"},
        )

    targets = set()
    with ThreadPoolExecutor(max_workers=3) as pool:
        for i, body in enumerate(
            pool.map(detail, sorted(set(identifiers), key=int)), 1
        ):
            targets.update(re.findall(r"data-geneid='(\d+)'", body))
            if i % 100 == 0:
                print(f"BioGRID details {i}/{len(identifiers)}", flush=True)

    def target(identifier: str) -> None:
        time.sleep(0.3)
        fetch(
            f"biogrid_target_{identifier}.html",
            f"https://thebiogrid.org/results.php?gene={identifier}&view=summary",
        )

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(target, sorted(targets)))
    manifest = dict(
        recorded_at=utc_now_iso(),
        sources=sources,
        licenses={
            "gtopdb": "ODbL database; CC BY-SA 4.0 contents; https://www.guidetopharmacology.org/about.jsp",
            "therasabdab": "Retain attribution; verify redistribution terms before publishing antibody sequences.",
            "biogrid": "MIT; https://downloads.thebiogrid.org/BioGRID/Latest-Release/",
            "existing_annotation": "Project public-D1 records; inherited extraction provenance, not revalidated.",
        },
    )
    (output / "sources.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Cached source files and sources.json", flush=True)


if __name__ == "__main__":
    main()
