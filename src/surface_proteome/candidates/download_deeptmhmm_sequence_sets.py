"""Build DeepTMHMM FASTA cohorts for human surfaceome genes and orthologs.

Cohorts generated:
1. Human canonical proteins (non-HLA) from surfaceome_expressed.csv UniProt IDs.
2. Human isoforms (non-HLA) from AFDB-resolved UniProt isoform accessions.
3. Mouse ortholog proteins from one2one + high-confidence Ensembl ortholog rows.
4. Cynomolgus ortholog proteins from one2one + high-confidence Ensembl ortholog rows.

Ortholog cohort membership is defined by Ensembl Compara outputs already generated in
this repository. Protein sequence retrieval is done from UniProt REST APIs.
"""

from __future__ import annotations

import argparse
import csv
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from surface_proteome.candidates.traceability import (
    USER_AGENT,
    build_file_record,
    relative_to_repo,
    write_manifest,
)

from surface_proteome.paths import REPO_ROOT as ROOT


DATASET = "DeepTMHMM_surfaceome_sequence_sets"
UNIPROT_FASTA_TEMPLATE = "https://rest.uniprot.org/uniprotkb/{accession}.fasta"
UNIPROT_SEARCH_URL = "https://rest.uniprot.org/uniprotkb/search"
RETRYABLE_HTTP_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
_FASTA_SEQ_LINE_RE = re.compile(r"^[A-Z*.-]+$")

DEFAULT_SURFACEOME_CSV = (
    ROOT / "data" / "analysis" / "deliverome" / "expression_filtering" / "surfaceome_expressed.csv"
)
DEFAULT_AFDB_BY_GENE_CSV = (
    ROOT / "data" / "external" / "afdb_surfaceome_expressed" / "afdb_surfaceome_tpm_expressed_by_gene.csv"
)
DEFAULT_ORTHOLOG_QUERY_CSV = (
    ROOT
    / "data"
    / "external"
    / "ensembl_compara_surfaceome_expressed"
    / "compara_mouse_cyno_one2one_highconf_by_ensembl_query.csv"
)
DEFAULT_OUTPUT_DIR = ROOT / "data" / "external" / "deeptmhmm_surfaceome_inputs"
DEFAULT_MANIFEST = DEFAULT_OUTPUT_DIR / "download_traceability.json"

SPECIES_CONFIG = {
    "mouse": {
        "taxid": "10090",
        "gene_col": "mouse_target_gene_symbol",
        "ensembl_col": "mouse_target_ensembl_gene_id",
        "pass_col": "mouse_has_one2one_high_confidence",
    },
    "cyno": {
        "taxid": "9541",
        "gene_col": "cyno_target_gene_symbol",
        "ensembl_col": "cyno_target_ensembl_gene_id",
        "pass_col": "cyno_has_one2one_high_confidence",
    },
}


@dataclass(frozen=True)
class FastaRecord:
    """One parsed FASTA sequence."""

    header: str
    sequence: str
    source_url: str
    response_headers: dict[str, str]


