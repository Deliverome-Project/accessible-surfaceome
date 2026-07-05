"""Ensembl Compara within-species paralog pull (BioMart REST).

Sibling of ``ensembl_compara.py`` (orthologs). For each query Ensembl gene ID,
this module pulls every Compara paralog from the ``hsapiens_paralog_*`` BioMart
attributes — paralogous human genes within the same Compara family.

Compara paralog ``orthology_type`` values:

* ``within_species_paralog`` — bona fide paralog (most common)
* ``other_paralog``           — outparalog (different family lineage)
* ``gene_split``              — split-gene neighbour pair

We retain all three but flag them in ``paralogy_type`` so downstream consumers
can filter. Unlike orthologs, BioMart's paralog API does **not** expose an
explicit confidence flag — so ``is_high_confidence`` is set based on
``paralogy_type == 'within_species_paralog'`` only.

One subcommand::

    python -m accessible_surfaceome.sources.ensembl_compara_paralogs download

Default input: the M1 candidate-universe TSV
(``data/processed/candidate_universe/candidate_universe.tsv``). HGNC TSV:
``data/raw/hgnc_complete_set.tsv`` (same as the ortholog puller).

Outputs (under ``data/external/ensembl_compara_paralogs/``):

* ``compara_paralogs_raw_rows.csv`` — raw BioMart payload rows
* ``compara_paralogs_by_gene.csv``  — top-50-by-perc-id per gene, gene-symbol view
* ``compara_paralogs_by_ensembl.csv`` — top-50-by-perc-id per gene, Ensembl-ID view
* ``download_traceability.json``   — manifest with SHA256s + capture time
"""

from __future__ import annotations

import argparse
import csv
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
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
from accessible_surfaceome.sources.ensembl_compara import (
    BIOMART_URL,
    DEFAULT_HGNC,
    DEFAULT_INPUT,
    InputRecord,
    ResolvedGene,
    build_resolved_genes,
    chunked,
    load_hgnc_maps,
    load_input_records,
    normalize_symbol,
    parse_float,
)

DATASET = "Ensembl_Compara_surfaceome_paralogs"

DEFAULT_OUTPUT_DIR = ROOT / "data" / "external" / "ensembl_compara_paralogs"
DEFAULT_RAW_OUTPUT = DEFAULT_OUTPUT_DIR / "compara_paralogs_raw_rows.csv"
DEFAULT_GENE_OUTPUT = DEFAULT_OUTPUT_DIR / "compara_paralogs_by_gene.csv"
DEFAULT_ENSEMBL_OUTPUT = DEFAULT_OUTPUT_DIR / "compara_paralogs_by_ensembl.csv"
DEFAULT_MANIFEST = DEFAULT_OUTPUT_DIR / "download_traceability.json"

# Per-gene cap. IGH / TCR / olfactory families can have hundreds of members;
# we keep only the top-N most-identical paralogs to bound table growth.
DEFAULT_TOP_N_PER_GENE = 50

# Compara release tag is now a REQUIRED CLI argument — no default. The
# BioMart endpoint (www.ensembl.org/biomart/martservice) is not versioned
# and always serves the current release, so a hard-coded default silently
# rots as Ensembl bumps releases (this file previously defaulted to
# "Compara r112" from April 2024 while pulls in 2026 actually got r115+
# data). The operator must supply the label explicitly, either as a dated
# snapshot tag (e.g. "ensembl_compara_2026_06_01" — matches the ortholog
# side's convention) or as the release number known-current at pull time.

RETRYABLE_HTTP_CODES = {408, 409, 425, 429, 500, 502, 503, 504}

