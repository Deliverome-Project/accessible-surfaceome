"""Export audited canonical residue evidence for the static contact-site viewer.

Run after audit_structural_intact_extension.py. No API or annotation writes.
Counts are snapshot evidence sites, not exhaustive database inventories.
"""

import csv
import gzip
import hashlib
import html
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data/analysis/deep_dive_binding_sites"
OUTPUT = ROOT / "viewer/public/data/contact-sites"


class SourceCounts(TypedDict):
    genes: set[str]
    sites: int
    ec_genes: set[str]
    ec_sites: int


def normalize(row):
    """Keep mapped contacts/epitopes; never turn IntAct constructs into contacts."""
    if row["tier"].startswith("intact_") or row["context"] in {
        "invalid_mapping",
        "removed_processing_segment",
    }:
        return None
    positions = sorted({int(p) for p in row["positions"].split(",") if p})
    if not positions or positions[0] < 1:
        raise ValueError("Invalid canonical residue mapping")
    source = "PDB/PDBe" if row["tier"] == "unrestricted_structural" else row["source"]
    reference = row["reference"]
    if reference.isdigit():
        reference = f"https://pubmed.ncbi.nlm.nih.gov/{reference}/"
    elif reference.startswith("10."):
        reference = f"https://doi.org/{reference}"
    if not reference.startswith("https://"):
        reference = ""
    return dict(
        source=source,
        partner=html.unescape(re.sub(r"<[^>]+>", "", row["partner"])),
        pdb=row["pdb_id"].lower(),
        positions=positions,
        context=row["context"],
        reference=reference,
        method=row["source"],
        evidence="Experimentally mapped epitope"
        if source == "IEDB"
        else "Structure-derived contacts",
        confidence=row["confidence"]
        or "Mapped residue evidence; no calibrated confidence score",
    )


