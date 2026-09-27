#!/usr/bin/env python3
"""Cut a numbered data release (dry-run by default).

    uv run python scripts/release/cut_data_release.py --version 1.3.0              # plan
    uv run python scripts/release/cut_data_release.py --version 1.3.0 --execute    # cut + draft Zenodo
    uv run python scripts/release/cut_data_release.py --set-doi 1.3.0 10.5281/zenodo.NNN

--execute: (1) refuses unless pyproject.toml says the same version,
(2) sweeps every gene, (3) writes the release + members (immutable),
(4) exports deep_dives_X.Y.Z.tar.gz from R2, (5) creates a DRAFT new
version of the Zenodo data record. Then YOU review + publish the draft on
Zenodo, run --set-doi with the version DOI, and create GitHub release vX.Y.Z.

``--zenodo-api`` defaults to the production Zenodo API. Pass
``https://sandbox.zenodo.org/api`` (with a sandbox ``ZENODO_TOKEN`` and
the sandbox's own concept record wired into
``accessible_surfaceome.cloud.record_history.zenodo``) to rehearse the
newversion/upload/metadata sequence before ever pointing this at the real,
publish-is-irreversible data record.
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import re
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

import httpx

from accessible_surfaceome.cloud import r2_client
from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.cloud.r2_client import R2Config
from accessible_surfaceome.cloud.record_history import releases as rel
from accessible_surfaceome.cloud.record_history.store import BUCKET
from accessible_surfaceome.cloud.record_history.zenodo import (
    ZENODO_API,
    ZenodoDraftError,
    create_draft_version,
)
from accessible_surfaceome.cloud.surface_annotation import purge_paths
from accessible_surfaceome.env import load_env

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "cloud"))
from sweep_record_history import sweep  # noqa: E402

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def pyproject_version() -> str:
    return tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--set-doi", nargs=2, metavar=("VERSION", "DOI"))
    ap.add_argument(
        "--out-dir", type=Path, default=ROOT / "data" / "external" / "zenodo"
    )
    ap.add_argument(
        "--zenodo-api",
        default=ZENODO_API,
        help=(
            "Zenodo API base. Pass https://sandbox.zenodo.org/api to dry-run "
            "the draft-version flow against sandbox before targeting production."
        ),
    )
    args = ap.parse_args()
    load_env()

    if args.set_doi:
        version, doi = args.set_doi
        with D1Client.public() as d1:
            rel.set_zenodo_doi(d1, version, doi)
        purge_paths(["/v1/releases", f"/v1/releases/{version}"])
        print(f"release {version} → {doi}")
        return

    version = (args.version or "").removeprefix("v")
    if not VERSION_RE.match(version):
        raise SystemExit("--version must look like 1.3.0")
    if pyproject_version() != version:
        raise SystemExit(
            f"pyproject.toml says {pyproject_version()}, not {version} — bump it first"
        )
    if not args.execute:
        print(
            f"[dry-run] would sweep, cut release {version}, export, and draft a Zenodo version."
        )
        return

    counts = sweep(None, execute=True, workers=8)
    if counts["failed"]:
        raise SystemExit(
            f"sweep had {counts['failed']} failures — fix and re-run before cutting"
        )

    with D1Client.public() as d1:
        members = rel.latest_members(d1)
        rel.create_release(
            d1,
            version=version,
            cut_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            github_tag=f"v{version}",
            zenodo_version_doi=None,
            notes=None,
            members=members,
        )
        print(f"release {version}: {len(members)} genes")
        purge_paths(["/v1/releases", f"/v1/releases/{version}"])
        r2cfg = dataclasses.replace(R2Config.from_env(), bucket=BUCKET)

        def get_blob(key: str) -> bytes:
            data = r2_client.get_object(key=key, cfg=r2cfg)
            if data is None:
                raise SystemExit(f"archived object missing: {key}")
            return data

        args.out_dir.mkdir(parents=True, exist_ok=True)
        tarball = rel.export_release(d1, version, args.out_dir, get_blob=get_blob)
    purge_paths(["/v1/releases"])
    print(f"exported {tarball}")

    token = os.environ.get("ZENODO_TOKEN", "").strip()
    if not token:
        print("ZENODO_TOKEN unset — upload the tarball as a new version by hand.")
        return
    with httpx.Client(timeout=900) as http:
        try:
            url = create_draft_version(
                token=token,
                tarball=tarball,
                version=version,
                http=http,
                api=args.zenodo_api,
            )
        except ZenodoDraftError as exc:
            # The release rows + export above are already committed and are
            # not touched here — only the Zenodo draft step failed, and it
            # needs a human in the Zenodo UI, not a retry of this script.
            print(str(exc))
            raise SystemExit(1) from exc
    print(
        f"Zenodo DRAFT: {url}\nReview + publish it, then: --set-doi {version} <version DOI>"
    )


if __name__ == "__main__":
    main()
