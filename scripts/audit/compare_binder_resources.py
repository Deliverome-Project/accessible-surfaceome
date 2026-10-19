"""Compare frozen binder coverage with explicit LLM ligand flags and SurfaceBind.

Use --fetch to refresh read-only public-D1 metadata; otherwise reuse cached inputs.
SurfaceBind predicted sites are never added to the experimental evidence union.
"""

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from accessible_surfaceome.binders.coverage import write_tsv
from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env
from accessible_surfaceome.sources._support.traceability import utc_now_iso

ROOT = Path(__file__).resolve().parents[2]
QUERIES = {
    "ligand_flags": "SELECT json_extract(annotation_json, '$.gene.hgnc_id') AS hgnc_id, json_extract(annotation_json, '$.filters.has_known_ligand') AS has_known_ligand, json_extract(annotation_json, '$.filters.has_known_ligand_rationale') AS rationale FROM surface_annotation",
    "surfacebind": "SELECT * FROM surface_bind_protein",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    raw = ROOT / "data/external/binder_coverage"
    out = ROOT / "data/analysis/deep_dive_binding_sites"
    if args.fetch:
        load_env()
        with D1Client(D1Config.from_env_public()) as d1:
            for name, sql in QUERIES.items():
                payload = dict(
                    retrieved_at=utc_now_iso(), query=sql, rows=d1.query(sql, [])
                )
                (raw / f"{name}.json").write_text(json.dumps(payload))
    payloads = {
        name: json.loads((raw / f"{name}.json").read_text()) for name in QUERIES
    }
    flags = {r["hgnc_id"]: r for r in payloads["ligand_flags"]["rows"]}
    assert len(flags) == len(payloads["ligand_flags"]["rows"])
    surfacebind = {r["uniprot_acc"]: r for r in payloads["surfacebind"]["rows"]}
    assert len(surfacebind) == len(payloads["surfacebind"]["rows"])
    genes = list(csv.DictReader((out / "gene_coverage.tsv").open(), delimiter="\t"))
    assert len(genes) == len({r["hgnc_id"] for r in genes}) == 5130
    for gene in genes:
        flag = flags.get(gene["hgnc_id"], {}).get("has_known_ligand")
        gene["llm_known_ligand"] = (
            "yes" if flag == 1 else "no" if flag == 0 else "unknown"
        )
        sb = surfacebind.get(gene["uniprot_acc"], {})
        unique = gene["identifier_status"] == "unique"
        gene["surfacebind_listed"] = int(unique and bool(sb))
        gene["surfacebind_predicted_sites"] = int(unique and sb.get("n_sites", 0) > 0)
        gene["surfacebind_predicted_seeds"] = int(
            unique and sb.get("n_seeds_total", 0) > 0
        )
        gene["experimental_or_predicted_sites"] = int(
            int(gene["union_mapped_sites"]) or gene["surfacebind_predicted_sites"]
        )
    write_tsv(out / "resource_comparison_genes.tsv", genes)
    metrics = [
        "sabdab_mapped_contacts",
        "iedb_exact_epitope",
        "iedb_epitope_region",
        "pdbe_gtopdb_supported_pair",
        "natural_ligand_mapped_contacts",
        "biogrid_literature_contacts",
        "union_mapped_sites",
        "union_including_regions",
        "union_mapped_sites_extracellular",
        "pdbe_chemical_contacts",
        "pdbe_chembl_identity",
        "surfacebind_listed",
        "surfacebind_predicted_sites",
        "surfacebind_predicted_seeds",
        "experimental_or_predicted_sites",
    ]
    summary = []
    for subset in ("all", "yes", "no", "unknown"):
        selected = [
            g for g in genes if subset == "all" or g["llm_known_ligand"] == subset
        ]
        for metric in metrics:
            count = sum(int(g[metric]) for g in selected)
            summary.append(
                dict(
                    subset=subset,
                    metric=metric,
                    covered=count,
                    denominator=len(selected),
                    percent=round(count / len(selected) * 100, 2) if selected else "",
                )
            )
    write_tsv(out / "resource_comparison.tsv", summary)
    manifest = dict(
        generated_at=utc_now_iso(),
        ligand_status_counts=dict(Counter(g["llm_known_ligand"] for g in genes)),
        explicit_yes_without_rationale=sum(
            g["llm_known_ligand"] == "yes" and not flags[g["hgnc_id"]].get("rationale")
            for g in genes
        ),
        surfacebind_versions=dict(
            Counter(r["surfacebind_version"] for r in surfacebind.values())
        ),
        inputs={
            name: dict(
                sha256=hashlib.sha256((raw / f"{name}.json").read_bytes()).hexdigest(),
                retrieved_at=p["retrieved_at"],
                query=p["query"],
            )
            for name, p in payloads.items()
        },
        coverage_sha256=hashlib.sha256(
            (out / "gene_coverage.tsv").read_bytes()
        ).hexdigest(),
    )
    (out / "resource_comparison_manifest.json").write_text(
        json.dumps(manifest, indent=2)
    )
    print(json.dumps(manifest, indent=2))
    for row in summary:
        if row["subset"] in ("all", "yes"):
            print(row)


if __name__ == "__main__":
    main()
