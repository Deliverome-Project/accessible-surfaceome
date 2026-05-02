"""Fetch human surface-proteome candidates from the UniProt REST API.

Pulls all reviewed Homo sapiens entries whose subcellular location or topology
feature places them at the plasma membrane / cell surface, and caches the full
JSON (preserving evidence codes and feature locations) plus a flat TSV summary
for downstream candidate-universe assembly (M1 of the surface-proteome
annotation plan in docs/plans/2026-04-16-surface-proteome-annotation.md).

The plan's draft query used ``cc_scl_term_exact`` which is not a valid UniProt
query field (HTTP 400 from the live API). The correct field is ``cc_scl_term``;
``cc_scl_term_exp`` (and its ``ft_*_exp`` siblings) is the experimental-
evidence-gated variant and is available via ``--query-mode exp``.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from surface_proteome.candidates.traceability import (
    build_file_record,
    utc_now_iso,
    write_manifest,
)

ROOT = Path(__file__).resolve().parents[3]

DATASET = "uniprot_human_surface_candidates"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "external" / DATASET
UNIPROT_SEARCH_URL = "https://rest.uniprot.org/uniprotkb/search"
USER_AGENT = "deliverome/0.1 (michael.smallegan@gmail.com)"
RETRYABLE_HTTP_CODES = {408, 409, 425, 429, 500, 502, 503, 504}

SURFACE_TERMS = [
    "Cell membrane",
    "Cell surface",
    "Apical cell membrane",
    "Basolateral cell membrane",
    "GPI-anchor",
]

RETURN_FIELDS = [
    "accession",
    "id",
    "protein_name",
    "gene_primary",
    "gene_names",
    "organism_id",
    "reviewed",
    "length",
    "protein_existence",
    "cc_subcellular_location",
    "ft_topo_dom",
    "ft_transmem",
    "ft_signal",
    "ft_lipid",
    "ft_carbohyd",
    "keyword",
    "xref_hgnc",
    "xref_ensembl",
    "xref_pdb",
]

LINK_NEXT_RE = re.compile(r'<(?P<url>[^>]+)>\s*;\s*rel="next"')


def build_query(mode: str) -> str:
    """Compose the union query for surface / plasma-membrane candidates.

    ``mode="any"``: any evidence — matches the plan's ~4.8k candidate pool.
    ``mode="exp"``: experimental evidence only (cc_scl_term_exp / ft_*_exp).
    """
    scl_field = "cc_scl_term_exp" if mode == "exp" else "cc_scl_term"
    topo_field = "ft_topo_dom_exp" if mode == "exp" else "ft_topo_dom"
    scl_clauses = [f'{scl_field}:"{term}"' for term in SURFACE_TERMS]
    scl_clauses.append(f"{topo_field}:Extracellular")
    return (
        "organism_id:9606 AND reviewed:true AND ("
        + " OR ".join(scl_clauses)
        + ")"
    )


def fetch_with_retries(
    url: str,
    *,
    timeout: int,
    retry_max_attempts: int,
    min_request_interval_ms: int,
) -> tuple[str, dict[str, str]]:
    """GET ``url`` returning (body_text, selected_response_headers).

    Retries transient failures (429 / 5xx / network) with a fixed backoff.
    """
    last_error: Exception | None = None
    for attempt in range(1, max(1, retry_max_attempts) + 1):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=timeout) as response:  # noqa: S310
                body = response.read().decode("utf-8", errors="replace")
                headers = {
                    "content_type": response.headers.get("Content-Type", ""),
                    "link": response.headers.get("Link", ""),
                    "x_total_results": response.headers.get("X-Total-Results", ""),
                    "x_uniprot_release": response.headers.get("X-UniProt-Release", ""),
                    "x_uniprot_release_date": response.headers.get("X-UniProt-Release-Date", ""),
                }
                return body, headers
        except HTTPError as exc:
            err_body = ""
            try:
                err_body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                err_body = ""
            if exc.code not in RETRYABLE_HTTP_CODES or attempt == retry_max_attempts:
                raise RuntimeError(f"HTTP {exc.code} for {url}; body={err_body[:300]}") from exc
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


def next_link(link_header: str) -> str | None:
    """Extract ``rel="next"`` URL from an RFC-5988 ``Link`` header, if any."""
    if not link_header:
        return None
    match = LINK_NEXT_RE.search(link_header)
    return match.group("url") if match else None


def iter_pages(
    query: str,
    *,
    page_size: int,
    timeout: int,
    retry_max_attempts: int,
    min_request_interval_ms: int,
    limit: int = 0,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Walk cursor pagination and accumulate all result entries.

    Returns (all_results, first_page_headers). The first-page headers carry
    ``X-Total-Results`` and the UniProt release tag — stored in the manifest.
    """
    params = [
        ("query", query),
        ("format", "json"),
        ("fields", ",".join(RETURN_FIELDS)),
        ("size", str(page_size)),
    ]
    url = f"{UNIPROT_SEARCH_URL}?{urlencode(params, quote_via=quote)}"
    first_headers: dict[str, str] | None = None
    all_results: list[dict[str, Any]] = []
    page_idx = 0
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
        url = next_link(headers.get("link", ""))
    return all_results, first_headers or {}


