"""Audit a fixed random sample of ligand-positive genes lacking strict EC sites.

Run with --fetch to refresh read-only public annotations, UniProt and PDBe.
Manual, evidence-linked adjudications are in ligand_gap_review_notes.json.
This diagnostic does not change production annotations or source coverage flags.
"""

import argparse
import csv
import gzip
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import httpx

from accessible_surfaceome.binders.coverage import write_tsv
from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env
from audit_biolip_gpcrdb import RAW as BIOLIP_RAW
from audit_biolip_gpcrdb import map_biolip_site
from summarize_binding_sites import EXCLUDE, load_uniprot, pdb_sites, topology

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/analysis/deep_dive_binding_sites"
RAW = ROOT / "data/external/ligand_gap_audit"
SEED = 20260917
EC = "all_experimental_ec_union_after_antibody_extension"


def sample_genes(genes):
    pool = sorted(
        [g for g in genes if g["llm_known_ligand"] == "yes" and g[EC] == "0"],
        key=lambda g: g["hgnc_id"],
    )
    return pool, random.Random(SEED).sample(pool, 50)


def fetch_one(job):
    path, url = job
    if path.exists():
        return
    try:
        response = httpx.get(url, timeout=60, follow_redirects=True)
        payload = {
            "status": response.status_code,
            "data": response.json() if response.status_code == 200 else {},
        }
    except (httpx.HTTPError, ValueError) as error:
        payload = {"status": "error", "error": str(error), "data": {}}
    payload.update(url=url, retrieved_at=datetime.now(UTC).isoformat())
    path.write_text(json.dumps(payload))


