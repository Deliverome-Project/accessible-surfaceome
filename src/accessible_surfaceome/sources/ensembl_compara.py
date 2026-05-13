"""Ensembl Compara mouse + cynomolgus orthology pull (BioMart REST).

Ported from ``Deliverome-Project/deliverome-internal``'s
``scripts/data_collection/download_ensembl_compara_surfaceome_orthologs.py``.

Why BioMart and not the Ensembl REST homology endpoint: the REST homology
payload doesn't expose Ensembl's orthology confidence flag, and we want the
strict ``ortholog_one2one`` + ``confidence=1`` filter for preclinical-model
selection.

One subcommand::

    python -m accessible_surfaceome.sources.ensembl_compara download

Default input: the M1 candidate-universe TSV
(``data/processed/candidate_universe/candidate_universe.tsv``). Default HGNC
TSV: ``data/raw/hgnc_complete_set.tsv``. Both are overridable via CLI flags.

Outputs (under ``data/external/ensembl_compara_surfaceome_expressed/``):

* ``compara_mouse_cyno_one2one_highconf_by_ensembl_query.csv`` — per query
  Ensembl-ID rows with pass flags for mouse + cyno. This is the file
  ``sources.deeptmhmm`` consumes via ``--ortholog-query-csv``.
* ``compara_mouse_cyno_one2one_highconf_by_gene.csv`` — per gene-symbol rows.
* ``compara_mouse_cyno_biomart_raw_rows.csv`` — raw BioMart payload rows.
* ``compara_mouse_cyno_one2one_highconf_summary.csv`` — proportions summary.
* ``download_traceability.json`` — manifest with SHA256s + capture time.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from accessible_surfaceome.paths import REPO_ROOT as ROOT
from accessible_surfaceome.sources._support.traceability import (
    USER_AGENT,
    build_file_record,
    relative_to_repo,
    write_manifest,
)

DATASET = "Ensembl_Compara_surfaceome_mouse_cyno"
BIOMART_URL = "https://www.ensembl.org/biomart/martservice"

MOUSE_TAXON_ID = 10090
CYNO_TAXON_ID = 9544

RETRYABLE_HTTP_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
_ENSG_WITH_OPTIONAL_VERSION = re.compile(r"^(ENSG\d{11})(?:\.\d+)?$", re.IGNORECASE)

BIOMART_ATTRIBUTES = [
    "ensembl_gene_id",
    "external_gene_name",
    "mmusculus_homolog_ensembl_gene",
    "mmusculus_homolog_associated_gene_name",
    "mmusculus_homolog_orthology_type",
    "mmusculus_homolog_orthology_confidence",
    "mmusculus_homolog_perc_id",
    "mfascicularis_homolog_ensembl_gene",
    "mfascicularis_homolog_associated_gene_name",
    "mfascicularis_homolog_orthology_type",
    "mfascicularis_homolog_orthology_confidence",
    "mfascicularis_homolog_perc_id",
]

DEFAULT_INPUT = ROOT / "data" / "processed" / "candidate_universe" / "candidate_universe.tsv"
DEFAULT_HGNC = ROOT / "data" / "raw" / "hgnc_complete_set.tsv"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "external" / "ensembl_compara_surfaceome_expressed"
DEFAULT_GENE_OUTPUT = DEFAULT_OUTPUT_DIR / "compara_mouse_cyno_one2one_highconf_by_gene.csv"
DEFAULT_QUERY_OUTPUT = DEFAULT_OUTPUT_DIR / "compara_mouse_cyno_one2one_highconf_by_ensembl_query.csv"
DEFAULT_RAW_OUTPUT = DEFAULT_OUTPUT_DIR / "compara_mouse_cyno_biomart_raw_rows.csv"
DEFAULT_SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "compara_mouse_cyno_one2one_highconf_summary.csv"
DEFAULT_MANIFEST = DEFAULT_OUTPUT_DIR / "download_traceability.json"


@dataclass(frozen=True)
class InputRecord:
    """One input row (one gene)."""

    gene_symbol: str
    input_uniprot_id: str
    input_ensembl_gene_ids: list[str]


@dataclass(frozen=True)
class ResolvedGene:
    """Resolved gene symbol + the Ensembl IDs we'll query against BioMart."""

    input_gene_symbol: str
    resolved_gene_symbol: str
    mapping_status: str
    resolver_ensembl_gene_ids: list[str]
    query_ensembl_gene_ids: list[str]
    input_records: list[InputRecord]


