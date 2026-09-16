"""Measure named-binder coverage without equating pharmacology with surface binding.

Run with ``uv run python -m accessible_surfaceome.binders.coverage`` after
``uv run python scripts/audit/fetch_binder_coverage.py``. No model calls or D1 writes.
The observation table preserves assay context; coverage counts unique HGNC IDs.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from accessible_surfaceome.sources._support.traceability import sha256_file, utc_now_iso

ROOT = Path(__file__).resolve().parents[3]
ID_FIELDS = ("hgnc_id", "hgnc_symbol", "uniprot_acc", "ensembl_gene", "ncbi_gene_id")
FIELDS = (
    *ID_FIELDS,
    "source",
    "source_record_id",
    "binder_id",
    "binder_name",
    "binder_type",
    "exact_identity",
    "endogenous",
    "approved",
    "target_scope",
    "binding_evidence",
    "measurement_type",
    "measurement_value",
    "measurement_low",
    "measurement_high",
    "measurement_units",
    "measurement_relation",
    "assay",
    "surface_evidence",
    "epitope",
    "epitope_evidence",
    "validation_strength",
    "validation_strategy",
    "clone",
    "vendor",
    "catalog",
    "rrid",
    "sequence_available",
    "structure_available",
    "pmids",
    "evidence_ids",
    "source_url",
)


def plain(value: Any) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]*>", "", str(value or ""))).split())


def read_csv(path: Path, *, gtop: bool = False) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        if gtop:
            if "GtoPdb Version:" not in next(stream):
                raise ValueError(f"{path}: expected GtoPdb version line")
        rows = list(csv.DictReader(stream))
    if not rows or None in rows[0]:
        raise ValueError(f"{path}: empty or malformed CSV")
    return rows


def unique_index(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    """Ambiguous accessions must not silently choose an arbitrary HGNC gene."""
    groups: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        value = str(row.get(field) or "")
        if value:
            groups[value][row["hgnc_id"]] = row
    return {
        key: next(iter(group.values()))
        for key, group in groups.items()
        if len(group) == 1
    }


def observation(gene: dict[str, Any], **values: Any) -> dict[str, str]:
    row = dict.fromkeys(FIELDS, "")
    row.update({key: str(gene.get(key) or "") for key in ID_FIELDS})
    row.update(
        target_scope="single_protein",
        surface_evidence="not_established",
        epitope_evidence="not_reported",
        exact_identity="yes",
    )
    for key, value in values.items():
        if key not in row:
            raise ValueError(f"Unknown observation field: {key}")
        row[key] = str(value or "")
    return row


def thera_index(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    names: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        aliases = [
            row["Therapeutic"],
            *row.get("Alternative Therapeutic Names", "").split(";"),
        ]
        for name in set(plain(x).casefold() for x in aliases if plain(x)):
            names[name].append(row)
    return {name: rs[0] for name, rs in names.items() if len(rs) == 1}


def gtop_observations(
    interactions: list[dict[str, str]],
    ligands: list[dict[str, str]],
    thera: list[dict[str, str]],
    by_acc: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, str]], Counter[str]]:
    ligand_by_id = {r["Ligand ID"]: r for r in ligands}
    therapeutics = thera_index(thera)
    output = []
    audit: Counter[str] = Counter()
    for number, raw in enumerate(interactions, 3):
        if raw["Target Species"] != "Human":
            audit["nonhuman_or_unspecified_species"] += 1
            continue
        target = raw["Target UniProt ID"] or raw["Target Ligand UniProt ID"]
        accs = target.split("|") if target else []
        if not accs or any(acc not in by_acc for acc in accs):
            audit["unmapped_or_outside_cohort"] += 1
            continue
        complex_target = len(accs) > 1 or bool(
            raw["Target Subunit IDs"] or raw["Target Ligand Subunit IDs"]
        )
        ligand = ligand_by_id[raw["Ligand ID"]]
        names = [raw["Ligand"], ligand["Name"], ligand.get("INN", "")]
        matches = {
            therapeutics[n.casefold()]["Therapeutic"]: therapeutics[n.casefold()]
            for n in map(plain, names)
            if n.casefold() in therapeutics
        }
        therapeutic = next(iter(matches.values())) if len(matches) == 1 else {}
        original = raw["Original Affinity Units"] not in ("", "-") and any(
            raw[f"Original Affinity {kind} nm"] for kind in ("Median", "Low", "High")
        )
        measurement = (
            raw["Original Affinity Units"] if original else raw["Affinity Units"]
        )
        values = {
            kind: raw[f"Original Affinity {kind} nm"]
            if original
            else raw[f"Affinity {kind}"]
            for kind in ("Median", "Low", "High")
        }
        direct = measurement in {"Kd", "Ki", "pKd", "pKi"}
        structure = therapeutic.get("100% SI Structure", "")
        for acc in accs:
            output.append(
                observation(
                    by_acc[acc],
                    source="gtopdb",
                    source_record_id=f"interactions.csv:{number}",
                    binder_id="GTOPDB:" + raw["Ligand ID"],
                    binder_name=plain(raw["Ligand"]),
                    binder_type=raw["Ligand Type"],
                    endogenous=raw["Endogenous"],
                    approved=raw["Approved"],
                    target_scope="complex_component"
                    if complex_target
                    else "single_protein",
                    binding_evidence="quantitative_affinity"
                    if direct
                    else "curated_pharmacology",
                    measurement_type=measurement,
                    measurement_value=values["Median"],
                    measurement_low=values["Low"],
                    measurement_high=values["High"],
                    measurement_units=("nM" if original else "negative_log_molar")
                    if any(values.values())
                    else "",
                    measurement_relation=raw["Original Affinity Relation"]
                    if original
                    else "",
                    assay=plain(raw["Assay Description"])
                    or f"{raw['Type']}; {raw['Action']}",
                    epitope=raw["Receptor Site"],
                    epitope_evidence="named_receptor_site"
                    if raw["Receptor Site"]
                    else "not_reported",
                    sequence_available="yes"
                    if therapeutic.get("HeavySequence") not in (None, "", "na")
                    else "no",
                    structure_available=structure
                    if structure not in ("None", "na", "")
                    else "",
                    pmids=raw["PubMed ID"],
                    source_url=f"https://www.guidetopharmacology.org/GRAC/LigandDisplayForward?ligandId={raw['Ligand ID']}",
                )
            )
        audit[
            "complex_interactions" if complex_target else "single_protein_interactions"
        ] += 1
        if therapeutic:
            audit["interactions_with_thera_sequence_match"] += 1
    return output, audit


def antibody_observations(
    annotations: list[dict[str, Any]],
    by_hgnc: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, str]], set[str]]:
    # The public table can retain several schema versions. Prefer the newest
    # timestamp per stable gene ID rather than inflating coverage with old records.
    latest: dict[str, dict[str, Any]] = {}
    for record in annotations:
        gene = json.loads(record["gene_json"])
        hgnc = gene["hgnc_id"]
        if hgnc not in by_hgnc:
            continue
        if hgnc not in latest or (record.get("record_generated_at") or "") > (
            latest[hgnc].get("record_generated_at") or ""
        ):
            latest[hgnc] = record
    output = []
    for hgnc, record in latest.items():
        methods = json.loads(record["methods_json"] or "[]")
        for method_i, method in enumerate(methods):
            for ab_i, ab in enumerate(method.get("antibodies", [])):
                exact = any(
                    plain(ab.get(k)).lower()
                    not in ("", "unknown", "not reported", "n/a", "none")
                    for k in ("clone", "catalog", "rrid")
                )
                live = (
                    method.get("permeabilization") == "live_cell"
                    and method.get("accessibility_relevance")
                    == "direct_surface_accessibility"
                    and ab.get("antibody_epitope_region") != "intracellular"
                )
                identity = "|".join(
                    plain(ab.get(k)).casefold()
                    for k in ("name", "clone", "vendor", "catalog", "rrid")
                )
                binder_id = (
                    "REAGENT:" + hashlib.sha256(identity.encode()).hexdigest()[:16]
                )
                output.append(
                    observation(
                        by_hgnc[hgnc],
                        source="existing_annotation",
                        source_record_id=f"{hgnc}:method:{method_i}:antibody:{ab_i}",
                        binder_id=binder_id,
                        binder_name=plain(ab["name"]),
                        binder_type="Antibody",
                        exact_identity="yes" if exact else "no",
                        binding_evidence="literature_extraction_not_reaudited",
                        assay=f"{method.get('method_subclass', '')}; {method.get('permeabilization', '')}",
                        surface_evidence="live_cell_reported"
                        if live
                        else "not_established",
                        epitope=ab.get("antibody_epitope_region", "unknown"),
                        epitope_evidence="broad_region_only",
                        validation_strength=ab.get("validation_strength"),
                        validation_strategy=ab.get("validation_strategy"),
                        clone=ab.get("clone"),
                        vendor=ab.get("vendor"),
                        catalog=ab.get("catalog"),
                        rrid=ab.get("rrid"),
                        evidence_ids="|".join(method.get("cited_evidence_ids", [])),
                        source_url=f"https://api.deliverome.org/surfaceome/v1/genes/{by_hgnc[hgnc]['hgnc_symbol']}",
                    )
                )
    return output, set(latest)


def biogrid_table_rows(body: str) -> list[list[str]]:
    """Expand the three row-spanned target cells in BioGRID's interaction table."""
    result = []
    target_cells: list[str] = []
    for tr in re.findall(r"<tr\b[^>]*>(.*?)</tr>", body, flags=re.S):
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", tr, flags=re.S)
        if not cells:
            continue
        if len(cells) == 9:
            target_cells = cells[:3]
        elif len(cells) == 6 and target_cells:
            cells = target_cells + cells
        else:
            raise ValueError(f"Unexpected BioGRID row shape: {len(cells)}")
        result.append(cells)
    return result


