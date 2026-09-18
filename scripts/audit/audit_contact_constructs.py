"""Suggest construct merges only from matching sequence, chemistry and mapping.

Run --fetch to cache public PDBe metadata/coordinates for reviewed partner groups.
No accepted identities are changed automatically. This is a review queue, not a
claim that matching residue footprints establish molecular identity.
"""

import argparse
import concurrent.futures
import hashlib
import io
import json
import re
from collections import defaultdict
from pathlib import Path

import httpx
from Bio.PDB.MMCIF2Dict import MMCIF2Dict

from accessible_surfaceome.binders.contact_constructs import equivalent_construct_groups

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/analysis/deep_dive_binding_sites"
CACHE = ROOT / "data/external/contact_construct_audit"
UNIPROT = re.compile(
    r"(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9][A-Z][A-Z0-9]{2}[0-9])(?:-\d+)?$"
)


def candidate_records():
    groups = defaultdict(list)
    for rule in json.loads((DATA / "reviewed_contact_partners.json").read_text())[
        "rules"
    ]:
        for partner in rule["names"]:
            if UNIPROT.fullmatch(partner) and rule["pdb"]:
                groups[rule["uniprot_acc"], partner].append(rule)
    return [
        dict(
            target=target, partner=partner, pdb=rule["pdb"], name=rule["canonical_name"]
        )
        for (target, partner), rules in groups.items()
        if len({r["canonical_name"] for r in rules}) > 1
        for rule in rules
    ]


def retrieve(pdb):
    for suffix, url in [
        (".cif", f"https://www.ebi.ac.uk/pdbe/entry-files/download/{pdb}.cif"),
        ("-mapping.json", f"https://www.ebi.ac.uk/pdbe/api/mappings/uniprot/{pdb}"),
    ]:
        path = CACHE / (pdb + suffix)
        if path.exists():
            continue
        try:
            response = httpx.get(url, timeout=60, follow_redirects=True)
            response.raise_for_status()
            path.write_bytes(response.content)
        except (httpx.HTTPError, OSError) as error:
            return {"pdb": pdb, "error": str(error)}
    return {"pdb": pdb, "status": "cached"}


class IncompleteCategory(ValueError):
    """A present CIF category lacks fields needed to establish construct chemistry."""


def rows(cif, prefix, fields):
    # A wholly absent category means no deposited annotations, not known absence
    # of biological chemistry. A partially present category must never look empty.
    if not any(key.startswith(prefix) for key in cif):
        return []
    missing = [field for field in fields if not cif.get(prefix + field)]
    if missing:
        raise IncompleteCategory(
            f"{prefix} missing required fields: {', '.join(missing)}"
        )
    columns = [cif[prefix + field] for field in fields]
    if len({len(column) for column in columns}) != 1:
        raise IncompleteCategory(f"{prefix} has inconsistent column lengths")
    return zip(*columns, strict=True)


