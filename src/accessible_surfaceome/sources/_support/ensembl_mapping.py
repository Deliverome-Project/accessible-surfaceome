"""ENSG / ENSP → UniProt primary accession mapping: download + load.

Two surfaces:

- ``load_ensembl_mapping`` / ``map_to_uniprot``: lookup helpers used by
  ``accessible_surfaceome.sources.hpa`` (ENSG keys) and
  ``accessible_surfaceome.sources.compartments`` (ENSP keys). Lists (rather
  than scalars) handle the rare case where one Ensembl ID legitimately
  maps to multiple UniProt primaries (alternative-isoform UniProt entries
  pointing at the same Ensembl gene).
- ``download_main`` / CLI: fetch the cross-reference tables from UniProt
  for every reviewed human entry (~20,400 rows). Two output TSVs are
  emitted: ``ensg_to_uniprot.tsv`` and ``ensp_to_uniprot.tsv``.

The full-proteome coverage (rather than the surface-only query used by
``sources.uniprot``) matters: COMPARTMENTS annotates ENSPs that aren't in
the surface-candidate query output, so we must be able to map *any*
reviewed human ENSP to a UniProt primary to avoid silently dropping
evidence.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

import pandas as pd

from accessible_surfaceome.paths import REPO_ROOT as ROOT
from accessible_surfaceome.sources._support.traceability import (
    build_file_record,
    utc_now_iso,
    write_manifest,
)


def _load_pair_tsv(path: Path, id_col: str) -> dict[str, list[str]]:
    """Read a two-column mapping TSV into ``{ensembl_id: [uniprot_primary, ...]}``."""
    mapping: dict[str, list[str]] = defaultdict(list)
    if not path.exists():
        raise FileNotFoundError(
            f"Missing Ensembl xref mapping at {path}. Run "
            "`uv run python -m accessible_surfaceome.sources._support.ensembl_mapping download` first."
        )
    df = pd.read_csv(path, sep="\t", dtype=str, usecols=[id_col, "uniprot_accession"])
    for eid, acc in zip(df[id_col].fillna(""), df["uniprot_accession"].fillna("")):
        if not eid or not acc:
            continue
        lst = mapping[eid]
        if acc not in lst:
            lst.append(acc)
    return dict(mapping)


def load_ensembl_mapping(
    xref_dir: Path,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Load both mappings from ``xref_dir`` and return ``(ensg, ensp)``.

    Raises ``FileNotFoundError`` if either file is missing.
    """
    ensg_path = xref_dir / "ensg_to_uniprot.tsv"
    ensp_path = xref_dir / "ensp_to_uniprot.tsv"
    ensg_map = _load_pair_tsv(ensg_path, "ensembl_gene_id")
    ensp_map = _load_pair_tsv(ensp_path, "ensembl_protein_id")
    return ensg_map, ensp_map


def map_to_uniprot(
    ensembl_ids: pd.Series,
    mapping: dict[str, list[str]],
) -> tuple[pd.Series, pd.Series]:
    """Attach a list-of-primaries column to each Ensembl ID.

    Returns ``(primaries_list, n_primaries)`` — the first a Series of lists
    (empty when the ID is unmapped), the second a Series of ints for quick
    filtering on mapped/ambiguous rows. Caller is responsible for
    exploding and flagging ``split_mapping_ambiguous`` rows.
    """
    primaries = ensembl_ids.map(lambda e: list(mapping.get(str(e).strip(), [])))
    n_primaries = primaries.map(len)
    return primaries, n_primaries


# ---- download ----

DOWNLOAD_DATASET = "uniprot_ensembl_xrefs"
DOWNLOAD_DEFAULT_DIR = ROOT / "data" / "external" / DOWNLOAD_DATASET
UNIPROT_SEARCH_URL = "https://rest.uniprot.org/uniprotkb/search"
RETURN_FIELDS = ["accession", "id", "xref_ensembl"]
QUERY = "organism_id:9606 AND reviewed:true"