def normalize_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper()


def normalize_ensembl_gene_id(value: str) -> str | None:
    """Normalize Ensembl gene ID by stripping optional ``.<version>`` suffix."""
    normalized = str(value or "").strip().upper()
    if not normalized:
        return None
    match = _ENSG_WITH_OPTIONAL_VERSION.fullmatch(normalized)
    if not match:
        return None
    return match.group(1)


def normalize_target_gene_id(value: str) -> str:
    """Normalize non-human target Ensembl gene IDs (ENSMUSG..., ENSMFAG...)."""
    return str(value or "").strip().upper()


def parse_ensembl_gene_ids(raw_value: str) -> list[str]:
    """Parse one or more Ensembl IDs from a delimited field."""
    tokens = re.split(r"[;,|\s]+", (raw_value or "").strip())
    parsed: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        cleaned = token.strip().strip("[]'\"")
        if not cleaned:
            continue
        normalized = normalize_ensembl_gene_id(cleaned)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        parsed.append(normalized)
    return parsed


def parse_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_confidence_one(value: str) -> bool:
    """True iff BioMart's orthology confidence column reads as Ensembl-high."""
    return (value or "").strip() in {"1", "1.0", "true", "TRUE", "True"}


def _detect_delimiter(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".tsv", ".tab"}:
        return "\t"
    return ","


_GENE_SYMBOL_COLS = ("gene_symbol", "gene_symbol_resolved", "gene_symbol_input", "symbol")
_UNIPROT_COLS = ("uniprot_accession", "uniprot_acc", "uniprot_id")
_ENSEMBL_COLS = ("ensembl_gene_id", "ensembl_gene", "ensembl_gene_ids")


