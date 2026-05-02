"""Normalize the CSPA (Cell Surface Protein Atlas) snapshot for M1 merge.

Input: ``data/raw/S1_File.xlsx`` — the PLOS ONE 2015 supplementary workbook
from Bausch-Fluck et al., containing six tables. This script uses:

- ``Table_A`` — per-experiment detection rows (24,445 rows for human + mouse);
  collapsed here to one row per (organism, UniProt accession).
- ``Table_B`` — 1,492 human proteins with CSPA category
  (``1 - high confidence`` / ``2 - putative`` / ``3 - unspecific``), CD number,
  ENTREZ gene ID, and a 47-column cell-type detection matrix.

Output: ``data/processed/cspa/cspa_human_snapshot.tsv`` — one row per human
UniProt primary accession with:

- identifiers: ``uniprot_accession``, ``uniprot_entry_name`` (from Table_A),
  ``gene_symbol`` (ENTREZ), ``entrez_gene_id``, ``cd_number``
- detection summary: ``cspa_n_experiments`` (rows in Table_A),
  ``cspa_max_protein_probability``, ``cspa_max_unique_peps``,
  ``cspa_cell_type_count`` (from Table_B "Protein count")
- classification: ``cspa_category`` + derived boolean flags
  ``cspa_is_high_confidence``, ``cspa_is_putative``, ``cspa_is_unspecific``,
  ``cspa_is_detected``

A mouse counterpart is emitted as ``cspa_mouse_snapshot.tsv`` for future
cross-species work. Mouse rows use Table_A only (Table_B in this workbook is
human-scoped).

Also writes:
- ``cspa_build_summary.json`` — row counts, category distributions
- ``cspa_build_traceability.json`` — source file SHA256, capture time
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

ROOT = Path(__file__).resolve().parents[3]

DATASET = "cspa"
DEFAULT_INPUT = ROOT / "data" / "raw" / "S1_File.xlsx"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "processed" / "cspa"
HUMAN_TSV = "cspa_human_snapshot.tsv"
MOUSE_TSV = "cspa_mouse_snapshot.tsv"
SUMMARY_JSON = "cspa_build_summary.json"
MANIFEST_JSON = "cspa_build_traceability.json"
SOURCE_URL = (
    "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0121314.s002"
    "&type=supplementary"
)


def _collapse_table_a(a: pd.DataFrame, organism: str) -> pd.DataFrame:
    """Collapse Table_A to one row per UniProt accession for a given organism."""
    sub = a[a["organism"] == organism].copy()
    grouped = (
        sub.groupby("ID_link", as_index=False)
        .agg(
            cspa_n_experiments=("Experiment tag", "count"),
            cspa_n_unique_experiments=("Experiment tag", "nunique"),
            cspa_max_protein_probability=("protein probability", "max"),
            cspa_max_unique_peps=("num unique peps", "max"),
            gene_symbol=("ENTREZ gene symbol", "first"),
            uniprot_entry_name=("UP_entry_name", "first"),
            entrez_gene_id=("ENTREZ ac", "first"),
        )
        .rename(columns={"ID_link": "uniprot_accession"})
    )
    return grouped


def _categorize(cat_str: str) -> dict[str, int]:
    low = str(cat_str or "").lower()
    return {
        "cspa_is_high_confidence": int("high" in low and "confidence" in low),
        "cspa_is_putative": int("putative" in low),
        "cspa_is_unspecific": int("unspecific" in low),
    }


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
        raise FileNotFoundError(f"CSPA source not found: {input_path}")

    print(f"reading {input_path} (Table_A, Table_B) ...")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a = pd.read_excel(input_path, sheet_name="Table_A")
        b = pd.read_excel(input_path, sheet_name="Table_B")

    # Normalize column names (Table_B has a few with embedded newlines/whitespace)
    b.columns = [str(c).strip() for c in b.columns]

    expected_a = {
        "organism", "Experiment tag", "ID_link", "CD", "ENTREZ ac",
        "ENTREZ gene symbol", "UP_entry_name",
        "count detection in different cell types", "protein probability",
        "num unique peps",
    }
    missing_a = expected_a - set(a.columns)
    if missing_a:
        raise RuntimeError(f"Table_A column drift; missing: {sorted(missing_a)}")

    expected_b = {"Organisme", "ID_link", "CSPA category", "CD", "ENTREZ geneID", "Protein count"}
    missing_b = expected_b - set(b.columns)
    if missing_b:
        raise RuntimeError(f"Table_B column drift; missing: {sorted(missing_b)}")

    # --- human build ---
    human = _collapse_table_a(a, "Human")
    b_meta = b.rename(columns={
        "ID_link": "uniprot_accession",
        "CSPA category": "cspa_category",
        "CD": "cd_number",
        "ENTREZ geneID": "entrez_gene_id_table_b",
        "Protein count": "cspa_cell_type_count",
    })[[
        "uniprot_accession", "cspa_category", "cd_number",
        "entrez_gene_id_table_b", "cspa_cell_type_count",
    ]]

    human = human.merge(b_meta, on="uniprot_accession", how="left")

    # prefer Table_B entrez when present (canonical in category table)
    human["entrez_gene_id"] = human["entrez_gene_id_table_b"].combine_first(
        human["entrez_gene_id"]
    )
    human = human.drop(columns=["entrez_gene_id_table_b"])

    for col in ["cspa_category", "cd_number", "uniprot_entry_name", "gene_symbol"]:
        human[col] = human[col].astype(object).where(human[col].notna(), "")

    derived = human["cspa_category"].apply(_categorize).apply(pd.Series)
    human = pd.concat([human, derived], axis=1)
    human["cspa_is_detected"] = 1

    human = human[[
        "uniprot_accession", "uniprot_entry_name", "gene_symbol", "entrez_gene_id",
        "cd_number", "cspa_category",
        "cspa_is_detected", "cspa_is_high_confidence", "cspa_is_putative",
        "cspa_is_unspecific",
        "cspa_n_experiments", "cspa_n_unique_experiments",
        "cspa_max_protein_probability", "cspa_max_unique_peps",
        "cspa_cell_type_count",
    ]].sort_values("uniprot_accession").reset_index(drop=True)

    human_tsv = out_dir / HUMAN_TSV
    human.to_csv(human_tsv, sep="\t", index=False)

    # --- mouse build (detection only; no category table in this workbook) ---
    mouse = _collapse_table_a(a, "Mouse")
    mouse["cspa_category"] = ""
    mouse["cd_number"] = ""
    mouse["cspa_cell_type_count"] = pd.NA
    mouse["cspa_is_detected"] = 1
    mouse["cspa_is_high_confidence"] = 0
    mouse["cspa_is_putative"] = 0
    mouse["cspa_is_unspecific"] = 0
    mouse = mouse[[
        "uniprot_accession", "uniprot_entry_name", "gene_symbol", "entrez_gene_id",
        "cd_number", "cspa_category",
        "cspa_is_detected", "cspa_is_high_confidence", "cspa_is_putative",
        "cspa_is_unspecific",
        "cspa_n_experiments", "cspa_n_unique_experiments",
        "cspa_max_protein_probability", "cspa_max_unique_peps",
        "cspa_cell_type_count",
    ]].sort_values("uniprot_accession").reset_index(drop=True)

    mouse_tsv = out_dir / MOUSE_TSV
    mouse.to_csv(mouse_tsv, sep="\t", index=False)

    human_cat_counts = {
        k: int(v) for k, v in
        human["cspa_category"].value_counts(dropna=False).to_dict().items()
    }
    summary = {
        "source_file": str(input_path.relative_to(ROOT)),
        "source_url": SOURCE_URL,
        "source_sha256": sha256_file(input_path),
        "source_size_bytes": input_path.stat().st_size,
        "human": {
            "n_proteins": int(len(human)),
            "n_unique_accession": int(human["uniprot_accession"].nunique()),
            "n_with_category": int((human["cspa_category"] != "").sum()),
            "n_high_confidence": int(human["cspa_is_high_confidence"].sum()),
            "n_putative": int(human["cspa_is_putative"].sum()),
            "n_unspecific": int(human["cspa_is_unspecific"].sum()),
            "cspa_category_counts": human_cat_counts,
        },
        "mouse": {
            "n_proteins": int(len(mouse)),
            "n_unique_accession": int(mouse["uniprot_accession"].nunique()),
        },
        "table_a_rows_total": int(len(a)),
        "table_b_rows_total": int(len(b)),
        "generated_at_utc": utc_now_iso(),
    }
    (out_dir / SUMMARY_JSON).write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    manifest = {
        "dataset": DATASET,
        "generated_at_utc": utc_now_iso(),
        "script": Path(__file__).relative_to(ROOT).as_posix(),
        "source": {
            "url": SOURCE_URL,
            "local_path": str(input_path.relative_to(ROOT)),
            "sheets_used": ["Table_A", "Table_B"],
            "sha256": sha256_file(input_path),
            "size_bytes": input_path.stat().st_size,
        },
        "outputs": {
            HUMAN_TSV: {
                "local_path": str(human_tsv.relative_to(ROOT)),
                "sha256": sha256_file(human_tsv),
                "size_bytes": human_tsv.stat().st_size,
                "n_rows": int(len(human)),
                "primary_key": "uniprot_accession",
            },
            MOUSE_TSV: {
                "local_path": str(mouse_tsv.relative_to(ROOT)),
                "sha256": sha256_file(mouse_tsv),
                "size_bytes": mouse_tsv.stat().st_size,
                "n_rows": int(len(mouse)),
                "primary_key": "uniprot_accession",
            },
        },
        "derived_columns": [
            {"name": "cspa_is_detected", "rule": "1 for all rows (presence in Table_A)"},
            {"name": "cspa_is_high_confidence", "rule": "1 iff 'high confidence' in cspa_category"},
            {"name": "cspa_is_putative", "rule": "1 iff 'putative' in cspa_category"},
            {"name": "cspa_is_unspecific", "rule": "1 iff 'unspecific' in cspa_category"},
        ],
    }
    (out_dir / MANIFEST_JSON).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(f"wrote {human_tsv}  ({len(human):,} proteins)")
    print(f"wrote {mouse_tsv}  ({len(mouse):,} proteins)")
    print(f"  human category counts: {human_cat_counts}")
    print(f"  high_confidence={summary['human']['n_high_confidence']:,}  "
          f"putative={summary['human']['n_putative']:,}  "
          f"unspecific={summary['human']['n_unspecific']:,}")


if __name__ == "__main__":
    main()
