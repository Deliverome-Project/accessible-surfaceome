"""Download the Human Protein Atlas subcellular-location bulk file.

Fetches https://www.proteinatlas.org/download/tsv/subcellular_location.tsv.zip
(v25.0, ~250 KB zipped, 13,604 rows — one row per Ensembl gene).

Emits:
- ``subcellular_location.tsv.zip`` (raw, as downloaded)
- ``subcellular_location.tsv``     (extracted alongside for easier grep/audit;
  both are tracked via Git LFS per the repo ``.gitattributes`` rules)
- ``hpa_subcellular_location_download_traceability.json`` with SHA256 and size.

Licensing: CC-BY-SA-3.0. Downstream tables derived from this snapshot
inherit the share-alike obligation.
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from surface_proteome.candidates.traceability import (
    build_file_record,
    download_binary,
    write_manifest,
)

ROOT = Path(__file__).resolve().parents[3]

DATASET = "hpa_subcellular_location"
SOURCE_URL = (
    "https://www.proteinatlas.org/download/tsv/subcellular_location.tsv.zip"
)
DEFAULT_OUTPUT_DIR = ROOT / "data" / "external" / "hpa_subcellular_location"
ZIP_NAME = "subcellular_location.tsv.zip"
TSV_NAME = "subcellular_location.tsv"


def _fetch(url: str, out_path: Path, force: bool) -> tuple[str, dict[str, str]]:
    if out_path.exists() and not force:
        return "reused", {}
    data, headers = download_binary(url, timeout=300)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return "downloaded", headers


def _extract_zip(zip_path: Path, out_dir: Path) -> Path:
    """Extract the single TSV member of the zip to ``out_dir``."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = [n for n in zf.namelist() if n.endswith(".tsv")]
        if len(members) != 1:
            raise RuntimeError(
                f"Expected exactly one .tsv member in {zip_path}; got {members}"
            )
        member = members[0]
        target = out_dir / TSV_NAME
        with zf.open(member) as src, target.open("wb") as dst:
            dst.write(src.read())
        return target


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--force", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    zip_path = out_dir / ZIP_NAME
    status, headers = _fetch(SOURCE_URL, zip_path, args.force)
    print(f"{ZIP_NAME}: {status}  ({zip_path.stat().st_size:,} bytes)")

    tsv_path = _extract_zip(zip_path, out_dir)
    print(f"extracted {TSV_NAME}  ({tsv_path.stat().st_size:,} bytes)")

    records = [
        build_file_record(
            repo_root=ROOT,
            file_path=zip_path,
            source_url=SOURCE_URL,
            dataset=DATASET,
            taxid="9606",
            species="Homo sapiens",
            status=status,
            response_headers=headers or None,
            note="Raw HPA subcellular-location bulk file (CC-BY-SA-3.0).",
        ),
        build_file_record(
            repo_root=ROOT,
            file_path=tsv_path,
            source_url=SOURCE_URL,
            dataset=DATASET,
            taxid="9606",
            species="Homo sapiens",
            status="derived",
            note=f"Extracted from {ZIP_NAME} for direct downstream reads.",
        ),
    ]
    manifest_path = out_dir / "download_traceability.json"
    write_manifest(
        manifest_path,
        dataset=DATASET,
        script=Path(__file__).relative_to(ROOT).as_posix(),
        records=records,
        extras={
            "source_url": SOURCE_URL,
            "license": "CC-BY-SA-3.0",
        },
    )
    print(f"wrote {manifest_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
