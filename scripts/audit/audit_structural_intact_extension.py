"""Compare unrestricted structural interfaces and IntAct features across 5,130 genes.

Structural candidates, binding regions and mutation effects remain distinct tiers.
"""

import csv
import gzip
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from accessible_surfaceome.binders.coverage import write_tsv
from accessible_surfaceome.binders.site_context import (
    EXOPLASMIC_CONTEXTS,
    EXTRACELLULAR_CONTEXTS,
    feature_records,
    site_context,
    validate_feature,
)
from summarize_binding_sites import load_uniprot, pdb_sites

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/external/structural_intact_extension"
OUT = ROOT / "data/analysis/deep_dive_binding_sites"
ID_FIELDS = ["hgnc_id", "hgnc_symbol", "uniprot_acc", "ensembl_gene", "ncbi_gene_id"]


def proteins():
    result = {}
    for path in (RAW / "uniprot").glob("*.json"):
        result.update(
            {
                r["primaryAccession"]: r
                for r in json.loads(path.read_text()).get("data", {}).get("results", [])
            }
        )
    return result


def positions(text):
    if not text:
        return []
    return [int(p) for p in re.split(r"[,;]", text)]


def existing_evidence():
    with gzip.open(OUT / "observations.tsv.gz", "rt") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row["evidence"] == "curated_epitope_region":
                continue
            if row["source"] == "PDBe" and not json.loads(row["details"]).get(
                "iuphar_ligand_ids"
            ):
                continue
            yield (
                row["uniprot_acc"],
                row["source"],
                row["binder_id"],
                row["pdb_id"],
                positions(row["residues"]),
                row["reference"],
            )
    with gzip.open(OUT / "biolip_gpcrdb_evidence.tsv.gz", "rt") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row["evidence_type"] == "binding_mutagenesis_not_direct_epitope":
                continue
            yield (
                row["uniprot_acc"],
                row["source"],
                row["binder"],
                row["pdb_id"],
                positions(row["canonical_positions"]),
                row["reference"],
            )
    with gzip.open(OUT / "therapeutic_aacdb_evidence.tsv.gz", "rt") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            yield (
                row["uniprot_acc"],
                row["source"],
                row["binder_name"],
                row["pdb_id"],
                positions(row["positions"]),
                row["reference"],
            )