@dataclass(frozen=True)
class OrthologTarget:
    """One target ortholog gene resolved from Ensembl Compara output."""

    target_gene_symbol: str
    target_ensembl_gene_id: str
    query_ensembl_gene_id: str
    query_input_gene_symbols: str


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--surfaceome-csv", type=Path, default=DEFAULT_SURFACEOME_CSV)
    parser.add_argument("--afdb-by-gene-csv", type=Path, default=DEFAULT_AFDB_BY_GENE_CSV)
    parser.add_argument("--ortholog-query-csv", type=Path, default=DEFAULT_ORTHOLOG_QUERY_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--max-workers", type=int, default=16)
    parser.add_argument("--retry-max-attempts", type=int, default=4)
    parser.add_argument("--min-request-interval-ms", type=int, default=200)
    return parser.parse_args()


def normalize_symbol(symbol: str) -> str:
    """Normalize symbol key."""
    return (symbol or "").strip().upper()


def is_hla_gene(symbol: str) -> bool:
    """Return True for HLA-prefixed genes."""
    return normalize_symbol(symbol).startswith("HLA-")


def parse_bool_token(value: str) -> bool:
    """Parse common boolean-like tokens."""
    token = (value or "").strip().lower()
    return token in {"1", "true", "t", "yes", "y", "reviewed"}


def split_pipe(raw_value: str) -> list[str]:
    """Split a pipe-delimited field into non-empty tokens."""
    values: list[str] = []
    seen: set[str] = set()
    for token in (raw_value or "").split("|"):
        cleaned = token.strip()
        if not cleaned:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        values.append(cleaned)
    return values


def canonicalize_uniprot_id(uniprot_id: str) -> str:
    """Canonicalize UniProt ID by stripping optional isoform suffix."""
    normalized = (uniprot_id or "").strip().upper()
    if not normalized:
        return ""
    return normalized.split("-", 1)[0].strip()


def fetch_text_with_retries(
    url: str,
    *,
    timeout: int,
    retry_max_attempts: int,
    min_request_interval_ms: int,
) -> tuple[str, dict[str, str]]:
    """Fetch URL text with retries for transient failures."""
    last_error: Exception | None = None
    for attempt in range(1, max(1, retry_max_attempts) + 1):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=timeout) as response:  # noqa: S310
                text = response.read().decode("utf-8", errors="replace")
                headers = {
                    "content_type": response.headers.get("Content-Type", ""),
                    "content_length_header": response.headers.get("Content-Length", ""),
                    "etag": response.headers.get("ETag", ""),
                    "last_modified": response.headers.get("Last-Modified", ""),
                }
                return text, headers
        except HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            if exc.code not in RETRYABLE_HTTP_CODES or attempt == retry_max_attempts:
                raise RuntimeError(f"HTTP {exc.code} for {url}; body={body[:300]}") from exc
            last_error = exc
        except (TimeoutError, URLError) as exc:
            if attempt == retry_max_attempts:
                raise RuntimeError(f"Network error for {url}: {exc}") from exc
            last_error = exc
        if min_request_interval_ms > 0:
            time.sleep(min_request_interval_ms / 1000.0)
    if last_error:
        raise RuntimeError(f"Failed to fetch {url}: {last_error}") from last_error
    raise RuntimeError(f"Failed to fetch {url}")


