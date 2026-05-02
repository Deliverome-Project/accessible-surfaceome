"""Normalize the SURFY surfaceome snapshot (Bausch-Fluck 2018) for M1 merge.

Input: ``data/raw/table_S3_surfaceome.xlsx`` — the SurfaceomeMasterTable sheet
(20,193 human proteins × 44 columns) as published at
``http://wlab.ethz.ch/surfaceome/``. Row 1 of the spreadsheet is a title;
row 2 holds column headers.

Output: ``data/processed/surfy/surfy_human_snapshot.tsv`` — one row per
UniProt primary accession with the fields needed for the M1 candidate merge:

- identifiers: ``uniprot_accession``, ``uniprot_name``, ``uniprot_description``,
  ``gene_symbol``, ``ensembl_gene``, ``ensembl_protein``, ``entrez_gene_id``,
  ``cd_number``
- SURFY classification: ``surfy_label`` (``surface`` / ``nonsurface`` / empty),
  ``surfy_label_source``, ``surfy_ml_score``, ``surfy_ml_fpr_class``,
  ``surfy_ml_trainingset``
- topology: ``protein_length``, ``tm_domain_count``, ``signal_peptide``,
  ``topology_string``, ``topology_source``
- Almen (Membranome) class: ``almen_main_class``, ``almen_sub_class``
- companion flags: ``cspa_category``, ``cspa_peptide_count`` (the SURFY
  table pre-joins CSPA information), ``uniprot_subcellular``,
  ``uniprot_keywords``, ``hpa_antibody``, ``drugbank_ids``

A compact derived boolean ``surfy_is_surface`` is emitted for downstream
filtering (``surfy_label == "surface"``).

Also writes:
- ``surfy_human_snapshot_summary.json`` — row counts by label, sanity checks
- ``surfy_build_traceability.json`` — source file SHA256, capture time,
  row counts, script identity
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import pandas as pd

from surface_proteome.candidates.traceability import (
    sha256_file,
    utc_now_iso,
)

from surface_proteome.paths import REPO_ROOT as ROOT

DATASET = "surfy"
DEFAULT_INPUT = ROOT / "data" / "raw" / "table_S3_surfaceome.xlsx"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "processed" / "surfy"
OUTPUT_TSV_NAME = "surfy_human_snapshot.tsv"
OUTPUT_SUMMARY_NAME = "surfy_human_snapshot_summary.json"
OUTPUT_MANIFEST_NAME = "surfy_build_traceability.json"
SURFY_SOURCE_URL = "http://wlab.ethz.ch/surfaceome/table_S3_surfaceome.xlsx"
SHEET_NAME = "SurfaceomeMasterTable"

COLUMN_MAP: list[tuple[str, str]] = [
    # (source column as it appears in row 2 of the sheet, normalized output name)
    ("UniProt accession", "uniprot_accession"),
    ("UniProt name", "uniprot_name"),
    ("UniProt description", "uniprot_description"),
    ("UniProt gene", "gene_symbol"),
    ("Ensembl gene", "ensembl_gene"),
    ("Ensembl protein", "ensembl_protein"),
    ("GeneID", "entrez_gene_id"),
    ("CD number", "cd_number"),
    ("Surfaceome Label", "surfy_label"),
    ("Surfaceome Label Source", "surfy_label_source"),
    ("Comment", "surfy_comment"),
    ("MachineLearning score", "surfy_ml_score"),
    ("MachineLearning FPR class (1=1%, 2=5%, 3=15%)", "surfy_ml_fpr_class"),
    ("MachineLearning trainingset", "surfy_ml_trainingset"),
    ("length", "protein_length"),
    ("TM domains", "tm_domain_count"),
    ("signalpeptide", "signal_peptide"),
    ("topology", "topology_string"),
    ("topology source", "topology_source"),
    ("Membranome Almen main-class", "almen_main_class"),
    ("Membranome Almen sub-class", "almen_sub_class"),
    ("CSPA category", "cspa_category"),
    ("CSPA peptide count", "cspa_peptide_count"),
    ("UniProt subcellular", "uniprot_subcellular"),
    ("UniProt keywords", "uniprot_keywords"),
    ("HPA antibody", "hpa_antibody"),
    ("DrugBank approved drug IDs", "drugbank_ids"),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    input_path: Path = args.input
    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise FileNotFoundError(f"SURFY source not found: {input_path}")

    print(f"reading {input_path} (sheet={SHEET_NAME!r}) ...")
    # row 1 is the title "table S3: List of human proteins..."; actual headers in row 2
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = pd.read_excel(input_path, sheet_name=SHEET_NAME, header=1)
    print(f"  rows={len(df):,}  cols={df.shape[1]}")

    missing = [src for src, _ in COLUMN_MAP if src not in df.columns]
    if missing:
        raise RuntimeError(
            "SURFY header layout drifted; missing expected columns:\n  "
            + "\n  ".join(missing)
        )

    out = df[[src for src, _ in COLUMN_MAP]].copy()
    out.columns = [dst for _, dst in COLUMN_MAP]

    if out["uniprot_accession"].isna().any():
        n_null = int(out["uniprot_accession"].isna().sum())
        raise RuntimeError(
            f"Refusing to write: {n_null} rows have NaN uniprot_accession "
            f"(M1 join key). Inspect source sheet."
        )

    out["uniprot_accession"] = out["uniprot_accession"].astype(str).str.strip()
    out["gene_symbol"] = out["gene_symbol"].astype(str).where(
        out["gene_symbol"].notna(), ""
    ).str.strip()
    out["surfy_label"] = out["surfy_label"].astype(str).where(
        out["surfy_label"].notna(), ""
    ).str.strip().str.lower()
    out["surfy_is_surface"] = (out["surfy_label"] == "surface").astype(int)

    dupes = out["uniprot_accession"].duplicated().sum()
    if dupes:
        print(f"  WARNING: {dupes} duplicate uniprot_accession rows")

    output_tsv = out_dir / OUTPUT_TSV_NAME
    out.to_csv(output_tsv, sep="\t", index=False)

    label_counts = out["surfy_label"].value_counts(dropna=False).to_dict()
    label_counts = {("" if k in ("", "nan") else str(k)): int(v) for k, v in label_counts.items()}
    summary = {
        "source_file": str(input_path.relative_to(ROOT)),
        "source_url": SURFY_SOURCE_URL,
        "source_sha256": sha256_file(input_path),
        "source_size_bytes": input_path.stat().st_size,
        "sheet": SHEET_NAME,
        "n_rows": int(len(out)),
        "n_unique_accession": int(out["uniprot_accession"].nunique()),
        "n_rows_with_gene_symbol": int((out["gene_symbol"] != "").sum()),
        "surfy_label_counts": label_counts,
        "n_surface": int(out["surfy_is_surface"].sum()),
        "n_cspa_high_confidence": int(
            out["cspa_category"].astype(str).str.contains(r"high\s*confidence", case=False, na=False).sum()
        ),
        "generated_at_utc": utc_now_iso(),
    }
    (out_dir / OUTPUT_SUMMARY_NAME).write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    manifest = {
        "dataset": DATASET,
        "generated_at_utc": utc_now_iso(),
        "script": Path(__file__).relative_to(ROOT).as_posix(),
        "source": {
            "url": SURFY_SOURCE_URL,
            "local_path": str(input_path.relative_to(ROOT)),
            "sheet": SHEET_NAME,
            "sha256": sha256_file(input_path),
            "size_bytes": input_path.stat().st_size,
        },
        "outputs": {
            OUTPUT_TSV_NAME: {
                "local_path": str(output_tsv.relative_to(ROOT)),
                "sha256": sha256_file(output_tsv),
                "size_bytes": output_tsv.stat().st_size,
                "n_rows": int(len(out)),
                "primary_key": "uniprot_accession",
            }
        },
        "column_map": [{"source": s, "output": d} for s, d in COLUMN_MAP],
        "derived_columns": [
            {
                "name": "surfy_is_surface",
                "rule": "1 iff lower(surfy_label) == 'surface' else 0",
            }
        ],
    }
    (out_dir / OUTPUT_MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(f"wrote {output_tsv}")
    print(f"  label counts: {label_counts}")
    print(f"  n_surface:                {summary['n_surface']:,}")
    print(f"  n_cspa_high_confidence:   {summary['n_cspa_high_confidence']:,}")
    print(f"  unique uniprot accession: {summary['n_unique_accession']:,}")


if __name__ == "__main__":
    main()
