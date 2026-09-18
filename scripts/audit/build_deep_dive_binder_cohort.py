"""Freeze the full 5,130-record deep-dive set, without candidate-universe filtering."""

import csv
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from accessible_surfaceome.binders.coverage import (
    FIELDS,
    ID_FIELDS,
    biogrid_observations,
    gtop_observations,
    read_csv,
    unique_index,
    write_tsv,
)

ROOT = Path(__file__).resolve().parents[2]


def main():
    raw = ROOT / "data/external/binder_coverage"
    out = ROOT / "data/analysis/deep_dive_binding_sites"
    out.mkdir(parents=True, exist_ok=True)
    annotations = json.loads((raw / "annotations.json").read_text())
    identifiers = unique_index(
        json.loads((raw / "identifiers.json").read_text()), "hgnc_id"
    )
    prior = {
        r["hgnc_id"]: r
        for r in csv.DictReader(
            (ROOT / "data/analysis/binder_coverage/gene_coverage.tsv").open(),
            delimiter="\t",
        )
    }
    genes = [json.loads(row["gene_json"]) for row in annotations]
    assert len(genes) == len({g["hgnc_id"] for g in genes}) == 5130
    counts = Counter(identifiers[g["hgnc_id"]]["uniprot_acc"] for g in genes)
    rows = []
    for gene in sorted(genes, key=lambda g: g["hgnc_id"]):
        canonical = identifiers[gene["hgnc_id"]]
        assert gene["uniprot_acc"] == canonical["uniprot_acc"]
        row: dict[str, Any] = {key: str(canonical.get(key) or "") for key in ID_FIELDS}
        row.update(
            triage_classical_receptor=prior.get(row["hgnc_id"], {}).get(
                "triage_classical_receptor", ""
            ),
            triage_surface_yes=prior.get(row["hgnc_id"], {}).get(
                "triage_surface_yes", ""
            ),
            in_previous_candidate_audit=int(row["hgnc_id"] in prior),
            identifier_status="unique"
            if counts[row["uniprot_acc"]] == 1
            else "shared_uniprot_ambiguous",
        )
        rows.append(row)
    write_tsv(out / "cohort.tsv", rows)
    unique = [r for r in rows if r["identifier_status"] == "unique"]
    observations, audit = gtop_observations(
        read_csv(raw / "gtop_interactions.txt", gtop=True),
        read_csv(raw / "gtop_ligands.txt", gtop=True),
        read_csv(raw / "thera.csv"),
        unique_index(unique, "uniprot_acc"),
    )
    synthetic, synthetic_audit = biogrid_observations(
        raw, unique_index(unique, "hgnc_id")
    )
    observations.extend(synthetic)
    write_tsv(out / "prior_observations.tsv", observations, FIELDS)
    (out / "prior_observations.tsv.gz").write_bytes(
        gzip.compress((out / "prior_observations.tsv").read_bytes(), mtime=0)
    )
    manifest = dict(
        denominator=len(rows),
        previous_overlap=sum(r["in_previous_candidate_audit"] for r in rows),
        unique_accessions=len(counts),
        ambiguous_rows=len(rows) - len(unique),
        ambiguous_accessions={a: n for a, n in counts.items() if n > 1},
        gtopdb=dict(audit),
        biogrid=dict(synthetic_audit),
        inputs={
            name: hashlib.sha256((raw / name).read_bytes()).hexdigest()
            for name in ["annotations.json", "identifiers.json"]
        },
    )
    (out / "cohort_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
