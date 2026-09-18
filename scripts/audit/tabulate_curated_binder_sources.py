"""Compare updated site sources using curated, site-independent denominators."""

import csv
import gzip
import hashlib
import json
from pathlib import Path

from accessible_surfaceome.binders.coverage import ID_FIELDS, write_tsv
from accessible_surfaceome.binders.site_context import EXTRACELLULAR_CONTEXTS

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/analysis/deep_dive_binding_sites"
# Source key, display name, evidence tier, antibody-specific evidence.
SOURCES = [
    ("SAbDab", "SAbDab: antibody contacts", "mapped", True),
    ("Thera-SAbDab", "Thera-SAbDab: named antibody contacts", "mapped", True),
    ("AACDB", "AACDB: antibody contacts", "mapped", True),
    ("IEDB", "IEDB: exact antibody epitopes", "mapped", True),
    ("PDBe", "PDBe + IUPHAR: chemical sites", "mapped", False),
    ("IUPHAR+PDBe", "PDBe + IUPHAR: protein ligands", "mapped", False),
    ("BioGRID+literature", "BioGRID-linked minibinders", "mapped", False),
    ("BioLiP", "BioLiP: biological ligand sites", "mapped", False),
    ("GPCRdb", "GPCRdb: experimental contacts", "mapped", False),
    ("expanded_pdb", "PDB/PDBe: expanded protein interfaces", "mapped", False),
    ("intact_binding_region", "IntAct: binding regions", "region", False),
    (
        "intact_mutation_effect",
        "IntAct: interaction-changing mutations",
        "mutation",
        False,
    ),
    ("SurfaceBind", "SurfaceBind: predicted sites", "predicted", False),
]