def _pick_col(fieldnames: list[str], candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in fieldnames:
            return candidate
    return None


def load_input_records(path: Path) -> list[InputRecord]:
    """Load input rows from a candidate-universe TSV/CSV.

    Accepts either the M1 ``candidate_universe.tsv`` (``uniprot_accession``,
    ``gene_symbol``) or any TSV/CSV exposing a gene-symbol column and a
    UniProt-accession column. ``ensembl_gene_id`` is optional — if absent
    the HGNC resolver fills it in.
    """
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    delimiter = _detect_delimiter(path)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        fieldnames = list(reader.fieldnames or [])
        if not fieldnames:
            raise ValueError(f"Input file has no header: {path}")
        gene_col = _pick_col(fieldnames, _GENE_SYMBOL_COLS)
        uniprot_col = _pick_col(fieldnames, _UNIPROT_COLS)
        ensembl_col = _pick_col(fieldnames, _ENSEMBL_COLS)
        if gene_col is None:
            raise ValueError(
                f"Input {path} missing a gene-symbol column (one of {list(_GENE_SYMBOL_COLS)})"
            )
        if uniprot_col is None:
            raise ValueError(
                f"Input {path} missing a UniProt column (one of {list(_UNIPROT_COLS)})"
            )

        records: list[InputRecord] = []
        for row in reader:
            gene_symbol = normalize_symbol(row.get(gene_col) or "")
            if not gene_symbol:
                continue
            uniprot = (row.get(uniprot_col) or "").strip().upper()
            ensembl_raw = (row.get(ensembl_col) or "") if ensembl_col else ""
            records.append(
                InputRecord(
                    gene_symbol=gene_symbol,
                    input_uniprot_id=uniprot,
                    input_ensembl_gene_ids=parse_ensembl_gene_ids(ensembl_raw),
                )
            )
        return records


def load_hgnc_maps(path: Path) -> tuple[dict[str, set[str]], dict[str, str], dict[str, str]]:
    """Build HGNC symbol/alias/previous-symbol → Ensembl-gene-ID maps."""
    if not path.exists():
        raise FileNotFoundError(f"HGNC TSV not found: {path}")

    symbol_to_ensg: dict[str, set[str]] = {}
    alias_to_symbol: dict[str, str] = {}
    prev_to_symbol: dict[str, str] = {}

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {"symbol", "alias_symbol", "prev_symbol", "ensembl_gene_id"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError(
                "HGNC TSV missing required columns: symbol, alias_symbol, prev_symbol, ensembl_gene_id"
            )

        for row in reader:
            symbol = normalize_symbol(row.get("symbol") or "")
            if not symbol:
                continue

            ensg_values = {
                normalized
                for normalized in parse_ensembl_gene_ids(row.get("ensembl_gene_id") or "")
                if normalized
            }
            if ensg_values:
                symbol_to_ensg[symbol] = ensg_values
            else:
                symbol_to_ensg.setdefault(symbol, set())

            for alias in re.split(r"[|]", row.get("alias_symbol") or ""):
                alias_norm = normalize_symbol(alias)
                if alias_norm and alias_norm not in alias_to_symbol:
                    alias_to_symbol[alias_norm] = symbol
            for prev in re.split(r"[|]", row.get("prev_symbol") or ""):
                prev_norm = normalize_symbol(prev)
                if prev_norm and prev_norm not in prev_to_symbol:
                    prev_to_symbol[prev_norm] = symbol

    return symbol_to_ensg, alias_to_symbol, prev_to_symbol


def resolve_gene_symbol(
    input_gene_symbol: str,
    symbol_to_ensg: dict[str, set[str]],
    alias_to_symbol: dict[str, str],
    prev_to_symbol: dict[str, str],
) -> tuple[str, str, list[str]]:
    """Map symbol → (resolved_symbol, mapping_status, ensembl_ids)."""
    gene = normalize_symbol(input_gene_symbol)
    if gene in symbol_to_ensg:
        return gene, "exact", sorted(symbol_to_ensg.get(gene, set()))
    alias_hit = alias_to_symbol.get(gene)
    if alias_hit:
        return alias_hit, "normalized_alias", sorted(symbol_to_ensg.get(alias_hit, set()))
    prev_hit = prev_to_symbol.get(gene)
    if prev_hit:
        return prev_hit, "normalized_previous", sorted(symbol_to_ensg.get(prev_hit, set()))
    return gene, "unresolved", []


def build_resolved_genes(
    records: list[InputRecord],
    symbol_to_ensg: dict[str, set[str]],
    alias_to_symbol: dict[str, str],
    prev_to_symbol: dict[str, str],
) -> dict[str, ResolvedGene]:
    grouped: dict[str, list[InputRecord]] = defaultdict(list)
    for record in records:
        grouped[record.gene_symbol].append(record)

    resolved: dict[str, ResolvedGene] = {}
    for input_gene_symbol, input_group in grouped.items():
        resolved_symbol, mapping_status, resolver_ensg = resolve_gene_symbol(
            input_gene_symbol,
            symbol_to_ensg,
            alias_to_symbol,
            prev_to_symbol,
        )
        seed_ensg = {
            ensg
            for record in input_group
            for ensg in record.input_ensembl_gene_ids
            if ensg
        }
        query_ensg = sorted(seed_ensg.union(set(resolver_ensg)))
        resolved[input_gene_symbol] = ResolvedGene(
            input_gene_symbol=input_gene_symbol,
            resolved_gene_symbol=resolved_symbol,
            mapping_status=mapping_status,
            resolver_ensembl_gene_ids=resolver_ensg,
            query_ensembl_gene_ids=query_ensg,
            input_records=input_group,
        )
    return resolved


def chunked(values: list[str], chunk_size: int) -> list[list[str]]:
    size = max(1, int(chunk_size))
    return [values[i : i + size] for i in range(0, len(values), size)]


def build_biomart_query_xml(ensembl_ids: list[str]) -> str:
    attr_xml = "\n".join([f'    <Attribute name="{attr}" />' for attr in BIOMART_ATTRIBUTES])
    id_value = ",".join(ensembl_ids)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!DOCTYPE Query>\n"
        '<Query virtualSchemaName="default" formatter="TSV" header="0" uniqueRows="0" datasetConfigVersion="0.6">\n'
        '  <Dataset name="hsapiens_gene_ensembl" interface="default">\n'
        f'    <Filter name="ensembl_gene_id" value="{id_value}" />\n'
        f"{attr_xml}\n"
        "  </Dataset>\n"
        "</Query>\n"
    )


def fetch_biomart_chunk(
    *,
    ensembl_ids: list[str],
    timeout: int,
    retry_max_attempts: int,
    min_request_interval_ms: int,
) -> str:
    """Fetch one BioMart chunk's TSV payload, retrying on transient failures."""
    query_xml = build_biomart_query_xml(ensembl_ids)
    query_url = f"{BIOMART_URL}?query={quote(query_xml)}"

    for attempt in range(1, max(1, retry_max_attempts) + 1):
        if attempt > 1:
            min_interval_s = max(0.0, min_request_interval_ms / 1000.0)
            backoff_s = float(2 ** (attempt - 2))
            time.sleep(max(min_interval_s, backoff_s))

        request = Request(
            query_url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/plain"},
        )
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310
                payload = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            if exc.code in RETRYABLE_HTTP_CODES and attempt < retry_max_attempts:
                continue
            body = exc.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(
                f"BioMart HTTP {exc.code} for chunk ({len(ensembl_ids)} IDs): {body}"
            ) from exc
        except URLError as exc:
            if attempt < retry_max_attempts:
                continue
            raise RuntimeError(
                f"BioMart request error for chunk ({len(ensembl_ids)} IDs): {exc!s}"
            ) from exc

        if payload.lstrip().startswith("Query ERROR"):
            if attempt < retry_max_attempts:
                continue
            raise RuntimeError(
                f"BioMart query error for chunk ({len(ensembl_ids)} IDs): {payload.strip()[:300]}"
            )

        return payload

    raise RuntimeError(f"BioMart retries exhausted for chunk ({len(ensembl_ids)} IDs)")


def parse_biomart_tsv(payload: str) -> list[dict[str, str]]:
    """Parse a BioMart TSV chunk using the fixed attribute ordering."""
    rows: list[dict[str, str]] = []
    for line in payload.splitlines():
        if not line.strip():
            continue
        values = line.split("\t")
        if len(values) < len(BIOMART_ATTRIBUTES):
            values = values + [""] * (len(BIOMART_ATTRIBUTES) - len(values))
        if len(values) > len(BIOMART_ATTRIBUTES):
            values = values[: len(BIOMART_ATTRIBUTES)]
        row: dict[str, str] = {
            BIOMART_ATTRIBUTES[idx]: (values[idx] or "").strip()
            for idx in range(len(BIOMART_ATTRIBUTES))
        }
        row["ensembl_gene_id"] = normalize_ensembl_gene_id(row.get("ensembl_gene_id") or "") or ""
        rows.append(row)
    return rows


def choose_best_species_row(rows: list[dict[str, str]], prefix: str) -> dict[str, str] | None:
    """Best one-to-one + high-confidence row for the species, ranked by % identity."""
    passing: list[dict[str, str]] = []
    for row in rows:
        orthology_type = (row.get(f"{prefix}_homolog_orthology_type") or "").strip().lower()
        confidence = row.get(f"{prefix}_homolog_orthology_confidence") or ""
        homolog_ensg = normalize_target_gene_id(row.get(f"{prefix}_homolog_ensembl_gene") or "")
        if orthology_type != "ortholog_one2one":
            continue
        if not parse_confidence_one(confidence):
            continue
        if not homolog_ensg:
            continue
        passing.append(row)

    if not passing:
        return None

    passing.sort(
        key=lambda row: (
            -(parse_float(row.get(f"{prefix}_homolog_perc_id") or "") or -1.0),
            row.get(f"{prefix}_homolog_ensembl_gene") or "",
        )
    )
    return passing[0]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--hgnc-tsv", type=Path, default=DEFAULT_HGNC)
    parser.add_argument("--gene-output-csv", type=Path, default=DEFAULT_GENE_OUTPUT)
    parser.add_argument("--query-output-csv", type=Path, default=DEFAULT_QUERY_OUTPUT)
    parser.add_argument("--raw-output-csv", type=Path, default=DEFAULT_RAW_OUTPUT)
    parser.add_argument("--summary-output-csv", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--chunk-size", type=int, default=250)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--retry-max-attempts", type=int, default=3)
    parser.add_argument("--min-request-interval-ms", type=int, default=200)
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="If >0, only query the first N unique Ensembl IDs (smoke-testing).",
    )
    return parser.parse_args(argv)