def _first_scalar(value: Any) -> str:
    """Flatten simple nested UniProt JSON value to a single string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("value", "fullName", "name", "id"):
            if key in value and isinstance(value[key], (str, dict)):
                return _first_scalar(value[key])
        return ""
    if isinstance(value, list):
        return "; ".join(v for v in (_first_scalar(x) for x in value) if v)
    return str(value)


def _protein_name(entry: dict[str, Any]) -> str:
    names = entry.get("proteinDescription") or {}
    recommended = names.get("recommendedName") or {}
    full = recommended.get("fullName") or {}
    return full.get("value", "") if isinstance(full, dict) else str(full)


def _subcell_locations(entry: dict[str, Any]) -> tuple[str, str]:
    """Return (pipe-joined location terms, pipe-joined ECO codes)."""
    terms: list[str] = []
    eco: list[str] = []
    for comment in entry.get("comments", []) or []:
        if comment.get("commentType") != "SUBCELLULAR LOCATION":
            continue
        for loc in comment.get("subcellularLocations", []) or []:
            location = loc.get("location") or {}
            value = location.get("value")
            if value:
                terms.append(value)
            for ev in location.get("evidences", []) or []:
                code = ev.get("evidenceCode")
                if code:
                    eco.append(code)
    return "|".join(terms), "|".join(sorted(set(eco)))


def _feature_counts(entry: dict[str, Any]) -> dict[str, int]:
    counts = {"transmembrane": 0, "signal": 0, "topo_extracellular": 0, "lipid": 0, "glycosylation": 0}
    for feat in entry.get("features", []) or []:
        ftype = feat.get("type", "")
        if ftype == "Transmembrane":
            counts["transmembrane"] += 1
        elif ftype == "Signal":
            counts["signal"] += 1
        elif ftype == "Topological domain" and feat.get("description", "").lower() == "extracellular":
            counts["topo_extracellular"] += 1
        elif ftype == "Lipidation":
            counts["lipid"] += 1
        elif ftype in ("Glycosylation", "Carbohydrate"):
            counts["glycosylation"] += 1
    return counts


def _xrefs(entry: dict[str, Any], db: str) -> str:
    ids = []
    for x in entry.get("uniProtKBCrossReferences", []) or []:
        if x.get("database") == db:
            xid = x.get("id")
            if xid:
                ids.append(xid)
    return "|".join(sorted(set(ids)))


def write_jsonl_gz(entries: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry, separators=(",", ":"), sort_keys=True))
            fh.write("\n")


def write_tsv_summary(entries: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "accession",
        "entry_name",
        "protein_name",
        "gene_primary",
        "gene_names",
        "organism_id",
        "length",
        "protein_existence",
        "subcellular_locations",
        "subcellular_eco_codes",
        "feature_transmembrane_count",
        "feature_signal_count",
        "feature_topo_extracellular_count",
        "feature_lipidation_count",
        "feature_glycosylation_count",
        "hgnc_ids",
        "ensembl_xrefs",
        "pdb_ids",
        "keywords",
    ]
    with path.open("w", encoding="utf-8") as fh:
        fh.write("\t".join(columns) + "\n")
        for entry in entries:
            locs, eco = _subcell_locations(entry)
            feats = _feature_counts(entry)
            organism = (entry.get("organism") or {}).get("taxonId", "")
            gene_rows = entry.get("genes") or []
            gene_primary = ""
            gene_names_all: list[str] = []
            for g in gene_rows:
                gn = (g.get("geneName") or {}).get("value", "")
                if gn and not gene_primary:
                    gene_primary = gn
                if gn:
                    gene_names_all.append(gn)
                for syn in g.get("synonyms", []) or []:
                    val = syn.get("value")
                    if val:
                        gene_names_all.append(val)
            keywords = "|".join(
                k.get("name", "") for k in (entry.get("keywords") or []) if k.get("name")
            )
            existence = entry.get("proteinExistence", "")
            values = [
                entry.get("primaryAccession", ""),
                entry.get("uniProtkbId", ""),
                _protein_name(entry),
                gene_primary,
                " ".join(dict.fromkeys(gene_names_all)),
                str(organism),
                str(entry.get("sequence", {}).get("length", "")),
                existence,
                locs,
                eco,
                str(feats["transmembrane"]),
                str(feats["signal"]),
                str(feats["topo_extracellular"]),
                str(feats["lipid"]),
                str(feats["glycosylation"]),
                _xrefs(entry, "HGNC"),
                _xrefs(entry, "Ensembl"),
                _xrefs(entry, "PDB"),
                keywords,
            ]
            fh.write("\t".join(v.replace("\t", " ").replace("\n", " ") for v in values) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--query-mode",
        choices=["any", "exp"],
        default="any",
        help="any = all evidence (plan default); exp = experimental-evidence-only fields",
    )
    parser.add_argument("--page-size", type=int, default=500)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--retry-max-attempts", type=int, default=5)
    parser.add_argument("--min-request-interval-ms", type=int, default=300)
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Stop after this many results (0 = no cap). Useful for smoke tests.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print query + total-results header and exit without writing.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    query = build_query(args.query_mode)
    print(f"query_mode={args.query_mode}")
    print(f"query={query}")

    if args.dry_run:
        params = [
            ("query", query),
            ("format", "json"),
            ("fields", ",".join(RETURN_FIELDS)),
            ("size", "0"),
        ]
        url = f"{UNIPROT_SEARCH_URL}?{urlencode(params, quote_via=quote)}"
        _, headers = fetch_with_retries(
            url,
            timeout=args.timeout,
            retry_max_attempts=args.retry_max_attempts,
            min_request_interval_ms=args.min_request_interval_ms,
        )
        print(f"x-total-results: {headers.get('x_total_results')}")
        print(f"uniprot-release: {headers.get('x_uniprot_release')} ({headers.get('x_uniprot_release_date')})")
        return

    started_at = utc_now_iso()
    results, first_headers = iter_pages(
        query,
        page_size=args.page_size,
        timeout=args.timeout,
        retry_max_attempts=args.retry_max_attempts,
        min_request_interval_ms=args.min_request_interval_ms,
        limit=args.limit,
    )

    total_header = first_headers.get("x_total_results")
    print(
        f"fetched {len(results)} entries (server total: {total_header}); "
        f"release {first_headers.get('x_uniprot_release')} "
        f"({first_headers.get('x_uniprot_release_date')})"
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = args.output_dir / f"{DATASET}.jsonl.gz"
    tsv_path = args.output_dir / f"{DATASET}.tsv"
    manifest_path = args.output_dir / "download_traceability.json"

    write_jsonl_gz(results, jsonl_path)
    write_tsv_summary(results, tsv_path)

    records = [
        build_file_record(
            repo_root=ROOT,
            file_path=jsonl_path,
            source_url=UNIPROT_SEARCH_URL,
            dataset=DATASET,
            taxid="9606",
            species="Homo sapiens",
            status="downloaded",
            note="Full UniProt JSON entries (gzip-compacted JSONL).",
        ),
        build_file_record(
            repo_root=ROOT,
            file_path=tsv_path,
            source_url=UNIPROT_SEARCH_URL,
            dataset=DATASET,
            taxid="9606",
            species="Homo sapiens",
            status="derived",
            note="Flat TSV summary derived from the JSONL payload.",
        ),
    ]
    write_manifest(
        manifest_path,
        dataset=DATASET,
        script=Path(__file__).as_posix(),
        records=records,
        extras={
            "query_mode": args.query_mode,
            "query": query,
            "return_fields": RETURN_FIELDS,
            "page_size": args.page_size,
            "server_total_results": total_header,
            "uniprot_release": first_headers.get("x_uniprot_release", ""),
            "uniprot_release_date": first_headers.get("x_uniprot_release_date", ""),
            "fetch_started_at_utc": started_at,
            "fetch_finished_at_utc": utc_now_iso(),
            "n_entries_written": len(results),
        },
    )
    print(jsonl_path)
    print(tsv_path)
    print(manifest_path)


if __name__ == "__main__":
    main()
