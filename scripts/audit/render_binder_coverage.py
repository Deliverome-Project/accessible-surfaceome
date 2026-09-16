"""Build a self-contained, searchable review artifact from pilot observations."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from accessible_surfaceome.sources._support.traceability import sha256_file, utc_now_iso

ROOT = Path(__file__).resolve().parents[2]
FIELDS = [
    "hgnc_id",
    "binder_name",
    "binder_type",
    "source",
    "exact_identity",
    "measurement_type",
    "measurement_value",
    "measurement_units",
    "measurement_low",
    "measurement_high",
    "measurement_relation",
    "assay",
    "surface_evidence",
    "epitope",
    "epitope_evidence",
    "validation_strength",
    "clone",
    "vendor",
    "catalog",
    "rrid",
    "sequence_available",
    "structure_available",
    "pmids",
    "source_url",
    "target_scope",
    "evidence_ids",
]


def main() -> None:
    directory = ROOT / "data/analysis/binder_coverage"

    def read(name: str) -> list[dict[str, str]]:
        with (directory / name).open() as stream:
            return list(csv.DictReader(stream, delimiter="\t"))

    observations = read("observations.tsv")
    genes = read("gene_coverage.tsv")
    strings = sorted({r[f] for r in observations for f in FIELDS})
    string_ids = {s: i for i, s in enumerate(strings)}
    data = {
        "genes": genes,
        "fields": FIELDS,
        "strings": strings,
        "observations": [[string_ids[r[f]] for f in FIELDS] for r in observations],
        "examples": read("literature_examples.tsv"),
    }
    template = ROOT / "src/accessible_surfaceome/binders/report.html"
    payload = json.dumps(data, separators=(",", ":")).replace("<", "\\u003c")
    destination = directory / "report.html"
    destination.write_text(template.read_text().replace("__PAYLOAD__", payload))
    (directory / "report_manifest.json").write_text(
        json.dumps(
            dict(
                generated_at=utc_now_iso(),
                template_sha256=sha256_file(template),
                generator_sha256=sha256_file(Path(__file__)),
                input_sha256={
                    n: sha256_file(directory / n)
                    for n in [
                        "observations.tsv",
                        "gene_coverage.tsv",
                        "coverage_summary.tsv",
                        "literature_examples.tsv",
                    ]
                },
                output_sha256=sha256_file(destination),
            ),
            indent=2,
        )
        + "\n"
    )
    print(destination, destination.stat().st_size)


if __name__ == "__main__":
    main()
