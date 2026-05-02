"""Download UniProt accession-history reference files with traceability.

Fetches the three canonical UniProt accession-history artifacts:

- ``sec_ac.txt``    — secondary → primary accession mapping
- ``delac_sp.txt``  — deleted Swiss-Prot accessions (with reason/replacement)
- ``delac_tr.txt.gz`` — deleted TrEMBL accessions (optional; very large)

These files let downstream code detect the two main failure modes that can
arise from merging UniProt-keyed snapshots taken at different times:

1. An old snapshot (for example SURFY 2018, CSPA 2015) uses an accession
   that UniProt has since merged into another entry — the old accession is
   now a *secondary* and current sources use the new *primary*.
2. An old snapshot uses an accession that UniProt has since deleted
   entirely (entry merged into a related gene or removed).

Default behavior fetches ``sec_ac.txt`` and ``delac_sp.txt`` only (Swiss-Prot
coverage). Pass ``--include-trembl`` to also fetch the much larger
``delac_tr.txt.gz`` (~630 MB gzipped) — almost never needed for our
curated-UniProt-keyed sources, but included for completeness.

Emits ``uniprot_accession_history_download_traceability.json`` with SHA256
and size for every downloaded file.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from surface_proteome.candidates.traceability import (
    build_file_record,
    download_binary,
    write_manifest,
)

from surface_proteome.paths import REPO_ROOT as ROOT

DATASET = "uniprot_accession_history"
BASE_URL = (
    "https://ftp.uniprot.org/pub/databases/uniprot/current_release/"
    "knowledgebase/complete/docs/"
)
DEFAULT_OUTPUT_DIR = ROOT / "data" / "external" / "uniprot_accession_history"
DEFAULT_MANIFEST = DEFAULT_OUTPUT_DIR / "uniprot_accession_history_download_traceability.json"

FILES_SWISSPROT: list[tuple[str, str]] = [
    # (filename, note)
    ("sec_ac.txt", "Secondary → primary accession map (Swiss-Prot + TrEMBL)."),
    ("delac_sp.txt", "Deleted Swiss-Prot accessions with reason/replacement."),
]
FILE_TREMBL: tuple[str, str] = (
    "delac_tr.txt.gz",
    "Deleted TrEMBL accessions (large; rarely needed for curated sources).",
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p.add_argument(
        "--include-trembl",
        action="store_true",
        help="Also fetch delac_tr.txt.gz (~630 MB).",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if a file of matching size already exists.",
    )
    return p.parse_args()


def _fetch(url: str, out_path: Path, force: bool) -> tuple[str, dict[str, str]]:
    """Download ``url`` to ``out_path`` unless it already exists.

    Returns ``(status, response_headers)`` where ``status`` is one of
    ``downloaded`` / ``reused``.
    """
    if out_path.exists() and not force:
        return "reused", {}
    data, headers = download_binary(url)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return "downloaded", headers


def main() -> None:
    args = parse_args()
    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    records = []
    files = list(FILES_SWISSPROT)
    if args.include_trembl:
        files.append(FILE_TREMBL)

    for filename, note in files:
        url = BASE_URL + filename
        out_path = out_dir / filename
        status, headers = _fetch(url, out_path, args.force)
        print(
            f"{filename}: {status}  "
            f"({out_path.stat().st_size:,} bytes)"
        )
        records.append(
            build_file_record(
                repo_root=ROOT,
                file_path=out_path,
                source_url=url,
                dataset=DATASET,
                status=status,
                response_headers=headers or None,
                note=note,
            )
        )

    manifest_path: Path = args.manifest
    write_manifest(
        manifest_path,
        dataset=DATASET,
        script=Path(__file__).relative_to(ROOT).as_posix(),
        records=records,
        extras={
            "base_url": BASE_URL,
            "include_trembl": bool(args.include_trembl),
        },
    )
    print(f"wrote {manifest_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