def describe(candidate):
    record = dict(candidate)
    pdb, partner = candidate["pdb"], candidate["partner"]
    path = CACHE / (pdb + ".cif")
    mapping_path = CACHE / (pdb + "-mapping.json")
    if not path.exists() or not mapping_path.exists():
        return dict(record, status="missing_inputs")
    try:
        mapping = json.loads(mapping_path.read_text())[pdb]["UniProt"]
        entities = {
            str(m["entity_id"]) for m in mapping.get(partner, {}).get("mappings", [])
        }
        if len(entities) != 1:
            return dict(record, status="ambiguous_or_missing_entity")
        entity = entities.pop()
        cif = MMCIF2Dict(io.StringIO(path.read_text()))
        monomers = [
            (int(num), mon)
            for eid, num, mon in rows(
                cif, "_entity_poly_seq.", ["entity_id", "num", "mon_id"]
            )
            if eid == entity
        ]
        ambiguity = len({n for n, _ in monomers}) != len(monomers)
        asym = dict(rows(cif, "_struct_asym.", ["id", "entity_id"]))
        links, external = [], []
        fields = [
            "conn_type_id",
            "ptnr1_label_asym_id",
            "ptnr1_label_seq_id",
            "ptnr1_label_comp_id",
            "ptnr1_label_atom_id",
            "ptnr2_label_asym_id",
            "ptnr2_label_seq_id",
            "ptnr2_label_comp_id",
            "ptnr2_label_atom_id",
        ]
        for kind, c1, n1, m1, a1, c2, n2, m2, a2 in rows(cif, "_struct_conn.", fields):
            if kind in {".", "?"}:
                raise IncompleteCategory("Unknown deposited connection type")
            if kind in {"covale", "disulf", "modres"} and any(
                value in {".", "?"} for value in (c1, m1, a1, c2, m2, a2)
            ):
                raise IncompleteCategory("Incomplete deposited covalent connection")
            if kind not in {"covale", "disulf", "modres"} or entity not in {
                asym.get(c1),
                asym.get(c2),
            }:
                continue
            if asym.get(c1) == asym.get(c2) == entity and c1 == c2:
                if n1 in {".", "?"} or n2 in {".", "?"}:
                    raise IncompleteCategory(
                        "Unknown polymer residue in covalent connection"
                    )
                links.append([kind, *sorted([[n1, m1, a1], [n2, m2, a2]])])
            else:
                external.append([kind, c1, n1, m1, c2, n2, m2])
        parents, spans = [], []
        for accession, info in mapping.items():
            matches = [m for m in info["mappings"] if str(m["entity_id"]) == entity]
            if matches:
                parents.append(accession)
                spans += [
                    (
                        accession,
                        m["unp_start"],
                        m["unp_end"],
                        m["start"]["residue_number"],
                        m["end"]["residue_number"],
                    )
                    for m in matches
                ]
        record.update(
            entity_id=entity,
            parent_accessions=sorted(parents),
            monomers=[m for _, m in sorted(monomers)],
            mapped_spans=sorted(set(spans)),
            internal_covalent_links=sorted({json.dumps(link) for link in links}),
            chemistry_checked=True,
            chemistry_annotation_scope="deposited_annotations_only",
            unresolved_chemistry=bool(external or ambiguity),
            attachment_caveats=external,
            status="complete" if not external and not ambiguity else "held_chemistry",
            coordinate_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            mapping_sha256=hashlib.sha256(mapping_path.read_bytes()).hexdigest(),
        )
        return record
    except IncompleteCategory as error:
        return dict(
            record,
            status="held_chemistry",
            chemistry_checked=False,
            unresolved_chemistry=True,
            error=str(error),
        )
    except (KeyError, ValueError, TypeError) as error:
        return dict(record, status="parse_error", error=str(error))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    candidates = candidate_records()
    CACHE.mkdir(parents=True, exist_ok=True)
    fetches = []
    if args.fetch:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            fetches = list(pool.map(retrieve, sorted({r["pdb"] for r in candidates})))
    records = [describe(r) for r in candidates]
    # Group within the same target and parent to avoid unnecessary cross-target
    # reidentification. No source observation or canonical name is overwritten.
    scoped = defaultdict(list)
    for record in records:
        scoped[record["target"], record["partner"]].append(record)
    suggestions = [
        g for group in scoped.values() for g in equivalent_construct_groups(group)
    ]
    output = dict(
        policy="suggestions_only_exact_deposited_construct_v1",
        records=records,
        suggestions=suggestions,
        fetches=fetches,
    )
    (DATA / "contact_construct_suggestions.json").write_text(
        json.dumps(output, indent=2) + "\n"
    )
    print(
        json.dumps(
            dict(
                records=len(records),
                structures=len({r["pdb"] for r in records}),
                suggestions=len(suggestions),
                held=sum(r["status"] != "complete" for r in records),
            )
        )
    )


if __name__ == "__main__":
    main()
