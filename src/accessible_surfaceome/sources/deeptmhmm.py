"""DeepTMHMM: build input FASTAs and parse output `.3line` predictions.

Two subcommands::

    python -m accessible_surfaceome.sources.deeptmhmm download
    python -m accessible_surfaceome.sources.deeptmhmm build

``download`` builds the per-cohort FASTA input sets that get fed into
the third-party DeepTMHMM 1.0.24 pipeline (see
``src/accessible_surfaceome/tools/install_deeptmhmm_academic.py``). The
actual prediction step is run out-of-band by that tool; its
``predicted_topologies.3line`` outputs land under
``data/external/deeptmhmm_surfaceome_predictions/<cohort>/``.

``build`` parses those .3line files into per-cohort TSVs for the M1
candidate-universe merge. (See the ``build_main`` docstring below for
the row schema.)

Build phase details (parsed by ``build_main``):

Inputs: per-cohort `predicted_topologies.3line` files under
``data/external/deeptmhmm_surfaceome_predictions/<cohort>/`` produced by the
DeepTMHMM 1.0.24 pipeline. The 3-line format is::

    >sp|ACCESSION|ENTRY_NAME | LABEL
    <amino acid sequence>
    <per-residue topology string over alphabet {S, O, M, I, B}>

DeepTMHMM emits one of five class labels per protein:
``TM`` (alpha-helical transmembrane), ``SP`` (signal peptide only, predicted
secreted), ``SP+TM`` (signal peptide + TM helices), ``BETA`` (beta-barrel
transmembrane), ``GLOB`` (globular / soluble, no TM or SP).

Outputs: per-cohort TSVs under ``data/processed/deeptmhmm/`` with one row per
UniProt accession as it appears in the 3-line header (isoform suffix
preserved in ``uniprot_accession_full``; the base accession is written to
``uniprot_accession`` for join convenience). Columns:

- identifiers: ``uniprot_accession``, ``uniprot_accession_full``,
  ``uniprot_entry_name``
- classification: ``deeptmhmm_label`` (one of TM/SP/SP+TM/BETA/GLOB)
- topology summaries: ``protein_length``, ``tm_helix_count``,
  ``beta_strand_count``, ``has_signal_peptide``, ``signal_peptide_length``
- terminal orientation (ignoring SP residues):
  ``n_term_side``, ``c_term_side`` (each ``I``/``O``/``M``/``B`` or empty),
  ``n_term_extracellular``, ``c_term_extracellular``,
  ``n_term_intracellular``, ``c_term_intracellular``
- derived flags: ``predicted_surface_membrane`` (1 iff label in
  {TM, SP+TM}), ``predicted_secreted`` (1 iff label == SP).
  BETA is deliberately excluded: human beta-barrel membrane proteins
  are essentially mitochondrial outer membrane (VDAC1/2/3, TOMM40,
  SAMM50, MTX1/2), not plasma-membrane / cell-surface proteins.

Also writes:
- ``deeptmhmm_build_summary.json`` — per-cohort row counts, label
  distributions, union accession coverage
- ``deeptmhmm_build_traceability.json`` — source file SHA256s and
  capture time

The terminal-orientation logic matches
``annotate_afdb_with_deeptmhmm_orientation.py``: the first/last topology
character *after skipping leading/trailing ``S`` residues* defines the
mature-chain termini side.
"""

from __future__ import annotations

import argparse
import csv
import json
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

from accessible_surfaceome.sources._support.traceability import (
    USER_AGENT,
    build_file_record,
    relative_to_repo,
    sha256_file,
    utc_now_iso,
    write_manifest,
)

from accessible_surfaceome.paths import REPO_ROOT as ROOT

DATASET = "deeptmhmm"
DEFAULT_INPUT_DIR = ROOT / "data" / "external" / "deeptmhmm_surfaceome_predictions"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "processed" / "deeptmhmm"
SUMMARY_JSON = "deeptmhmm_build_summary.json"
MANIFEST_JSON = "deeptmhmm_build_traceability.json"

