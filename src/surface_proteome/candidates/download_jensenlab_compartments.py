"""Download JensenLab COMPARTMENTS human TSVs with traceability.

Fetches five channel-specific TSVs from https://download.jensenlab.org/ for
the human taxonomy (9606):

- ``human_compartment_integrated_full.tsv``
- ``human_compartment_knowledge_full.tsv``
- ``human_compartment_experiments_full.tsv`` (human-only channel; includes
  rows where ``source == "HPA"`` — downstream code excludes those to avoid
  double-counting the first-class HPA source)
- ``human_compartment_textmining_full.tsv``  **filter-at-download**: the raw
  upstream is ~850 MB and dominated by non-surface GO terms, so this
  script streams the file and keeps only rows whose ``go_id`` is in the
  configured surface working set. Both the upstream ``content-length`` and
  the filtered-output SHA256 are recorded in the traceability manifest.
- ``human_compartment_predictions_full.tsv``

All files key on Ensembl protein ID (ENSP), carry the HGNC symbol as a
convenience column, and use integer ``stars`` ∈ [0, 5] (5 = highest
confidence). License: CC-BY-4.0. Reference: Binder et al., Database
(Oxford), 2014, DOI ``10.1093/database/bau012``.

Emits ``download_traceability.json`` with SHA256 / size for every file +
the filter predicate for the textmining output.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from surface_proteome.candidates.traceability import (  # noqa: E402
    USER_AGENT,
    build_file_record,
    download_binary,
    write_manifest,
)

DATASET = "jensenlab_compartments"
BASE_URL = "https://download.jensenlab.org/"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "external" / DATASET

# Surface-relevant GO cellular-component terms used to filter the
# 850 MB textmining TSV at download time. Mirror of the set in
# ``src/surface_proteome/candidates/build_jensenlab_compartments.py`` — keep in sync.
SURFACE_TERMS: set[str] = {
    "GO:0005886",  # plasma membrane
    "GO:0009986",  # cell surface
    "GO:0031225",  # anchored component of membrane
    "GO:0005887",  # integral component of plasma membrane
}

# (filename, filter-mode, note). filter-mode "none" saves the raw bytes;
# "surface_terms" streams line-by-line and keeps rows whose go_id
# (TSV column 3, 0-indexed 2) is in SURFACE_TERMS.
FILES: list[tuple[str, str, str]] = [
    ("human_compartment_integrated_full.tsv", "none",
     "Integrated score (0-5 stars) across all four channels per GO term."),
    ("human_compartment_knowledge_full.tsv", "none",
     "Knowledge channel: curated-literature + DB annotations (re-ingests GO / UniProt-SubCell)."),
    ("human_compartment_experiments_full.tsv", "none",
     "Experiments channel (human-only); includes HPA IF rows with source=='HPA'."),
    ("human_compartment_textmining_full.tsv", "surface_terms",
     "Textmining channel: filter-at-download to SURFACE_TERMS GO IDs."),
    ("human_compartment_predictions_full.tsv", "none",
     "Predictions channel: WoLF PSORT + YLoc-HighRes. Carried as "
     "provenance only — sequence-based predictors are redundant with "
     "SURFY + DeepTMHMM in the M1 merge."),
]


def _fetch_raw(url: str, out_path: Path, force: bool) -> tuple[str, dict[str, str]]:
    if out_path.exists() and not force:
        return "reused", {}
    data, headers = download_binary(url, timeout=600)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return "downloaded", headers


def _fetch_filtered(
    url: str,
    out_path: Path,
    *,
    surface_terms: set[str],
    force: bool,
) -> tuple[str, dict[str, str], int, int]:
    """Stream ``url``, write only rows whose go_id is in ``surface_terms``.

    Returns (status, response_headers, n_upstream_rows, n_kept_rows).
    The upstream ``Content-Length`` / ``ETag`` headers are recorded so a
    reviewer can tell whether the upstream file changed between runs.
    """
    if out_path.exists() and not force:
        return "reused", {}, 0, 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    kept = 0
    total = 0
    with urlopen(req, timeout=1800) as response:  # noqa: S310
        headers = {
            "content_type": response.headers.get("Content-Type", ""),
            "content_length_header": response.headers.get("Content-Length", ""),
            "etag": response.headers.get("ETag", ""),
            "last_modified": response.headers.get("Last-Modified", ""),
        }
        with out_path.open("wb") as dst:
            while True:
                line_bytes = response.readline()
                if not line_bytes:
                    break
                total += 1
                try:
                    line = line_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    line = line_bytes.decode("utf-8", errors="replace")
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 4:
                    continue
                go_id = parts[2]
                if go_id in surface_terms:
                    dst.write(line_bytes)
                    kept += 1
    return "downloaded", headers, total, kept


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--force", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    records = []
    filter_stats: dict[str, dict[str, int]] = {}
    for filename, mode, note in FILES:
        url = BASE_URL + filename
        out_path = out_dir / filename
        if mode == "surface_terms":
            status, headers, n_upstream, n_kept = _fetch_filtered(
                url, out_path,
                surface_terms=SURFACE_TERMS,
                force=args.force,
            )
            if status == "downloaded":
                print(
                    f"{filename}: {status}  kept {n_kept:,} / {n_upstream:,} rows "
                    f"(surface GO terms only)"
                )
                filter_stats[filename] = {
                    "n_upstream_rows": n_upstream,
                    "n_kept_rows": n_kept,
                }
            else:
                print(f"{filename}: {status}  ({out_path.stat().st_size:,} bytes)")
        else:
            status, headers = _fetch_raw(url, out_path, args.force)
            print(f"{filename}: {status}  ({out_path.stat().st_size:,} bytes)")
        record = build_file_record(
            repo_root=ROOT,
            file_path=out_path,
            source_url=url,
            dataset=DATASET,
            taxid="9606",
            species="Homo sapiens",
            status=status,
            response_headers=headers or None,
            note=note,
        )
        if filename in filter_stats:
            record["filter"] = {
                "mode": "surface_terms",
                "surface_terms": sorted(SURFACE_TERMS),
                "n_upstream_rows": filter_stats[filename]["n_upstream_rows"],
                "n_kept_rows": filter_stats[filename]["n_kept_rows"],
                "rule": "keep line iff TSV column 3 (go_id) is in surface_terms",
            }
        records.append(record)

    manifest_path = out_dir / "download_traceability.json"
    write_manifest(
        manifest_path,
        dataset=DATASET,
        script=Path(__file__).relative_to(ROOT).as_posix(),
        records=records,
        extras={
            "base_url": BASE_URL,
            "license": "CC-BY-4.0",
            "citation": "Binder et al., Database (Oxford), 2014, DOI: 10.1093/database/bau012",
            "star_scale": "integer 1-5; higher = more confident",
            "surface_terms": sorted(SURFACE_TERMS),
        },
    )
    print(f"wrote {manifest_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
