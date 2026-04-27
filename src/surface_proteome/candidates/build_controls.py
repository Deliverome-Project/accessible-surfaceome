"""Build a consolidated positive/negative control table for surfaceome QC.

This script builds a single deduplicated control panel with:
1) Positive controls from ADC benchmark targets.
2) Positive controls from Lycia/LYTAC handle targets.
3) Negative controls from user-specified genes plus an additional non-surface
   set selected from a parent 2,379-gene surfaceome list.

Inputs are intentionally passed as file arguments so this script can be reused
against updated control JSONs and updated parent surfaceome lists.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_OUTPUT_TSV = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "processed"
    / "controls"
    / "surfaceome_control_panel.tsv"
)
DEFAULT_OUTPUT_SUMMARY = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "processed"
    / "controls"
    / "surfaceome_control_panel_summary.json"
)
DEFAULT_ADDITIONAL_NEGATIVE = "RPN2,GALNT1,ST3GAL1,ST3GAL4,TMED4,EXTL2,DMXL2"
DEFAULT_SPECIFIED_NEGATIVE = "ABCB9,KRAS"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--controls-json",
        type=Path,
        required=True,
        help="Path to canonical delivery positive controls JSON.",
    )
    parser.add_argument(
        "--surfaceome-csv",
        type=Path,
        required=True,
        help="Path to parent surfaceome_expressed.csv (~2,379 genes).",
    )
    parser.add_argument(
        "--output-tsv",
        type=Path,
        default=DEFAULT_OUTPUT_TSV,
        help=f"Output TSV path (default: {DEFAULT_OUTPUT_TSV})",
    )
    parser.add_argument(
        "--output-summary",
        type=Path,
        default=DEFAULT_OUTPUT_SUMMARY,
        help=f"Output summary JSON path (default: {DEFAULT_OUTPUT_SUMMARY})",
    )
    parser.add_argument(
        "--additional-negative-genes",
        default=DEFAULT_ADDITIONAL_NEGATIVE,
        help=(
            "Comma-separated extra likely non-surface genes from the parent "
            "surfaceome list."
        ),
    )
    parser.add_argument(
        "--specified-negative-genes",
        default=DEFAULT_SPECIFIED_NEGATIVE,
        help="Comma-separated explicitly requested non-surface negatives.",
    )
    return parser.parse_args()


def _csv_symbols(raw: str) -> list[str]:
    """Parse comma-separated symbols into uppercase tokens."""
    return [token.strip().upper() for token in raw.split(",") if token.strip()]


def _extract_adc_rows(positive_controls: dict[str, Any]) -> list[dict[str, Any]]:
    """Return ADC benchmark rows."""
    return list(positive_controls["tumor_adc_targets"])


def _extract_lytac_rows(positive_controls: dict[str, Any]) -> list[dict[str, Any]]:
    """Return Lycia/LYTAC handle rows plus IGF2R (CI-M6PR handle)."""
    patent_rows = list(positive_controls["patent_delivery_handles"])
    lycia_rows = [
        row
        for row in patent_rows
        if "lycia handle list" in str(row.get("notes", "")).lower()
    ]

    igf2r_rows = [
        row
        for row in positive_controls["bbb_rmt_targets"]
        if str(row.get("gene_symbol", "")).upper() == "IGF2R"
    ]
    return lycia_rows + igf2r_rows


def _build_record(
    *,
    gene_symbol: str,
    target_name: str,
    control_class: str,
    control_group: str,
    provenance: str,
    source_note: str,
) -> dict[str, str]:
    """Create one control row."""
    return {
        "gene_symbol": gene_symbol.upper(),
        "target_name": target_name,
        "control_class": control_class,
        "control_group": control_group,
        "provenance": provenance,
        "source_note": source_note,
    }


def build_control_panel(
    *,
    controls_json: Path,
    surfaceome_csv: Path,
    additional_negative_genes: list[str],
    specified_negative_genes: list[str],
) -> pd.DataFrame:
    """Build the consolidated panel and annotate against the parent list."""
    controls_obj = json.loads(controls_json.read_text())
    positive_controls = controls_obj["positive_controls"]

    records: list[dict[str, str]] = []

    for row in _extract_adc_rows(positive_controls):
        records.append(
            _build_record(
                gene_symbol=str(row.get("gene_symbol", "")),
                target_name=str(row.get("target_name", "")),
                control_class="positive_surfaceome",
                control_group="adc_benchmark",
                provenance=(
                    "canonical_delivery_positive_controls.controls.json:"
                    "positive_controls.tumor_adc_targets"
                ),
                source_note=str(row.get("notes", "")),
            )
        )

    for row in _extract_lytac_rows(positive_controls):
        records.append(
            _build_record(
                gene_symbol=str(row.get("gene_symbol", "")),
                target_name=str(row.get("target_name", "")),
                control_class="positive_surfaceome",
                control_group="lytac_benchmark",
                provenance=(
                    "canonical_delivery_positive_controls.controls.json "
                    "(Lycia WO2024155750A1 handles + IGF2R/CI-M6PR handle)"
                ),
                source_note=str(row.get("notes", "")),
            )
        )

    for gene in additional_negative_genes:
        records.append(
            _build_record(
                gene_symbol=gene,
                target_name=gene,
                control_class="negative_non_surfaceome",
                control_group="additional_negative_from_2379",
                provenance=(
                    "surfaceome_expressed.csv (parent repo) candidates with "
                    "nonsurface label and non-cell-membrane UniProt localization"
                ),
                source_note=(
                    "Added as likely non-surface negative control from "
                    "2,379-list request"
                ),
            )
        )

    for gene in specified_negative_genes:
        records.append(
            _build_record(
                gene_symbol=gene,
                target_name=gene,
                control_class="negative_non_surfaceome",
                control_group="specified_negative",
                provenance="User-specified negatives",
                source_note="Explicitly requested as non-surface control",
            )
        )

    raw = pd.DataFrame.from_records(records)

    # Aggregate in case any gene appears in multiple groups.
    agg = raw.groupby("gene_symbol", as_index=False).agg(
        {
            "target_name": lambda x: "; ".join(sorted(set(v for v in x if v))),
            "control_class": lambda x: ";".join(sorted(set(x))),
            "control_group": lambda x: ";".join(sorted(set(x))),
            "provenance": lambda x: " | ".join(sorted(set(x))),
            "source_note": lambda x: " | ".join(sorted(set(v for v in x if v))),
        }
    )

    surfaceome = pd.read_csv(surfaceome_csv)
    surfaceome["gene_symbol"] = surfaceome["gene_symbol"].astype(str).str.upper()

    lookup_cols = [
        "gene_symbol",
        "surfaceome_label",
        "label_source",
        "uniprot_id",
        "uniprot_subcellular",
        "has_cell_membrane_uniprot",
        "passes_topology_gate",
    ]
    lookup = (
        surfaceome[lookup_cols]
        .sort_values("gene_symbol")
        .drop_duplicates("gene_symbol", keep="first")
    )

    final = agg.merge(lookup, on="gene_symbol", how="left")
    final["in_parent_surfaceome_2379"] = final["surfaceome_label"].notna().map(
        {True: "yes", False: "no"}
    )

    final["sort_order"] = final["control_class"].map(
        {
            "positive_surfaceome": 0,
            "negative_non_surfaceome": 1,
        }
    ).fillna(9)
    final = final.sort_values(["sort_order", "control_group", "gene_symbol"]).drop(
        columns=["sort_order"]
    )

    ordered_cols = [
        "gene_symbol",
        "target_name",
        "control_class",
        "control_group",
        "in_parent_surfaceome_2379",
        "surfaceome_label",
        "label_source",
        "uniprot_id",
        "has_cell_membrane_uniprot",
        "passes_topology_gate",
        "uniprot_subcellular",
        "provenance",
        "source_note",
    ]
    return final[ordered_cols]


def main() -> None:
    """CLI entrypoint."""
    args = parse_args()
    controls_json = args.controls_json.expanduser().resolve()
    surfaceome_csv = args.surfaceome_csv.expanduser().resolve()
    output_tsv = args.output_tsv.expanduser().resolve()
    output_summary = args.output_summary.expanduser().resolve()
    additional_negative_genes = _csv_symbols(args.additional_negative_genes)
    specified_negative_genes = _csv_symbols(args.specified_negative_genes)

    panel = build_control_panel(
        controls_json=controls_json,
        surfaceome_csv=surfaceome_csv,
        additional_negative_genes=additional_negative_genes,
        specified_negative_genes=specified_negative_genes,
    )

    output_tsv.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(output_tsv, sep="\t", index=False)

    summary = {
        "output": str(output_tsv),
        "n_rows": int(len(panel)),
        "n_positive_surfaceome": int(
            (panel["control_class"] == "positive_surfaceome").sum()
        ),
        "n_negative_non_surfaceome": int(
            (panel["control_class"] == "negative_non_surfaceome").sum()
        ),
        "n_missing_from_parent_surfaceome_2379": int(
            (panel["in_parent_surfaceome_2379"] == "no").sum()
        ),
    }
    output_summary.write_text(json.dumps(summary, indent=2) + "\n")

    print(json.dumps(summary, indent=2))
    print(f"Wrote {output_tsv}")
    print(f"Wrote {output_summary}")


if __name__ == "__main__":
    main()