def scan_biolip(sample, proteins):
    """Check all sampled BioLiP rows, avoiding the earlier first-site stopping rule."""
    index = {g["uniprot_acc"] for g in sample}
    chemicals = {}
    with gzip.open(BIOLIP_RAW / "ligand.tsv.gz", "rt") as stream:
        for row in csv.reader(stream, delimiter="\t"):
            if len(row) >= 6 and not row[0].startswith("#"):
                chemicals[row[0]] = row
    counts = defaultdict(Counter)
    with gzip.open(BIOLIP_RAW / "BioLiP.txt.gz", "rt") as stream:
        for row in csv.reader(stream, delimiter="\t"):
            acc = row[17]
            if acc not in index:
                continue
            counts[acc]["raw_rows"] += 1
            atoms = re.findall(
                r"([A-Z][a-z]?)(\d*)", chemicals.get(row[4], ["", ""])[1]
            )
            heavy = sum(int(n or 1) for e, n in atoms if e not in {"H", "D"})
            if row[4] != "peptide" and (
                row[4] in EXCLUDE or not any(e == "C" for e, n in atoms) or heavy < 6
            ):
                counts[acc]["excluded_" + row[4]] += 1
                continue
            counts[acc]["eligible_rows"] += 1
            positions = map_biolip_site(
                proteins[acc]["sequence"]["value"], row[20], row[8]
            )
            if positions:
                counts[acc]["mapped_rows"] += 1
                counts[acc][topology(positions, proteins[acc])] += 1
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    cohort_path = OUT / "all_source_comparison_genes.tsv"
    genes = list(csv.DictReader(cohort_path.open(), delimiter="\t"))
    pool, sample = sample_genes(genes)
    assert len(genes) == 5130 and len(pool) == 2792
    assert len({g["hgnc_id"] for g in sample}) == 50
    if args.fetch:
        if not (RAW / "records.json").exists():
            load_env()
            query = (
                "SELECT annotation_json FROM surface_annotation WHERE "
                "json_extract(annotation_json, '$.gene.hgnc_id') IN ("
                + ",".join("?" for _ in sample)
                + ")"
            )
            with D1Client(D1Config.from_env_public()) as d1:
                records = d1.query(query, [g["hgnc_id"] for g in sample])
            (RAW / "records.json").write_text(
                json.dumps([json.loads(r["annotation_json"]) for r in records])
            )
        jobs = []
        for gene in sample:
            acc = gene["uniprot_acc"]
            jobs.extend(
                [
                    (
                        RAW / f"{acc}_interfaces.json",
                        f"https://www.ebi.ac.uk/pdbe/api/uniprot/interface_residues/{acc}",
                    ),
                    (
                        RAW / f"{acc}_uniprot.json",
                        f"https://rest.uniprot.org/uniprotkb/{acc}.json",
                    ),
                ]
            )
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(fetch_one, jobs))
    notes_path = OUT / "ligand_gap_review_notes.json"
    notes = {r["hgnc_id"]: r for r in json.loads(notes_path.read_text())}
    assert set(notes) == {g["hgnc_id"] for g in sample}
    flags_path = ROOT / "data/external/binder_coverage/ligand_flags.json"
    flags = {r["hgnc_id"]: r for r in json.loads(flags_path.read_text())["rows"]}
    records = {
        r["gene"]["hgnc_id"]: r for r in json.loads((RAW / "records.json").read_text())
    }
    assert set(records) == set(notes)
    proteins = load_uniprot()
    biolip = scan_biolip(sample, proteins)
    rows, interfaces, uniprot_sites = [], [], []
    retrievals = Counter()
    for rank, gene in enumerate(sample, 1):
        hgnc, acc = gene["hgnc_id"], gene["uniprot_acc"]
        note = notes[hgnc]
        assert note["hgnc_symbol"] == gene["hgnc_symbol"]
        identifiers = {
            k: gene[k]
            for k in (
                "hgnc_id",
                "hgnc_symbol",
                "uniprot_acc",
                "ensembl_gene",
                "ncbi_gene_id",
            )
        }
        payload = json.loads((RAW / f"{acc}_interfaces.json").read_text())
        retrievals[f"pdbe_{payload['status']}"] += 1
        for partner in payload.get("data", {}).get(acc, {}).get("data", []):
            if partner["accession"] == acc:
                continue
            for pdb, positions in pdb_sites(partner).items():
                assert positions and min(positions) > 0
                assert max(positions) <= len(proteins[acc]["sequence"]["value"])
                interfaces.append(
                    dict(
                        identifiers,
                        partner_accession=partner["accession"],
                        pdb_id=pdb,
                        canonical_positions=",".join(map(str, positions)),
                        strict_topology=topology(positions, proteins[acc]),
                        source_url=f"https://www.ebi.ac.uk/pdbe/api/uniprot/interface_residues/{acc}",
                        evidence_status="candidate_not_promoted_to_coverage",
                    )
                )
        uniprot = json.loads((RAW / f"{acc}_uniprot.json").read_text())
        retrievals[f"uniprot_{uniprot['status']}"] += 1
        for feature in uniprot.get("data", {}).get("features", []):
            if feature["type"] == "Binding site":
                uniprot_sites.append(
                    dict(
                        identifiers,
                        ligand=feature.get("ligand", {}).get("name", ""),
                        start=feature["location"]["start"].get("value"),
                        end=feature["location"]["end"].get("value"),
                        evidence=json.dumps(
                            feature.get("evidences", []), sort_keys=True
                        ),
                        evidence_status="annotation_not_promoted_to_coverage",
                    )
                )
        rationale = flags[hgnc].get("rationale", "")
        ids = set(re.findall(r"a[12]_evi_\d+", rationale))
        cited = [e for e in records[hgnc]["evidence"] if e["evidence_id"] in ids]
        urls = sorted(
            {
                span["source"]["url"]
                for evidence in cited
                for span in evidence.get("spans", [])
                if span["source"].get("url")
            }
        )
        rows.append(
            dict(
                identifiers,
                sample_rank=rank,
                **{k: v for k, v in note.items() if k not in identifiers},
                original_ligand_flag="yes",
                original_any_experimental_site=gene[
                    "all_experimental_union_after_antibody_extension"
                ],
                original_ec_site=gene[EC],
                identifier_status=gene["identifier_status"],
                llm_rationale_sha256=hashlib.sha256(rationale.encode()).hexdigest(),
                llm_cited_evidence_ids=";".join(sorted(ids)),
                llm_cited_source_urls=";".join(urls),
                pdbe_status=payload["status"],
                biolip_full_scan_counts=json.dumps(biolip.get(acc, {}), sort_keys=True),
            )
        )
    write_tsv(OUT / "ligand_gap_sample50.tsv", rows)
    write_tsv(OUT / "ligand_gap_pdbe_interfaces.tsv", interfaces)
    write_tsv(OUT / "ligand_gap_uniprot_sites.tsv", uniprot_sites)
    counts = Counter(r["primary_gap"] for r in rows)
    strict_leads = sorted(
        {
            r["hgnc_symbol"]
            for r in interfaces
            if r["strict_topology"] == "extracellular"
        }
    )
    manifest = {
        "audit_date": "2026-09-17",
        "sample_seed": SEED,
        "sampling": "random.Random(seed).sample; pool sorted by HGNC ID; no replacements",
        "cohort": len(genes),
        "ligand_yes": 3157,
        "strict_ec_ligand_yes": 365,
        "eligible_uncovered_pool": len(pool),
        "sample_size": len(rows),
        "primary_gap_counts": dict(counts),
        "retrieval_status": dict(retrievals),
        "direct_pdbe_strict_ec_candidate_genes": strict_leads,
        "existing_any_experimental_sites_in_sample": sum(
            int(r["original_any_experimental_site"]) for r in rows
        ),
        "biolip_all_rows_additional_strict_ec_genes": sorted(
            g["hgnc_symbol"]
            for g in sample
            if biolip.get(g["uniprot_acc"], {}).get("extracellular", 0)
        ),
        "scope": "All 50 frozen rationales and linked ledger claims reviewed; targeted fresh primary-source checks, not 50 exhaustive systematic literature reviews. PDBe 404 is endpoint absence, not absence of binding or PDB structures. No coverage flags changed.",
        "frozen_topology_subset_sha256": hashlib.sha256(
            json.dumps(
                {g["uniprot_acc"]: proteins[g["uniprot_acc"]] for g in sample},
                sort_keys=True,
            ).encode()
        ).hexdigest(),
        "inputs_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [
                cohort_path,
                notes_path,
                flags_path,
                *sorted(RAW.glob("*.json")),
            ]
        },
    }
    (OUT / "ligand_gap_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in manifest.items() if k != "inputs_sha256"}, indent=2
        )
    )


if __name__ == "__main__":
    main()
