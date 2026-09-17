"""Build site-aware coverage with separate structural, curated and review tiers."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data/external/binding_site_audit"
OUT = ROOT / "data/analysis/binding_site_audit"
# Conservative exclusion of common solvents, salts and attached sugars. Remaining
# contacts are structural observations, not proof of pharmacological specificity.
EXCLUDE = set(
    "HOH DOD SO4 PO4 GOL EDO PEG PGE PG4 P6G MPD DMS ACT ACE TRS MES HEP BME EOH IPA FMT CIT CL NA K MG CA ZN MN CU CO NI CD NAG NDG BMA MAN FUC FUL GLC GAL SIA NANA".split()
)


def load_uniprot() -> dict:
    return {
        r["primaryAccession"]: r
        for p in (CACHE / "uniprot").glob("*.json")
        for r in json.loads(p.read_text()).get("data", {}).get("results", [])
    }


def topology(positions: list[int], protein: dict) -> str:
    if not positions:
        return "unmapped"
    labels = set()
    for pos in positions:
        hits = []
        for feature in protein.get("features", []):
            location = feature["location"]
            start, end = location["start"].get("value"), location["end"].get("value")
            if start and end and start <= pos <= end:
                if feature["type"] == "Transmembrane":
                    hits.append("transmembrane")
                elif feature["type"] == "Topological domain":
                    hits.append(feature.get("description", "unknown").lower())
        labels.update(hits or ["unknown"])
    return (
        next(iter(labels)) if len(labels) == 1 else "mixed:" + ";".join(sorted(labels))
    )


def pdb_sites(item: dict) -> dict[str, list[int]]:
    sites = defaultdict(set)
    for residue in item.get("residues", []):
        if residue.get("indexType") != "UNIPROT":
            continue
        for entry in residue.get("interactingPDBEntries", []):
            # Preserve per-structure sites; do not union unrelated pockets.
            sites[entry["pdbId"]].update(
                range(residue["startIndex"], residue["endIndex"] + 1)
            )
    return {pdb: sorted(positions) for pdb, positions in sites.items()}


def mapped_iedb_positions(row: dict, sequence: str) -> list[int]:
    if not sequence:
        return []
    linear = row.get("linear_sequence")
    if linear:
        # Only unique exact matches, never infer coordinates across mutations.
        starts = [m.start() for m in re.finditer(f"(?={re.escape(linear)})", sequence)]
        if len(starts) == 1:
            return list(range(starts[0] + 1, starts[0] + len(linear) + 1))
        return []
    tokens = [t.strip() for t in (row.get("structure_description") or "").split(",")]
    if not tokens or not all(re.fullmatch(r"[A-Z]\d+", t) for t in tokens):
        return []
    positions = [int(t[1:]) for t in tokens]
    if all(
        0 < pos <= len(sequence) and sequence[pos - 1] == token[0]
        for pos, token in zip(positions, tokens, strict=True)
    ):
        return sorted(set(positions))
    return []


def write_tsv(name: str, rows: list[dict]) -> None:
    if not rows:
        return
    with (OUT / name).open("w") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cohort = list(
        csv.DictReader(
            (ROOT / "data/analysis/binder_coverage/gene_coverage.tsv").open(),
            delimiter="\t",
        )
    )
    assert len({r["hgnc_id"] for r in cohort}) == len(cohort)
    by_acc = {r["uniprot_acc"]: r for r in cohort}
    missing = [
        acc for acc in by_acc if not (CACHE / "ligands" / f"{acc}.json").exists()
    ]
    if missing:
        raise ValueError(f"Incomplete PDBe scan: {len(missing)} accessions not queried")
    pages = sorted(
        (CACHE / "iedb").glob("bcell_*.json"), key=lambda p: int(p.stem.split("_")[-1])
    )
    if not pages or len(json.loads(pages[-1].read_text()).get("data", [])) >= 500:
        raise ValueError(
            "IEDB pagination is incomplete; finish retrieval before reporting coverage"
        )
    if [int(p.stem.split("_")[-1]) for p in pages] != list(
        range(0, len(pages) * 500, 500)
    ):
        raise ValueError("Missing IEDB page")
    proteins = load_uniprot()
    compounds = {
        ccd: values[0]
        for path in (CACHE / "compounds").glob("*.json")
        for ccd, values in json.loads(path.read_text()).get("data", {}).items()
        if values
    }
    observations = []
    coverage = defaultdict(set)
    retrieval = []

    def add(
        acc: str,
        source: str,
        binder_id: str,
        binder_name: str,
        evidence: str,
        positions: list[int],
        pdb: str = "",
        reference: str = "",
        extra: str = "",
    ) -> dict:
        gene = by_acc[acc]
        row = {
            k: gene[k]
            for k in [
                "hgnc_id",
                "hgnc_symbol",
                "uniprot_acc",
                "ensembl_gene",
                "ncbi_gene_id",
            ]
        }
        row.update(
            source=source,
            binder_id=binder_id,
            binder_name=binder_name,
            evidence=evidence,
            residues=";".join(map(str, positions)),
            topology=topology(positions, proteins.get(acc, {})),
            pdb_id=pdb,
            reference=reference,
            details=extra,
        )
        observations.append(row)
        return row

    # IUPHAR supplies an independent exact ligand-target cross-check when CCD
    # chemical identifiers carry ChEMBL links; no chemical-name matching.
    with (ROOT / "data/external/binder_coverage/gtop_ligands.txt").open() as handle:
        next(handle)
        ligands = {r["Ligand ID"]: r for r in csv.DictReader(handle)}
    with gzip.open(
        ROOT / "data/analysis/binder_coverage/observations.tsv.gz", "rt"
    ) as handle:
        prior = list(csv.DictReader(handle, delimiter="\t"))
    gtop_pairs = defaultdict(set)
    gtop_inchikey_pairs = defaultdict(set)
    natural_pairs = {}
    for row in prior:
        if row["source"] != "gtopdb" or row["target_scope"] != "single_protein":
            continue
        ligand = ligands.get(row["binder_id"].split(":")[-1], {})
        if ligand.get("InChIKey"):
            gtop_inchikey_pairs[row["uniprot_acc"], ligand["InChIKey"]].add(
                row["binder_id"]
            )
        for chembl in ligand.get("ChEMBL ID", "").split("|"):
            if chembl:
                gtop_pairs[row["uniprot_acc"], chembl].add(row["binder_id"])
        if row["endogenous"] == "true" and ligand.get("UniProt ID"):
            for acc in ligand["UniProt ID"].split("|"):
                natural_pairs[row["uniprot_acc"], acc] = row

    for acc in by_acc:
        path = CACHE / "ligands" / f"{acc}.json"
        result: dict[str, Any] = (
            json.loads(path.read_text()) if path.exists() else {"status": "not_queried"}
        )
        retrieval.append(
            dict(uniprot_acc=acc, source="PDBe_ligand_sites", status=result["status"])
        )
        if result["status"] != 200:
            continue
        protein = result["data"].get(acc, {})
        for item in protein.get("data", []):
            additional = item.get("additionalData") or {}
            compound = compounds.get(item["accession"], {})
            if (
                item["accession"] in EXCLUDE
                or additional.get("isSolvent") is not False
                or (additional.get("numAtoms") or 0) < 6
            ):
                continue
            if compound.get("compound_type") != "NON-POLYMER":
                continue
            chembl_ids = {
                link["resource_id"]
                for link in (compound.get("cross_links") or [])
                if link["resource"] == "ChEMBL"
            }
            chembl = ";".join(sorted(chembl_ids))
            supported_ids = set(
                gtop_inchikey_pairs.get((acc, compound.get("inchi_key")), set())
            )
            for identifier in chembl_ids:
                supported_ids.update(gtop_pairs.get((acc, identifier), set()))
            for pdb, positions in pdb_sites(item).items():
                if not positions:
                    continue
                row = add(
                    acc,
                    "PDBe",
                    f"CCD:{item['accession']}",
                    item["name"],
                    "experimental_chemical_contacts",
                    positions,
                    pdb,
                    f"https://www.ebi.ac.uk/pdbe/entry/pdb/{pdb}",
                    json.dumps(
                        dict(
                            chembl_ids=sorted(chembl_ids),
                            iuphar_ligand_ids=sorted(supported_ids),
                            inchi_key=compound.get("inchi_key"),
                            specificity_independently_reviewed=False,
                        )
                    ),
                )
                coverage["pdbe_chemical_contacts"].add(acc)
                if row["topology"] == "extracellular":
                    coverage["pdbe_chemical_contacts_extracellular"].add(acc)
                if chembl:
                    coverage["pdbe_chembl_identity"].add(acc)
                if supported_ids:
                    coverage["pdbe_gtopdb_supported_pair"].add(acc)
                    if row["topology"] == "extracellular":
                        coverage["pdbe_gtopdb_supported_pair_extracellular"].add(acc)

    matched = json.loads((CACHE / "sabdab_matched.json").read_text())
    coverage["sabdab_target_complex"] = {r["uniprot_acc"] for r in matched}
    for path in (CACHE / "antibody_contacts").glob("*.json"):
        item = json.loads(path.read_text())
        acc = item["uniprot_acc"]
        retrieval.append(
            dict(
                uniprot_acc=acc,
                source="SAbDab_representative_contacts",
                status=item["status"],
            )
        )
        if item["status"] != "mapped_contacts":
            continue
        row = add(
            acc,
            "SAbDab",
            item["SABDAB_ID"],
            f"{item['SABDAB_ID']} ({item['type']})",
            "experimental_antibody_contacts",
            item["positions"],
            item["pdb_id"],
            "https://sabdab.opig.stats.ox.ac.uk/",
            json.dumps(item, sort_keys=True),
        )
        coverage["sabdab_mapped_contacts"].add(acc)
        if row["topology"] == "extracellular":
            coverage["sabdab_mapped_contacts_extracellular"].add(acc)

    seen = set()
    for path in sorted((CACHE / "iedb").glob("bcell_*.json")):
        result = json.loads(path.read_text())
        for item in result.get("data", []):
            assert item["bcell_id"] not in seen, "Duplicate IEDB assay across pages"
            seen.add(item["bcell_id"])
            acc = (item.get("parent_source_antigen_iri") or "").removeprefix("UNIPROT:")
            if acc not in by_acc:
                continue
            coverage["iedb_any_bcell_assay"].add(acc)
            if not item.get("receptor_names") or not (
                item.get("qualitative_measure") or ""
            ).startswith("Positive"):
                continue
            assay = (item.get("assay_names") or "").lower()
            if not any(
                term in assay
                for term in [
                    "binding",
                    "3d structure",
                    "dissociation constant",
                    "on rate",
                    "off rate",
                ]
            ):
                continue
            if item.get("antigen_er") not in {
                "Epitope",
                "Source Antigen",
                "Fragment of Source Antigen",
            }:
                continue
            coverage["iedb_named_positive_binding"].add(acc)
            positions = mapped_iedb_positions(
                item, proteins.get(acc, {}).get("sequence", {}).get("value", "")
            )
            if not positions:
                continue
            exact = item["epitope_structure_defined"] == "Exact Epitope"
            row = add(
                acc,
                "IEDB",
                ";".join(
                    map(
                        str,
                        item.get("bcr_receptor_group_ids")
                        or item.get("receptor_names")
                        or [],
                    )
                ),
                ";".join(item["receptor_names"]),
                "curated_exact_epitope" if exact else "curated_epitope_region",
                positions,
                item.get("pdb_id") or "",
                f"https://www.iedb.org/assay/{item['bcell_id']}",
                json.dumps(
                    {
                        k: item[k]
                        for k in [
                            "bcell_id",
                            "structure_id",
                            "pubmed_id",
                            "assay_names",
                            "antigen_er",
                            "epitope_structure_defined",
                        ]
                    }
                ),
            )
            metric = "iedb_exact_epitope" if exact else "iedb_epitope_region"
            coverage[metric].add(acc)
            if row["topology"] == "extracellular":
                coverage[metric + "_extracellular"].add(acc)

    for (target, ligand), prior_row in natural_pairs.items():
        path = CACHE / "interfaces" / f"{target}.json"
        if not path.exists():
            continue
        result = json.loads(path.read_text())
        for item in result.get("data", {}).get(target, {}).get("data", []):
            if item["accession"] != ligand:
                continue
            for pdb, positions in pdb_sites(item).items():
                row = add(
                    target,
                    "IUPHAR+PDBe",
                    prior_row["binder_id"],
                    prior_row["binder_name"],
                    "experimental_natural_ligand_interface",
                    positions,
                    pdb,
                    prior_row["source_url"],
                    f"ligand UniProt:{ligand}; PMID:{prior_row['pmids']}",
                )
                coverage["natural_ligand_mapped_contacts"].add(target)
                if row["topology"] == "extracellular":
                    coverage["natural_ligand_mapped_contacts_extracellular"].add(target)

    for path in (CACHE / "minibinder_contacts").glob("*.json"):
        item = json.loads(path.read_text())
        acc = item["uniprot_acc"]
        positions = item["positions"]
        if positions:
            row = add(
                acc,
                "BioGRID+literature",
                item["binder_id"],
                item["binder_name"],
                "experimental_minibinder_contacts",
                positions,
                item["pdb_id"].lower(),
                item["source_url"],
                item["source_locator"] + "; " + item["epitope_domain"],
            )
            coverage["biogrid_literature_contacts"].add(acc)
            if row["topology"] == "extracellular":
                coverage["biogrid_literature_contacts_extracellular"].add(acc)
    union_keys = [
        "pdbe_gtopdb_supported_pair",
        "sabdab_mapped_contacts",
        "iedb_exact_epitope",
        "natural_ligand_mapped_contacts",
        "biogrid_literature_contacts",
    ]
    coverage["union_mapped_sites"] = set().union(*(coverage[key] for key in union_keys))
    coverage["union_mapped_sites_extracellular"] = set().union(
        *(coverage[key + "_extracellular"] for key in union_keys)
    )
    coverage["union_including_regions"] = (
        coverage["union_mapped_sites"] | coverage["iedb_epitope_region"]
    )
    coverage["union_including_regions_extracellular"] = (
        coverage["union_mapped_sites_extracellular"]
        | coverage["iedb_epitope_region_extracellular"]
    )
    gene_rows = [
        {
            **{
                k: r[k]
                for k in [
                    "hgnc_id",
                    "hgnc_symbol",
                    "uniprot_acc",
                    "ensembl_gene",
                    "ncbi_gene_id",
                    "triage_classical_receptor",
                    "triage_surface_yes",
                ]
            },
            **{key: int(r["uniprot_acc"] in coverage[key]) for key in sorted(coverage)},
        }
        for r in cohort
    ]
    summaries = []
    for key in sorted(coverage):
        for subset, rows in [
            ("all_candidates", cohort),
            (
                "classical_receptors",
                [r for r in cohort if r["triage_classical_receptor"] == "1"],
            ),
            ("surface_positive", [r for r in cohort if r["triage_surface_yes"] == "1"]),
        ]:
            count = sum(r["uniprot_acc"] in coverage[key] for r in rows)
            summaries.append(
                dict(
                    metric=key,
                    subset=subset,
                    covered=count,
                    denominator=len(rows),
                    percent=round(100 * count / len(rows), 2),
                )
            )
    write_tsv("gene_coverage.tsv", gene_rows)
    write_tsv("coverage_summary.tsv", summaries)
    write_tsv("observations.tsv", observations)
    with (OUT / "observations.tsv.gz").open("wb") as handle:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=handle, mtime=0
        ) as compressed:
            compressed.write((OUT / "observations.tsv").read_bytes())
    write_tsv("retrieval_status.tsv", retrieval)
    manifest = dict(
        generated_at=datetime.now(UTC).isoformat(),
        cohort_genes=len(cohort),
        iedb_assays=len(seen),
        iedb_pagination_complete=True,
        cohort_sha256=hashlib.sha256(
            (ROOT / "data/analysis/binder_coverage/gene_coverage.tsv").read_bytes()
        ).hexdigest(),
        contact_cutoff_angstrom=5.0,
        source_endpoints={
            "ligands/{uniprot}.json": "https://www.ebi.ac.uk/pdbe/api/uniprot/ligand_sites/{uniprot}",
            "interfaces/{uniprot}.json": "https://www.ebi.ac.uk/pdbe/api/uniprot/interface_residues/{uniprot}",
            "compounds/{offset}.json": "https://www.ebi.ac.uk/pdbe/api/pdb/compound/summary/{comma_separated_ccd_ids}",
            "uniprot/{offset}.json": "https://rest.uniprot.org/uniprotkb/search",
            "iedb/bcell_{offset}.json": "https://query-api.iedb.org/bcell_search?parent_source_antigen_source_org_iri=eq.NCBITaxon:9606&order=bcell_id.asc&limit=500&offset={offset}",
            "sabdab_summary.txt": "https://sabdab.opig.stats.ox.ac.uk/api/download/all-summary",
            "sifts.csv.gz": "https://ftp.ebi.ac.uk/pub/databases/msd/sifts/flatfiles/csv/pdb_chain_uniprot.csv.gz",
            "sifts_xml/{pdb}.xml.gz": "https://ftp.ebi.ac.uk/pub/databases/msd/sifts/xml/{pdb}.xml.gz",
            "coordinates/{pdb}.cif": "https://www.ebi.ac.uk/pdbe/entry-files/download/{pdb}.cif",
        },
        sources=[
            dict(
                path=str(p.relative_to(CACHE)),
                sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                cached_file_mtime=datetime.fromtimestamp(
                    p.stat().st_mtime, UTC
                ).isoformat(),
            )
            for p in sorted(CACHE.rglob("*"))
            if p.is_file() and p.suffix != ".js"
        ],
    )
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(
        json.dumps(
            [r for r in summaries if r["subset"] == "classical_receptors"], indent=2
        )
    )


if __name__ == "__main__":
    main()