def main():
    categories = json.loads((INPUT / "ligand_categories.json").read_text())
    ligand_names = json.loads((INPUT / "ligand_names.json").read_text())["ligands"]
    observation_names = {}
    with gzip.open(INPUT / "observations.tsv.gz", "rt") as handle:
        for observation in csv.DictReader(handle, delimiter="\t"):
            if observation["binder_name"]:
                observation_names[
                    (
                        observation["source"],
                        observation["binder_id"],
                        observation["reference"],
                    )
                ] = observation["binder_name"]
    protein_ligands = {
        v["uniprot_acc"]: v for v in ligand_names.values() if v["uniprot_acc"]
    }
    genes = {}
    with (INPUT / "binder_denominator_genes.tsv").open() as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row["identifier_status"] == "unique":
                acc = row["uniprot_acc"]
                assert acc not in genes
                genes[acc] = dict(
                    hgnc_id=row["hgnc_id"], symbol=row["hgnc_symbol"], sites=[]
                )
    seen = defaultdict(set)
    with gzip.open(INPUT / "structural_intact_evidence.tsv.gz", "rt") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            site = normalize(row)
            if site is None:
                continue
            name = observation_names.get(
                (site["source"], site["partner"], site["reference"])
            )
            if name:
                site["partner_label"] = name
            partner_gene = genes.get(site["partner"])
            if partner_gene:
                site["partner_label"] = partner_gene["symbol"]
            ligand = ligand_names.get(site["partner"]) or protein_ligands.get(
                site["partner"]
            )
            if ligand:
                site["partner_label"] = ligand["name"]
                symbol = genes.get(ligand["uniprot_acc"], {}).get("symbol")
                if symbol and symbol.casefold() != ligand["name"].casefold():
                    site["partner_label"] += f" ({symbol})"
            acc = row["uniprot_acc"]
            category_name = re.sub(
                r"\s*\([^)]*\)\s*$", "", site.get("partner_label", site["partner"])
            )
            category_name = (
                re.sub(r"\s+(Fab|Fv|VHH)$", "", category_name, flags=re.I)
                .strip()
                .lower()
            )
            if category_name.startswith("cetuximab"):
                category_name = "cetuximab"
            if category_name in {"imc-11f8", "11f8"}:
                category_name = "necitumumab"
            review = categories["reviewed"].get(f"{acc}|{category_name}")
            site["category"] = "unclassified"
            if (
                site["source"] == "Thera-SAbDab"
                or category_name in categories["therapeutic_names"]
            ):
                site["category"] = "therapeutic"
                site["category_reference"] = (
                    "https://opig.stats.ox.ac.uk/webapps/therasabdab/"
                )
            endogenous = categories["endogenous_pairs"].get(f"{acc}|{site['partner']}")
            if endogenous:
                site["category"] = endogenous
                site["category_reference"] = (
                    "https://www.guidetopharmacology.org/download.jsp"
                )
            if review:
                site["category"] = review["category"]
                site["category_reference"] = review["reference"]
                site["category_reason"] = review["reason"]
                if review.get("canonical_name"):
                    site["canonical_partner_label"] = review["canonical_name"]
            assert genes[acc]["hgnc_id"] == row["hgnc_id"]
            key = (
                site["source"],
                site["partner"],
                site["pdb"],
                tuple(site["positions"]),
                site["context"],
                site["reference"],
            )
            if key not in seen[acc]:
                genes[acc]["sites"].append(site)
                seen[acc].add(key)
    shards = [{} for _ in range(64)]
    stats = defaultdict(
        lambda: SourceCounts(genes=set(), sites=0, ec_genes=set(), ec_sites=0)
    )
    for acc, gene in sorted(genes.items()):
        gene["sites"].sort(
            key=lambda s: (
                not s["context"].startswith("extracellular_"),
                s["source"],
                s["partner"],
                s["pdb"],
                s["positions"],
            )
        )
        shards[sum(map(ord, acc)) % 64][acc] = gene
        for site in gene["sites"]:
            stat = stats[site["source"]]
            stat["genes"].add(gene["hgnc_id"])
            stat["sites"] += 1
            if site["context"].startswith("extracellular_"):
                stat["ec_genes"].add(gene["hgnc_id"])
                stat["ec_sites"] += 1
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for i, shard in enumerate(shards):
        (OUTPUT / f"{i:02x}.json").write_text(
            json.dumps(shard, separators=(",", ":")) + "\n"
        )
    summary = {
        source: {k: len(v) if isinstance(v, set) else v for k, v in stat.items()}
        for source, stat in sorted(stats.items())
    }
    manifest = dict(
        schema_version=1,
        categories_sha256=hashlib.sha256(
            (INPUT / "ligand_categories.json").read_bytes()
        ).hexdigest(),
        observation_names_sha256=hashlib.sha256(
            (INPUT / "observations.tsv.gz").read_bytes()
        ).hexdigest(),
        ligand_names_sha256=hashlib.sha256(
            (INPUT / "ligand_names.json").read_bytes()
        ).hexdigest(),
        audit_snapshot_date="2026-09-17",
        sampling={
            "SAbDab": "One representative mapped interface per gene",
            "BioLiP": "One representative mapped site per gene",
        },
        denominator_sha256=hashlib.sha256(
            (INPUT / "binder_denominator_genes.tsv").read_bytes()
        ).hexdigest(),
        input_sha256=hashlib.sha256(
            (INPUT / "structural_intact_evidence.tsv.gz").read_bytes()
        ).hexdigest(),
        audited_genes=len(genes),
        covered_genes=sum(bool(g["sites"]) for g in genes.values()),
        site_definition="Unique source, partner, PDB, canonical residue set, context and reference; sources may describe the same interface. Audit snapshot, not exhaustive DB coverage.",
        excluded="IntAct regions and mutation effects; invalid mappings; removed processing segments; ambiguous gene mappings",
        sources=summary,
    )
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
