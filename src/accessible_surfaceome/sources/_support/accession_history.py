"""UniProt accession-history reference: download + parse.

Two subcommands::

    python -m accessible_surfaceome.sources._support.accession_history download
    # (no build subcommand — this module is consumed as a parser library)

The downloader fetches the canonical UniProt accession-history artifacts:

- ``sec_ac.txt``    — secondary → primary accession map
- ``delac_sp.txt``  — deleted Swiss-Prot accessions
- ``delac_tr.txt.gz`` — deleted TrEMBL accessions (optional; ~630 MB)

The ``parse_*`` / ``load_accession_history`` functions below are used by
the merge orchestrator and the audit module to reconcile per-source
accessions against the current primaries.
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

from accessible_surfaceome.paths import REPO_ROOT as ROOT
from accessible_surfaceome.sources._support.traceability import (
    build_file_record,
    download_binary,
    write_manifest,
)

# UniProt accession regex (Swiss-Prot + TrEMBL long-form).
# https://www.uniprot.org/help/accession_numbers
UNIPROT_ACCESSION_RE = re.compile(
    r"^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]"
    r"|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})$"
)


def parse_sec_ac(path: Path) -> dict[str, list[str]]:
    """Parse ``sec_ac.txt`` into ``{secondary_accession: [primary, ...]}``.

    sec_ac.txt structure: header block, then a table under column headers
    ``Secondary AC / Primary AC`` separated from data by a line of
    underscores. Each data line has one secondary and one primary
    accession; the same secondary can appear on multiple lines if the
    original entry was later split into several current primaries.
    """
    mapping: dict[str, list[str]] = defaultdict(list)
    in_data = False
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not in_data:
                if line.startswith("_" * 4):
                    in_data = True
                continue
            parts = line.split()
            if len(parts) != 2:
                continue
            sec, prim = parts
            if not (
                UNIPROT_ACCESSION_RE.match(sec)
                and UNIPROT_ACCESSION_RE.match(prim)
            ):
                continue
            mapping[sec].append(prim)
    return dict(mapping)


def parse_delac_sp(path: Path) -> set[str]:
    """Parse ``delac_sp.txt`` into a set of deleted Swiss-Prot accessions."""
    deleted: set[str] = set()
    in_data = False
    with path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not in_data:
                if line.startswith("_" * 4):
                    in_data = True
                continue
            if line.startswith("-" * 4):
                # Trailing license / footer block starts with dashes.
                break
            if not line:
                continue
            if UNIPROT_ACCESSION_RE.match(line):
                deleted.add(line)
    return deleted


def load_accession_history(history_dir: Path) -> tuple[dict[str, list[str]], set[str]]:
    """Load sec_ac + delac_sp from ``history_dir`` and return (sec_ac, delac_sp).

    Raises ``FileNotFoundError`` if either file is missing.
    """
    sec_ac_path = history_dir / "sec_ac.txt"
    delac_sp_path = history_dir / "delac_sp.txt"
    if not sec_ac_path.exists() or not delac_sp_path.exists():
        raise FileNotFoundError(
            f"Missing accession-history files under {history_dir}. Run "
            "`uv run python -m accessible_surfaceome.sources._support.accession_history download` first."
        )
    return parse_sec_ac(sec_ac_path), parse_delac_sp(delac_sp_path)


# ---- download ----

DOWNLOAD_DATASET = "uniprot_accession_history"
DOWNLOAD_BASE_URL = (
    "https://ftp.uniprot.org/pub/databases/uniprot/current_release/"
    "knowledgebase/complete/docs/"
)
DOWNLOAD_DEFAULT_DIR = ROOT / "data" / "external" / "uniprot_accession_history"
DOWNLOAD_DEFAULT_MANIFEST = (
    DOWNLOAD_DEFAULT_DIR / "uniprot_accession_history_download_traceability.json"
)

DOWNLOAD_FILES_SWISSPROT: list[tuple[str, str]] = [
    ("sec_ac.txt", "Secondary → primary accession map (Swiss-Prot + TrEMBL)."),
    ("delac_sp.txt", "Deleted Swiss-Prot accessions with reason/replacement."),
]
DOWNLOAD_FILE_TREMBL: tuple[str, str] = (
    "delac_tr.txt.gz",
    "Deleted TrEMBL accessions (large; rarely needed for curated sources).",
)


def _download_parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download UniProt accession-history reference files."
    )
    p.add_argument("--output-dir", type=Path, default=DOWNLOAD_DEFAULT_DIR)
    p.add_argument("--manifest", type=Path, default=DOWNLOAD_DEFAULT_MANIFEST)
    p.add_argument("--include-trembl", action="store_true",
                   help="Also fetch delac_tr.txt.gz (~630 MB).")
    p.add_argument("--force", action="store_true",
                   help="Re-download even if a file already exists.")
    return p.parse_args(argv)


def _download_fetch(url: str, out_path: Path, force: bool) -> tuple[str, dict[str, str]]:
    if out_path.exists() and not force:
        return "reused", {}
    data, headers = download_binary(url)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return "downloaded", headers


def download_main(argv: list[str] | None = None) -> None:
    args = _download_parse_args(argv)
    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    records = []
    files = list(DOWNLOAD_FILES_SWISSPROT)
    if args.include_trembl:
        files.append(DOWNLOAD_FILE_TREMBL)

    for filename, note in files:
        url = DOWNLOAD_BASE_URL + filename
        out_path = out_dir / filename
        status, headers = _download_fetch(url, out_path, args.force)
        print(
            f"{filename}: {status}  "
            f"({out_path.stat().st_size:,} bytes)"
        )
        records.append(
            build_file_record(
                repo_root=ROOT,
                file_path=out_path,
                source_url=url,
                dataset=DOWNLOAD_DATASET,
                status=status,
                response_headers=headers or None,
                note=note,
            )
        )

    manifest_path: Path = args.manifest
    write_manifest(
        manifest_path,
        dataset=DOWNLOAD_DATASET,
        script=Path(__file__).relative_to(ROOT).as_posix(),
        records=records,
        extras={
            "base_url": DOWNLOAD_BASE_URL,
            "include_trembl": bool(args.include_trembl),
        },
    )
    print(f"wrote {manifest_path.relative_to(ROOT)}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(
        "download",
        help="Fetch UniProt accession-history reference files.",
        add_help=False,
    )
    args, remainder = parser.parse_known_args(argv)
    if args.command == "download":
        download_main(remainder)


if __name__ == "__main__":
    main()