def biogrid_observations(
    raw_dir: Path, by_hgnc: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, str]], Counter[str]]:
    pages = sorted(raw_dir.glob("biogrid_[0-9]*.json"))
    if not pages:
        raise ValueError("No BioGRID pages downloaded")
    proteins = [row for page in pages for row in json.loads(page.read_text())["data"]]
    if len({r[0] for r in proteins}) != len(proteins):
        raise ValueError("Duplicate BioGRID synthetic protein IDs")
    expected = json.loads(pages[0].read_text())["recordsFiltered"]
    if len(proteins) != expected:
        raise ValueError(f"Incomplete BioGRID table: {len(proteins)}/{expected}")
    output = []
    audit: Counter[str] = Counter(proteins_downloaded=len(proteins))
    for protein in proteins:
        match = re.search(r"data-id='(\d+)'", protein[5])
        if not match:
            raise ValueError("Missing BioGRID synthetic ID")
        file = raw_dir / f"biogrid_detail_{match[1]}.html"
        if not file.exists():
            audit["missing_detail_pages"] += 1
            continue
        for number, cells in enumerate(biogrid_table_rows(file.read_text())):
            if plain(cells[2]) != "Human":
                audit["nonhuman_interactions"] += 1
                continue
            target = re.search(r"data-geneid='(\d+)'", cells[0])
            if not target:
                raise ValueError("Missing target ID")
            mapping_file = raw_dir / f"biogrid_target_{target[1]}.html"
            if not mapping_file.exists():
                audit["missing_target_pages"] += 1
                continue
            stable_ids = set(re.findall(r"HGNC:\d+", mapping_file.read_text()))
            if len(stable_ids) != 1:
                audit["ambiguous_or_missing_hgnc_mapping"] += 1
                continue
            hgnc = stable_ids.pop()
            if hgnc not in by_hgnc:
                audit["outside_cohort"] += 1
                continue
            assay = re.search(
                r"class=['\"]systemColorBox[^'\"]*['\"]>(.*?)</div>", cells[4]
            )
            affinity = plain(cells[5])
            output.append(
                observation(
                    by_hgnc[hgnc],
                    source="biogrid_synthetic",
                    source_record_id=f"{protein[0]}:{number}",
                    binder_id="BIOGRID:" + protein[0],
                    binder_name=plain(protein[1]),
                    binder_type=plain(protein[3]),
                    binding_evidence="curated_experimental_interaction",
                    measurement_value="" if affinity == "-" else affinity,
                    measurement_type="affinity_type_not_specified"
                    if affinity != "-"
                    else "",
                    assay=plain(assay[1]) if assay else plain(cells[4]),
                    sequence_available="yes"
                    if re.search(r"[A-Z]{10}", plain(protein[2]))
                    else "no",
                    pmids="|".join(
                        sorted(
                            set(re.findall(r"pubmed.ncbi.nlm.nih.gov/(\d+)", cells[8]))
                        )
                    ),
                    source_url="https://thebiogrid.org/project/12",
                )
            )
            audit["matched_interactions"] += 1
    return output, audit