def parse_fasta(text: str, source_url: str, response_headers: dict[str, str]) -> FastaRecord:
    """Parse one-entry FASTA text payload."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or not lines[0].startswith(">"):
        raise ValueError(f"Invalid FASTA header from {source_url}")
    sequence = "".join(lines[1:]).upper()
    if not sequence or not _FASTA_SEQ_LINE_RE.fullmatch(sequence):
        raise ValueError(f"Invalid FASTA sequence from {source_url}")
    return FastaRecord(
        header=lines[0],
        sequence=sequence,
        source_url=source_url,
        response_headers=response_headers,
    )


def fetch_uniprot_fasta(
    accession: str,
    *,
    timeout: int,
    retry_max_attempts: int,
    min_request_interval_ms: int,
) -> FastaRecord:
    """Fetch and parse UniProt FASTA for one accession."""
    source_url = UNIPROT_FASTA_TEMPLATE.format(accession=accession)
    text, response_headers = fetch_text_with_retries(
        source_url,
        timeout=timeout,
        retry_max_attempts=retry_max_attempts,
        min_request_interval_ms=min_request_interval_ms,
    )
    return parse_fasta(text, source_url=source_url, response_headers=response_headers)


def read_dict_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    """Read CSV rows and headers."""
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {path}")
        fieldnames = list(reader.fieldnames)
        rows = [row for row in reader]
        return rows, fieldnames


def load_human_canonical_targets(surfaceome_csv: Path) -> dict[str, set[str]]:
    """Load non-HLA canonical human UniProt targets from surfaceome input."""
    targets: dict[str, set[str]] = defaultdict(set)
    rows, fieldnames = read_dict_rows(surfaceome_csv)
    required = {"gene_symbol", "uniprot_id"}
    missing_cols = required.difference(set(fieldnames))
    if missing_cols:
        raise ValueError(f"{surfaceome_csv} missing columns: {sorted(missing_cols)}")

    for row in rows:
        gene_symbol = normalize_symbol(row.get("gene_symbol") or "")
        if not gene_symbol or is_hla_gene(gene_symbol):
            continue
        canonical_accession = canonicalize_uniprot_id(row.get("uniprot_id") or "")
        if not canonical_accession:
            continue
        targets[canonical_accession].add(gene_symbol)
    return targets


def load_non_hla_gene_set(surfaceome_csv: Path) -> set[str]:
    """Load non-HLA human gene symbols from surfaceome input."""
    rows, _fieldnames = read_dict_rows(surfaceome_csv)
    genes = {
        normalize_symbol(row.get("gene_symbol") or "")
        for row in rows
        if normalize_symbol(row.get("gene_symbol") or "") and not is_hla_gene(row.get("gene_symbol") or "")
    }
    return genes


def load_human_isoform_targets(afdb_by_gene_csv: Path) -> dict[str, set[str]]:
    """Load non-HLA human isoform accessions from AFDB output."""
    targets: dict[str, set[str]] = defaultdict(set)
    rows, fieldnames = read_dict_rows(afdb_by_gene_csv)
    required = {"gene_symbol", "afdb_uniprot_accession", "afdb_query_status", "afdb_tax_id", "is_hla_gene"}
    missing_cols = required.difference(set(fieldnames))
    if missing_cols:
        raise ValueError(f"{afdb_by_gene_csv} missing columns: {sorted(missing_cols)}")

    for row in rows:
        gene_symbol = normalize_symbol(row.get("gene_symbol") or "")
        if not gene_symbol:
            continue
        if parse_bool_token(row.get("is_hla_gene") or "") or is_hla_gene(gene_symbol):
            continue
        if (row.get("afdb_query_status") or "").strip().lower() != "ok":
            continue
        tax_id = (row.get("afdb_tax_id") or "").strip()
        if not tax_id.startswith("9606"):
            continue
        accession = (row.get("afdb_uniprot_accession") or "").strip().upper()
        if not accession or "-" not in accession:
            continue
        targets[accession].add(gene_symbol)
    return targets


def load_ortholog_targets(
    ortholog_query_csv: Path,
    non_hla_human_genes: set[str],
    species_key: str,
) -> list[OrthologTarget]:
    """Load ortholog targets for one species using pass criteria from Compara output."""
    rows, fieldnames = read_dict_rows(ortholog_query_csv)
    cfg = SPECIES_CONFIG[species_key]
    required = {"query_ensembl_gene_id", "query_input_gene_symbols", cfg["pass_col"], cfg["gene_col"], cfg["ensembl_col"]}
    missing_cols = required.difference(set(fieldnames))
    if missing_cols:
        raise ValueError(f"{ortholog_query_csv} missing columns: {sorted(missing_cols)}")

    targets: list[OrthologTarget] = []
    for row in rows:
        if not parse_bool_token(row.get(cfg["pass_col"]) or ""):
            continue

        input_symbols = [normalize_symbol(token) for token in split_pipe(row.get("query_input_gene_symbols") or "")]
        if not input_symbols:
            continue
        if not any(symbol in non_hla_human_genes for symbol in input_symbols):
            continue

        target_symbol = (row.get(cfg["gene_col"]) or "").strip()
        target_ensembl = (row.get(cfg["ensembl_col"]) or "").strip()
        if not target_symbol or not target_ensembl:
            continue

        targets.append(
            OrthologTarget(
                target_gene_symbol=target_symbol,
                target_ensembl_gene_id=target_ensembl,
                query_ensembl_gene_id=(row.get("query_ensembl_gene_id") or "").strip(),
                query_input_gene_symbols=(row.get("query_input_gene_symbols") or "").strip(),
            )
        )

    # Keep one target per Ensembl gene ID to avoid duplicate FASTA downloads.
    deduped_by_ensembl: dict[str, OrthologTarget] = {}
    for target in targets:
        deduped_by_ensembl.setdefault(target.target_ensembl_gene_id, target)
    return sorted(deduped_by_ensembl.values(), key=lambda item: item.target_ensembl_gene_id)


def parse_tsv_rows(tsv_text: str) -> list[dict[str, str]]:
    """Parse TSV payload into dictionaries."""
    lines = [line for line in tsv_text.splitlines() if line.strip()]
    if not lines:
        return []
    reader = csv.DictReader(lines, delimiter="\t")
    return [row for row in reader]


def normalize_gene_name_tokens(gene_names_raw: str) -> set[str]:
    """Normalize UniProt gene name tokens from space-delimited list."""
    tokens = {normalize_symbol(token) for token in (gene_names_raw or "").split() if normalize_symbol(token)}
    return tokens


def choose_best_candidate(
    *,
    candidates: list[dict[str, str]],
    target_symbol: str,
) -> dict[str, str] | None:
    """Select best UniProt candidate for one target symbol."""
    target_norm = normalize_symbol(target_symbol)

    def rank(row: dict[str, str]) -> tuple[int, int, int, int, str]:
        primary = normalize_symbol(row.get("Gene Names (primary)") or "")
        name_tokens = normalize_gene_name_tokens(row.get("Gene Names") or "")
        reviewed = parse_bool_token(row.get("Reviewed") or "")
        length_raw = (row.get("Length") or "").strip()
        try:
            length = int(length_raw)
        except ValueError:
            length = 0
        return (
            1 if primary == target_norm else 0,
            1 if target_norm in name_tokens else 0,
            1 if reviewed else 0,
            length,
            (row.get("Entry") or "").strip(),
        )

    if not candidates:
        return None
    return sorted(candidates, key=rank, reverse=True)[0]


def search_uniprot_gene_candidates(
    *,
    gene_symbol: str,
    taxid: str,
    timeout: int,
    retry_max_attempts: int,
    min_request_interval_ms: int,
) -> tuple[list[dict[str, str]], str]:
    """Search UniProt candidates for a gene symbol within one species."""
    escaped_symbol = gene_symbol.replace('"', '\\"')
    query = f'gene_exact:"{escaped_symbol}" AND organism_id:{taxid}'
    fields = "accession,id,gene_primary,gene_names,reviewed,length,organism_name"
    url = (
        f"{UNIPROT_SEARCH_URL}?format=tsv&size=500&fields={quote(fields, safe='')}"
        f"&query={quote(query, safe='')}"
    )
    tsv_text, _headers = fetch_text_with_retries(
        url,
        timeout=timeout,
        retry_max_attempts=retry_max_attempts,
        min_request_interval_ms=min_request_interval_ms,
    )
    return parse_tsv_rows(tsv_text), url


def write_fasta(path: Path, records: list[FastaRecord]) -> None:
    """Write FASTA file from parsed records."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(record.header + "\n")
            seq = record.sequence
            for i in range(0, len(seq), 80):
                handle.write(seq[i : i + 80] + "\n")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    """Write CSV with deterministic header."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def build_human_fasta_set(
    *,
    accession_to_genes: dict[str, set[str]],
    cohort_label: str,
    max_workers: int,
    timeout: int,
    retry_max_attempts: int,
    min_request_interval_ms: int,
) -> tuple[list[FastaRecord], list[dict[str, Any]]]:
    """Build one human cohort by direct UniProt accession fetch."""
    fasta_records: list[FastaRecord] = []
    metadata_rows: list[dict[str, Any]] = []

    accession_list = sorted(accession_to_genes)

    def worker(accession: str) -> tuple[FastaRecord | None, dict[str, Any]]:
        genes = sorted(accession_to_genes[accession])
        row_base: dict[str, Any] = {
            "cohort": cohort_label,
            "gene_symbols": "|".join(genes),
            "uniprot_accession": accession,
        }
        try:
            fasta = fetch_uniprot_fasta(
                accession,
                timeout=timeout,
                retry_max_attempts=retry_max_attempts,
                min_request_interval_ms=min_request_interval_ms,
            )
            return (
                fasta,
                {
                    **row_base,
                    "status": "ok",
                    "sequence_length": len(fasta.sequence),
                    "source_url": fasta.source_url,
                    "error": "",
                },
            )
        except Exception as exc:  # noqa: BLE001
            return (
                None,
                {
                    **row_base,
                    "status": "error",
                    "sequence_length": "",
                    "source_url": UNIPROT_FASTA_TEMPLATE.format(accession=accession),
                    "error": str(exc),
                },
            )

    with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as pool:
        futures = {pool.submit(worker, accession): accession for accession in accession_list}
        total = len(futures)
        completed = 0
        for future in as_completed(futures):
            completed += 1
            fasta, row = future.result()
            metadata_rows.append(row)
            if fasta is not None:
                fasta_records.append(fasta)
            if completed % 250 == 0 or completed == total:
                print(f"[{cohort_label}] completed {completed}/{total}", flush=True)

    metadata_rows.sort(key=lambda row: str(row.get("uniprot_accession") or ""))
    fasta_records.sort(key=lambda record: record.header)
    return fasta_records, metadata_rows


def build_ortholog_fasta_set(
    *,
    species_key: str,
    targets: list[OrthologTarget],
    max_workers: int,
    timeout: int,
    retry_max_attempts: int,
    min_request_interval_ms: int,
) -> tuple[list[FastaRecord], list[dict[str, Any]]]:
    """Build one ortholog cohort by gene-symbol search then FASTA fetch."""
    species_cfg = SPECIES_CONFIG[species_key]
    taxid = species_cfg["taxid"]

    fasta_records: list[FastaRecord] = []
    metadata_rows: list[dict[str, Any]] = []
    seen_accessions: set[str] = set()

    def worker(target: OrthologTarget) -> tuple[FastaRecord | None, dict[str, Any]]:
        row_base: dict[str, Any] = {
            "cohort": f"{species_key}_ortholog_one2one_highconf_non_hla",
            "species": species_key,
            "taxid": taxid,
            "target_gene_symbol": target.target_gene_symbol,
            "target_ensembl_gene_id": target.target_ensembl_gene_id,
            "query_ensembl_gene_id": target.query_ensembl_gene_id,
            "query_input_gene_symbols": target.query_input_gene_symbols,
        }

        try:
            candidates, query_url = search_uniprot_gene_candidates(
                gene_symbol=target.target_gene_symbol,
                taxid=taxid,
                timeout=timeout,
                retry_max_attempts=retry_max_attempts,
                min_request_interval_ms=min_request_interval_ms,
            )
            chosen = choose_best_candidate(candidates=candidates, target_symbol=target.target_gene_symbol)
            if not chosen:
                return (
                    None,
                    {
                        **row_base,
                        "status": "no_uniprot_candidate",
                        "n_candidates": len(candidates),
                        "selected_uniprot_accession": "",
                        "selected_uniprot_entry_name": "",
                        "selected_reviewed": "",
                        "selected_length": "",
                        "search_url": query_url,
                        "source_url": "",
                        "sequence_length": "",
                        "error": "",
                    },
                )

            accession = (chosen.get("Entry") or "").strip()
            if not accession:
                raise ValueError("Selected UniProt candidate missing accession")

            fasta = fetch_uniprot_fasta(
                accession,
                timeout=timeout,
                retry_max_attempts=retry_max_attempts,
                min_request_interval_ms=min_request_interval_ms,
            )

            return (
                fasta,
                {
                    **row_base,
                    "status": "ok",
                    "n_candidates": len(candidates),
                    "selected_uniprot_accession": accession,
                    "selected_uniprot_entry_name": (chosen.get("Entry Name") or "").strip(),
                    "selected_reviewed": (chosen.get("Reviewed") or "").strip(),
                    "selected_length": (chosen.get("Length") or "").strip(),
                    "search_url": query_url,
                    "source_url": fasta.source_url,
                    "sequence_length": len(fasta.sequence),
                    "error": "",
                },
            )
        except Exception as exc:  # noqa: BLE001
            return (
                None,
                {
                    **row_base,
                    "status": "error",
                    "n_candidates": "",
                    "selected_uniprot_accession": "",
                    "selected_uniprot_entry_name": "",
                    "selected_reviewed": "",
                    "selected_length": "",
                    "search_url": "",
                    "source_url": "",
                    "sequence_length": "",
                    "error": str(exc),
                },
            )

    with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as pool:
        futures = {pool.submit(worker, target): target for target in targets}
        total = len(futures)
        completed = 0
        for future in as_completed(futures):
            completed += 1
            fasta, row = future.result()
            metadata_rows.append(row)
            accession = str(row.get("selected_uniprot_accession") or "").strip()
            if fasta is not None and accession and accession not in seen_accessions:
                seen_accessions.add(accession)
                fasta_records.append(fasta)
            if completed % 250 == 0 or completed == total:
                print(f"[{species_key}] completed {completed}/{total}", flush=True)

    metadata_rows.sort(key=lambda row: str(row.get("target_ensembl_gene_id") or ""))
    fasta_records.sort(key=lambda record: record.header)
    return fasta_records, metadata_rows


def summarize_status(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Count status values in metadata rows."""
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row.get("status") or "unknown")] += 1
    return dict(sorted(counts.items()))