def _strip_version(ensembl_id: str) -> str:
    """Drop the trailing ``.<N>`` Ensembl version suffix, if present.

    HPA and JensenLab COMPARTMENTS emit unversioned Ensembl IDs (e.g.
    ``ENSG00000000003``). UniProt's ``xref_ensembl`` payload carries
    versioned IDs (e.g. ``ENSG00000000003.17``). Strip so the mapping
    tables key on the unversioned form that downstream consumers use.
    """
    if not ensembl_id:
        return ensembl_id
    base = ensembl_id.split(".", 1)[0]
    return base


def _extract_ensembl_pairs(entry: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Return a list of ``(ensg, enst, ensp)`` triples for the entry.

    The UniProt xref_ensembl payload carries the ENST as ``id`` and
    ``properties`` with ``ProteinId`` (ENSP) and ``GeneId`` (ENSG). All
    three can be missing independently (rare). Version suffixes are
    stripped so the table keys on the unversioned form.
    """
    triples: list[tuple[str, str, str]] = []
    for xref in entry.get("uniProtKBCrossReferences", []) or []:
        if xref.get("database") != "Ensembl":
            continue
        enst = _strip_version(str(xref.get("id") or ""))
        ensg = ""
        ensp = ""
        for prop in xref.get("properties", []) or []:
            key = prop.get("key") or ""
            value = prop.get("value") or ""
            if key == "ProteinId":
                ensp = _strip_version(str(value))
            elif key == "GeneId":
                ensg = _strip_version(str(value))
        triples.append((ensg, enst, ensp))
    return triples


def _iter_pages_full(
    *,
    page_size: int,
    timeout: int,
    retry_max_attempts: int,
    min_request_interval_ms: int,
    limit: int = 0,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Walk cursor pagination over the full reviewed human proteome."""
    import re

    # Imported lazily to avoid import cycles: sources.uniprot imports from
    # this module via the ensembl-xref helpers in some tests.
    from accessible_surfaceome.sources.uniprot import fetch_with_retries

    params = [
        ("query", QUERY),
        ("format", "json"),
        ("fields", ",".join(RETURN_FIELDS)),
        ("size", str(page_size)),
    ]
    url: str | None = f"{UNIPROT_SEARCH_URL}?{urlencode(params, quote_via=quote)}"
    all_results: list[dict[str, Any]] = []
    first_headers: dict[str, str] | None = None
    page_idx = 0
    link_next_re = re.compile(r'<(?P<url>[^>]+)>\s*;\s*rel="next"')
    while url:
        body, headers = fetch_with_retries(
            url,
            timeout=timeout,
            retry_max_attempts=retry_max_attempts,
            min_request_interval_ms=min_request_interval_ms,
        )
        if first_headers is None:
            first_headers = headers
        payload = json.loads(body)
        batch = payload.get("results", []) or []
        all_results.extend(batch)
        page_idx += 1
        total = first_headers.get("x_total_results", "?")
        print(
            f"  page {page_idx:>3}: +{len(batch):>4} rows "
            f"(running total: {len(all_results):>5} / {total})",
            flush=True,
        )
        if limit and len(all_results) >= limit:
            all_results = all_results[:limit]
            break
        link_header = headers.get("link", "")
        match = link_next_re.search(link_header) if link_header else None
        url = match.group("url") if match else None
    return all_results, first_headers or {}


def _write_pair_tsv(
    path: Path,
    *,
    id_col: str,
    pairs: list[tuple[str, str, str]],
) -> int:
    """Write (ensembl_id, uniprot_accession, uniprot_entry_name) to TSV.

    ``pairs`` holds 3-tuples; the first element is the Ensembl identifier
    we want to emit (ENSG or ENSP). Empty identifiers are skipped. The
    same pair may be listed more than once across entries — deduplicated
    here.
    """
    seen: set[tuple[str, str, str]] = set()
    deduped: list[tuple[str, str, str]] = []
    for triple in pairs:
        ensembl_id, accession, entry_name = triple
        if not ensembl_id or not accession:
            continue
        if triple in seen:
            continue
        seen.add(triple)
        deduped.append(triple)
    deduped.sort()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"{id_col}\tuniprot_accession\tuniprot_entry_name\n")
        for ensembl_id, accession, entry_name in deduped:
            fh.write(f"{ensembl_id}\t{accession}\t{entry_name}\n")
    return len(deduped)