COHORTS: list[tuple[str, str, str]] = [
    # (cohort_key, source_subdir, output_tsv_basename)
    ("human_canonical", "human_canonical_non_hla", "deeptmhmm_human_canonical.tsv"),
    ("human_isoforms", "human_isoforms_from_afdb_non_hla", "deeptmhmm_human_isoforms.tsv"),
    ("mouse_ortholog", "mouse_ortholog_one2one_highconf_non_hla", "deeptmhmm_mouse_ortholog.tsv"),
    ("cyno_ortholog", "cyno_ortholog_one2one_highconf_non_hla", "deeptmhmm_cyno_ortholog.tsv"),
]

VALID_LABELS = {"TM", "SP", "SP+TM", "BETA", "GLOB"}
SURFACE_MEMBRANE_LABELS = {"TM", "SP+TM"}

OUTPUT_COLUMNS = [
    "uniprot_accession",
    "uniprot_accession_full",
    "uniprot_entry_name",
    "deeptmhmm_label",
    "protein_length",
    "tm_helix_count",
    "beta_strand_count",
    "has_signal_peptide",
    "signal_peptide_length",
    "n_term_side",
    "c_term_side",
    "n_term_extracellular",
    "c_term_extracellular",
    "n_term_intracellular",
    "c_term_intracellular",
    "predicted_surface_membrane",
    "predicted_secreted",
    # ---- v0.5 additions (back-compat: existing consumers ignore extra columns)
    "ecd_length_residues",
    "icd_length_residues",
    "n_terminal_orientation",
    "c_terminal_orientation",
    "per_residue_topology",
]

# The full record set written to *.jsonl alongside the TSV. JSONL carries the
# input sequence too, which the TSV deliberately doesn't (raw FASTA is large
# and the TSV consumers don't need it).
JSONL_EXTRA_COLUMNS = ["sequence"]


def _translate_orientation(side: str) -> str:
    """Map DeepTMHMM terminal-side char to IsoformTopology orientation enum.

    Matches accessible_surfaceome.tools._shared.models.TerminalOrientation:
    'extracellular' | 'cytoplasmic' | 'indeterminate'.
    'B' is beta-strand outside; treat as extracellular (matches BETA-label
    OMP topology where strands face the periplasm/outside).
    """
    if side == "O" or side == "B":
        return "extracellular"
    if side == "I":
        return "cytoplasmic"
    return "indeterminate"


def _split_base_accession(acc: str) -> str:
    """Strip UniProt isoform suffix (e.g. ``Q9Y6K8-2`` -> ``Q9Y6K8``)."""
    return acc.split("-", 1)[0] if "-" in acc else acc


def _terminal_state(topology: str, *, from_n_term: bool) -> str:
    """First/last topology char after skipping SP residues."""
    if not topology:
        return ""
    chars = topology if from_n_term else reversed(topology)
    for ch in chars:
        if ch != "S":
            return ch
    return ""


def _count_runs(topology: str, state: str) -> int:
    """Count contiguous runs of `state` in the topology string."""
    if not topology or state not in topology:
        return 0
    return len(re.findall(f"{re.escape(state)}+", topology))


