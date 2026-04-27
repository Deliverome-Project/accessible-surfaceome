"""Build a consolidated positive/negative control table for surfaceome QC.

This script builds a single deduplicated control panel with:
1) Positive controls from ADC benchmark targets.
2) Positive controls from Lycia/LYTAC handle targets.
3) Negative controls from user-specified genes plus an additional non-surface
   set selected from a parent 2,379-gene surfaceome list.

Alias resolution is done via one MyGene pass over a provided symbol universe
(for this project, typically the ~6.5k candidate universe symbols). No HGNC
fallback map is used in this resolver.

Inputs are intentionally passed as file arguments so this script can be reused
against updated control JSONs and updated parent surfaceome lists.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import mygene
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]

DEFAULT_OUTPUT_TSV = (
    ROOT
    / "data"
    / "processed"
    / "controls"
    / "surfaceome_control_panel.tsv"
)
DEFAULT_OUTPUT_SUMMARY = (
    ROOT
    / "data"
    / "processed"
    / "controls"
    / "surfaceome_control_panel_summary.json"
)
DEFAULT_CANDIDATE_UNIVERSE_TSV = (
    ROOT / "data" / "processed" / "candidate_universe" / "candidate_universe.tsv"
)
DEFAULT_ADDITIONAL_NEGATIVE = (
    "RPN2,GALNT1,ST3GAL1,ST3GAL4,TMED4,EXTL2,DMXL2,GPR137B,LMAN2"
)
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
        "--mygene-symbol-universe-tsv",
        type=Path,
        default=DEFAULT_CANDIDATE_UNIVERSE_TSV,
        help=(
            "TSV/CSV with `gene_symbol` column used to build one-pass MyGene "
            "alias index (default: candidate_universe.tsv)."
        ),
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


def _load_gene_symbols(table_path: Path) -> list[str]:
    """Load uppercase gene symbols from a CSV/TSV table."""
    if table_path.suffix.lower() == ".tsv":
        table = pd.read_csv(table_path, sep="\t")
    else:
        table = pd.read_csv(table_path)
    if "gene_symbol" not in table.columns:
        raise ValueError(f"{table_path} missing required column: gene_symbol")
    symbols = sorted(
        {
            str(symbol).strip().upper()
            for symbol in table["gene_symbol"].astype(str)
            if str(symbol).strip()
        }
    )
    return symbols


def _build_mygene_alias_index(symbols: list[str]) -> tuple[dict[str, str], dict[str, int]]:
    """Resolve aliases with one MyGene query pass over the symbol universe."""
    mg = mygene.MyGeneInfo()
    symbol_set = set(symbols)
    hits = mg.querymany(
        symbols,
        scopes="symbol,alias,prev_symbol",
        fields="symbol,alias,prev_symbol",
        species="human",
        as_dataframe=False,
        returnall=False,
        verbose=False,
    )

    alias_to_symbols: dict[str, set[str]] = {}
    resolved_hits = 0
    notfound_hits = 0
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        query_symbol = str(hit.get("query", "")).strip().upper()
        if query_symbol not in symbol_set:
            continue
        if hit.get("notfound"):
            notfound_hits += 1
            continue
        symbol = str(hit.get("symbol", "")).strip().upper()
        if not symbol:
            continue
        resolved_hits += 1
        raw_aliases = hit.get("alias", [])
        if isinstance(raw_aliases, str):
            alias_values = [raw_aliases]
        elif isinstance(raw_aliases, list):
            alias_values = raw_aliases
        else:
            alias_values = []
        aliases = [symbol, *alias_values]
        for alias in aliases:
            alias_symbol = str(alias).strip().upper()
            if not alias_symbol:
                continue
            alias_to_symbols.setdefault(alias_symbol, set()).add(query_symbol)

    alias_to_symbol: dict[str, str] = {}
    ambiguous_aliases = 0
    for alias_symbol, mapped_symbols in alias_to_symbols.items():
        if len(mapped_symbols) == 1:
            alias_to_symbol[alias_symbol] = next(iter(mapped_symbols))
        else:
            ambiguous_aliases += 1

    stats = {
        "n_query_symbols": len(symbols),
        "n_hits_resolved": resolved_hits,
        "n_hits_notfound": notfound_hits,
        "n_aliases_unique": len(alias_to_symbol),
        "n_aliases_ambiguous": ambiguous_aliases,
    }
    return alias_to_symbol, stats


def _row_aliases(row: dict[str, Any]) -> list[str]:
    """Return normalized alias symbols from a control row."""
    raw_aliases = row.get("aliases", [])
    if isinstance(raw_aliases, str):
        return _csv_symbols(raw_aliases)
    if isinstance(raw_aliases, list):
        return [
            str(alias).strip().upper()
            for alias in raw_aliases
            if str(alias).strip()
        ]
    return []


def _build_record(
    *,
    gene_symbol: str,
    target_name: str,
    control_class: str,
    control_group: str,
    provenance: str,
    source_note: str,
    aliases: list[str] | None = None,
) -> dict[str, str]:
    """Create one control row."""
    alias_values = aliases or []
    alias_symbols = sorted(
        {
            alias.strip().upper()
            for alias in alias_values
            if alias and alias.strip()
        }
    )
    return {
        "gene_symbol": gene_symbol.upper(),
        "gene_symbol_aliases": ";".join(alias_symbols),
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
    mygene_alias_to_symbol: dict[str, str],
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
                aliases=_row_aliases(row),
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
                aliases=_row_aliases(row),
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
                aliases=[],
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
                aliases=[],
            )
        )

    raw = pd.DataFrame.from_records(records)

    # Aggregate in case any gene appears in multiple groups.
    agg = raw.groupby("gene_symbol", as_index=False).agg(
        {
            "gene_symbol_aliases": lambda x: ";".join(
                sorted(
                    {
                        token
                        for value in x
                        for token in str(value).split(";")
                        if token
                    }
                )
            ),
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

    lookup_gene_set = set(lookup["gene_symbol"])

    def resolve_lookup_match(row: pd.Series) -> pd.Series:
        candidates = [str(row["gene_symbol"]).upper()]
        aliases = [
            token
            for token in str(row.get("gene_symbol_aliases", "")).split(";")
            if token
        ]
        for symbol in candidates:
            if symbol in lookup_gene_set:
                return pd.Series(
                    {
                        "matched_surfaceome_gene_symbol": symbol,
                        "lookup_match_source": "direct_symbol",
                        "lookup_match_input_symbol": symbol,
                    }
                )
        for symbol in candidates + aliases:
            mapped_symbol = mygene_alias_to_symbol.get(symbol)
            if mapped_symbol and mapped_symbol in lookup_gene_set:
                return pd.Series(
                    {
                        "matched_surfaceome_gene_symbol": mapped_symbol,
                        "lookup_match_source": "mygene_alias",
                        "lookup_match_input_symbol": symbol,
                    }
                )
        return pd.Series(
            {
                "matched_surfaceome_gene_symbol": pd.NA,
                "lookup_match_source": "unmatched",
                "lookup_match_input_symbol": pd.NA,
            }
        )

    match_cols = agg.apply(resolve_lookup_match, axis=1)
    agg = pd.concat([agg, match_cols], axis=1)

    final = agg.merge(
        lookup.rename(columns={"gene_symbol": "matched_surfaceome_gene_symbol"}),
        on="matched_surfaceome_gene_symbol",
        how="left",
    )
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
        "gene_symbol_aliases",
        "matched_surfaceome_gene_symbol",
        "lookup_match_source",
        "lookup_match_input_symbol",
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
    mygene_symbol_universe_tsv = args.mygene_symbol_universe_tsv.expanduser().resolve()
    output_tsv = args.output_tsv.expanduser().resolve()
    output_summary = args.output_summary.expanduser().resolve()
    additional_negative_genes = _csv_symbols(args.additional_negative_genes)
    specified_negative_genes = _csv_symbols(args.specified_negative_genes)
    mygene_symbols = _load_gene_symbols(mygene_symbol_universe_tsv)
    mygene_alias_to_symbol, mygene_stats = _build_mygene_alias_index(mygene_symbols)

    panel = build_control_panel(
        controls_json=controls_json,
        surfaceome_csv=surfaceome_csv,
        additional_negative_genes=additional_negative_genes,
        specified_negative_genes=specified_negative_genes,
        mygene_alias_to_symbol=mygene_alias_to_symbol,
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
        "mygene_symbol_universe_tsv": str(mygene_symbol_universe_tsv),
        "mygene_stats": mygene_stats,
        "n_mygene_alias_matches": int((panel["lookup_match_source"] == "mygene_alias").sum()),
    }
    output_summary.write_text(json.dumps(summary, indent=2) + "\n")

    print(json.dumps(summary, indent=2))
    print(f"Wrote {output_tsv}")
    print(f"Wrote {output_summary}")


if __name__ == "__main__":
    main()