def _download_parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download UniProt ENSG/ENSP cross-references for reviewed human entries."
    )
    p.add_argument("--output-dir", type=Path, default=DOWNLOAD_DEFAULT_DIR)
    p.add_argument("--page-size", type=int, default=500)
    p.add_argument("--timeout", type=int, default=180)
    p.add_argument("--retry-max-attempts", type=int, default=5)
    p.add_argument("--min-request-interval-ms", type=int, default=300)
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Stop after this many entries (0 = no cap). Useful for smoke tests.",
    )
    return p.parse_args(argv)


def download_main(argv: list[str] | None = None) -> None:
    args = _download_parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"query={QUERY}")
    started_at = utc_now_iso()
    results, first_headers = _iter_pages_full(
        page_size=args.page_size,
        timeout=args.timeout,
        retry_max_attempts=args.retry_max_attempts,
        min_request_interval_ms=args.min_request_interval_ms,
        limit=args.limit,
    )
    total_header = first_headers.get("x_total_results")
    release = first_headers.get("x_uniprot_release", "")
    release_date = first_headers.get("x_uniprot_release_date", "")
    print(
        f"fetched {len(results)} entries (server total: {total_header}); "
        f"release {release} ({release_date})"
    )

    ensg_rows: list[tuple[str, str, str]] = []
    ensp_rows: list[tuple[str, str, str]] = []
    for entry in results:
        accession = entry.get("primaryAccession", "")
        entry_name = entry.get("uniProtkbId", "")
        if not accession:
            continue
        for ensg, _enst, ensp in _extract_ensembl_pairs(entry):
            if ensg:
                ensg_rows.append((ensg, accession, entry_name))
            if ensp:
                ensp_rows.append((ensp, accession, entry_name))

    ensg_path = args.output_dir / "ensg_to_uniprot.tsv"
    ensp_path = args.output_dir / "ensp_to_uniprot.tsv"
    n_ensg = _write_pair_tsv(ensg_path, id_col="ensembl_gene_id", pairs=ensg_rows)
    n_ensp = _write_pair_tsv(ensp_path, id_col="ensembl_protein_id", pairs=ensp_rows)
    print(f"wrote {ensg_path.relative_to(ROOT)}  ({n_ensg:,} ENSG pairs)")
    print(f"wrote {ensp_path.relative_to(ROOT)}  ({n_ensp:,} ENSP pairs)")

    records = [
        build_file_record(
            repo_root=ROOT,
            file_path=ensg_path,
            source_url=UNIPROT_SEARCH_URL,
            dataset=DOWNLOAD_DATASET,
            taxid="9606",
            species="Homo sapiens",
            status="derived",
            note="Deduplicated (ENSG, UniProt primary, UniProt entry name).",
        ),
        build_file_record(
            repo_root=ROOT,
            file_path=ensp_path,
            source_url=UNIPROT_SEARCH_URL,
            dataset=DOWNLOAD_DATASET,
            taxid="9606",
            species="Homo sapiens",
            status="derived",
            note="Deduplicated (ENSP, UniProt primary, UniProt entry name).",
        ),
    ]
    manifest_path = args.output_dir / "download_traceability.json"
    write_manifest(
        manifest_path,
        dataset=DOWNLOAD_DATASET,
        script=Path(__file__).relative_to(ROOT).as_posix(),
        records=records,
        extras={
            "query": QUERY,
            "return_fields": RETURN_FIELDS,
            "page_size": args.page_size,
            "server_total_results": total_header,
            "uniprot_release": release,
            "uniprot_release_date": release_date,
            "fetch_started_at_utc": started_at,
            "fetch_finished_at_utc": utc_now_iso(),
            "n_entries_fetched": len(results),
            "n_ensg_pairs": n_ensg,
            "n_ensp_pairs": n_ensp,
        },
    )
    print(f"wrote {manifest_path.relative_to(ROOT)}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(
        "download",
        help="Fetch UniProt ENSG/ENSP cross-references for reviewed human entries.",
        add_help=False,
    )
    args, remainder = parser.parse_known_args(argv)
    if args.command == "download":
        download_main(remainder)


if __name__ == "__main__":
    main()
