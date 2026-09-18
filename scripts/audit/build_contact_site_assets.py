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
from itertools import chain
from pathlib import Path
from typing import TypedDict

from accessible_surfaceome.binders.contact_identity import annotate_identities
from accessible_surfaceome.binders.contact_constructs import (
    accepted_construct_updates,
    load_accepted_constructs,
)

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data/analysis/deep_dive_binding_sites"
OUTPUT = ROOT / "viewer/public/data/contact-sites"


class SourceCounts(TypedDict):
    genes: set[str]
    sites: int
    ec_genes: set[str]
    ec_sites: int


def reviewed_chemical_rows():
    """Accept only individually reviewed, canonical-coordinate chemical pairs."""
    review_bytes = (INPUT / "reviewed_chemical_contacts.json").read_bytes()
    payload = json.loads(review_bytes)
    for row in payload["records"]:
        if row["mapping_issues"] or row["tier"] != "reviewed_chemical_contacts":
            raise ValueError("Reviewed chemical contacts must have valid mappings")
    ledger = json.loads((INPUT / "reviewed_chemical_validation.json").read_text())
    if (
        ledger.get("review_sha256") != hashlib.sha256(review_bytes).hexdigest()
        or ledger.get("validator_sha256")
        != hashlib.sha256(
            (
                ROOT / "src/accessible_surfaceome/binders/contact_coordinates.py"
            ).read_bytes()
        ).hexdigest()
        or not ledger.get("ok")
        or ledger.get("errors")
        or len(ledger.get("records", [])) != len(payload["records"])
        or any(item.get("status") != "verified" for item in ledger["records"])
        or [item.get("record_index") for item in ledger["records"]]
        != list(range(len(payload["records"])))
    ):
        raise ValueError(
            "Reviewed chemicals require a current successful coordinate validation ledger"
        )
    yield from payload["records"]


