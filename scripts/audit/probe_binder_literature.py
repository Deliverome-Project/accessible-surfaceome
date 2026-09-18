"""Measure full-text reachability for the BioGRID binder papers in the pilot.

Epitope/mapping mentions are retrieval leads, never promoted to epitope evidence.
Full text stays in the ignored local cache; only availability/counts are exported.
"""

from __future__ import annotations

import csv
import argparse
import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from accessible_surfaceome.sources._support.traceability import sha256_file, utc_now_iso
from accessible_surfaceome.tools._shared.http import USER_AGENT

ROOT = Path(__file__).resolve().parents[2]
BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deep-dives", action="store_true")
    args = parser.parse_args()
    raw = ROOT / "data/external/binder_coverage/literature"
    out = ROOT / (
        "data/analysis/deep_dive_binding_sites"
        if args.deep_dives
        else "data/analysis/binder_coverage"
    )
    observations_path = out / (
        "prior_observations.tsv" if args.deep_dives else "observations.tsv"
    )
    raw.mkdir(exist_ok=True)
    with observations_path.open() as stream:
        observations = [
            r
            for r in csv.DictReader(stream, delimiter="\t")
            if r["source"] == "biogrid_synthetic"
        ]
    pmids = sorted({p for row in observations for p in row["pmids"].split("|") if p})
    metadata = {}
    requests = []
    with httpx.Client(timeout=40, headers={"User-Agent": USER_AGENT}) as client:
        for start in range(0, len(pmids), 25):
            batch = pmids[start : start + 25]
            params = {
                "query": "SRC:MED AND ("
                + " OR ".join("EXT_ID:" + p for p in batch)
                + ")",
                "format": "json",
                "resultType": "core",
                "pageSize": 100,
            }
            path = (
                raw
                / f"metadata_batch_{hashlib.sha256('|'.join(batch).encode()).hexdigest()[:16]}.json"
            )
            if not path.exists():
                response = client.get(BASE + "/search", params=params)
                response.raise_for_status()
                path.write_text(response.text)
            results = json.loads(path.read_text())["resultList"]["result"]
            metadata.update({r["id"]: r for r in results})
            requests.append(
                dict(
                    url=BASE + "/search",
                    params=params,
                    path=str(path.relative_to(ROOT)),
                    sha256=sha256_file(path),
                )
            )

    def retrieve(pmid: str) -> dict[str, str | int]:
        item = metadata.get(pmid, {})
        pmcid = item.get("pmcid", "")
        row: dict[str, str | int] = dict(
            pmid=pmid,
            pmcid=pmcid,
            title=item.get("title", ""),
            doi=item.get("doi", ""),
            metadata_found=int(bool(item)),
            open_access_flag=item.get("isOpenAccess", ""),
            supplement_flag=item.get("hasSuppl", ""),
            fulltext_status="not_available",
            epitope_lead_paragraphs=0,
            structure_lead_paragraphs=0,
            body_paragraphs=0,
            fulltext_url="",
            fulltext_sha256="",
        )
        if not pmcid:
            return row
        url = f"{BASE}/{pmcid}/fullTextXML"
        row["fulltext_url"] = url
        path = raw / f"{pmcid}.xml"
        try:
            if not path.exists():
                time.sleep(0.4)
                with httpx.Client(
                    timeout=40, headers={"User-Agent": USER_AGENT}
                ) as client:
                    for attempt in range(3):
                        response = client.get(url)
                        if response.status_code not in (429, 500, 502, 503, 504):
                            break
                        time.sleep(2**attempt)
                    if response.status_code != 200:
                        row["fulltext_status"] = f"http_{response.status_code}"
                        return row
                    root = ET.fromstring(response.text)
                    if root.find("body") is None:
                        row["fulltext_status"] = "no_body"
                        return row
                    path.write_text(response.text)
            root = ET.fromstring(path.read_text())
            paragraphs = [" ".join(p.itertext()) for p in root.findall("./body//p")]
            row.update(
                fulltext_status="retrieved",
                body_paragraphs=len(paragraphs),
                fulltext_sha256=sha256_file(path),
                epitope_lead_paragraphs=sum(
                    bool(
                        re.search(
                            r"\bepitope\b|alanine.scanning|binding.interface|binding.site",
                            p,
                            re.I,
                        )
                    )
                    for p in paragraphs
                ),
                structure_lead_paragraphs=sum(
                    bool(re.search(r"cryo.EM|crystal.structure|co.crystal", p, re.I))
                    for p in paragraphs
                ),
            )
        except (httpx.HTTPError, ET.ParseError) as error:
            row["fulltext_status"] = type(error).__name__
        return row

    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(retrieve, pmids))
    with (out / "literature_retrieval.tsv").open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    summary = dict(
        papers=len(rows),
        metadata_found=sum(r["metadata_found"] for r in rows),
        fulltexts_retrieved=sum(r["fulltext_status"] == "retrieved" for r in rows),
        papers_with_epitope_leads=sum(bool(r["epitope_lead_paragraphs"]) for r in rows),
        papers_with_structure_leads=sum(
            bool(r["structure_lead_paragraphs"]) for r in rows
        ),
        supplement_flag_yes=sum(r["supplement_flag"] == "Y" for r in rows),
    )
    manifest = dict(
        generated_at=utc_now_iso(),
        generator_sha256=sha256_file(Path(__file__)),
        observations_sha256=sha256_file(observations_path),
        requests=requests,
        summary=summary,
        limitation="Keyword hits are paper-level triage leads, not validated target-specific epitopes. Supplements flagged but not downloaded. No paid model calls.",
    )
    (out / "literature_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