def read(name):
    with (OUT / name).open() as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def main():
    genes = read("binder_denominator_genes.tsv")
    previous = read("all_source_comparison_genes.tsv")
    index = {g["hgnc_id"]: g for g in genes}
    assert len(genes) == len(index) == 5130
    cpdb = {
        g["hgnc_id"]
        for g in genes
        if g["cpdb_single_protein_participant"] == "1"
        and g["binder_target_location"].startswith("membrane")
    }
    thera = {
        g["hgnc_id"]
        for g in genes
        if g["thera_named_binder"] == "1"
        and g["binder_target_location"].startswith("membrane")
    }
    assert len(cpdb) == 621 and len(thera) == 244
    any_site = {key: set() for key, *_ in SOURCES}
    ec_site = {key: set() for key, *_ in SOURCES}
    with gzip.open(OUT / "structural_intact_evidence.tsv.gz", "rt") as handle:
        for r in csv.DictReader(handle, delimiter="\t"):
            if r["context"] in {"invalid_mapping", "removed_processing_segment"}:
                continue
            key = (
                "expanded_pdb"
                if r["tier"] == "unrestricted_structural"
                else r["tier"]
                if r["tier"].startswith("intact_")
                else r["source"]
            )
            assert key in any_site, key
            assert index[r["hgnc_id"]]["identifier_status"] == "unique"
            any_site[key].add(r["hgnc_id"])
            if r["context"] in EXTRACELLULAR_CONTEXTS:
                ec_site[key].add(r["hgnc_id"])
    any_site["SurfaceBind"] = {
        r["hgnc_id"]
        for r in previous
        if r["surfacebind_predicted_sites"] == "1"
        and r["identifier_status"] == "unique"
    }
    mapped = [key for key, _, tier, _ in SOURCES if tier == "mapped"]
    antibody = [key for key, _, _, ab in SOURCES if ab]
    unions = [
        ("Mapped-site union", mapped),
        ("Mapped sites OR IntAct regions", mapped + ["intact_binding_region"]),
        (
            "Also including mutation effects",
            mapped + ["intact_binding_region", "intact_mutation_effect"],
        ),
        ("Mapped sites OR SurfaceBind predictions", mapped + ["SurfaceBind"]),
    ]
    rows = []

    def metrics(name, keys, predicted=False):
        covered = set().union(*(any_site[k] for k in keys))
        outside = set().union(*(ec_site[k] for k in keys))
        ab_keys = set(keys) & set(antibody)
        abs_any = set().union(*(any_site[k] for k in ab_keys))
        abs_ec = set().union(*(ec_site[k] for k in ab_keys))
        return dict(
            source=name,
            all_genes=len(covered),
            unique_genes="NA",
            cellphonedb_any_binder=len(covered & cpdb),
            therasabdab_any_ab_epitope=len(abs_any & thera) if ab_keys else "NA",
            extracellular_all="NA" if predicted else len(outside),
            extracellular_cellphonedb="NA" if predicted else len(outside & cpdb),
            extracellular_therasabdab_ab=len(abs_ec & thera) if ab_keys else "NA",
        )

    for key, name, tier, ab in SOURCES:
        row = metrics(name, [key], tier == "predicted")
        others = set().union(*(v for k, v in any_site.items() if k != key))
        row["unique_genes"] = len(any_site[key] - others)
        row["unique_among_mapped_sources"] = (
            len(any_site[key] - set().union(*(any_site[k] for k in mapped if k != key)))
            if tier == "mapped"
            else "NA"
        )
        row["evidence_tier"] = tier
        rows.append(row)
    for name, keys in unions:
        row = metrics(name, keys, "SurfaceBind" in keys)
        row.update(unique_among_mapped_sources="NA", evidence_tier="union")
        rows.append(row)
    write_tsv(OUT / "curated_source_comparison.tsv", rows)
    source_genes = []
    for key, name, tier, ab in SOURCES:
        for h in sorted(any_site[key]):
            g = index[h]
            source_genes.append(
                {
                    **{k: g[k] for k in ID_FIELDS},
                    "source": name,
                    "evidence_tier": tier,
                    "cellphonedb_denominator_member": int(h in cpdb),
                    "therasabdab_denominator_member": int(h in thera),
                    "antibody_evidence": int(ab),
                    "extracellular": "NA"
                    if tier == "predicted"
                    else int(h in ec_site[key]),
                }
            )
    write_tsv(OUT / "curated_source_comparison_genes.tsv", source_genes)
    old_ab = [
        "sabdab_mapped_contacts",
        "therapeutic_mapped_contacts",
        "aacdb_mapped_contacts",
        "iedb_exact_epitope",
    ]
    old_ec = [
        "sabdab_mapped_contacts_extracellular",
        "therapeutic_mapped_contacts_extracellular",
        "aacdb_mapped_contacts_extracellular",
        "iedb_exact_epitope_extracellular",
    ]
    old_members = {
        g["hgnc_id"]
        for g in previous
        if g["all_experimental_union_after_antibody_extension"] == "1"
    }
    old_external = {
        g["hgnc_id"]
        for g in previous
        if g["all_experimental_ec_union_after_antibody_extension"] == "1"
    }
    old_abs = {g["hgnc_id"] for g in previous if any(g[k] == "1" for k in old_ab)}
    old_abs_ec = {g["hgnc_id"] for g in previous if any(g[k] == "1" for k in old_ec)}
    stages = [
        dict(
            source="Previous pipeline, same curated denominators",
            all_genes=len(old_members),
            unique_genes="NA",
            cellphonedb_any_binder=len(old_members & cpdb),
            therasabdab_any_ab_epitope=len(old_abs & thera),
            extracellular_all=len(old_external),
            extracellular_cellphonedb=len(old_external & cpdb),
            extracellular_therasabdab_ab=len(old_abs_ec & thera),
        )
    ]
    stages += [
        metrics(
            "Mature-protein topology repair", [k for k in mapped if k != "expanded_pdb"]
        ),
        metrics("Plus expanded PDB/PDBe retrieval", mapped),
        metrics("Plus IntAct binding regions", mapped + ["intact_binding_region"]),
        metrics(
            "Plus IntAct mutation effects",
            mapped + ["intact_binding_region", "intact_mutation_effect"],
        ),
    ]
    write_tsv(OUT / "curated_source_comparison_stages.tsv", stages)
    # Independent reconciliation against the existing gene-level extension results.
    extension = read("structural_intact_genes.tsv")
    ec_union = set().union(*(ec_site[k] for k in mapped))
    assert ec_union == {
        g["hgnc_id"]
        for g in extension
        if g["extension_reclassified_plus_structural_ec"] == "1"
    }
    assert len(ec_union & cpdb) == 276
    assert len(set().union(*(ec_site[k] for k in antibody)) & thera) == 116

    def cell(n, denominator=None):
        if n == "NA":
            return "—"
        if denominator is None:
            return f"{n:,}"
        percent = 100 * n / denominator
        label = "<0.1" if 0 < percent < 0.1 else f"{percent:.1f}"
        return f"{n:,} ({label}%)"

    lines = [
        "# Updated source coverage with curated binder denominators",
        "",
        "Denominators: all 5,130 candidates; 621 membrane-associated CellPhoneDB single-protein participants; 244 membrane-associated Thera-SAbDab target genes. Catalogue membership does not require an epitope. The two curated sets overlap by 138 genes.",
        "",
        "## Source-by-source coverage",
        "",
        "| Source | All genes / 5,130 | Unique genes¹ | CPDB: any binder / 621 | Thera: any antibody epitope / 244 | EC: all / 5,130 | EC: CPDB / 621 | EC: Thera antibody / 244 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    columns = [
        ("all_genes", 5130),
        ("unique_genes", None),
        ("cellphonedb_any_binder", 621),
        ("therasabdab_any_ab_epitope", 244),
        ("extracellular_all", 5130),
        ("extracellular_cellphonedb", 621),
        ("extracellular_therasabdab_ab", 244),
    ]
    for r in rows:
        lines.append(
            "| "
            + str(r["source"])
            + " | "
            + " | ".join(cell(r[k], d) for k, d in columns)
            + " |"
        )
    lines += [
        "",
        "## Effect of the pipeline improvements",
        "",
        "These are before/after comparisons using the same curated denominator memberships, not the earlier LLM subset.",
        "",
        "| Pipeline stage | CPDB: any binder site / 621 | CPDB: EC binder site / 621 | Thera: any antibody epitope / 244 | Thera: EC antibody epitope / 244 |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in stages:
        lines.append(
            "| "
            + str(r["source"])
            + " | "
            + " | ".join(
                cell(r[k], d)
                for k, d in [columns[2], columns[5], columns[3], columns[6]]
            )
            + " |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "- CPDB columns count any qualifying binder on a catalogue gene; the binder need not be the CellPhoneDB ligand. Thera columns count any qualifying antibody epitope on a catalogue target; it need not belong to the named therapeutic. Neither column is same-binder coverage.",
        "- Streams without validated antibody identity show — in the Thera antibody columns: antibody-epitope coverage was not classified for those streams. Generic structure databases may contain antibody complexes, but those are not automatically credited. IntAct therefore increases binder-region coverage but does not increase the antibody-epitope numerator in this audit.",
        "- IntAct regions are often broad constructs; mutation effects may be indirect. Their union rows broaden the evidence definition and must not be described as exact-site or exact-epitope coverage. The mapped-site union remains the primary residue-level result.",
        "- SurfaceBind is predicted evidence and stays separate. Its anchor-only export cannot establish a wholly extracellular patch or an antibody epitope, so those columns are unassessed rather than zero.",
        "- EC means all retained mapped site residues are explicitly extracellular or in a mature cell-membrane GPI chain, with precursor exclusions and the recorded CFAP95 assembly-context correction. Secreted-only targets are outside these membrane-associated denominator columns. Structural interfaces remain candidates with biological relevance not reviewed individually in every case.",
        "- ¹ Unique genes means covered by that stream and none of the other 12 displayed source streams, including IntAct tiers and SurfaceBind. This is not order-dependent incremental coverage. The TSV also gives exclusivity among mapped-site sources only. Thera-SAbDab is an identity layer over structures, not an independent experimental corpus.",
        "- The compartment denominator includes annotated forms/isoforms and a flagged generic-membrane plus extracellular-topology subset: 66 CellPhoneDB genes and 43 Thera genes. It does not demonstrate live-cell accessibility. Name-resolution and complex-membership exclusions are documented in [the denominator audit](../../../docs/reports/2026-09-17-binder-denominators.md).",
        "",
        "## Reproduction",
        "",
        "Run `PYTHONPATH=src:scripts/audit uv run python scripts/audit/tabulate_curated_binder_sources.py` after hydrating the existing audit inputs. Companion TSVs contain the full source table, fixed-denominator improvement stages and per-gene source membership with stable identifiers. No source downloads, paid model calls or production changes are needed.",
    ]
    (OUT / "curated_source_comparison.md").write_text("\n".join(lines) + "\n")
    inputs = [
        "binder_denominator_genes.tsv",
        "all_source_comparison_genes.tsv",
        "structural_intact_evidence.tsv.gz",
        "structural_intact_genes.tsv",
    ]
    (OUT / "curated_source_comparison_manifest.json").write_text(
        json.dumps(
            {
                "denominators": {
                    "all": 5130,
                    "cellphonedb_membrane": 621,
                    "therasabdab_membrane": 244,
                },
                "source_streams": len(SOURCES),
                "inputs": {
                    n: hashlib.sha256((OUT / n).read_bytes()).hexdigest()
                    for n in inputs
                },
                "numerators": {
                    "cellphonedb": "Any audited binder; not required to match catalogue ligand",
                    "therasabdab": "Antibody-specific epitope evidence only; not required to match named therapeutic",
                },
            },
            indent=2,
        )
        + "\n"
    )
    for r in stages:
        print(r)


if __name__ == "__main__":
    main()