def normalize(row):
    """Keep mapped contacts/epitopes; never turn IntAct constructs into contacts."""
    if row["tier"].startswith("intact_") or row["context"] == "invalid_mapping":
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
    site = dict(
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
    if row["context"] == "removed_processing_segment":
        site.update(
            exclude_from_ec_overview=True,
            processing_status="overlaps_annotated_processing_segment",
            identity_note="Experimental contacts overlap an annotated signal, transit or propeptide segment. Retained as processed-domain/precursor evidence; mature extracellular accessibility is not established.",
        )
    return site


def apply_partner_review(site, acc, reviews, matches):
    """Apply explicit stable-target/label/structure decisions; preserve source labels."""
    if acc not in reviews["targets"]:
        return

    def identity_label(value):
        value = re.sub(r"\s+(Fab|Fv|VHH)$", "", value, flags=re.I)
        return re.sub(r"\s*\([^)]*\)\s*$", "", value).strip().casefold()

    matching_rules = []
    for rule in reviews["rules"]:
        names = {identity_label(name) for name in rule["names"]}
        if rule["uniprot_acc"] != acc or not names.intersection(
            {
                identity_label(site["partner"]),
                identity_label(site.get("partner_label", "")),
            }
        ):
            continue
        if rule["pdb"] and rule["pdb"] != site["pdb"]:
            continue
        matching_rules.append(rule)
    if matching_rules:
        # A deposited construct correction must beat a broad parent-antibody
        # alias regardless of the order of curated rules in the file.
        specificity = max(bool(rule["pdb"]) for rule in matching_rules)
        matching_rules = [
            rule for rule in matching_rules if bool(rule["pdb"]) == specificity
        ]
        identities = {
            (
                rule["canonical_name"],
                rule["category"],
                rule["exclude_from_overview"],
                bool(rule.get("exclude_from_ec_overview")),
            )
            for rule in matching_rules
        }
        if len(identities) != 1:
            raise ValueError(
                f"Conflicting contact reviews: {acc} {site['partner']} {site['pdb']}"
            )
        rule = matching_rules[0]
        site.update(
            canonical_partner_label=rule["canonical_name"],
            category=rule["category"],
            category_reference=rule["reference"],
            category_reason=rule["reason"],
        )
        if rule["exclude_from_overview"]:
            site["exclude_from_overview"] = True
        if rule.get("exclude_from_ec_overview"):
            site["exclude_from_ec_overview"] = True
        site["review_date"] = reviews["review_date"]
    if site["source"] == "Thera-SAbDab":
        hits = matches.get((acc, site["partner"].casefold(), site["pdb"]), [])
        site["identity_evidence"] = (
            "sequence_matched_antibody_arm" if hits else "therapeutic_catalogue_link"
        )
        site["identity_matches"] = hits
        site["evidence"] = (
            "Contacts from a sequence-matched antibody arm"
            if hits
            else "Therapeutic-linked structural contacts (match unresolved)"
        )
        site["identity_note"] = (
            "The deposited complex supplies the contact residues. The therapeutic link is based on an antibody variable-region/arm match, not proof that the complete named drug was crystallized."
        )
    elif site["category"] == "unclassified" and not site.get("category_reason"):
        site["category_reason"] = (
            "Reviewed source label retained; its role or clinical identity is not established by the available record."
        )


def main():
    constructs = load_accepted_constructs(
        INPUT / "accepted_constructs.json", INPUT / "contact_construct_suggestions.json"
    )
    reviews = json.loads((INPUT / "reviewed_contact_partners.json").read_text())
    matches = defaultdict(list)
    with gzip.open(INPUT / "therapeutic_aacdb_evidence.tsv.gz", "rt") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            if (
                row["source"] == "Thera-SAbDab"
                and row["uniprot_acc"] in reviews["targets"]
            ):
                hit = {
                    key: row[key]
                    for key in [
                        "match_method",
                        "arm",
                        "antibody_chains",
                        "antigen_chain",
                    ]
                }
                key = (
                    row["uniprot_acc"],
                    row["therapeutic"].casefold(),
                    row["pdb_id"].lower(),
                )
                if hit not in matches[key]:
                    matches[key].append(hit)
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
                genes[acc].update(reviews.get("target_notes", {}).get(acc, {}))
    seen = defaultdict(set)
    with gzip.open(INPUT / "structural_intact_evidence.tsv.gz", "rt") as handle:
        for row in chain(
            csv.DictReader(handle, delimiter="\t"), reviewed_chemical_rows()
        ):
            site = normalize(row)
            if site is None:
                continue
            if row["tier"] == "reviewed_chemical_contacts":
                site["method"] = row["method"]
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
                site["catalogue_identity_key"] = "therasabdab:" + category_name
            endogenous = categories["endogenous_pairs"].get(f"{acc}|{site['partner']}")
            if endogenous:
                site["category"] = endogenous
                site["category_reference"] = (
                    "https://www.guidetopharmacology.org/download.jsp"
                )
                if ligand:
                    site["catalogue_identity_key"] = "iuphar:" + (
                        ligand.get("uniprot_acc") or site["partner"]
                    )
            if review:
                site["reviewed_identity_label"] = category_name
                site["category"] = review["category"]
                site["category_reference"] = review["reference"]
                site["category_reason"] = review["reason"]
                if review.get("canonical_name"):
                    site["canonical_partner_label"] = review["canonical_name"]
            apply_partner_review(site, acc, reviews, matches)
            updates = accepted_construct_updates(site, acc, constructs)
            if updates:
                previous_note = site.get("identity_note", "")
                site.update(updates)
                if previous_note:
                    site["identity_note"] = previous_note + " " + site["identity_note"]
            if site.get("processing_status"):
                note = "Contacts overlap an annotated processing segment; mature extracellular accessibility is not established."
                site["identity_note"] = site.get("identity_note", "") + " " + note
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
    annotate_identities(genes)
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
        partner_review_sha256=hashlib.sha256(
            (INPUT / "reviewed_contact_partners.json").read_bytes()
        ).hexdigest(),
        accepted_constructs_sha256=hashlib.sha256(
            (INPUT / "accepted_constructs.json").read_bytes()
        ).hexdigest(),
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
        reviewed_chemical_sha256=hashlib.sha256(
            (INPUT / "reviewed_chemical_contacts.json").read_bytes()
        ).hexdigest(),
        coordinate_validation_sha256=hashlib.sha256(
            (INPUT / "reviewed_chemical_validation.json").read_bytes()
        ).hexdigest(),
        identity_policy="scoped_identity_v2: chemical IDs, verified constructs, target-reviewed aliases, catalogue IDs, parent protein groups and source-scoped groups; groups are not complete molecule equivalence",
        audited_genes=len(genes),
        covered_genes=sum(bool(g["sites"]) for g in genes.values()),
        site_definition="Unique source, partner, PDB, canonical residue set, context and reference; sources may describe the same interface. Audit snapshot, not exhaustive DB coverage.",
        excluded="IntAct regions and mutation effects; invalid mappings; ambiguous gene mappings. Processing-segment contacts are retained only outside the extracellular overview.",
        sources=summary,
    )
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
