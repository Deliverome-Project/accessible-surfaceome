"""Audit experimental BioLiP sites and GPCRdb contacts against frozen deep dives.

--fetch retrieves GPCRdb records (six workers). Bulk BioLiP annotations are
cached separately from https://zhanggroup.org/BioLiP/download/BioLiP.txt.gz.
"""

import argparse
import csv
import gzip
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import httpx
from Bio.Align import PairwiseAligner

from accessible_surfaceome.binders.coverage import write_tsv
from summarize_binding_sites import EXCLUDE, load_uniprot, topology

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/external/binder_resource_extension"
OUT = ROOT / "data/analysis/deep_dive_binding_sites"


def fetch(job):
    name, url = job
    path = RAW / (name + ".json")
    if path.exists():
        return json.loads(path.read_text())
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            r = httpx.get(url, timeout=90, follow_redirects=True)
            r.raise_for_status()
            result = dict(
                url=url,
                retrieved_at=datetime.now(UTC).isoformat(),
                status=r.status_code,
                data=r.json(),
            )
            path.write_text(json.dumps(result))
            return result
        except (httpx.HTTPError, ValueError) as e:
            if attempt == 2:
                return dict(url=url, status="error", error=str(e))
            time.sleep(attempt + 1)
    raise RuntimeError(url)


