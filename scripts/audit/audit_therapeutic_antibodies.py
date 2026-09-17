"""Audit exact therapeutic binding domains and AACDB antibody epitopes.

Uses frozen Thera-SAbDab metadata, the complete cached SAbDab2 export,
AACDB experimental interfaces, and chain/residue-level SIFTS mappings.
"""

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from Bio.PDB.MMCIF2Dict import MMCIF2Dict
from Bio.SeqUtils import seq1

from accessible_surfaceome.binders.coverage import write_tsv
from audit_antibody_contacts import CACHE, contacts, download, residue_mapping
from summarize_binding_sites import load_uniprot, topology

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/external/therapeutic_antibody_audit"
OUT = ROOT / "data/analysis/deep_dive_binding_sites"


def therapeutic_lookup(therapies):
    structures = defaultdict(set)
    sequences = defaultdict(set)
    for row in therapies:
        for arm, (hk, lk) in enumerate(
            (
                ("HeavySequence", "LightSequence"),
                ("HeavySequence(ifbispec)", "LightSequence(ifbispec)"),
            )
        ):
            heavy, light = row[hk], row[lk]
            if heavy and heavy != "na":
                sequences[heavy, light if light != "na" else ""].add(
                    (row["Therapeutic"], arm)
                )
        for arm, arm_hits in enumerate(row["100% SI Structure"].split(";")):
            for entry in arm_hits.split("/"):
                parts = entry.split(":")
                if not re.fullmatch(r"[0-9][a-zA-Z0-9]{3}", parts[0]):
                    continue
                for chains in parts[1:]:
                    if len(chains) in (1, 2):
                        structures[parts[0].lower(), chains[0], chains[1:] or ""].add(
                            (row["Therapeutic"], arm)
                        )
    return structures, sequences


def prepare(genes):
    index = {g["uniprot_acc"]: g for g in genes if g["identifier_status"] == "unique"}
    chain_accs = defaultdict(set)
    with gzip.open(CACHE / "sifts.csv.gz", "rt") as stream:
        next(stream)
        for r in csv.DictReader(stream):
            chain_accs[r["PDB"], r["CHAIN"]].add(r["SP_PRIMARY"])
    therapies = list(
        csv.DictReader(
            (ROOT / "data/external/binder_coverage/thera.csv").open(
                encoding="utf-8-sig"
            )
        )
    )
    exact_structures, exact_sequences = therapeutic_lookup(therapies)
    therapeutic_candidates = []
    for row in csv.DictReader((CACHE / "sabdab_summary.txt").open()):
        if row["method"] not in {"XRAY", "ELECTRON_MICROSCOPY", "NMR"}:
            continue
        pdb = row["PDB"].removeprefix("pdb_0000")
        light = row["Lchain"] if row["Lchain"] != "NA" else ""
        listed = exact_structures[pdb, row["Hchain"], light]
        sequenced = exact_sequences[row["VH"], row["VL"] if row["VL"] != "NA" else ""]
        matches = listed | sequenced
        if not matches:
            continue
        for chain in row["antigen_chain"].split("|"):
            accessions = chain_accs[pdb, chain]
            if len(accessions) != 1 or not accessions <= index.keys():
                continue
            acc = next(iter(accessions))
            for drug, arm in matches:
                therapeutic_candidates.append(
                    dict(
                        row,
                        pdb_id=pdb,
                        target_chain=chain,
                        uniprot_acc=acc,
                        therapeutic=drug,
                        arm=arm,
                        match_method="exact_VH_VL"
                        if (drug, arm) in sequenced
                        else "Thera_100pct_structure_chain",
                    )
                )
    aacdb = []
    for row in csv.DictReader((RAW / "protein_table.txt").open(), delimiter="\t"):
        pdb = row["pdb"].lower()
        parts = row["chains"].split("_")
        if len(parts) != 2:
            continue
        for chain in parts[1]:
            accessions = chain_accs[pdb, chain]
            if len(accessions) == 1 and accessions <= index.keys():
                aacdb.append(
                    dict(
                        row,
                        pdb_id=pdb,
                        target_chain=chain,
                        uniprot_acc=next(iter(accessions)),
                        antibody_chains=parts[0],
                    )
                )
    # AACDB can supply a complex absent from SAbDab or with different domain boundaries.
    from Bio import SeqIO

    antibody_sequences = {
        r.id.split("|")[0]: str(r.seq)
        for r in SeqIO.parse(RAW / "Antibody_seq_all.fasta", "fasta")
    }
    seen = {
        (
            r["pdb_id"],
            r["Hchain"],
            r["Lchain"],
            r["target_chain"],
            r["therapeutic"],
            r["arm"],
        )
        for r in therapeutic_candidates
    }
    for row in aacdb:
        chains = row["antibody_chains"]
        if len(chains) not in (1, 2):
            continue
        hc, lc = chains[0], chains[1:] or chains[0]
        hs = antibody_sequences.get(row["pdb"] + "_" + hc, "")
        ls = antibody_sequences.get(row["pdb"] + "_" + lc, "")
        for (heavy, light), names in exact_sequences.items():
            if (
                heavy not in hs
                or (light and light not in ls)
                or (not light and len(chains) != 1)
            ):
                continue
            for drug, arm in names:
                key = (
                    row["pdb_id"],
                    hc,
                    lc if light else "NA",
                    row["target_chain"],
                    drug,
                    arm,
                )
                if key in seen:
                    continue
                seen.add(key)
                therapeutic_candidates.append(
                    dict(
                        row,
                        Hchain=hc,
                        Lchain=lc if light else "NA",
                        VH=heavy,
                        VL=light or "NA",
                        therapeutic=drug,
                        arm=arm,
                        match_method="AACDB_exact_VH_VL",
                        INSTANCE="AACDB:" + row["id"],
                        SABDAB_ID="",
                    )
                )
    return index, therapeutic_candidates, aacdb