def parse_3line(path: Path) -> list[dict]:
    """Parse one predicted_topologies.3line file into records."""
    lines = [ln.rstrip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if len(lines) % 3 != 0:
        raise ValueError(f"3line file malformed (not 3-line groups): {path}")

    records: list[dict] = []
    for i in range(0, len(lines), 3):
        header = lines[i]
        sequence = lines[i + 1]
        topology = lines[i + 2].upper()

        if not header.startswith(">"):
            raise ValueError(f"Bad header at offset {i} in {path}: {header!r}")
        payload = header[1:].strip()
        # "sp|ACC|ENTRY_NAME | LABEL"
        if " | " not in payload:
            raise ValueError(f"Header missing ' | LABEL' in {path}: {header!r}")
        seq_id, label = payload.rsplit(" | ", 1)
        label = label.strip()
        if label not in VALID_LABELS:
            raise ValueError(f"Unknown DeepTMHMM label {label!r} in {path}")

        parts = seq_id.split("|")
        if len(parts) < 3:
            raise ValueError(f"Unexpected seq_id format in {path}: {seq_id!r}")
        acc_full = parts[1].strip()
        entry_name = parts[2].strip()
        if not acc_full:
            raise ValueError(f"Empty accession in {path}: {header!r}")

        if len(sequence) != len(topology):
            raise ValueError(
                f"Length mismatch for {acc_full} in {path}: "
                f"seq={len(sequence)} topo={len(topology)}"
            )

        n_side = _terminal_state(topology, from_n_term=True)
        c_side = _terminal_state(topology, from_n_term=False)

        sp_len = 0
        for ch in topology:
            if ch == "S":
                sp_len += 1
            else:
                break

        records.append(
            {
                "uniprot_accession": _split_base_accession(acc_full),
                "uniprot_accession_full": acc_full,
                "uniprot_entry_name": entry_name,
                "deeptmhmm_label": label,
                "protein_length": len(sequence),
                "tm_helix_count": _count_runs(topology, "M"),
                "beta_strand_count": _count_runs(topology, "B"),
                "has_signal_peptide": int("S" in topology),
                "signal_peptide_length": sp_len,
                "n_term_side": n_side,
                "c_term_side": c_side,
                "n_term_extracellular": int(n_side == "O"),
                "c_term_extracellular": int(c_side == "O"),
                "n_term_intracellular": int(n_side == "I"),
                "c_term_intracellular": int(c_side == "I"),
                "predicted_surface_membrane": int(label in SURFACE_MEMBRANE_LABELS),
                "predicted_secreted": int(label == "SP"),
                "ecd_length_residues": topology.count("O"),
                "icd_length_residues": topology.count("I"),
                "n_terminal_orientation": _translate_orientation(n_side),
                "c_terminal_orientation": _translate_orientation(c_side),
                "per_residue_topology": topology,
                "sequence": sequence,
            }
        )
    return records


def write_jsonl(records: list[dict], path: Path) -> None:
    """Write records as JSONL — carries the full sequence and topology string."""
    path.parent.mkdir(parents=True, exist_ok=True)
    records_sorted = sorted(records, key=lambda r: r["uniprot_accession_full"])
    with path.open("w", encoding="utf-8") as f:
        for r in records_sorted:
            f.write(json.dumps(r, sort_keys=True) + "\n")


def write_tsv(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    records_sorted = sorted(records, key=lambda r: r["uniprot_accession_full"])
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write("\t".join(OUTPUT_COLUMNS) + "\n")
        for r in records_sorted:
            f.write("\t".join(str(r[c]) for c in OUTPUT_COLUMNS) + "\n")


def _build_parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Parse DeepTMHMM .3line predictions for the M1 merge."
    )
    p.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return p.parse_args(argv)


def build_main(argv: list[str] | None = None) -> None:
    args = _build_parse_args(argv)
    in_dir: Path = args.input_dir
    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    cohort_summaries: dict[str, dict] = {}
    cohort_outputs: dict[str, dict] = {}
    source_files: dict[str, dict] = {}

    union_full = set()
    union_base = set()

    for key, subdir, out_name in COHORTS:
        src_path = in_dir / subdir / "predicted_topologies.3line"
        if not src_path.exists():
            raise FileNotFoundError(f"Missing DeepTMHMM input: {src_path}")

        print(f"parsing cohort={key}  {src_path}")
        records = parse_3line(src_path)

        dup_full = len(records) - len({r["uniprot_accession_full"] for r in records})
        if dup_full:
            print(f"  WARNING: {dup_full} duplicate uniprot_accession_full rows in {key}")

        out_path = out_dir / out_name
        write_tsv(records, out_path)

        labels = sorted({r["deeptmhmm_label"] for r in records})
        label_counts = {
            lab: sum(1 for r in records if r["deeptmhmm_label"] == lab) for lab in labels
        }
        n_surface = sum(1 for r in records if r["predicted_surface_membrane"])
        n_secreted = sum(1 for r in records if r["predicted_secreted"])

        cohort_summaries[key] = {
            "n_proteins": len(records),
            "n_unique_accession_full": len({r["uniprot_accession_full"] for r in records}),
            "n_unique_accession_base": len({r["uniprot_accession"] for r in records}),
            "label_counts": label_counts,
            "n_predicted_surface_membrane": n_surface,
            "n_predicted_secreted": n_secreted,
        }
        cohort_outputs[out_name] = {
            "local_path": str(out_path.relative_to(ROOT)),
            "sha256": sha256_file(out_path),
            "size_bytes": out_path.stat().st_size,
            "n_rows": len(records),
            "primary_key": "uniprot_accession_full",
        }
        source_files[key] = {
            "local_path": str(src_path.relative_to(ROOT)),
            "sha256": sha256_file(src_path),
            "size_bytes": src_path.stat().st_size,
            "n_sequences": len(records),
        }

        if key in {"human_canonical", "human_isoforms"}:
            union_full.update(r["uniprot_accession_full"] for r in records)
            union_base.update(r["uniprot_accession"] for r in records)

        print(
            f"  wrote {out_path.relative_to(ROOT)}  "
            f"n={len(records):,}  surface={n_surface:,}  "
            f"secreted={n_secreted:,}  labels={label_counts}"
        )

    summary = {
        "generated_at_utc": utc_now_iso(),
        "cohorts": cohort_summaries,
        "human_union": {
            "n_unique_accession_full": len(union_full),
            "n_unique_accession_base": len(union_base),
            "description": (
                "union of uniprot accessions across human_canonical + human_isoforms cohorts"
            ),
        },
    }
    (out_dir / SUMMARY_JSON).write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    manifest = {
        "dataset": DATASET,
        "generated_at_utc": utc_now_iso(),
        "script": Path(__file__).relative_to(ROOT).as_posix(),
        "source_files": source_files,
        "outputs": cohort_outputs,
        "label_vocabulary": sorted(VALID_LABELS),
        "derived_columns": [
            {"name": "n_term_side", "rule": "first topology char after skipping leading 'S'"},
            {"name": "c_term_side", "rule": "last topology char after skipping trailing 'S'"},
            {
                "name": "predicted_surface_membrane",
                "rule": "1 iff deeptmhmm_label in {TM, SP+TM} (BETA excluded — human beta-barrels are mitochondrial outer membrane, not plasma-membrane)",
            },
            {"name": "predicted_secreted", "rule": "1 iff deeptmhmm_label == 'SP'"},
            {
                "name": "signal_peptide_length",
                "rule": "count of leading 'S' residues in topology",
            },
        ],
    }
    (out_dir / MANIFEST_JSON).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(
        f"human union (canonical + isoforms): "
        f"n_full={len(union_full):,}  n_base={len(union_base):,}"
    )


# ---- download ----
DOWNLOAD_DATASET = "DeepTMHMM_surfaceome_sequence_sets"
UNIPROT_FASTA_TEMPLATE = "https://rest.uniprot.org/uniprotkb/{accession}.fasta"
UNIPROT_SEARCH_URL = "https://rest.uniprot.org/uniprotkb/search"
RETRYABLE_HTTP_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
_FASTA_SEQ_LINE_RE = re.compile(r"^[A-Z*.-]+$")

DEFAULT_SURFACEOME_CSV = (
    ROOT / "data" / "analysis" / "expression_filtering" / "surfaceome_expressed.csv"
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


def _download_parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse command-line arguments for the DeepTMHMM cohort builder."""
    parser = argparse.ArgumentParser(
        description="Build DeepTMHMM input FASTA cohorts (human + ortholog)."
    )
    parser.add_argument("--surfaceome-csv", type=Path, default=DEFAULT_SURFACEOME_CSV)
    parser.add_argument("--afdb-by-gene-csv", type=Path, default=DEFAULT_AFDB_BY_GENE_CSV)
    parser.add_argument("--ortholog-query-csv", type=Path, default=DEFAULT_ORTHOLOG_QUERY_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--max-workers", type=int, default=16)
    parser.add_argument("--retry-max-attempts", type=int, default=4)
    parser.add_argument("--min-request-interval-ms", type=int, default=200)
    return parser.parse_args(argv)


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


def download_main(argv: list[str] | None = None) -> None:
    """Build cohort FASTA files and metadata with traceability manifest."""
    args = _download_parse_args(argv)
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
                dataset=DOWNLOAD_DATASET,
                status="downloaded",
                note=f"{cohort_name} FASTA",
            )
        )
        manifest_records.append(
            build_file_record(
                repo_root=ROOT,
                file_path=metadata_path,
                source_url="https://rest.uniprot.org/uniprotkb/search + /uniprotkb/{accession}.fasta",
                dataset=DOWNLOAD_DATASET,
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
        dataset=DOWNLOAD_DATASET,
        script=relative_to_repo(Path(__file__), ROOT),
        records=manifest_records,
        extras=extras,
    )

    print(f"Wrote DeepTMHMM input cohorts to: {relative_to_repo(output_dir, ROOT)}")
    for cohort_name, _, metadata_rows in outputs:
        counts = summarize_status(metadata_rows)
        print(f"  {cohort_name}: {counts}")

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("download", help="Build DeepTMHMM input FASTA cohorts.", add_help=False)
    sub.add_parser("build", help="Parse DeepTMHMM .3line predictions for the M1 merge.", add_help=False)
    args, remainder = parser.parse_known_args(argv)
    if args.command == "download":
        download_main(remainder)
    elif args.command == "build":
        build_main(remainder)


# ---------------------------------------------------------------------------
# Sweep helpers — added for the topology + paralog pipeline.
# These are used by scripts/run_topology_sweep.py to (a) fetch FASTAs into a
# disk cache, (b) invoke DeepTMHMM on a batch FASTA, and (c) parse the
# resulting .3line into rich JSONL records.
# ---------------------------------------------------------------------------


DEEPTMHMM_PACKAGE_DIR = ROOT / "data" / "external" / "deeptmhmm" / "DeepTMHMM-Academic-License-v1.0"
DEEPTMHMM_VENV = ROOT / ".venv-deeptmhmm"
DEEPTMHMM_TOOL_VERSION = "deeptmhmm-1.0.24"
SEQUENCE_CACHE_DIR = ROOT / "data" / "external" / "sequences"
# DeepTMHMM 1.0.24 OOMs on sequences much longer than this; titin is ~34000 aa.
DEEPTMHMM_MAX_SEQUENCE_LENGTH = 8000


def resolve_deeptmhmm_paths(root_override: Path | None = None) -> tuple[Path, Path]:
    """Return ``(package_dir, venv_dir)`` for DeepTMHMM, honoring overrides.

    Resolution order: explicit ``root_override`` arg, then ``DEEPTMHMM_ROOT``
    env var, then this repo's ``data/external/deeptmhmm`` + ``.venv-deeptmhmm``.
    ``root`` is the parent directory holding both the package dir and the venv —
    matches the layout that ``install_deeptmhmm_academic.py`` produces and the
    one used in ``deliverome-internal``::

        <root>/data/external/deeptmhmm/DeepTMHMM-Academic-License-v1.0/predict.py
        <root>/.venv-deeptmhmm/bin/python

    The override can point at deliverome-internal directly when DeepTMHMM is
    installed there:

        DEEPTMHMM_ROOT=/Users/.../Git/deliverome-internal \\
            uv run python scripts/run_topology_sweep.py ...
    """
    import os as _os

    if root_override is None:
        env_root = _os.environ.get("DEEPTMHMM_ROOT", "").strip()
        if env_root:
            root_override = Path(env_root).expanduser().resolve()

    if root_override is None:
        return DEEPTMHMM_PACKAGE_DIR, DEEPTMHMM_VENV

    package_dir = root_override / "data" / "external" / "deeptmhmm" / "DeepTMHMM-Academic-License-v1.0"
    venv_dir = root_override / ".venv-deeptmhmm"
    return package_dir, venv_dir


def fasta_cache_path(accession: str, cache_dir: Path = SEQUENCE_CACHE_DIR) -> Path:
    """Disk path for the cached single-protein FASTA for ``accession``."""
    return cache_dir / f"{accession}.fasta"


def fetch_uniprot_fastas_to_cache(
    accessions: list[str],
    *,
    cache_dir: Path = SEQUENCE_CACHE_DIR,
    timeout: int = 30,
    retry_max_attempts: int = 4,
    min_request_interval_ms: int = 100,
    max_workers: int = 8,
    on_progress: "Any | None" = None,
) -> dict[str, Path]:
    """Concurrently fetch UniProt FASTAs and cache one file per accession.

    Returns a mapping accession -> cached file path for every input accession
    that resolved successfully. Accessions already on disk are skipped (the
    cache is the source of truth). I/O-bound; threads not processes.

    Raises if no accession resolves; logs but continues on per-accession errors.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}

    to_fetch: list[str] = []
    for acc in accessions:
        if not acc:
            continue
        path = fasta_cache_path(acc, cache_dir)
        if path.exists() and path.stat().st_size > 0:
            out[acc] = path
            continue
        to_fetch.append(acc)

    if not to_fetch:
        return out

    def worker(acc: str) -> tuple[str, Path | None, str | None]:
        try:
            record = fetch_uniprot_fasta(
                acc,
                timeout=timeout,
                retry_max_attempts=retry_max_attempts,
                min_request_interval_ms=min_request_interval_ms,
            )
        except Exception as exc:  # noqa: BLE001 - we want every failure
            return acc, None, str(exc)
        path = fasta_cache_path(acc, cache_dir)
        # Write back as plain UniProt-style FASTA so downstream parsers are
        # happy. Preserve the original header (carries `sp|ACC|ENTRY_NAME`).
        path.write_text(record.header + "\n" + record.sequence + "\n", encoding="utf-8")
        return acc, path, None

    n_done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for acc, path, err in pool.map(worker, to_fetch):
            n_done += 1
            if path is None:
                if on_progress is not None:
                    on_progress("fetch_error", acc, err)
                continue
            out[acc] = path
            if on_progress is not None and n_done % 50 == 0:
                on_progress("fetch_progress", acc, f"{n_done}/{len(to_fetch)}")
    return out


def assemble_batch_fasta(
    fasta_paths: list[Path], *, batch_path: Path, max_seq_length: int = DEEPTMHMM_MAX_SEQUENCE_LENGTH,
) -> tuple[int, list[str]]:
    """Concatenate ``fasta_paths`` into ``batch_path``, skipping over-long sequences.

    Returns ``(n_written, skipped_accessions)``. The skip-list reason is
    always "sequence_too_long" — callers are expected to log it themselves.
    """
    batch_path.parent.mkdir(parents=True, exist_ok=True)
    skipped: list[str] = []
    n_written = 0
    with batch_path.open("w", encoding="utf-8") as out_f:
        for src in fasta_paths:
            text = src.read_text(encoding="utf-8")
            lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
            if not lines or not lines[0].startswith(">"):
                continue
            header = lines[0]
            sequence = "".join(lines[1:])
            if len(sequence) > max_seq_length:
                # Recover the bare accession from the header for the skip-list.
                acc_full = header.split("|")[1] if "|" in header else header.lstrip(">")
                skipped.append(acc_full)
                continue
            out_f.write(header + "\n" + sequence + "\n")
            n_written += 1
    return n_written, skipped


def run_deeptmhmm_batch(
    input_fasta: Path,
    *,
    output_dir: Path,
    package_dir: Path = DEEPTMHMM_PACKAGE_DIR,
    venv_dir: Path = DEEPTMHMM_VENV,
    timeout_s: float = 7200.0,
) -> Path:
    """Run DeepTMHMM ``predict.py`` on one batch FASTA. Returns the .3line path.

    Idempotent: if ``output_dir/predicted_topologies.3line`` already exists
    and is non-empty, returns it without re-running. This is the checkpoint
    mechanism for the overnight sweep.

    Raises ``RuntimeError`` if the subprocess exits non-zero or the expected
    output file is missing.
    """
    import subprocess

    output_dir.mkdir(parents=True, exist_ok=True)
    expected = output_dir / "predicted_topologies.3line"
    if expected.exists() and expected.stat().st_size > 0:
        return expected

    predict_py = package_dir / "predict.py"
    if not predict_py.exists():
        raise RuntimeError(
            f"DeepTMHMM not installed; predict.py missing at {predict_py}. "
            "Run: uv run python -m accessible_surfaceome.tools.install_deeptmhmm_academic"
        )
    python_bin = venv_dir / "bin" / "python"
    if not python_bin.exists():
        raise RuntimeError(
            f"DeepTMHMM venv missing at {venv_dir}. "
            "Run: uv run python -m accessible_surfaceome.tools.install_deeptmhmm_academic"
        )

    cmd = [
        str(python_bin),
        str(predict_py),
        "--fasta",
        str(input_fasta.resolve()),
        "--output-dir",
        str(output_dir.resolve()),
    ]
    result = subprocess.run(
        cmd,
        cwd=str(package_dir),
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    if result.returncode != 0:
        # Surface stderr's tail so the orchestrator's error log is actionable.
        tail = (result.stderr or "")[-2000:]
        raise RuntimeError(
            f"DeepTMHMM predict.py exited {result.returncode} on {input_fasta.name}: {tail!r}"
        )
    if not expected.exists() or expected.stat().st_size == 0:
        raise RuntimeError(
            f"DeepTMHMM finished but no output at {expected} (stdout tail: {result.stdout[-500:]!r})"
        )
    return expected


if __name__ == "__main__":
    main()
