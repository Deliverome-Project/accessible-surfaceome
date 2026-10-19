"""Compare audited source coverage and exclusivity across the frozen cohort.

Uniqueness is computed across all ten displayed evidence streams, including
SurfaceBind predictions. A separate field excludes predictions for experimental
source prioritization. Entirely extracellular means all mapped site residues;
SurfaceBind anchor-only data cannot establish this criterion.
"""

import csv
import hashlib
import json
from pathlib import Path

from accessible_surfaceome.binders.coverage import write_tsv

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/analysis/deep_dive_binding_sites"
SOURCES = [
    (
        "SAbDab: antibody contacts",
        "sabdab_mapped_contacts",
        "sabdab_mapped_contacts_extracellular",
    ),
    (
        "Thera-SAbDab: exact therapeutic domains",
        "therapeutic_mapped_contacts",
        "therapeutic_mapped_contacts_extracellular",
    ),
    (
        "AACDB: antibody contacts",
        "aacdb_mapped_contacts",
        "aacdb_mapped_contacts_extracellular",
    ),
    ("IEDB: exact epitopes", "iedb_exact_epitope", "iedb_exact_epitope_extracellular"),
    (
        "PDBe + IUPHAR: chemical sites",
        "pdbe_gtopdb_supported_pair",
        "pdbe_gtopdb_supported_pair_extracellular",
    ),
    (
        "PDBe + IUPHAR: natural protein-ligand sites",
        "natural_ligand_mapped_contacts",
        "natural_ligand_mapped_contacts_extracellular",
    ),
    (
        "BioGRID-linked literature: minibinders",
        "biogrid_literature_contacts",
        "biogrid_literature_contacts_extracellular",
    ),
    ("BioLiP: biological ligand sites", "biolip_mapped_sites", "biolip_extracellular"),
    ("GPCRdb: experimental contacts", "gpcr_mapped_sites", "gpcr_extracellular"),
    ("SurfaceBind: predicted sites", "surfacebind_predicted_sites", None),
]


def main():
    path = OUT / "therapeutic_aacdb_genes.tsv"
    genes = list(csv.DictReader(path.open(), delimiter="\t"))
    assert len(genes) == len({g["hgnc_id"] for g in genes}) == 5130
    yes = {g["hgnc_id"] for g in genes if g["llm_known_ligand"] == "yes"}
    assert len(yes) == 3157
    covered = {
        key: {g["hgnc_id"] for g in genes if g[key] == "1"} for _, key, _ in SOURCES
    }
    experimental = set().union(*(covered[key] for _, key, ec in SOURCES if ec))
    combined = set().union(*covered.values())
    rows = []
    for name, key, ec in SOURCES:
        others = set().union(
            *(members for other, members in covered.items() if other != key)
        )
        experimental_others = set().union(
            *(covered[k] for _, k, e in SOURCES if e and k != key)
        )
        exclusive = covered[key] - others
        ec_members = {g["hgnc_id"] for g in genes if ec and g[ec] == "1"}
        assert not ec_members - covered[key]
        rows.append(
            dict(
                source=name,
                covered_all=len(covered[key]),
                unique_all_sources=len(exclusive),
                covered_ligand_yes=len(covered[key] & yes),
                extracellular_all=len(ec_members) if ec else "NA",
                extracellular_ligand_yes=len(ec_members & yes) if ec else "NA",
                unique_excluding_prediction_competition=len(
                    covered[key] - experimental_others
                ),
                unique_ligand_yes=len(exclusive & yes),
            )
        )
        for g in genes:
            g[key + "_exclusive_all_sources"] = int(g["hgnc_id"] in exclusive)
    ec_union = {
        g["hgnc_id"] for g in genes if any(ec and g[ec] == "1" for _, _, ec in SOURCES)
    }
    assert experimental == {
        g["hgnc_id"]
        for g in genes
        if g["all_experimental_union_after_antibody_extension"] == "1"
    }
    assert ec_union == {
        g["hgnc_id"]
        for g in genes
        if g["all_experimental_ec_union_after_antibody_extension"] == "1"
    }
    rows.append(
        dict(
            source="Experimental union",
            covered_all=len(experimental),
            unique_all_sources="NA",
            covered_ligand_yes=len(experimental & yes),
            extracellular_all=len(ec_union),
            extracellular_ligand_yes=len(ec_union & yes),
            unique_excluding_prediction_competition="NA",
            unique_ligand_yes="NA",
        )
    )
    rows.append(
        dict(
            source="Experimental or predicted union",
            covered_all=len(combined),
            unique_all_sources="NA",
            covered_ligand_yes=len(combined & yes),
            extracellular_all="NA",
            extracellular_ligand_yes="NA",
            unique_excluding_prediction_competition="NA",
            unique_ligand_yes="NA",
        )
    )
    write_tsv(OUT / "all_source_comparison.tsv", rows)
    write_tsv(OUT / "all_source_comparison_genes.tsv", genes)

    def cell(value, denominator):
        if value == "NA":
            return "—"
        percentage = 100 * value / denominator
        label = "<0.1" if 0 < percentage < 0.1 else f"{percentage:.1f}"
        return f"{value:,} ({label}%)"

    lines = [
        "| Source | All genes (5,130) | Unique genes¹ | Ligand=yes (3,157) | EC sites: all (5,130) | EC sites: ligand=yes (3,157) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        unique = (
            "—"
            if row["unique_all_sources"] == "NA"
            else f"{row['unique_all_sources']:,}"
        )
        lines.append(
            f"| {row['source']} | {cell(row['covered_all'], 5130)} | {unique} | {cell(row['covered_ligand_yes'], 3157)} | {cell(row['extracellular_all'], 5130)} | {cell(row['extracellular_ligand_yes'], 3157)} |"
        )
    text = "\n".join(lines)
    notes = (
        "\n\n¹ Unique = covered by this evidence stream and none of the other nine displayed streams, "
        "including SurfaceBind. This is exclusivity, not the order-dependent incremental counts in the earlier audit. "
        "The TSV also reports uniqueness ignoring prediction overlap.\n\n"
        "EC = all mapped contact residues annotated extracellular by UniProt; not demonstrated live-cell accessibility. "
        "SurfaceBind provides predicted anchors rather than full mapped patch residues, so EC coverage is not assessed, not zero.\n\n"
        "Ligand=yes is the explicit LLM label; numerators include any qualifying binder on those genes. "
        "BioLiP includes substrates, lipids, cofactors and peptide fragments. BioGRID reflects limited validated literature extraction. "
        "BioLiP and SAbDab representative-site selection can undercount EC coverage.\n\n"
        "Only qualifying mapped-site evidence is included: broader IEDB regions, uncorroborated PDBe chemical contacts, "
        "ChEMBL identity links and GPCRdb mutation records are excluded from this comparison. "
        "Thera-SAbDab matches therapeutic domains to SAbDab/AACDB structures and is not an independent experimental corpus. "
        "SurfaceBind predictions remain separate from experimental evidence. "
        "Shared-accession gene records stay in the denominator without gene-specific credit.\n"
    )
    (OUT / "all_source_comparison.md").write_text(text + notes)
    (OUT / "all_source_comparison_manifest.json").write_text(
        json.dumps(
            dict(
                input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                denominator=5130,
                ligand_yes_denominator=3157,
                unique_definition="Exclusive across all ten displayed source/evidence streams, including SurfaceBind",
                extracellular_definition="All mapped residues extracellular; not assessed for SurfaceBind anchors",
            ),
            indent=2,
        )
    )
    print(text)


if __name__ == "__main__":
    main()