def fetch_structure(pdb, coordinates=False):
    try:
        download(
            CACHE / "sifts_xml" / f"{pdb}.xml.gz",
            f"https://ftp.ebi.ac.uk/pub/databases/msd/sifts/xml/{pdb}.xml.gz",
        )
        if coordinates:
            download(
                CACHE / "coordinates" / f"{pdb}.cif",
                f"https://www.ebi.ac.uk/pdbe/entry-files/download/{pdb}.cif",
            )
        return dict(pdb_id=pdb, status="ok", coordinates=coordinates)
    except Exception as exc:
        return dict(pdb_id=pdb, status="error", coordinates=coordinates, error=str(exc))


def variable_only_cif(cif, row):
    """Retain antibody variable-domain atoms, excluding Fc/constant-domain binding."""
    chain_sequences = {}
    for chains, sequence in zip(
        cif["_entity_poly.pdbx_strand_id"],
        cif["_entity_poly.pdbx_seq_one_letter_code_can"],
        strict=True,
    ):
        for chain in chains.split(","):
            chain_sequences[chain.strip()] = re.sub(r"\s+", "", sequence)
    allowed = defaultdict(set)
    logical_names = {}
    for ck, sk in (("Hchain", "VH"), ("Lchain", "VL")):
        chain, domain = row[ck], row[sk]
        if chain == "NA":
            continue
        logical_chain = chain
        # Documented SAbDab2 convention: split domains on author chain A become A1/A2.
        if (
            chain not in chain_sequences
            and row.get("chainsharing_construct", "NA") != "NA"
        ):
            match = re.fullmatch(r"(.+?)[0-9]+", chain)
            if match and match[1] in chain_sequences:
                chain = match[1]
        polymer = chain_sequences.get(chain, "")
        if not domain or domain == "NA" or polymer.count(domain) != 1:
            return None
        start = polymer.index(domain)
        for pos in range(start + 1, start + len(domain) + 1):
            if (chain, pos) in logical_names and logical_names[
                chain, pos
            ] != logical_chain:
                return None
            logical_names[chain, pos] = logical_chain
            allowed[chain].add(pos)
    if row["target_chain"] in allowed:
        return None
    indices = []
    for i, chain in enumerate(cif["_atom_site.auth_asym_id"]):
        if chain == row["target_chain"]:
            indices.append(i)
        elif chain in allowed:
            number = cif["_atom_site.label_seq_id"][i]
            if number.isdigit() and int(number) in allowed[chain]:
                indices.append(i)
    result = {
        k: [v[i] for i in indices] if k.startswith("_atom_site.") else v
        for k, v in cif.items()
    }
    result["_atom_site.auth_asym_id"] = [
        logical_names.get(
            (cif["_atom_site.auth_asym_id"][i], int(cif["_atom_site.label_seq_id"][i])),
            cif["_atom_site.auth_asym_id"][i],
        )
        if cif["_atom_site.label_seq_id"][i].isdigit()
        else cif["_atom_site.auth_asym_id"][i]
        for i in indices
    ]
    return result