def download_main(argv: list[str] | None = None) -> None:
    """Run the BioMart pull and write all outputs + traceability manifest."""
    args = parse_args(argv)

    records = load_input_records(args.input_csv.expanduser().resolve())
    symbol_to_ensg, alias_to_symbol, prev_to_symbol = load_hgnc_maps(
        args.hgnc_tsv.expanduser().resolve()
    )
    resolved_genes = build_resolved_genes(records, symbol_to_ensg, alias_to_symbol, prev_to_symbol)

    unique_query_ensg = sorted(
        {
            ensg
            for resolved in resolved_genes.values()
            for ensg in resolved.query_ensembl_gene_ids
            if ensg
        }
    )

    if args.limit and args.limit > 0:
        unique_query_ensg = unique_query_ensg[: args.limit]

    print(f"Input rows: {len(records)}")
    print(f"Unique genes: {len(resolved_genes)}")
    print(f"Unique Ensembl query IDs: {len(unique_query_ensg)}")

    biomart_rows: list[dict[str, str]] = []
    id_chunks = chunked(unique_query_ensg, args.chunk_size)
    for idx, id_chunk in enumerate(id_chunks, start=1):
        payload = fetch_biomart_chunk(
            ensembl_ids=id_chunk,
            timeout=max(1, args.timeout),
            retry_max_attempts=max(1, args.retry_max_attempts),
            min_request_interval_ms=max(0, args.min_request_interval_ms),
        )
        parsed = parse_biomart_tsv(payload)
        biomart_rows.extend(parsed)
        print(
            f"Completed {idx}/{len(id_chunks)} BioMart chunks "
            f"({len(id_chunk)} IDs, {len(parsed)} rows)",
            flush=True,
        )

    rows_by_human_ensg: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in biomart_rows:
        ensg = row.get("ensembl_gene_id") or ""
        if ensg:
            rows_by_human_ensg[ensg].append(row)

    query_to_input_genes: dict[str, set[str]] = defaultdict(set)
    for resolved in resolved_genes.values():
        for ensg in resolved.query_ensembl_gene_ids:
            query_to_input_genes[ensg].add(resolved.input_gene_symbol)

    query_rows: list[dict[str, Any]] = []
    query_pass_map: dict[str, dict[str, Any]] = {}

    for ensg in unique_query_ensg:
        qrows = rows_by_human_ensg.get(ensg, [])
        mouse_best = choose_best_species_row(qrows, "mmusculus")
        cyno_best = choose_best_species_row(qrows, "mfascicularis")

        mouse_pass = mouse_best is not None
        cyno_pass = cyno_best is not None

        query_pass_map[ensg] = {"mouse_pass": mouse_pass, "cyno_pass": cyno_pass}

        query_rows.append(
            {
                "query_ensembl_gene_id": ensg,
                "query_input_gene_symbols": "|".join(sorted(query_to_input_genes.get(ensg, set()))),
                "n_input_genes_for_query_id": len(query_to_input_genes.get(ensg, set())),
                "n_biomart_rows_for_query_id": len(qrows),
                "mouse_has_one2one_high_confidence": "1" if mouse_pass else "0",
                "mouse_target_ensembl_gene_id": (
                    normalize_target_gene_id(mouse_best.get("mmusculus_homolog_ensembl_gene") or "")
                    if mouse_best
                    else ""
                ),
                "mouse_target_gene_symbol": (
                    (mouse_best.get("mmusculus_homolog_associated_gene_name") or "")
                    if mouse_best
                    else ""
                ),
                "mouse_target_percent_identity": (
                    (mouse_best.get("mmusculus_homolog_perc_id") or "") if mouse_best else ""
                ),
                "mouse_orthology_type": (
                    (mouse_best.get("mmusculus_homolog_orthology_type") or "") if mouse_best else ""
                ),
                "mouse_orthology_confidence": (
                    (mouse_best.get("mmusculus_homolog_orthology_confidence") or "")
                    if mouse_best
                    else ""
                ),
                "cyno_has_one2one_high_confidence": "1" if cyno_pass else "0",
                "cyno_target_ensembl_gene_id": (
                    normalize_target_gene_id(cyno_best.get("mfascicularis_homolog_ensembl_gene") or "")
                    if cyno_best
                    else ""
                ),
                "cyno_target_gene_symbol": (
                    (cyno_best.get("mfascicularis_homolog_associated_gene_name") or "")
                    if cyno_best
                    else ""
                ),
                "cyno_target_percent_identity": (
                    (cyno_best.get("mfascicularis_homolog_perc_id") or "") if cyno_best else ""
                ),
                "cyno_orthology_type": (
                    (cyno_best.get("mfascicularis_homolog_orthology_type") or "")
                    if cyno_best
                    else ""
                ),
                "cyno_orthology_confidence": (
                    (cyno_best.get("mfascicularis_homolog_orthology_confidence") or "")
                    if cyno_best
                    else ""
                ),
                "has_one_or_both_species_pass": "1" if (mouse_pass or cyno_pass) else "0",
                "has_both_species_pass": "1" if (mouse_pass and cyno_pass) else "0",
            }
        )

    gene_rows: list[dict[str, Any]] = []
    mapping_status_counts: Counter[str] = Counter()

    for input_gene_symbol in sorted(resolved_genes.keys()):
        resolved = resolved_genes[input_gene_symbol]
        mapping_status_counts[resolved.mapping_status] += 1

        query_ids = resolved.query_ensembl_gene_ids
        mouse_supporting_ids = [
            ensg for ensg in query_ids if query_pass_map.get(ensg, {}).get("mouse_pass")
        ]
        cyno_supporting_ids = [
            ensg for ensg in query_ids if query_pass_map.get(ensg, {}).get("cyno_pass")
        ]

        mouse_has = bool(mouse_supporting_ids)
        cyno_has = bool(cyno_supporting_ids)

        input_uniprot_ids = sorted(
            {
                record.input_uniprot_id
                for record in resolved.input_records
                if record.input_uniprot_id
            }
        )

        gene_rows.append(
            {
                "input_gene_symbol": resolved.input_gene_symbol,
                "resolver_resolved_gene_symbol": resolved.resolved_gene_symbol,
                "resolver_mapping_status": resolved.mapping_status,
                "resolver_ensembl_gene_ids": "|".join(resolved.resolver_ensembl_gene_ids),
                "query_ensembl_gene_ids": "|".join(query_ids),
                "n_query_ensembl_gene_ids": len(query_ids),
                "n_input_rows_for_gene": len(resolved.input_records),
                "input_uniprot_ids": "|".join(input_uniprot_ids),
                "mouse_has_one2one_high_confidence": "1" if mouse_has else "0",
                "mouse_supporting_query_ensembl_ids": "|".join(mouse_supporting_ids),
                "n_mouse_supporting_query_ensembl_ids": len(mouse_supporting_ids),
                "cyno_has_one2one_high_confidence": "1" if cyno_has else "0",
                "cyno_supporting_query_ensembl_ids": "|".join(cyno_supporting_ids),
                "n_cyno_supporting_query_ensembl_ids": len(cyno_supporting_ids),
                "has_one_or_both_species_pass": "1" if (mouse_has or cyno_has) else "0",
                "has_both_species_pass": "1" if (mouse_has and cyno_has) else "0",
            }
        )

    biomart_raw_rows: list[dict[str, Any]] = []
    for row in biomart_rows:
        mouse_pass_row = (
            (row.get("mmusculus_homolog_orthology_type") or "").strip().lower() == "ortholog_one2one"
            and parse_confidence_one(row.get("mmusculus_homolog_orthology_confidence") or "")
            and bool(normalize_target_gene_id(row.get("mmusculus_homolog_ensembl_gene") or ""))
        )
        cyno_pass_row = (
            (row.get("mfascicularis_homolog_orthology_type") or "").strip().lower() == "ortholog_one2one"
            and parse_confidence_one(row.get("mfascicularis_homolog_orthology_confidence") or "")
            and bool(normalize_target_gene_id(row.get("mfascicularis_homolog_ensembl_gene") or ""))
        )
        biomart_raw_rows.append(
            {
                "human_ensembl_gene_id": row.get("ensembl_gene_id") or "",
                "human_gene_symbol": row.get("external_gene_name") or "",
                "mouse_homolog_ensembl_gene_id": normalize_target_gene_id(
                    row.get("mmusculus_homolog_ensembl_gene") or ""
                ),
                "mouse_homolog_gene_symbol": row.get("mmusculus_homolog_associated_gene_name") or "",
                "mouse_homology_type": row.get("mmusculus_homolog_orthology_type") or "",
                "mouse_homology_confidence": row.get("mmusculus_homolog_orthology_confidence") or "",
                "mouse_target_percent_identity": row.get("mmusculus_homolog_perc_id") or "",
                "mouse_pass_one2one_high_confidence": "1" if mouse_pass_row else "0",
                "cyno_homolog_ensembl_gene_id": normalize_target_gene_id(
                    row.get("mfascicularis_homolog_ensembl_gene") or ""
                ),
                "cyno_homolog_gene_symbol": row.get("mfascicularis_homolog_associated_gene_name") or "",
                "cyno_homology_type": row.get("mfascicularis_homolog_orthology_type") or "",
                "cyno_homology_confidence": row.get("mfascicularis_homolog_orthology_confidence") or "",
                "cyno_target_percent_identity": row.get("mfascicularis_homolog_perc_id") or "",
                "cyno_pass_one2one_high_confidence": "1" if cyno_pass_row else "0",
            }
        )

    gene_rows.sort(key=lambda row: (row["input_gene_symbol"], row["resolver_resolved_gene_symbol"]))
    query_rows.sort(key=lambda row: row["query_ensembl_gene_id"])
    biomart_raw_rows.sort(
        key=lambda row: (
            row["human_ensembl_gene_id"],
            row["mouse_homolog_ensembl_gene_id"],
            row["cyno_homolog_ensembl_gene_id"],
        )
    )

    total_genes = len(gene_rows)
    genes_mouse = sum(row["mouse_has_one2one_high_confidence"] == "1" for row in gene_rows)
    genes_cyno = sum(row["cyno_has_one2one_high_confidence"] == "1" for row in gene_rows)
    genes_one_or_both = sum(row["has_one_or_both_species_pass"] == "1" for row in gene_rows)
    genes_both = sum(row["has_both_species_pass"] == "1" for row in gene_rows)
    genes_with_no_query_ids = sum(int(row["n_query_ensembl_gene_ids"]) == 0 for row in gene_rows)

    summary_row = {
        "total_input_rows": len(records),
        "total_unique_genes": total_genes,
        "total_unique_query_ensembl_gene_ids": len(unique_query_ensg),
        "genes_with_no_query_ensembl_ids": genes_with_no_query_ids,
        "genes_with_mouse_one2one_high_confidence": genes_mouse,
        "genes_with_cyno_one2one_high_confidence": genes_cyno,
        "genes_with_one_or_both_species_pass": genes_one_or_both,
        "genes_with_both_species_pass": genes_both,
        "proportion_mouse": round(genes_mouse / total_genes, 6) if total_genes else 0.0,
        "proportion_cyno": round(genes_cyno / total_genes, 6) if total_genes else 0.0,
        "proportion_one_or_both": round(genes_one_or_both / total_genes, 6) if total_genes else 0.0,
        "proportion_both": round(genes_both / total_genes, 6) if total_genes else 0.0,
    }

    gene_output = args.gene_output_csv.expanduser().resolve()
    query_output = args.query_output_csv.expanduser().resolve()
    raw_output = args.raw_output_csv.expanduser().resolve()
    summary_output = args.summary_output_csv.expanduser().resolve()
    manifest_path = args.manifest.expanduser().resolve()

    write_csv(
        gene_output,
        [
            "input_gene_symbol",
            "resolver_resolved_gene_symbol",
            "resolver_mapping_status",
            "resolver_ensembl_gene_ids",
            "query_ensembl_gene_ids",
            "n_query_ensembl_gene_ids",
            "n_input_rows_for_gene",
            "input_uniprot_ids",
            "mouse_has_one2one_high_confidence",
            "mouse_supporting_query_ensembl_ids",
            "n_mouse_supporting_query_ensembl_ids",
            "cyno_has_one2one_high_confidence",
            "cyno_supporting_query_ensembl_ids",
            "n_cyno_supporting_query_ensembl_ids",
            "has_one_or_both_species_pass",
            "has_both_species_pass",
        ],
        gene_rows,
    )
    write_csv(
        query_output,
        [
            "query_ensembl_gene_id",
            "query_input_gene_symbols",
            "n_input_genes_for_query_id",
            "n_biomart_rows_for_query_id",
            "mouse_has_one2one_high_confidence",
            "mouse_target_ensembl_gene_id",
            "mouse_target_gene_symbol",
            "mouse_target_percent_identity",
            "mouse_orthology_type",
            "mouse_orthology_confidence",
            "cyno_has_one2one_high_confidence",
            "cyno_target_ensembl_gene_id",
            "cyno_target_gene_symbol",
            "cyno_target_percent_identity",
            "cyno_orthology_type",
            "cyno_orthology_confidence",
            "has_one_or_both_species_pass",
            "has_both_species_pass",
        ],
        query_rows,
    )
    write_csv(
        raw_output,
        [
            "human_ensembl_gene_id",
            "human_gene_symbol",
            "mouse_homolog_ensembl_gene_id",
            "mouse_homolog_gene_symbol",
            "mouse_homology_type",
            "mouse_homology_confidence",
            "mouse_target_percent_identity",
            "mouse_pass_one2one_high_confidence",
            "cyno_homolog_ensembl_gene_id",
            "cyno_homolog_gene_symbol",
            "cyno_homology_type",
            "cyno_homology_confidence",
            "cyno_target_percent_identity",
            "cyno_pass_one2one_high_confidence",
        ],
        biomart_raw_rows,
    )
    write_csv(summary_output, list(summary_row.keys()), [summary_row])

    manifest_records = [
        build_file_record(
            repo_root=ROOT,
            file_path=gene_output,
            source_url=BIOMART_URL,
            dataset=DATASET,
            status="downloaded",
            note="Gene-level mouse/cyno ortholog pass flags (ortholog_one2one + confidence=1).",
        ),
        build_file_record(
            repo_root=ROOT,
            file_path=query_output,
            source_url=BIOMART_URL,
            dataset=DATASET,
            status="downloaded",
            note="Per-Ensembl-query-ID ortholog pass flags for mouse/cyno.",
        ),
        build_file_record(
            repo_root=ROOT,
            file_path=raw_output,
            source_url=BIOMART_URL,
            dataset=DATASET,
            status="downloaded",
            note="Raw BioMart homology rows for queried human Ensembl IDs.",
        ),
        build_file_record(
            repo_root=ROOT,
            file_path=summary_output,
            source_url=BIOMART_URL,
            dataset=DATASET,
            status="downloaded",
            note="Summary proportions for mouse/cyno ortholog pass criteria.",
        ),
    ]
    write_manifest(
        manifest_path,
        dataset=DATASET,
        script=Path(__file__).as_posix(),
        records=manifest_records,
        extras={
            "input_csv": relative_to_repo(args.input_csv.expanduser().resolve(), ROOT),
            "hgnc_tsv": relative_to_repo(args.hgnc_tsv.expanduser().resolve(), ROOT),
            "input_rows": len(records),
            "unique_input_genes": len(resolved_genes),
            "resolver_mapping_status_counts": dict(mapping_status_counts),
            "unique_query_ensembl_gene_ids": len(unique_query_ensg),
            "biomart_rows_returned": len(biomart_rows),
            "biomart_chunk_count": len(id_chunks),
            "biomart_chunk_size": max(1, args.chunk_size),
            "mouse_taxon_id": MOUSE_TAXON_ID,
            "cyno_taxon_id": CYNO_TAXON_ID,
            **summary_row,
        },
    )

    print(str(gene_output))
    print(str(query_output))
    print(str(raw_output))
    print(str(summary_output))
    print(str(manifest_path))
    if total_genes:
        print(
            f"Mouse one2one+high-confidence: {genes_mouse}/{total_genes} "
            f"({genes_mouse / total_genes * 100.0:.2f}%)"
        )
        print(
            f"Cyno one2one+high-confidence: {genes_cyno}/{total_genes} "
            f"({genes_cyno / total_genes * 100.0:.2f}%)"
        )


def main(argv: list[str] | None = None) -> None:
    """CLI dispatch: only ``download`` is supported today."""
    parser = argparse.ArgumentParser(prog="ensembl_compara", description=__doc__)
    parser.add_argument("subcommand", choices=["download"])
    args, rest = parser.parse_known_args(argv)
    if args.subcommand == "download":
        download_main(rest)


if __name__ == "__main__":
    main(sys.argv[1:])