def coverage_rows(
    genes: list[dict[str, Any]], observations: list[dict[str, str]], annotated: set[str]
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in observations:
        grouped[row["hgnc_id"]].append(row)
    output = []
    for gene in genes:
        all_rows = grouped[gene["hgnc_id"]]
        rows = [
            r
            for r in all_rows
            if r["target_scope"] == "single_protein" and r["exact_identity"] == "yes"
        ]

        def count(selected: list[dict[str, str]]) -> int:
            return len({r["binder_id"] for r in selected})

        output.append(
            dict(
                gene,
                annotated=int(gene["hgnc_id"] in annotated),
                any_named_binder=int(bool(rows)),
                named_binder_ids=count(rows),
                gtopdb=int(any(r["source"] == "gtopdb" for r in rows)),
                natural_ligand=int(any(r["endogenous"] == "true" for r in rows)),
                approved_drug=int(any(r["approved"] == "true" for r in rows)),
                gtopdb_antibody=int(
                    any(
                        r["source"] == "gtopdb" and r["binder_type"] == "Antibody"
                        for r in rows
                    )
                ),
                existing_exact_antibody=int(
                    any(r["source"] == "existing_annotation" for r in rows)
                ),
                existing_any_antibody=int(
                    any(r["source"] == "existing_annotation" for r in all_rows)
                ),
                biogrid_designed_binder=int(
                    any(r["source"] == "biogrid_synthetic" for r in rows)
                ),
                biogrid_minibinder=int(
                    any(
                        r["source"] == "biogrid_synthetic"
                        and "minibinder" in r["binder_type"].lower()
                        for r in rows
                    )
                ),
                quantitative_affinity=int(
                    any(r["binding_evidence"] == "quantitative_affinity" for r in rows)
                ),
                quantitative_measurement=int(
                    any(
                        r["measurement_value"]
                        or r["measurement_low"]
                        or r["measurement_high"]
                        for r in rows
                    )
                ),
                live_cell_antibody=int(
                    any(r["surface_evidence"] == "live_cell_reported" for r in rows)
                ),
                validated_live_cell_antibody=int(
                    any(
                        r["surface_evidence"] == "live_cell_reported"
                        and r["validation_strength"] in ("moderate", "strong")
                        and r["validation_strategy"]
                        not in ("vendor_claim_only", "none", "unknown", "")
                        for r in rows
                    )
                ),
                antibody_sequence=int(
                    any(
                        r["binder_type"] == "Antibody"
                        and r["sequence_available"] == "yes"
                        for r in rows
                    )
                ),
                antibody_structure_lead=int(
                    any(r["structure_available"] for r in rows)
                ),
                complex_only=int(
                    bool(all_rows)
                    and not rows
                    and all(r["target_scope"] == "complex_component" for r in all_rows)
                ),
            )
        )
    return output


def write_tsv(
    path: Path, rows: list[dict[str, Any]], fields: tuple[str, ...] | None = None
) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fields or list(rows[0]),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-dir", type=Path, default=ROOT / "data/external/binder_coverage"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "data/analysis/binder_coverage"
    )
    args = parser.parse_args()
    raw, out = args.raw_dir, args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    identifiers = json.loads((raw / "identifiers.json").read_text())
    by_hgnc = unique_index(identifiers, "hgnc_id")
    with (
        ROOT / "data/processed/candidate_universe/candidate_universe.tsv"
    ).open() as stream:
        candidates = list(csv.DictReader(stream, delimiter="\t"))
    candidate_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        if row["hgnc_id"]:
            candidate_groups[row["hgnc_id"]].append(row)
    genes = []
    for hgnc, entries in sorted(candidate_groups.items()):
        if hgnc not in by_hgnc:
            continue
        gene: dict[str, Any] = {k: str(by_hgnc[hgnc].get(k) or "") for k in ID_FIELDS}
        gene["triage_classical_receptor"] = int(
            any(r["sonnet_reason"] == "classical_surface_receptor" for r in entries)
        )
        gene["triage_surface_yes"] = int(
            any(r["sonnet_verdict"] == "yes" for r in entries)
        )
        genes.append(gene)
    cohort = {g["hgnc_id"]: g for g in genes}
    observations, gtop_audit = gtop_observations(
        read_csv(raw / "gtop_interactions.txt", gtop=True),
        read_csv(raw / "gtop_ligands.txt", gtop=True),
        read_csv(raw / "thera.csv"),
        unique_index(genes, "uniprot_acc"),
    )
    antibody_rows, annotated = antibody_observations(
        json.loads((raw / "annotations.json").read_text()), cohort
    )
    synthetic, biogrid_audit = biogrid_observations(raw, cohort)
    observations.extend(antibody_rows)
    observations.extend(synthetic)
    observations.sort(
        key=lambda r: (r["hgnc_id"], r["source"], r["binder_id"], r["source_record_id"])
    )
    coverage = coverage_rows(genes, observations, annotated)
    metrics = [
        k
        for k in coverage[0]
        if k
        not in (
            *ID_FIELDS,
            "triage_classical_receptor",
            "triage_surface_yes",
            "named_binder_ids",
        )
    ]
    summary = []
    for name, subset in [
        ("candidate_genes", coverage),
        (
            "triage_classical_receptors",
            [r for r in coverage if r["triage_classical_receptor"]],
        ),
        ("triage_surface_yes", [r for r in coverage if r["triage_surface_yes"]]),
        ("annotated_candidates", [r for r in coverage if r["annotated"]]),
    ]:
        for metric in metrics:
            count = sum(int(r[metric]) for r in subset)
            summary.append(
                dict(
                    cohort=name,
                    metric=metric,
                    genes=count,
                    denominator=len(subset),
                    percent=round(100 * count / len(subset), 2) if subset else 0,
                )
            )
    write_tsv(out / "observations.tsv", observations, FIELDS)
    (out / "observations.tsv.gz").write_bytes(
        gzip.compress((out / "observations.tsv").read_bytes(), mtime=0)
    )
    write_tsv(out / "gene_coverage.tsv", coverage)
    write_tsv(out / "coverage_summary.tsv", summary)
    audit = dict(
        candidate_rows=len(candidates),
        candidate_unique_hgnc=len(candidate_groups),
        missing_canonical_ids=sorted(set(candidate_groups) - set(cohort)),
        gtopdb=dict(gtop_audit),
        biogrid=dict(biogrid_audit),
        observation_count=len(observations),
    )
    (out / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    (out / "source_manifest.json").write_bytes((raw / "sources.json").read_bytes())
    inputs = [
        *raw.glob("*.json"),
        *raw.glob("*.html"),
        raw / "gtop_interactions.txt",
        raw / "gtop_ligands.txt",
        raw / "thera.csv",
        ROOT / "data/processed/candidate_universe/candidate_universe.tsv",
    ]
    manifest = dict(
        generated_at=utc_now_iso(),
        generator="src/accessible_surfaceome/binders/coverage.py",
        generator_sha256=sha256_file(Path(__file__)),
        inputs=[
            dict(path=str(p.relative_to(ROOT)), sha256=sha256_file(p))
            for p in sorted(inputs)
        ],
        outputs=[
            dict(path=str(p.relative_to(ROOT)), sha256=sha256_file(p))
            for p in sorted([*out.glob("*.tsv"), out / "observations.tsv.gz"])
        ],
        assumptions=[
            "Unique HGNC genes, not accession rows, form denominators.",
            "Receptor subset means triage reason classical_surface_receptor, not all possible receptors.",
            "Complex-component associations are retained but excluded from named single-protein binder coverage.",
            "Exact existing antibody requires clone, catalog, or RRID; extracted metadata has not been independently reaudited.",
            "Thera sequence-name matches enrich IUPHAR pairs; they do not add symbol-mapped targets.",
            "Thera exact-sequence structure hits are leads, not verified antigen complexes or residue epitopes.",
            "Residue-level epitope coverage has not been measured by this pilot.",
            "BioGRID Surface Display is not assumed to be mammalian live-cell binding.",
            "Binder counts are source IDs; cross-source identities are not fully deduplicated.",
        ],
    )
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(audit, indent=2))
    for r in summary:
        if r["cohort"] == "triage_classical_receptors":
            print(r)


if __name__ == "__main__":
    main()