def checked_mapping(xml, accession, canonical):
    mapping = residue_mapping(xml, accession)
    # Sequence verification is performed against actual contact residue identities below.
    return {key: pos for key, pos in mapping.items() if 0 < pos <= len(canonical)}


def aacdb_positions(rows, chain, mapping, canonical):
    """AACDB omits insertion codes: reject any ambiguous native residue number."""
    native = {}
    variants = defaultdict(list)
    for (c, number), position in mapping.items():
        if c == chain:
            match = re.fullmatch(r"(-?\d+)[A-Za-z]*", number)
            if match:
                variants[match[1]].append(position)
    for row in rows:
        if float(row["distance"]) > 5.0:
            continue
        match = re.fullmatch(r"([^:]+):([A-Z]{3})(-?\d+)", row["antigen"])
        if not match or match[1] != chain:
            continue
        aa, number = seq1(match[2]), match[3]
        if len(variants[number]) != 1:
            return []
        pos = variants[number][0]
        if not (0 < pos <= len(canonical)) or canonical[pos - 1] != aa:
            return []
        native[number] = pos
    return sorted(set(native.values()))


@lru_cache(maxsize=4)
def load_cif(pdb):
    return MMCIF2Dict(str(CACHE / "coordinates" / f"{pdb}.cif"))


def therapeutic_contacts(row, canonical):
    pdb, acc = row["pdb_id"], row["uniprot_acc"]
    xml = gzip.decompress((CACHE / "sifts_xml" / f"{pdb}.xml.gz").read_bytes())
    mapping = checked_mapping(xml, acc, canonical)
    cif = load_cif(pdb)
    filtered = variable_only_cif(cif, row)
    if filtered is None:
        return [], "variable_domain_not_exactly_located"
    # Reject mutations at contact residues, while preserving insertion-aware numbering.
    mismatches = set()
    for i, chain in enumerate(cif["_atom_site.auth_asym_id"]):
        if chain != row["target_chain"]:
            continue
        insertion = cif["_atom_site.pdbx_PDB_ins_code"][i]
        number = cif["_atom_site.auth_seq_id"][i] + (
            insertion if insertion not in {"?", "."} else ""
        )
        pos = mapping.get((chain, number))
        if pos and canonical[pos - 1] != seq1(cif["_atom_site.auth_comp_id"][i]):
            mismatches.add(pos)
    positions = contacts(
        filtered, row["target_chain"], {row["Hchain"], row["Lchain"]} - {"NA"}, mapping
    )
    if set(positions) & mismatches:
        return [], "noncanonical_contact_residue"
    return positions, "mapped" if positions else "no_variable_domain_contacts"