def main() -> None:
    """Build cohort FASTA files and metadata with traceability manifest."""
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    human_canonical_targets = load_human_canonical_targets(args.surfaceome_csv.expanduser().resolve())
    human_isoform_targets = load_human_isoform_targets(args.afdb_by_gene_csv.expanduser().resolve())
    non_hla_human_genes = load_non_hla_gene_set(args.surfaceome_csv.expanduser().resolve())

    ortholog_query_csv = args.ortholog_query_csv.expanduser().resolve()
    mouse_targets = load_ortholog_targets(
        ortholog_query_csv=ortholog_query_csv,
        non_hla_human_genes=non_hla_human_genes,
        species_key="mouse",
    )
    cyno_targets = load_ortholog_targets(
        ortholog_query_csv=ortholog_query_csv,
        non_hla_human_genes=non_hla_human_genes,
        species_key="cyno",
    )

    human_canonical_fasta, human_canonical_meta = build_human_fasta_set(
        accession_to_genes=human_canonical_targets,
        cohort_label="human_canonical_non_hla",
        max_workers=args.max_workers,
        timeout=args.timeout,
        retry_max_attempts=args.retry_max_attempts,
        min_request_interval_ms=args.min_request_interval_ms,
    )
    human_isoform_fasta, human_isoform_meta = build_human_fasta_set(
        accession_to_genes=human_isoform_targets,
        cohort_label="human_isoforms_from_afdb_non_hla",
        max_workers=args.max_workers,
        timeout=args.timeout,
        retry_max_attempts=args.retry_max_attempts,
        min_request_interval_ms=args.min_request_interval_ms,
    )
    mouse_fasta, mouse_meta = build_ortholog_fasta_set(
        species_key="mouse",
        targets=mouse_targets,
        max_workers=args.max_workers,
        timeout=args.timeout,
        retry_max_attempts=args.retry_max_attempts,
        min_request_interval_ms=args.min_request_interval_ms,
    )
    cyno_fasta, cyno_meta = build_ortholog_fasta_set(
        species_key="cyno",
        targets=cyno_targets,
        max_workers=args.max_workers,
        timeout=args.timeout,
        retry_max_attempts=args.retry_max_attempts,
        min_request_interval_ms=args.min_request_interval_ms,
    )

    outputs: list[tuple[str, list[FastaRecord], list[dict[str, Any]]]] = [
        ("human_canonical_non_hla", human_canonical_fasta, human_canonical_meta),
        ("human_isoforms_from_afdb_non_hla", human_isoform_fasta, human_isoform_meta),
        ("mouse_ortholog_one2one_highconf_non_hla", mouse_fasta, mouse_meta),
        ("cyno_ortholog_one2one_highconf_non_hla", cyno_fasta, cyno_meta),
    ]

    manifest_records: list[dict[str, Any]] = []
    extras: dict[str, Any] = {"cohorts": {}}

    for cohort_name, fasta_records, metadata_rows in outputs:
        fasta_path = output_dir / f"{cohort_name}.fasta"
        metadata_path = output_dir / f"{cohort_name}_metadata.csv"
        write_fasta(fasta_path, fasta_records)

        metadata_fieldnames = sorted({key for row in metadata_rows for key in row.keys()})
        write_csv(metadata_path, metadata_fieldnames, metadata_rows)

        manifest_records.append(
            build_file_record(
                repo_root=ROOT,
                file_path=fasta_path,
                source_url="https://rest.uniprot.org/uniprotkb/{accession}.fasta",
                dataset=DATASET,
                status="downloaded",
                note=f"{cohort_name} FASTA",
            )
        )
        manifest_records.append(
            build_file_record(
                repo_root=ROOT,
                file_path=metadata_path,
                source_url="https://rest.uniprot.org/uniprotkb/search + /uniprotkb/{accession}.fasta",
                dataset=DATASET,
                status="downloaded",
                note=f"{cohort_name} metadata",
            )
        )

        extras["cohorts"][cohort_name] = {
            "n_sequences": len(fasta_records),
            "n_rows_metadata": len(metadata_rows),
            "status_counts": summarize_status(metadata_rows),
            "fasta_path": relative_to_repo(fasta_path, ROOT),
            "metadata_path": relative_to_repo(metadata_path, ROOT),
        }

    write_manifest(
        args.manifest.expanduser().resolve(),
        dataset=DATASET,
        script=relative_to_repo(Path(__file__), ROOT),
        records=manifest_records,
        extras=extras,
    )

    print(f"Wrote DeepTMHMM input cohorts to: {relative_to_repo(output_dir, ROOT)}")
    for cohort_name, _, metadata_rows in outputs:
        counts = summarize_status(metadata_rows)
        print(f"  {cohort_name}: {counts}")


if __name__ == "__main__":
    main()