def main():
    genes = list(
        csv.DictReader((OUT / "all_source_comparison_genes.tsv").open(), delimiter="\t")
    )
    assert len(genes) == 5130 and len({g["hgnc_id"] for g in genes}) == 5130
    index = {g["uniprot_acc"]: g for g in genes if g["identifier_status"] == "unique"}
    assert len(index) == 5106
    ps = proteins()
    old = load_uniprot()
    stats = Counter()
    hits = defaultdict(set)
    evidence = []
    failures = []

    overrides = {
        (r["hgnc_id"], r["pdb_id"]): r
        for r in csv.DictReader(
            (OUT / "structural_site_context_overrides.tsv").open(), delimiter="\t"
        )
    }

    def add(acc, source, partner, pdb, pos, reference, tier, **extra):
        if acc not in index or acc not in ps:
            return
        context = site_context(pos, ps[acc])
        g = index[acc]
        override = overrides.get((g["hgnc_id"], pdb.lower()))
        if override:
            extra["context_before_review"] = context
            extra["context_review_reason"] = override["reason"]
            extra["context_review_reference"] = override["reference"]
            context = override["context"]
        row = {k: g[k] for k in ID_FIELDS}
        row.update(
            source=source,
            partner=partner,
            pdb_id=pdb,
            positions=",".join(map(str, pos)),
            context=context,
            reference=reference,
            tier=tier,
            **extra,
        )
        evidence.append(row)
        if context not in {"invalid_mapping", "removed_processing_segment"}:
            hits[tier].add(acc)
            if context in EXTRACELLULAR_CONTEXTS:
                hits[tier + "_ec"].add(acc)
            if context in EXOPLASMIC_CONTEXTS:
                hits[tier + "_exoplasmic"].add(acc)
        stats[source + ":" + context] += 1

    for acc, source, partner, pdb, pos, ref in existing_evidence():
        if acc not in index or acc not in ps:
            continue
        if (
            old.get(acc, {}).get("sequence", {}).get("value")
            != ps[acc]["sequence"]["value"]
        ):
            stats["existing_reference_sequence_changed"] += 1
            continue
        add(acc, source, partner, pdb, pos, ref, "existing_reclassified")
    for acc, g in index.items():
        path = RAW / "interfaces" / f"{acc}.json"
        if not path.exists():
            failures.append(
                {"uniprot_acc": acc, "source": "PDBe", "status": "not_retrieved"}
            )
            continue
        payload = json.loads(path.read_text())
        stats["pdbe_http_" + str(payload["status"])] += 1
        record = payload.get("data", {}).get(acc, {})
        if not record:
            continue
        if acc not in ps:
            continue
        seq = record.get("sequence", "")
        if seq and seq != ps[acc]["sequence"]["value"]:
            failures.append(
                {
                    "uniprot_acc": acc,
                    "source": "PDBe",
                    "status": "reference_sequence_mismatch",
                }
            )
            continue
        for partner in record.get("data", []):
            partner_id = partner.get("accession", "")
            # Anonymous partners, nucleic acids and same-protein contacts cannot establish an exact non-self protein binder.
            if not re.fullmatch(
                r"(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-\d+)?",
                partner_id,
            ):
                stats["pdbe_partner_identity_unresolved"] += 1
                continue
            if partner_id.split("-")[0] == acc:
                continue
            for pdb, pos in pdb_sites(partner).items():
                add(
                    acc,
                    "PDBe unrestricted",
                    partner_id,
                    pdb,
                    pos,
                    "https://www.rcsb.org/structure/" + pdb,
                    "unrestricted_structural",
                    confidence="experimental interface; physiological relevance not independently established",
                    pair_scope="nonself_protein",
                    source_record_id=f"{acc}:{partner_id}:{pdb}",
                )
    fallback = RAW / "fallback_contacts.json"
    if fallback.exists():
        for row in json.loads(fallback.read_text()):
            if row["status"] == "mapped":
                add(
                    row["uniprot_acc"],
                    "PDB coordinate fallback",
                    row["partner_accession"],
                    row["pdb_id"],
                    row["positions"],
                    "https://www.rcsb.org/structure/" + row["pdb_id"],
                    "unrestricted_structural",
                    confidence="5A heavy-atom contacts; target residue identities checked; biological relevance unreviewed",
                    source_record_id=f"{row['pdb_id']}:{row['target_chain']}:{row['partner_chain']}",
                )
            else:
                stats["fallback_" + row["status"]] += 1
    negative_ids = set()
    for line in (RAW / "intact_negative.txt").read_text().splitlines():
        fields = line.split("\t")
        if len(fields) > 35 and fields[35].lower() == "true":
            negative_ids.update(re.findall(r"EBI-\d+", fields[13]))
    stats["negative_interaction_ids"] = len(negative_ids)
    feature_attempts = []
    seen = set()
    feature_pairs = set()
    for filename, kind in [
        ("bindings_regions.tsv", "intact_binding_region"),
        ("mutations.tsv", "intact_mutation_effect"),
    ]:
        for header, values in feature_records(RAW / filename):
            if len(values) != len(header):
                stats["intact_malformed_record"] += 1
                continue
            r = dict(zip(header, values, strict=True))
            raw_id = r["Affected molecule identifier"]
            match = re.fullmatch(r"uniprotkb:([A-Z0-9]+)(?:-(\d+))?", raw_id)
            if not match or match[1] not in index:
                continue
            acc = match[1]
            if "taxid:9606(" not in r["Affected molecule organism"]:
                stats["intact_wrong_species"] += 1
                continue
            key = (kind, r["# Feature AC"], r["Interaction AC"])
            if key in seen:
                continue
            seen.add(key)
            feature_type = r["Feature type"]
            partner_ids = sorted(
                set(
                    re.findall(
                        r"uniprotkb:([A-Z0-9]+(?:-\d+)?)", r["Interaction participants"]
                    )
                )
                - {raw_id.removeprefix("uniprotkb:")}
            )
            is_effect = bool(
                re.search(
                    r"mutation (?:decreasing|increasing|disrupting)", feature_type
                )
            )
            selected = kind == "intact_binding_region" or is_effect
            pos, status = validate_feature(
                r["Feature range(s)"],
                r["Original sequence"],
                ps.get(acc, {}).get("sequence", {}).get("value", ""),
            )
            # Explicit non-self protein partner required for this binder audit.
            partners = [p for p in partner_ids if p.split("-")[0] != acc]
            if not partners:
                status = "no_identified_nonself_protein_partner"
            if not selected:
                status = "neutral_or_unclassified_mutation"
            if (
                status == "exact_sequence"
                and kind == "intact_binding_region"
                and len(pos) == len(ps[acc]["sequence"]["value"])
            ):
                status = "whole_protein_not_localized"
            if set(re.findall(r"EBI-\d+", r["Interaction AC"])) & negative_ids:
                status = "negative_interaction"
            attempt = {k: index[acc][k] for k in ID_FIELDS}
            attempt.update(
                source=kind,
                feature_id=r["# Feature AC"],
                interaction_id=r["Interaction AC"],
                feature_type=feature_type,
                range=r["Feature range(s)"],
                source_accession=raw_id,
                status=status,
                partner_accessions=";".join(partners),
                reference=r["PubMed ID"],
                feature_annotation=r["Feature annotation(s)"],
            )
            feature_attempts.append(attempt)
            stats[kind + ":" + status] += 1
            if status != "exact_sequence":
                continue
            for partner in partners:
                feature_pairs.add((acc, partner.split("-")[0]))
            add(
                acc,
                "IntAct",
                ";".join(partners),
                "",
                pos,
                r["PubMed ID"],
                kind,
                source_record_id=r["# Feature AC"],
                feature_type=feature_type,
                interaction_id=r["Interaction AC"],
                range=r["Feature range(s)"],
                partner_scope="binary" if len(partners) == 1 else "complex",
                source_accession=raw_id,
                feature_annotation=r["Feature annotation(s)"],
                confidence="reported region, not residue contacts"
                if kind == "intact_binding_region"
                else "mutation affects interaction; indirect folding effects possible",
            )
    for row in evidence:
        row["intact_pair_feature_support"] = (
            int((row["uniprot_acc"], row["partner"].split("-")[0]) in feature_pairs)
            if row["tier"] == "unrestricted_structural"
            else ""
        )
        if row["intact_pair_feature_support"] == 1:
            hits["structural_with_intact_feature_support"].add(row["uniprot_acc"])
            if row["context"] in EXTRACELLULAR_CONTEXTS:
                hits["structural_with_intact_feature_support_ec"].add(
                    row["uniprot_acc"]
                )
    baseline = {
        g["uniprot_acc"]
        for g in genes
        if g["all_experimental_union_after_antibody_extension"] == "1"
    }
    baseline_ec = {
        g["uniprot_acc"]
        for g in genes
        if g["all_experimental_ec_union_after_antibody_extension"] == "1"
    }
    hits["previous_structural_union"] = baseline
    hits["previous_strict_ec"] = baseline_ec
    hits["reclassified_plus_structural"] = (
        hits["existing_reclassified"] | hits["unrestricted_structural"]
    )
    hits["reclassified_plus_structural_ec"] = (
        hits["existing_reclassified_ec"] | hits["unrestricted_structural_ec"]
    )
    hits["reclassified_plus_structural_exoplasmic"] = (
        hits["existing_reclassified_exoplasmic"]
        | hits["unrestricted_structural_exoplasmic"]
    )
    hits["structural_or_region_ec"] = (
        hits["reclassified_plus_structural_ec"] | hits["intact_binding_region_ec"]
    )
    hits["structural_region_or_mutation_ec"] = (
        hits["structural_or_region_ec"] | hits["intact_mutation_effect_ec"]
    )
    summary = []
    for name, covered in sorted(hits.items()):
        for subset in ["all", "llm_ligand_yes"]:
            eligible = {
                g["uniprot_acc"]
                for g in genes
                if g["identifier_status"] == "unique"
                and (subset == "all" or g["llm_known_ligand"] == "yes")
            }
            den = 5130 if subset == "all" else 3157
            summary.append(
                {
                    "metric": name,
                    "subset": subset,
                    "genes": len(covered & eligible),
                    "denominator": den,
                    "percent": round(100 * len(covered & eligible) / den, 2),
                    "beyond_previous_ec": len((covered - baseline_ec) & eligible)
                    if name.endswith("_ec")
                    else "",
                    "beyond_previous_any_site": len((covered - baseline) & eligible),
                    "beyond_revised_structural_ec": len(
                        (covered - hits["reclassified_plus_structural_ec"]) & eligible
                    )
                    if name.endswith("_ec")
                    else "",
                }
            )
    for g in genes:
        for name, covered in hits.items():
            g["extension_" + name] = int(
                g["identifier_status"] == "unique" and g["uniprot_acc"] in covered
            )
    all_fields = list(dict.fromkeys(k for r in evidence for k in r))
    write_tsv(OUT / "structural_intact_evidence.tsv", evidence, tuple(all_fields))
    raw = (OUT / "structural_intact_evidence.tsv").read_bytes()
    (OUT / "structural_intact_evidence.tsv.gz").write_bytes(gzip.compress(raw, mtime=0))
    write_tsv(OUT / "structural_intact_attempts.tsv", feature_attempts)
    attempts_raw = (OUT / "structural_intact_attempts.tsv").read_bytes()
    (OUT / "structural_intact_attempts.tsv.gz").write_bytes(
        gzip.compress(attempts_raw, mtime=0)
    )
    write_tsv(OUT / "structural_intact_summary.tsv", summary)
    write_tsv(OUT / "structural_intact_genes.tsv", genes)
    if failures:
        write_tsv(OUT / "structural_intact_failures.tsv", failures)
    if (RAW / "fallback_contacts.json").exists():
        (OUT / "structural_fallback_contacts.json.gz").write_bytes(
            gzip.compress((RAW / "fallback_contacts.json").read_bytes(), mtime=0)
        )
    manifest = {
        "sources": {
            "uniprot": "https://rest.uniprot.org/uniprotkb/search",
            "pdbe": "https://www.ebi.ac.uk/pdbe/api/uniprot/interface_residues/{accession}",
            "intact": "https://ftp.ebi.ac.uk/pub/databases/intact/current/psimitab/",
            "intact_export_date": "2026-01-14",
            "coordinates": "https://www.ebi.ac.uk/pdbe/entry-files/download/{pdb}.cif",
            "sifts": "https://ftp.ebi.ac.uk/pub/databases/msd/sifts/xml/{pdb}.xml.gz",
        },
        "cohort": 5130,
        "llm_ligand_yes": 3157,
        "unique_gene_proteins": len(index),
        "uniprot_records": len(ps),
        "stats": dict(stats),
        "unretrieved_or_mismapped": failures,
        "evidence_rows": len(evidence),
        "feature_attempts": len(feature_attempts),
        "definitions": {
            "ec": "explicit extracellular or mature cell-membrane GPI site",
            "exoplasmic": "ec plus mature secreted sites; not proof of membrane display",
            "structural": "existing source-qualified evidence or non-self named protein interfaces; physiological relevance not automatically established",
            "intact": "sequence-checked regions and effect mutations kept separate; neutral mutations excluded",
        },
        "input_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                OUT / "all_source_comparison_genes.tsv",
                OUT / "structural_site_context_overrides.tsv",
                OUT / "observations.tsv.gz",
                OUT / "biolip_gpcrdb_evidence.tsv.gz",
                OUT / "therapeutic_aacdb_evidence.tsv.gz",
                RAW / "bindings_regions.tsv",
                RAW / "mutations.tsv",
                RAW / "intact_negative.txt",
                *sorted(RAW.glob("fallback_*.json")),
                *sorted((RAW / "coordinates").glob("*.cif")),
                *sorted((RAW / "sifts").glob("*.xml.gz")),
                *sorted((RAW / "uniprot").glob("*.json")),
                *sorted((RAW / "interfaces").glob("*.json")),
            ]
        },
    }
    (OUT / "structural_intact_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(
        json.dumps({k: v for k, v in manifest.items() if k != "input_sha256"}, indent=2)
    )
    for row in summary:
        if row["subset"] == "llm_ligand_yes":
            print(row)


if __name__ == "__main__":
    main()