def analyze(genes, index, therapeutic, aacdb):
    proteins = load_uniprot()
    evidence, attempts = [], []
    hits = defaultdict(set)
    z = zipfile.ZipFile(RAW / "interacting_res_distance.zip")
    for row in aacdb:
        pdb, acc = row["pdb_id"], row["uniprot_acc"]
        canonical = proteins.get(acc, {}).get("sequence", {}).get("value", "")
        result = dict(source="AACDB", record_id=row["id"], pdb_id=pdb, uniprot_acc=acc)
        hits["aacdb_target_complex"].add(acc)
        try:
            name = f"{row['pdb']}_{row['chains']}_interacting_residues_distance.txt"
            records = list(
                csv.DictReader(io.StringIO(z.read(name).decode()), delimiter="\t")
            )
            xml = gzip.decompress((CACHE / "sifts_xml" / f"{pdb}.xml.gz").read_bytes())
            mapping = checked_mapping(xml, acc, canonical)
            positions = aacdb_positions(
                records, row["target_chain"], mapping, canonical
            )
            result["status"] = (
                "mapped" if positions else "no_unambiguous_canonical_site"
            )
        except Exception as exc:
            positions = []
            result.update(status="error", error=str(exc))
        attempts.append(result)
        if not positions:
            continue
        hits["aacdb_mapped_contacts"].add(acc)
        topo = topology(positions, proteins[acc])
        if topo == "extracellular":
            hits["aacdb_mapped_contacts_extracellular"].add(acc)
        evidence.append(
            dict(
                source="AACDB",
                record_id=row["id"],
                uniprot_acc=acc,
                therapeutic="",
                arm="",
                match_method="curated_antibody_antigen_complex",
                binder_name=row["antibody"],
                pdb_id=pdb,
                antibody_chains=row["antibody_chains"],
                antigen_chain=row["target_chain"],
                positions=",".join(map(str, positions)),
                topology=topo,
                reference=row["reference"],
                source_therapeutic_annotation=row["INN(clinical_trial)"],
            )
        )
    # Every distinct therapeutic/arm/target/structure pair is attempted; no per-gene cap.
    interface_cache = {}
    for i, row in enumerate(sorted(therapeutic, key=lambda r: r["pdb_id"])):
        if i % 50 == 0:
            print("Therapeutic interface attempts", i, len(therapeutic), flush=True)
        acc = row["uniprot_acc"]
        canonical = proteins.get(acc, {}).get("sequence", {}).get("value", "")
        result = dict(
            source="Thera-SAbDab",
            record_id=row["INSTANCE"],
            pdb_id=row["pdb_id"],
            uniprot_acc=acc,
            therapeutic=row["therapeutic"],
            arm=row["arm"],
        )
        hits["therapeutic_exact_complex_candidate"].add(acc)
        try:
            interface_key = (
                row["pdb_id"],
                row["Hchain"],
                row["Lchain"],
                row["target_chain"],
                acc,
                row["VH"],
                row["VL"],
            )
            if interface_key not in interface_cache:
                interface_cache[interface_key] = therapeutic_contacts(row, canonical)
            positions, status = interface_cache[interface_key]
            result["status"] = status
        except Exception as exc:
            positions = []
            result.update(status="error", error=str(exc))
        attempts.append(result)
        if not positions:
            continue
        topo = topology(positions, proteins[acc])
        hits["therapeutic_mapped_contacts"].add(acc)
        if topo == "extracellular":
            hits["therapeutic_mapped_contacts_extracellular"].add(acc)
        evidence.append(
            dict(
                source="Thera-SAbDab",
                record_id=row["INSTANCE"],
                uniprot_acc=acc,
                therapeutic=row["therapeutic"],
                arm=row["arm"],
                match_method=row["match_method"],
                binder_name=row["therapeutic"],
                pdb_id=row["pdb_id"],
                antibody_chains="|".join([row["Hchain"], row["Lchain"]]),
                antigen_chain=row["target_chain"],
                positions=",".join(map(str, positions)),
                topology=topo,
                reference=f"https://www.ebi.ac.uk/pdbe/entry/pdb/{row['pdb_id']}",
                source_therapeutic_annotation="",
            )
        )
        if i % 50 == 0:
            print("Therapeutic interfaces", i, len(therapeutic), flush=True)
    old = {g["uniprot_acc"] for g in genes if g["expanded_union"] == "1"}
    old_ab = {
        g["uniprot_acc"]
        for g in genes
        if g["sabdab_mapped_contacts"] == "1" or g["iedb_exact_epitope"] == "1"
    }
    old_ec = {
        g["uniprot_acc"] for g in genes if g["expanded_extracellular_union"] == "1"
    }
    hits["antibody_union_after_extension"] = (
        old_ab | hits["aacdb_mapped_contacts"] | hits["therapeutic_mapped_contacts"]
    )
    hits["all_experimental_union_after_antibody_extension"] = (
        old | hits["aacdb_mapped_contacts"] | hits["therapeutic_mapped_contacts"]
    )
    hits["all_experimental_ec_union_after_antibody_extension"] = (
        old_ec
        | hits["aacdb_mapped_contacts_extracellular"]
        | hits["therapeutic_mapped_contacts_extracellular"]
    )
    summaries = []
    for subset in ["all", "yes"]:
        selected = [
            g for g in genes if subset == "all" or g["llm_known_ligand"] == "yes"
        ]
        for metric, members in sorted(hits.items()):
            count = sum(
                g["uniprot_acc"] in members and g["identifier_status"] == "unique"
                for g in selected
            )
            summaries.append(
                dict(
                    subset=subset,
                    metric=metric,
                    genes=count,
                    denominator=len(selected),
                    percent=round(100 * count / len(selected), 2),
                    new_vs_previous_all=sum(
                        g["uniprot_acc"] in members - old for g in selected
                    ),
                    new_vs_previous_antibody=sum(
                        g["uniprot_acc"] in members - old_ab for g in selected
                    ),
                )
            )
    for gene in genes:
        for metric, members in hits.items():
            gene[metric] = int(
                gene["uniprot_acc"] in members and gene["identifier_status"] == "unique"
            )
    for row in evidence:
        row.update(
            {
                k: index[row["uniprot_acc"]][k]
                for k in ["hgnc_id", "hgnc_symbol", "ensembl_gene", "ncbi_gene_id"]
            }
        )
    write_tsv(OUT / "therapeutic_aacdb_genes.tsv", genes)
    write_tsv(OUT / "therapeutic_aacdb_summary.tsv", summaries)
    write_tsv(OUT / "therapeutic_aacdb_evidence.tsv", evidence)
    write_tsv(
        OUT / "therapeutic_aacdb_attempts.tsv",
        attempts,
        (
            "source",
            "record_id",
            "pdb_id",
            "uniprot_acc",
            "therapeutic",
            "arm",
            "status",
            "error",
        ),
    )
    (OUT / "therapeutic_aacdb_evidence.tsv.gz").write_bytes(
        gzip.compress((OUT / "therapeutic_aacdb_evidence.tsv").read_bytes(), mtime=0)
    )
    grouped = defaultdict(list)
    for row in evidence:
        if row["therapeutic"]:
            grouped[row["therapeutic"], row["hgnc_id"]].append(row)
    catalogue = []
    for (drug, hgnc), records in sorted(grouped.items()):
        first = records[0]
        catalogue.append(
            dict(
                therapeutic=drug,
                **{
                    k: first[k]
                    for k in [
                        "hgnc_id",
                        "hgnc_symbol",
                        "uniprot_acc",
                        "ensembl_gene",
                        "ncbi_gene_id",
                    ]
                },
                arms=";".join(sorted({str(r["arm"]) for r in records})),
                pdb_ids=";".join(sorted({r["pdb_id"] for r in records})),
                has_extracellular_site=int(
                    any(r["topology"] == "extracellular" for r in records)
                ),
                match_methods=";".join(sorted({r["match_method"] for r in records})),
            )
        )
    write_tsv(OUT / "therapeutic_antibody_catalogue.tsv", catalogue)
    used_pdbs = {r["pdb_id"] for r in aacdb + therapeutic}
    source_files = [
        *(CACHE / "uniprot").glob("*.json"),
        *[CACHE / "sifts_xml" / f"{p}.xml.gz" for p in used_pdbs],
        *[
            CACHE / "coordinates" / f"{p}.cif"
            for p in {r["pdb_id"] for r in therapeutic}
        ],
    ]
    manifest = dict(
        bulk_source_url="https://i.uestc.edu.cn/AACDB/data_zip/",
        source_data_hashes={
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in source_files
            if p.exists()
        },
        generated_at=datetime.now(UTC).isoformat(),
        aacdb_version="1.0 (2024-05-30)",
        thera_status_date="February 2025; not current clinical status",
        attempts=dict(Counter(r["source"] + ":" + r["status"] for r in attempts)),
        therapeutics_with_sites=len(
            {r["therapeutic"] for r in evidence if r["therapeutic"]}
        ),
        therapeutic_target_pairs=len(
            {(r["therapeutic"], r["uniprot_acc"]) for r in evidence if r["therapeutic"]}
        ),
        therapeutic_distinct_interfaces=len(
            {
                (
                    r["uniprot_acc"],
                    r["pdb_id"],
                    r["antibody_chains"],
                    r["antigen_chain"],
                )
                for r in evidence
                if r["therapeutic"]
            }
        ),
        inputs={
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                ROOT / "data/external/binder_coverage/thera.csv",
                CACHE / "sabdab_summary.txt",
                CACHE / "sifts.csv.gz",
                OUT / "biolip_gpcrdb_genes.tsv",
                *sorted(RAW.glob("*")),
            ]
            if p.is_file()
        },
    )
    (OUT / "therapeutic_aacdb_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(summaries, indent=2))
    print(json.dumps({k: v for k, v in manifest.items() if k not in {"inputs", "source_data_hashes"}}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    if args.fetch:
        RAW.mkdir(parents=True, exist_ok=True)
        for name in (
            "protein_table.txt",
            "Antibody_seq_all.fasta",
            "Antigen_seq_all.fasta",
            "interacting_res_distance.zip",
        ):
            download(RAW / name, "https://i.uestc.edu.cn/AACDB/data_zip/" + name)
    genes = list(
        csv.DictReader((OUT / "biolip_gpcrdb_genes.tsv").open(), delimiter="\t")
    )
    index, therapeutic, aacdb = prepare(genes)
    (RAW / "therapeutic_candidates.json").write_text(json.dumps(therapeutic))
    (RAW / "aacdb_candidates.json").write_text(json.dumps(aacdb))
    print(
        "Candidates",
        dict(
            therapeutic_rows=len(therapeutic),
            therapeutic_names=len({r["therapeutic"] for r in therapeutic}),
            therapeutic_genes=len({r["uniprot_acc"] for r in therapeutic}),
            aacdb_rows=len(aacdb),
            aacdb_genes=len({r["uniprot_acc"] for r in aacdb}),
        ),
        flush=True,
    )
    if args.fetch:
        therapeutic_pdbs = {r["pdb_id"] for r in therapeutic}
        all_pdbs = therapeutic_pdbs | {r["pdb_id"] for r in aacdb}
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = []
            for i, r in enumerate(
                pool.map(
                    lambda p: fetch_structure(p, p in therapeutic_pdbs),
                    sorted(all_pdbs),
                )
            ):
                results.append(r)
                if i % 100 == 0:
                    print("Structures", i, len(all_pdbs), flush=True)
        (RAW / "retrieval.json").write_text(json.dumps(results))
        print(Counter(r["status"] for r in results), flush=True)
        return
    analyze(genes, index, therapeutic, aacdb)


if __name__ == "__main__":
    main()