PARALOG_ATTRIBUTES = [
    "ensembl_gene_id",                                  # query gene
    "external_gene_name",                               # query symbol
    "hsapiens_paralog_ensembl_gene",
    "hsapiens_paralog_associated_gene_name",
    "hsapiens_paralog_chromosome",
    "hsapiens_paralog_perc_id",
    "hsapiens_paralog_perc_id_r1",
    # BioMart names paralog-type "orthology_type" too (Ensembl's terminology
    # quirk — same attribute for ortholog and paralog views).
    "hsapiens_paralog_orthology_type",
    # Compara family / clade descriptor (e.g. "Opisthokonta", "Mammalia").
    # This is NOT the ENSFM family ID GPR75.json uses; that requires the
    # separate Compara family endpoint. We carry the BioMart subtype in
    # ``family_id`` for now — same column, different value semantics.
    "hsapiens_paralog_subtype",
]

PARALOG_HIGH_CONFIDENCE_TYPE = "within_species_paralog"


@dataclass(frozen=True)
class ParalogRow:
    """One BioMart paralog row, normalized."""

    query_ensembl_gene: str
    query_gene_symbol: str
    paralog_ensembl_gene: str
    paralog_gene_symbol: str
    paralog_chromosome: str
    paralogy_type: str
    family_id: str
    percent_identity: float | None
    percent_identity_r1: float | None

    @property
    def is_high_confidence(self) -> bool:
        return self.paralogy_type == PARALOG_HIGH_CONFIDENCE_TYPE


def build_biomart_query_xml(ensembl_ids: list[str]) -> str:
    attr_xml = "\n".join([f'    <Attribute name="{attr}" />' for attr in PARALOG_ATTRIBUTES])
    id_value = ",".join(ensembl_ids)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!DOCTYPE Query>\n"
        '<Query virtualSchemaName="default" formatter="TSV" header="0" '
        'uniqueRows="0" datasetConfigVersion="0.6">\n'
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
                return response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            if exc.code not in RETRYABLE_HTTP_CODES or attempt == retry_max_attempts:
                raise RuntimeError(f"BioMart HTTP {exc.code} for {len(ensembl_ids)} IDs") from exc
        except (TimeoutError, URLError) as exc:
            if attempt == retry_max_attempts:
                raise RuntimeError(f"BioMart network error: {exc}") from exc
        if min_request_interval_ms > 0:
            time.sleep(min_request_interval_ms / 1000.0)
    raise RuntimeError("BioMart exhausted retries")


def parse_paralog_tsv(payload: str) -> list[ParalogRow]:
    """Parse one BioMart TSV payload (no header) into ParalogRow records."""
    rows: list[ParalogRow] = []
    for line in payload.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        # BioMart silently truncates trailing-empty fields; pad to the schema.
        while len(fields) < len(PARALOG_ATTRIBUTES):
            fields.append("")
        if len(fields) > len(PARALOG_ATTRIBUTES):
            fields = fields[: len(PARALOG_ATTRIBUTES)]

        query_ensg = (fields[0] or "").strip().upper()
        if not query_ensg:
            continue
        paralog_ensg = (fields[2] or "").strip().upper()
        if not paralog_ensg:
            # Rows without a paralog are valid BioMart output for genes with no paralogs.
            # Skip them — they would clutter the table with nulls.
            continue
        rows.append(
            ParalogRow(
                query_ensembl_gene=query_ensg,
                query_gene_symbol=normalize_symbol(fields[1]),
                paralog_ensembl_gene=paralog_ensg,
                paralog_gene_symbol=normalize_symbol(fields[3]),
                paralog_chromosome=(fields[4] or "").strip(),
                percent_identity=parse_float(fields[5]),
                percent_identity_r1=parse_float(fields[6]),
                paralogy_type=(fields[7] or "").strip(),
                family_id=(fields[8] or "").strip(),
            )
        )
    return rows


