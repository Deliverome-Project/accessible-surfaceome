"""Find target-matched PDB leads in accessible BioGRID-linked papers.

A target in a cited PDB is not proof that the exact synthetic binder is present.
These records deliberately remain review leads, outside mapped-site coverage.
"""

from __future__ import annotations

import csv
import argparse
import gzip
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def paper_pdb_ids(xml: str) -> set[str]:
    root = ET.fromstring(xml)
    ids = set()
    for link in root.iter("ext-link"):
        url = link.get("{http://www.w3.org/1999/xlink}href", "")
        for match in re.finditer(
            r"(?:rcsb.org/structure/|pdb)([0-9][a-zA-Z0-9]{3})(?:/|$)", url, re.I
        ):
            ids.add(match[1].lower())
    for section in root.iter("sec"):
        title = section.findtext("title", "").lower()
        if "data availability" not in title:
            continue
        text = " ".join(section.itertext())
        if "Protein Data Bank" not in text and "PDB" not in text:
            continue
        ids.update(
            match.lower()
            for match in re.findall(r"\b[1-9][A-Za-z0-9]{3}\b", text)
            if re.search("[A-Za-z]", match)
        )
    return ids


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deep-dives", action="store_true")
    args = parser.parse_args()
    output = ROOT / (
        "data/analysis/deep_dive_binding_sites"
        if args.deep_dives
        else "data/analysis/binding_site_audit"
    )
    literature_output = (
        output if args.deep_dives else ROOT / "data/analysis/binder_coverage"
    )
    output.mkdir(parents=True, exist_ok=True)
    mapping = defaultdict(set)
    with gzip.open(
        ROOT / "data/external/binding_site_audit/sifts.csv.gz", "rt"
    ) as handle:
        next(handle)
        for row in csv.DictReader(handle):
            mapping[row["PDB"]].add(row["SP_PRIMARY"])
    papers = {
        r["pmid"]: r
        for r in csv.DictReader(
            (literature_output / "literature_retrieval.tsv").open(),
            delimiter="\t",
        )
    }
    with gzip.open(
        (
            output / "prior_observations.tsv.gz"
            if args.deep_dives
            else ROOT / "data/analysis/binder_coverage/observations.tsv.gz"
        ),
        "rt",
    ) as handle:
        binders = [
            r
            for r in csv.DictReader(handle, delimiter="\t")
            if r["source"] == "biogrid_synthetic"
        ]
    rows = []
    for binder in binders:
        for pmid in re.findall(r"\d+", binder["pmids"]):
            paper = papers.get(pmid, {})
            path = (
                ROOT
                / "data/external/binder_coverage/literature"
                / f"{paper.get('pmcid', '')}.xml"
            )
            ids = paper_pdb_ids(path.read_text()) if path.exists() else set()
            matched = sorted(
                pdb for pdb in ids if binder["uniprot_acc"] in mapping[pdb]
            )
            rows.append(
                {
                    **{
                        k: binder[k]
                        for k in [
                            "hgnc_id",
                            "hgnc_symbol",
                            "uniprot_acc",
                            "ensembl_gene",
                            "ncbi_gene_id",
                            "binder_id",
                            "binder_name",
                        ]
                    },
                    "pmid": pmid,
                    "pmcid": paper.get("pmcid", ""),
                    "xml_available": int(path.exists()),
                    "pdb_leads": ";".join(matched),
                    "evidence": "target_present_in_cited_structure_not_binder_verified"
                    if matched
                    else "not_established",
                }
            )
    # Multiple source assays need not multiply identical paper leads.
    rows = list({tuple(row.values()): row for row in rows}.values())
    with (output / "biogrid_structure_leads.tsv").open("w") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    print(
        json.dumps(
            dict(
                binder_paper_rows=len(rows),
                genes_with_leads=len({r["hgnc_id"] for r in rows if r["pdb_leads"]}),
                papers_with_leads=len({r["pmid"] for r in rows if r["pdb_leads"]}),
            )
        )
    )


if __name__ == "__main__":
    main()