def map_biolip_site(canonical: str, sequence: str, residue_text: str) -> list[int]:
    aligner = PairwiseAligner()
    aligner.match_score = 2
    aligner.mismatch_score = -3
    aligner.open_gap_score = -5
    aligner.extend_gap_score = -0.5
    aligner.end_gap_score = 0

    tokens = re.findall(r"([A-Z])(\d+)", residue_text)
    if not canonical or not sequence or not tokens:
        return []
    alignments = aligner.align(canonical, sequence)
    alignment = alignments[0]
    mapping = {}
    for (a, b), (c, d) in zip(*alignment.aligned, strict=True):
        for offset in range(b - a):
            if canonical[a + offset] == sequence[c + offset]:
                mapping[c + offset + 1] = a + offset + 1
    if len(mapping) / len(sequence) < 0.95:
        return []
    if any(
        int(pos) not in mapping or sequence[int(pos) - 1] != aa for aa, pos in tokens
    ):
        return []
    positions = sorted({mapping[int(pos)] for aa, pos in tokens})
    # Repeated sequence placements cannot be assigned to canonical coordinates.
    try:
        alternative = alignments[1]
    except IndexError:
        alternative = None
    if alternative is not None:
        return []
    return positions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    bulk_urls = {
        "BioLiP.txt.gz": "https://zhanggroup.org/BioLiP/download/BioLiP.txt.gz",
        "ligand.tsv.gz": "https://zhanggroup.org/BioLiP/data/ligand.tsv.gz",
        "readme.txt": "https://zhanggroup.org/BioLiP/download/readme.txt",
        "gpcr_receptors.json": "https://gpcrdb.org/services/receptorlist/",
        "gpcr_structures.json": "https://gpcrdb.org/services/structure/",
    }
    if args.fetch:
        RAW.mkdir(parents=True, exist_ok=True)
        for name, url in bulk_urls.items():
            path = RAW / name
            if not path.exists():
                temporary = path.with_suffix(path.suffix + ".partial")
                with httpx.stream(
                    "GET", url, timeout=120, follow_redirects=True
                ) as response:
                    response.raise_for_status()
                    with temporary.open("wb") as stream:
                        for chunk in response.iter_bytes():
                            stream.write(chunk)
                temporary.replace(path)
    genes = list(
        csv.DictReader((OUT / "resource_comparison_genes.tsv").open(), delimiter="\t")
    )
    index = {g["uniprot_acc"]: g for g in genes if g["identifier_status"] == "unique"}
    receptors = json.loads((RAW / "gpcr_receptors.json").read_text())
    receptors = {
        r["entry_name"]: r
        for r in receptors
        if r["species"] == "Homo sapiens" and r["accession"] in index
    }
    structures = json.loads((RAW / "gpcr_structures.json").read_text())
    structures = [
        s
        for s in structures
        if s["protein"] in receptors
        and s["species"] == "Homo sapiens"
        and s["ligands"]
        and s["type"] in {"X-ray diffraction", "Electron microscopy", "NMR"}
    ]
    jobs = [
        ("mutants/" + name, "https://gpcrdb.org/services/mutants/" + name + "/")
        for name in receptors
    ]
    for pdb in sorted({s["pdb_code"] for s in structures}):
        jobs.append(
            (
                "contacts/" + pdb,
                f"https://gpcrdb.org/services/structure/{pdb}/interaction/",
            )
        )
        # PDB lookup explicitly selects experimental complexes, not predicted peptide poses.
        jobs.append(
            (
                "peptides/" + pdb,
                f"https://gpcrdb.org/services/structure/{pdb}/peptideinteraction/",
            )
        )
    for name in sorted({s["protein"] for s in structures}):
        jobs.append(
            (
                "residues/" + name,
                f"https://gpcrdb.org/services/residues/extended/{name}/",
            )
        )
    if args.fetch:
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = []
            for i, result in enumerate(pool.map(fetch, jobs)):
                results.append({k: v for k, v in result.items() if k != "data"})
                if i % 100 == 0:
                    print(f"GPCRdb {i}/{len(jobs)}", flush=True)
        (RAW / "retrieval.json").write_text(json.dumps(results))
        print(
            "GPCRdb fetch complete",
            Counter(str(r["status"]) for r in results),
            flush=True,
        )
        return
    proteins = load_uniprot()
    evidence = []
    hits = defaultdict(set)
    stats = Counter()
    chemicals = {}
    with gzip.open(RAW / "ligand.tsv.gz", "rt") as stream:
        for row in csv.reader(stream, delimiter="\t"):
            if len(row) >= 6 and not row[0].startswith("#"):
                chemicals[row[0]] = row
    candidates = defaultdict(list)
    with gzip.open(RAW / "BioLiP.txt.gz", "rt") as stream:
        for row in csv.reader(stream, delimiter="\t"):
            stats["biolip_total_rows"] += 1
            if len(row) != 21:
                raise ValueError("Unexpected BioLiP schema")
            acc = row[17]
            if acc not in index:
                continue
            stats["biolip_cohort_rows"] += 1
            ligand = row[4]
            chemical = chemicals.get(ligand, [])
            formula = chemical[1] if chemical else ""
            atoms = re.findall(r"([A-Z][a-z]?)(\d*)", formula)
            heavy = sum(
                int(n or 1) for element, n in atoms if element not in {"H", "D"}
            )
            if ligand != "peptide" and (
                ligand in EXCLUDE or not any(e == "C" for e, n in atoms) or heavy < 6
            ):
                continue
            if not row[7] or not row[8]:
                continue
            hits["biolip_native_sites"].add(acc)
            candidates[acc].append(row)
    for acc, rows in candidates.items():
        canonical = proteins.get(acc, {}).get("sequence", {}).get("value", "")
        # Up to ten representative sites per protein; full native coverage retained separately.
        rows.sort(
            key=lambda r: (
                not any(r[13:17]),
                float(r[2]) if float(r[2]) > 0 else 999,
                r[0],
            )
        )
        for row in rows[:10]:
            positions = map_biolip_site(canonical, row[20], row[8])
            if not positions:
                continue
            hits["biolip_mapped_sites"].add(acc)
            category = "peptide" if row[4] == "peptide" else "organic_compound"
            hits["biolip_" + category].add(acc)
            if any(row[13:17]):
                hits["biolip_affinity_annotated"].add(acc)
            topo = topology(positions, proteins[acc])
            if topo == "extracellular":
                hits["biolip_extracellular"].add(acc)
            evidence.append(
                dict(
                    source="BioLiP",
                    uniprot_acc=acc,
                    pdb_id=row[0],
                    binder=row[4],
                    binder_identity=f"{row[0]}:{row[5]}:{row[6]}:{row[19]}",
                    evidence_type=category,
                    canonical_positions=",".join(map(str, positions)),
                    native_positions=row[7],
                    reference=row[18],
                    topology=topo,
                    affinity=" | ".join(row[13:17]),
                )
            )
            # One mapped representative establishes gene coverage, not a complete binder catalogue.
            break
    for structure in structures:
        acc = receptors[structure["protein"]]["accession"]
        seq = proteins.get(acc, {}).get("sequence", {}).get("value", "")
        residue_path = RAW / "residues" / (structure["protein"] + ".json")
        residue_rows = (
            json.loads(residue_path.read_text())["data"]
            if residue_path.exists()
            else []
        )
        generic_map = {
            r["display_generic_number"]: r
            for r in residue_rows
            if r.get("display_generic_number")
        }
        for folder in ("contacts", "peptides"):
            path = RAW / folder / (structure["pdb_code"] + ".json")
            if not path.exists():
                stats["gpcr_missing_contact_responses"] += 1
                continue
            groups = defaultdict(list)
            for row in json.loads(path.read_text())["data"]:
                if row.get("interaction_type", "").lower() == "accessible":
                    continue
                if row.get("ligand_name"):
                    groups[row["ligand_name"]].append(row)
            for ligand, rows in groups.items():
                hits["gpcr_native_sites"].add(acc)
                pairs = set()
                for r in rows:
                    generic = r.get(
                        "display_generic_number",
                        r.get("receptor_residue_generic_number"),
                    )
                    mapped = generic_map.get(generic)
                    pos = (
                        mapped["sequence_number"]
                        if mapped
                        else r.get("sequence_number", r.get("receptor_residue_number"))
                    )
                    aa = r.get("amino_acid", r.get("receptor_amino_acid"))
                    pairs.add((pos, aa))
                if not all(
                    isinstance(pos, int) and 0 < pos <= len(seq) and seq[pos - 1] == aa
                    for pos, aa in pairs
                ):
                    stats["gpcr_sites_requiring_numbering_remap"] += 1
                    continue
                positions = sorted({pos for pos, aa in pairs})
                hits["gpcr_mapped_sites"].add(acc)
                topo = topology(positions, proteins[acc])
                if topo == "extracellular":
                    hits["gpcr_extracellular"].add(acc)
                evidence.append(
                    dict(
                        source="GPCRdb",
                        uniprot_acc=acc,
                        pdb_id=structure["pdb_code"],
                        binder=ligand,
                        binder_identity=ligand,
                        evidence_type="structural_contacts",
                        canonical_positions=",".join(map(str, positions)),
                        native_positions=",".join(
                            map(
                                str,
                                sorted(
                                    {
                                        r.get(
                                            "sequence_number",
                                            r.get("receptor_residue_number"),
                                        )
                                        for r in rows
                                    }
                                ),
                            )
                        ),
                        reference=structure.get("publication", ""),
                        topology=topo,
                        affinity="",
                    )
                )
    for name, receptor in receptors.items():
        acc = receptor["accession"]
        path = RAW / "mutants" / (name + ".json")
        if not path.exists():
            stats["gpcr_missing_mutation_responses"] += 1
            continue
        seq = proteins.get(acc, {}).get("sequence", {}).get("value", "")
        for row in json.loads(path.read_text())["data"]:
            pos = row["mutation_pos"]
            if (
                not row["ligand_name"]
                or not row["reference"]
                or not (0 < pos <= len(seq) and seq[pos - 1] == row["mutation_from"])
            ):
                continue
            if row["exp_type"] not in {
                "K(i)",
                "K(d)",
                "pK(i)",
                "pK(d)",
                "K(l)",
                "K(h)",
            }:
                continue
            # Measured WT binding is required; functional-only or empty records do not count.
            if row["exp_wt_value"] == 0 or not row["exp_wt_unit"]:
                continue
            hits["gpcr_binding_mutagenesis"].add(acc)
            evidence.append(
                dict(
                    source="GPCRdb",
                    uniprot_acc=acc,
                    pdb_id="",
                    binder=row["ligand_name"],
                    binder_identity=f"{row['ligand_idtype']}:{row['ligand_id']}",
                    evidence_type="binding_mutagenesis_not_direct_epitope",
                    canonical_positions=str(pos),
                    native_positions=str(pos),
                    reference=row["reference"],
                    topology=topology([pos], proteins[acc]),
                    affinity=f"{row['exp_type']} WT {row['exp_wt_value']} {row['exp_wt_unit']}; fold change {row['exp_fold_change']}",
                )
            )
    old = {g["uniprot_acc"] for g in genes if g["union_mapped_sites"] == "1"}
    hits["new_sources_union"] = hits["biolip_mapped_sites"] | hits["gpcr_mapped_sites"]
    hits["expanded_union"] = old | hits["new_sources_union"]
    hits["new_sources_increment"] = hits["new_sources_union"] - old
    old_external = {
        g["uniprot_acc"] for g in genes if g["union_mapped_sites_extracellular"] == "1"
    }
    hits["expanded_extracellular_union"] = (
        old_external | hits["biolip_extracellular"] | hits["gpcr_extracellular"]
    )
    hits["expanded_affinity_annotated_or_gpcr_union"] = (
        old | hits["biolip_affinity_annotated"] | hits["gpcr_mapped_sites"]
    )
    summary = []
    for subset in ("all", "yes"):
        selected = [
            g for g in genes if subset == "all" or g["llm_known_ligand"] == "yes"
        ]
        for metric, members in sorted(hits.items()):
            count = sum(
                g["uniprot_acc"] in members and g["identifier_status"] == "unique"
                for g in selected
            )
            new = sum(
                g["uniprot_acc"] in members - old and g["identifier_status"] == "unique"
                for g in selected
            )
            summary.append(
                dict(
                    subset=subset,
                    metric=metric,
                    covered=count,
                    denominator=len(selected),
                    percent=round(100 * count / len(selected), 2),
                    new_vs_previous=new,
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
                for k in ("hgnc_id", "hgnc_symbol", "ensembl_gene", "ncbi_gene_id")
            }
        )
    write_tsv(OUT / "biolip_gpcrdb_summary.tsv", summary)
    write_tsv(OUT / "biolip_gpcrdb_genes.tsv", genes)
    write_tsv(OUT / "biolip_gpcrdb_evidence.tsv", evidence)
    (OUT / "biolip_gpcrdb_evidence.tsv.gz").write_bytes(
        gzip.compress((OUT / "biolip_gpcrdb_evidence.tsv").read_bytes(), mtime=0)
    )
    manifest = dict(
        bulk_urls=bulk_urls,
        bulk_file_times={
            name: datetime.fromtimestamp((RAW / name).stat().st_mtime, UTC).isoformat()
            for name in bulk_urls
        },
        uniprot_inputs={
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(
                (ROOT / "data/external/binding_site_audit/uniprot").glob("*.json")
            )
        },
        generated_at=datetime.now(UTC).isoformat(),
        stats=dict(stats),
        eligible_gpcr_receptors=len(receptors),
        experimental_structures=len(structures),
        inputs={
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(RAW.rglob("*"))
            if p.is_file()
        },
        cohort_sha256=hashlib.sha256(
            (OUT / "resource_comparison_genes.tsv").read_bytes()
        ).hexdigest(),
    )
    (OUT / "biolip_gpcrdb_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(summary, indent=2))
    print(stats)


if __name__ == "__main__":
    main()