def fetch_all_paralogs(
    *,
    ensembl_ids: list[str],
    chunk_size: int = 200,
    timeout: int = 60,
    retry_max_attempts: int = 4,
    min_request_interval_ms: int = 200,
) -> list[ParalogRow]:
    """Fetch paralogs for every Ensembl gene ID, chunked over BioMart."""
    if not ensembl_ids:
        return []
    all_rows: list[ParalogRow] = []
    chunks = chunked(ensembl_ids, chunk_size)
    print(f"  paralog BioMart pull: {len(chunks)} chunks of ≤{chunk_size} IDs")
    for i, chunk in enumerate(chunks, 1):
        payload = fetch_biomart_chunk(
            ensembl_ids=chunk,
            timeout=timeout,
            retry_max_attempts=retry_max_attempts,
            min_request_interval_ms=min_request_interval_ms,
        )
        chunk_rows = parse_paralog_tsv(payload)
        all_rows.extend(chunk_rows)
        print(f"    chunk {i}/{len(chunks)}: {len(chunk_rows)} paralog rows")
    return all_rows


def top_n_paralogs_per_gene(
    rows: list[ParalogRow], *, top_n: int = DEFAULT_TOP_N_PER_GENE
) -> list[ParalogRow]:
    """Keep only the top-N paralogs per query gene, ranked by perc_id DESC."""
    by_gene: dict[str, list[ParalogRow]] = defaultdict(list)
    for r in rows:
        by_gene[r.query_ensembl_gene].append(r)
    kept: list[ParalogRow] = []
    for gene_id in sorted(by_gene):
        group = by_gene[gene_id]
        group.sort(
            key=lambda r: (
                -(r.percent_identity if r.percent_identity is not None else -1),
                r.paralog_ensembl_gene,
            )
        )
        kept.extend(group[:top_n])
    return kept


# ---- output writers -------------------------------------------------------

_RAW_COLUMNS = [
    "query_ensembl_gene",
    "query_gene_symbol",
    "paralog_ensembl_gene",
    "paralog_gene_symbol",
    "paralog_chromosome",
    "paralogy_type",
    "family_id",
    "percent_identity",
    "percent_identity_r1",
    "is_high_confidence",
]


