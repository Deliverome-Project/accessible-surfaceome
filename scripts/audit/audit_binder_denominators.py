"""Site-independent CellPhoneDB and Thera-SAbDab benchmarks for the frozen cohort."""

import argparse
import csv
import gzip
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import httpx

from accessible_surfaceome.binders.coverage import ID_FIELDS, write_tsv
from accessible_surfaceome.binders.site_context import (
    EXOPLASMIC_CONTEXTS,
    EXTRACELLULAR_CONTEXTS,
)
from audit_structural_intact_extension import proteins

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/external/binder_denominators"
OUT = ROOT / "data/analysis/deep_dive_binding_sites"
CPDB_COMMIT = "71ffa8a163389913907d40993bec2821a111f64d"
HGNC = ROOT / "data/external/hgnc/hgnc_complete_set.tsv"
URLS = {
    **{
        f"cpdb_{k}.csv": f"https://raw.githubusercontent.com/ventolab/cellphonedb-data/{CPDB_COMMIT}/data/{k}_input.csv"
        for k in ("interaction", "protein", "complex")
    },
    "thera.csv": "https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/static/downloads/TheraSAbDab_SeqStruc_OnlineDownload.csv",
}


def read(path, delimiter=","):
    with path.open(encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def location_class(protein):
    """Gene-level compartment evidence, including explicitly annotated isoforms."""
    locations = {
        x.get("location", {}).get("value", "")
        for c in protein.get("comments", [])
        if c.get("commentType") == "SUBCELLULAR LOCATION"
        for x in c.get("subcellularLocations", [])
    }
    membrane = any(
        "cell membrane" in x.lower() or "cell surface" in x.lower() for x in locations
    )
    inferred = "Membrane" in locations and any(
        f["type"] == "Topological domain" and f.get("description") == "Extracellular"
        for f in protein.get("features", [])
    )
    secreted = any(x.startswith("Secreted") for x in locations)
    if membrane:
        return "membrane_and_secreted" if secreted else "membrane"
    if inferred:
        return "membrane_inferred_and_secreted" if secreted else "membrane_inferred"
    return "secreted_only" if secreted else "other_or_uncertain"


def endpoint(name, complexes):
    if name not in complexes:
        return "protein", name, (name,)
    row = complexes[name]
    if "_by" in name or "biosynthesis_enzyme" in row.get("other_desc", ""):
        # Multiple biosynthetic routes describe one chemical, not separate ligands.
        return "chemical", name.split("_by", 1)[0], ()
    members = tuple(
        sorted({row[f"uniprot_{i}"] for i in range(1, 6) if row[f"uniprot_{i}"]})
    )
    return "complex", name, members


def hgnc_names(rows):
    approved, aliases = {}, defaultdict(set)
    for r in rows:
        if r["status"] != "Approved":
            continue
        approved[r["symbol"].upper()] = r["hgnc_id"]
        for field in ("alias_symbol", "prev_symbol", "cd"):
            for name in r[field].split("|"):
                if name:
                    aliases[name.upper()].add(r["hgnc_id"])
    return approved, aliases


def resolve_component(component, approved, aliases):
    """Source free text -> HGNC, with approved names preferred over colliding aliases."""
    if re.search(r"canine|feline|veterinary", component, re.I):
        return set(), "nonhuman_target"
    if component.strip() in {"CD3", "CD8"} or re.match(
        r"ITGA[A-Z0-9]+B[0-9]+(?:/|$)", component
    ):
        return set(), "complex_target_not_direct_subunit"
    raw_tokens = [re.sub(r"\s*\([^)]*\)", "", x).strip() for x in component.split("/")]
    exact = {approved[t] for t in raw_tokens if t in approved}
    tokens = [t.upper() for t in raw_tokens]
    if not exact:
        exact = {approved[t] for t in tokens if t in approved}
    if len(exact) == 1:
        return exact, "approved_symbol"
    if len(exact) > 1:
        return exact, "ambiguous_slash_group"
    found = set().union(*(aliases.get(t, set()) for t in tokens))
    return found, "unique_alias" if len(
        found
    ) == 1 else "ambiguous_alias" if found else "unresolved_or_nonprotein"


def is_site_compatible(context, location):
    return context in (
        EXOPLASMIC_CONTEXTS if location == "secreted_only" else EXTRACELLULAR_CONTEXTS
    )


def fetch():
    RAW.mkdir(parents=True, exist_ok=True)
    for name, url in URLS.items():
        path = RAW / name
        if not path.exists():
            response = httpx.get(url, timeout=120, follow_redirects=True)
            response.raise_for_status()
            path.write_bytes(response.content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    if args.fetch:
        fetch()
    genes = read(OUT / "structural_intact_genes.tsv", "\t")
    assert len(genes) == len({g["hgnc_id"] for g in genes}) == 5130
    by_id = {g["hgnc_id"]: g for g in genes}
    by_acc = {g["uniprot_acc"]: g for g in genes if g["identifier_status"] == "unique"}
    ps = proteins()
    for g in genes:
        g["binder_target_location"] = location_class(ps.get(g["uniprot_acc"], {}))
    with gzip.open(OUT / "structural_intact_evidence.tsv.gz", "rt") as handle:
        evidence = list(csv.DictReader(handle, delimiter="\t"))
    structural = defaultdict(list)
    regions = defaultdict(list)
    antibody = defaultdict(list)
    therapeutic = defaultdict(list)
    for e in evidence:
        if e["context"] in {"invalid_mapping", "removed_processing_segment"}:
            continue
        if e["tier"] == "unrestricted_structural":
            structural[e["hgnc_id"], e["partner"]].append(e)
        if e["tier"] == "intact_binding_region" and e["partner_scope"] == "binary":
            regions[e["hgnc_id"], e["partner"]].append(e)
        if e["source"] in {"SAbDab", "AACDB", "IEDB", "Thera-SAbDab"}:
            antibody[e["hgnc_id"]].append(e)
        if e["source"] == "Thera-SAbDab":
            therapeutic[e["hgnc_id"], e["partner"].casefold()].append(e)
    complexes = {r["complex_name"]: r for r in read(RAW / "cpdb_complex.csv")}
    interactions = read(RAW / "cpdb_interaction.csv")
    cp_pairs = {}
    proxy_members = set()
    for i, r in enumerate(interactions, 2):
        sides = [endpoint(r[k], complexes) for k in ("partner_a", "partner_b")]
        for target_i, partner_i in ((0, 1), (1, 0)):
            target, partner = sides[target_i], sides[partner_i]
            if target[0] == "chemical":
                original = r["partner_a" if target_i == 0 else "partner_b"]
                proxy_members.update(
                    complexes[original][f"uniprot_{n}"]
                    for n in range(1, 6)
                    if complexes[original][f"uniprot_{n}"]
                )
                continue
            for acc in target[2]:
                if acc not in by_acc:
                    continue
                g = by_acc[acc]
                key = (g["hgnc_id"], partner[0], partner[1], target[0], target[1])
                if key not in cp_pairs:
                    cp_pairs[key] = {
                        **{k: g[k] for k in ID_FIELDS},
                        "binder_target_location": g["binder_target_location"],
                        "target_unit": target[1],
                        "target_scope": target[0],
                        "partner_type": partner[0],
                        "partner_id": partner[1],
                        "partner_members": ";".join(partner[2]),
                        "source_rows": set(),
                        "references": set(),
                        "directions": set(),
                    }
                cp_pairs[key]["source_rows"].add(str(i))
                cp_pairs[key]["references"].add(r["source"])
                cp_pairs[key]["directions"].add(r["directionality"])
    cp_rows = []
    for r in cp_pairs.values():
        h = r["hgnc_id"]
        single = r["target_scope"] == r["partner_type"] == "protein"
        self_pair = single and r["uniprot_acc"] == r["partner_id"]
        r["exact_pair_assessed"] = int(single and not self_pair)
        r["assessment_scope"] = (
            "single_protein_pair"
            if single and not self_pair
            else "self_interface_not_audited"
            if self_pair
            else "chemical_identity_not_mapped"
            if r["partner_type"] == "chemical"
            else "complex_component_support_only"
        )
        es = structural[h, r["partner_id"]] if single and not self_pair else []
        er = regions[h, r["partner_id"]] if single and not self_pair else []

        def compatible(e):
            return is_site_compatible(e["context"], r["binder_target_location"])

        r["same_pair_structural_any_site"] = int(bool(es))
        r["same_pair_structural_external_site"] = int(any(compatible(e) for e in es))
        r["same_pair_region_external"] = int(any(compatible(e) for e in er))
        r["same_pair_structural_or_region_external"] = int(
            r["same_pair_structural_external_site"] or r["same_pair_region_external"]
        )
        partial = (
            [
                e
                for acc in r["partner_members"].split(";")
                for e in structural[h, acc]
                if compatible(e)
            ]
            if not single
            else []
        )
        r["complex_component_contact_support"] = int(bool(partial))
        r["support_pdb_ids"] = ";".join(
            sorted({e["pdb_id"] for e in es + partial if compatible(e)})
        )
        r["region_references"] = ";".join(
            sorted({e["reference"] for e in er if compatible(e)})
        )
        for k in ("source_rows", "references", "directions"):
            r[k] = ";".join(sorted(r[k]))
        cp_rows.append(r)
    # The denominator comes only from catalogue targets, never from structure matching.
    approved, aliases = hgnc_names(read(HGNC, "\t"))
    therapies = read(RAW / "thera.csv")
    attempts, thera_pairs = [], {}
    target_reviews = {
        r["component"]: r
        for r in read(OUT / "binder_denominator_target_review.tsv", "\t")
    }
    exclusions = {
        r["therapeutic"].casefold(): r
        for r in read(OUT / "binder_denominator_exclusions.tsv", "\t")
    }
    for drug in therapies:
        for arm, group in enumerate(drug["Target"].split(";")):
            components = re.split(r"\s+and\s+|&", group.strip())
            complex_group = len(components) > 1 and all(
                re.match(r"(?:ITG|CD3)", x.strip()) for x in components
            )
            for component in components:
                ids, status = resolve_component(component.strip(), approved, aliases)
                review = target_reviews.get(component.strip())
                if review:
                    ids, status = {review["hgnc_id"]}, "reviewed_gene_product"
                if complex_group:
                    status = "complex_target_not_direct_subunit"
                if re.search(r"canine|feline", drug["Format"], re.I):
                    status = "nonhuman_target"
                exclusion = exclusions.get(drug["Therapeutic"].casefold())
                if exclusion:
                    status = exclusion["reason"]
                attempts.append(
                    {
                        "therapeutic": drug["Therapeutic"],
                        "target_annotation": drug["Target"],
                        "arm_group": arm,
                        "component": component,
                        "status": status,
                        "candidate_hgnc_ids": ";".join(sorted(ids)),
                        "exclusion_reference": exclusion["reference"]
                        if exclusion
                        else "",
                    }
                )
                if status not in {
                    "approved_symbol",
                    "unique_alias",
                    "reviewed_gene_product",
                }:
                    continue
                h = next(iter(ids))
                if h not in by_id or by_id[h]["identifier_status"] != "unique":
                    continue
                g = by_id[h]
                key = (h, drug["Therapeutic"].casefold())
                es = therapeutic[key]
                thera_pairs[key] = {
                    **{k: g[k] for k in ID_FIELDS},
                    "binder_target_location": g["binder_target_location"],
                    "therapeutic": drug["Therapeutic"],
                    "target_annotation": drug["Target"],
                    "format": drug["Format"],
                    "development_status_in_source": drug["Est. Status"],
                    "same_therapeutic_any_site": int(bool(es)),
                    "same_therapeutic_external_site": int(
                        any(
                            is_site_compatible(
                                e["context"], g["binder_target_location"]
                            )
                            for e in es
                        )
                    ),
                    "support_pdb_ids": ";".join(sorted({e["pdb_id"] for e in es})),
                    "mapping_method": status,
                    "target_qualifier": review["target_qualifier"] if review else "",
                }
    cp_by_gene, th_by_gene = defaultdict(list), defaultdict(list)
    for r in cp_rows:
        cp_by_gene[r["hgnc_id"]].append(r)
    for r in thera_pairs.values():
        th_by_gene[r["hgnc_id"]].append(r)
    output_genes = []
    for g in genes:
        h = g["hgnc_id"]
        cp, th = cp_by_gene[h], th_by_gene[h]
        r = {k: g[k] for k in ID_FIELDS}
        r.update(
            identifier_status=g["identifier_status"],
            binder_target_location=g["binder_target_location"],
            llm_known_ligand=g["llm_known_ligand"],
        )
        r.update(
            cpdb_any_participant=int(bool(cp)),
            cpdb_single_protein_participant=int(
                any(x["target_scope"] == "protein" for x in cp)
            ),
            cpdb_assessed_protein_pair_gene=int(
                any(x["exact_pair_assessed"] for x in cp)
            ),
            cpdb_complex_component=int(any(x["target_scope"] == "complex" for x in cp)),
            cpdb_proxy_enzyme=int(g["uniprot_acc"] in proxy_members),
            cpdb_same_protein_pair_external_site=int(
                any(x["same_pair_structural_external_site"] for x in cp)
            ),
            cpdb_same_protein_pair_external_site_or_region=int(
                any(x["same_pair_structural_or_region_external"] for x in cp)
            ),
            thera_named_binder=int(bool(th)),
            thera_same_therapeutic_any_site=int(
                any(x["same_therapeutic_any_site"] for x in th)
            ),
            thera_same_therapeutic_external_site=int(
                any(x["same_therapeutic_external_site"] for x in th)
            ),
            any_antibody_external_site=int(
                any(
                    is_site_compatible(e["context"], g["binder_target_location"])
                    for e in antibody[h]
                )
            ),
            any_binder_external_site=int(
                g[
                    "extension_reclassified_plus_structural_exoplasmic"
                    if g["binder_target_location"] == "secreted_only"
                    else "extension_reclassified_plus_structural_ec"
                ]
            ),
        )
        output_genes.append(r)
    summary = []
    for name, rows, membership, metrics in [
        (
            "CellPhoneDB single-protein targets",
            output_genes,
            "cpdb_single_protein_participant",
            [
                "any_binder_external_site",
                "cpdb_same_protein_pair_external_site",
                "cpdb_same_protein_pair_external_site_or_region",
            ],
        ),
        (
            "CellPhoneDB assessed protein-pair genes",
            output_genes,
            "cpdb_assessed_protein_pair_gene",
            [
                "cpdb_same_protein_pair_external_site",
                "cpdb_same_protein_pair_external_site_or_region",
            ],
        ),
        (
            "CellPhoneDB including complex components",
            output_genes,
            "cpdb_any_participant",
            ["any_binder_external_site"],
        ),
        (
            "Thera-SAbDab named-binder genes",
            output_genes,
            "thera_named_binder",
            [
                "any_antibody_external_site",
                "thera_same_therapeutic_external_site",
                "thera_same_therapeutic_any_site",
            ],
        ),
        (
            "CellPhoneDB exact protein pairs",
            cp_rows,
            "exact_pair_assessed",
            [
                "same_pair_structural_external_site",
                "same_pair_structural_or_region_external",
                "same_pair_structural_any_site",
            ],
        ),
        (
            "Thera-SAbDab therapeutic-target pairs",
            list(thera_pairs.values()),
            None,
            ["same_therapeutic_external_site", "same_therapeutic_any_site"],
        ),
    ]:
        for location in (
            "all_locations",
            "membrane",
            "secreted_only",
            "other_or_uncertain",
        ):
            eligible = [
                r
                for r in rows
                if (membership is None or r[membership])
                and (
                    location == "all_locations"
                    or r["binder_target_location"] == location
                    or location == "membrane"
                    and r["binder_target_location"].startswith("membrane")
                )
            ]
            for metric in metrics:
                n = sum(int(r[metric]) for r in eligible)
                summary.append(
                    dict(
                        benchmark=name,
                        location=location,
                        metric=metric,
                        covered=n,
                        denominator=len(eligible),
                        percent=round(100 * n / len(eligible), 2) if eligible else "",
                    )
                )
    write_tsv(OUT / "binder_denominator_genes.tsv", output_genes)
    write_tsv(OUT / "binder_denominator_cpdb_pairs.tsv", cp_rows)
    write_tsv(OUT / "binder_denominator_thera_pairs.tsv", list(thera_pairs.values()))
    write_tsv(OUT / "binder_denominator_thera_resolution.tsv", attempts)
    write_tsv(OUT / "binder_denominator_summary.tsv", summary)
    inputs = [
        *sorted(RAW.glob("*.csv")),
        HGNC,
        *sorted(
            (ROOT / "data/external/structural_intact_extension/uniprot").glob("*.json")
        ),
        OUT / "structural_intact_genes.tsv",
        OUT / "structural_intact_evidence.tsv.gz",
        OUT / "binder_denominator_exclusions.tsv",
        OUT / "binder_denominator_target_review.tsv",
    ]
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "cohort": len(genes),
        "cellphonedb_commit": CPDB_COMMIT,
        "cellphonedb_interactions": len(interactions),
        "thera_catalogue_rows": len(therapies),
        "thera_identical_to_contact_audit_snapshot": (RAW / "thera.csv").read_bytes()
        == (ROOT / "data/external/binder_coverage/thera.csv").read_bytes(),
        "thera_resolution_counts": dict(Counter(r["status"] for r in attempts)),
        "cpdb_pair_scope_counts": dict(Counter(r["assessment_scope"] for r in cp_rows)),
        "source_urls": URLS,
        "inputs": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in inputs
        },
        "limitations": [
            "Catalogue target mapping is independent of site availability; unresolved targets are not negatives.",
            "Exact protein-pair coverage does not assess chemical identity, self interfaces, or complete complexes.",
            "Location comments describe possible compartments, not live-cell accessibility or epitope exposure.",
            "Thera clinical status is the source's February 2025 snapshot, not current regulatory status.",
        ],
    }
    (OUT / "binder_denominator_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(
        json.dumps(
            {k: v for k, v in manifest.items() if k not in {"inputs", "source_urls"}},
            indent=2,
        )
    )
    for r in summary:
        if r["location"] in {"membrane", "secreted_only"}:
            print(r)


if __name__ == "__main__":
    main()