def write_raw_csv(path: Path, rows: list[ParalogRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(_RAW_COLUMNS)
        for r in rows:
            w.writerow(
                [
                    r.query_ensembl_gene,
                    r.query_gene_symbol,
                    r.paralog_ensembl_gene,
                    r.paralog_gene_symbol,
                    r.paralog_chromosome,
                    r.paralogy_type,
                    r.family_id,
                    r.percent_identity if r.percent_identity is not None else "",
                    r.percent_identity_r1 if r.percent_identity_r1 is not None else "",
                    1 if r.is_high_confidence else 0,
                ]
            )


def write_by_gene_csv(
    path: Path,
    rows: list[ParalogRow],
    *,
    resolved_by_gene: dict[str, ResolvedGene],
    input_by_symbol: dict[str, InputRecord],
) -> None:
    """One row per (input gene_symbol, paralog) with denormalized join info.

    ``input_by_symbol`` maps gene_symbol → InputRecord so we can carry the
    UniProt accession that brought this gene into the candidate set.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "query_gene_symbol_resolved",
        "query_gene_symbol_input",
        "query_uniprot_acc",
        "query_ensembl_gene",
        "paralog_ensembl_gene",
        "paralog_gene_symbol",
        "paralog_chromosome",
        "paralogy_type",
        "family_id",
        "percent_identity",
        "is_high_confidence",
    ]

    by_query_ensg: dict[str, str] = {}  # ensembl -> input_gene_symbol (for join)
    for sym, resolved in resolved_by_gene.items():
        for ensg in resolved.query_ensembl_gene_ids:
            by_query_ensg.setdefault(ensg, sym)

    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            input_sym = by_query_ensg.get(r.query_ensembl_gene, "")
            input_record = input_by_symbol.get(input_sym)
            resolved = resolved_by_gene.get(input_sym)
            w.writerow(
                [
                    resolved.resolved_gene_symbol if resolved else input_sym,
                    input_sym,
                    (input_record.input_uniprot_id if input_record else ""),
                    r.query_ensembl_gene,
                    r.paralog_ensembl_gene,
                    r.paralog_gene_symbol,
                    r.paralog_chromosome,
                    r.paralogy_type,
                    r.family_id,
                    r.percent_identity if r.percent_identity is not None else "",
                    1 if r.is_high_confidence else 0,
                ]
            )


# ---- CLI ------------------------------------------------------------------


def _download_parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-tsv", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--hgnc-tsv", type=Path, default=DEFAULT_HGNC)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--chunk-size", type=int, default=200)
    p.add_argument("--timeout", type=int, default=60)
    p.add_argument("--retry-max-attempts", type=int, default=4)
    p.add_argument("--min-request-interval-ms", type=int, default=200)
    p.add_argument("--top-n-per-gene", type=int, default=DEFAULT_TOP_N_PER_GENE)
    p.add_argument(
        "--compara-version",
        type=str,
        required=True,
        help="Label carried into every output row; used as an FK to D1's "
        "compara_release table. Must be supplied explicitly — the BioMart "
        "endpoint is not versioned, so a hard-coded default would silently "
        "misrepresent which release actually got pulled. Preferred shape: "
        "a dated snapshot tag matching the ortholog side "
        "(e.g. 'ensembl_compara_2026_06_01').",
    )
    p.add_argument(
        "--override-genes",
        type=str,
        default="",
        help="Comma-separated gene symbols. When set, the input TSV is filtered "
             "to just these symbols (for dry-run testing). Legacy path; the "
             "HGNC-keyed entry point is --override-ensembl-ids.",
    )
    p.add_argument(
        "--override-ensembl-ids",
        type=str,
        default="",
        help="Comma-separated Ensembl gene IDs (ENSG...). When set, skips "
             "HGNC TSV loading and symbol resolution entirely — BioMart is "
             "queried directly with these IDs. The HGNC-first orchestrator "
             "passes its candidate set's ensembl_gene values through here.",
    )
    return p.parse_args(argv)


def _resolve_with_override_ensembl_ids(
    *, override_ensembl_ids: list[str]
) -> tuple[list[InputRecord], dict[str, ResolvedGene]]:
    """Build a minimal records + resolved-genes pair from raw Ensembl IDs.

    No HGNC TSV, no UniProt lookup — just enough scaffolding to feed
    ``fetch_all_paralogs`` and ``write_by_gene_csv``. The query_uniprot_acc
    column in the output CSV will be empty in this path; downstream
    consumers (``run_topology_sweep.compute_paralog_records``) resolve
    paralog UniProt accessions via ``gene_identifier`` rather than reading
    that column.
    """
    from accessible_surfaceome.sources.ensembl_compara import (
        InputRecord as _InputRecord,
        ResolvedGene as _ResolvedGene,
    )

    records: list[InputRecord] = []
    resolved: dict[str, ResolvedGene] = {}
    seen: set[str] = set()
    for raw in override_ensembl_ids:
        ensg = raw.strip().upper()
        if not ensg or ensg in seen:
            continue
        seen.add(ensg)
        # InputRecord uses gene_symbol as the dict key; with no HGNC TSV
        # available, the Ensembl ID itself serves as a stand-in identity.
        fake_symbol = ensg  # query-local placeholder, never written to TSV
        records.append(
            _InputRecord(
                gene_symbol=fake_symbol,
                input_uniprot_id="",
                input_ensembl_gene_ids=[ensg],
            )
        )
        resolved[fake_symbol] = _ResolvedGene(
            input_gene_symbol=fake_symbol,
            resolved_gene_symbol=fake_symbol,
            mapping_status="override_ensembl_id",
            resolver_ensembl_gene_ids=[ensg],
            query_ensembl_gene_ids=[ensg],
            input_records=[records[-1]],
        )
    return records, resolved


def download_main(argv: list[str] | None = None) -> None:
    args = _download_parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    override_ensembl = [
        s.strip() for s in args.override_ensembl_ids.split(",") if s.strip()
    ]
    if override_ensembl:
        # HGNC-first path: skip HGNC TSV + symbol resolution entirely.
        print(f"using --override-ensembl-ids: {len(override_ensembl)} Ensembl IDs")
        records, resolved = _resolve_with_override_ensembl_ids(
            override_ensembl_ids=override_ensembl,
        )
    else:
        print(f"loading input records from {args.input_tsv}")
        records = load_input_records(args.input_tsv)
        print(f"  loaded {len(records)} input rows")

        override = {s.strip().upper() for s in args.override_genes.split(",") if s.strip()}
        if override:
            records = [r for r in records if r.gene_symbol in override]
            print(f"  filtered to {len(records)} rows via --override-genes={sorted(override)}")

        print(f"loading HGNC maps from {args.hgnc_tsv}")
        sym2ensg, alias2sym, prev2sym = load_hgnc_maps(args.hgnc_tsv)
        resolved = build_resolved_genes(records, sym2ensg, alias2sym, prev2sym)
        print(f"  resolved {len(resolved)} unique gene symbols")

    all_query_ids: list[str] = []
    seen: set[str] = set()
    for r in resolved.values():
        for ensg in r.query_ensembl_gene_ids:
            if ensg and ensg not in seen:
                seen.add(ensg)
                all_query_ids.append(ensg)
    print(f"  total Ensembl gene IDs to query: {len(all_query_ids)}")

    rows = fetch_all_paralogs(
        ensembl_ids=all_query_ids,
        chunk_size=args.chunk_size,
        timeout=args.timeout,
        retry_max_attempts=args.retry_max_attempts,
        min_request_interval_ms=args.min_request_interval_ms,
    )
    print(f"fetched {len(rows)} raw paralog rows")

    write_raw_csv(args.output_dir / "compara_paralogs_raw_rows.csv", rows)

    kept = top_n_paralogs_per_gene(rows, top_n=args.top_n_per_gene)
    print(f"after top-{args.top_n_per_gene} per gene cap: {len(kept)} rows")

    input_by_symbol = {rec.gene_symbol: rec for rec in records}
    write_by_gene_csv(
        args.output_dir / "compara_paralogs_by_gene.csv",
        kept,
        resolved_by_gene=resolved,
        input_by_symbol=input_by_symbol,
    )

    manifest_records = [
        build_file_record(
            repo_root=ROOT,
            file_path=args.output_dir / "compara_paralogs_raw_rows.csv",
            source_url=BIOMART_URL,
            dataset=DATASET,
            status="downloaded",
            note=f"BioMart paralog rows (compara_version={args.compara_version})",
        ),
        build_file_record(
            repo_root=ROOT,
            file_path=args.output_dir / "compara_paralogs_by_gene.csv",
            source_url=BIOMART_URL,
            dataset=DATASET,
            status="derived",
            note=f"Top-{args.top_n_per_gene} paralogs per query gene",
        ),
    ]
    write_manifest(
        args.output_dir / "download_traceability.json",
        dataset=DATASET,
        script=relative_to_repo(Path(__file__), ROOT),
        records=manifest_records,
        extras={
            "compara_version": args.compara_version,
            "n_input_records": len(records),
            "n_unique_query_genes": len(all_query_ids),
            "n_raw_paralog_rows": len(rows),
            "n_top_n_rows": len(kept),
            "top_n_per_gene": args.top_n_per_gene,
        },
    )

    print(f"\nWrote paralog outputs to {relative_to_repo(args.output_dir, ROOT)}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("download", help="Pull Ensembl Compara paralogs via BioMart.", add_help=False)
    args, remainder = parser.parse_known_args(argv)
    if args.command == "download":
        download_main(remainder)


if __name__ == "__main__":
    main()
