#!/usr/bin/env python3
"""Cut a numbered data release (dry-run by default).

    uv run python scripts/release/cut_data_release.py --version 1.3.0              # plan
    uv run python scripts/release/cut_data_release.py --version 1.3.0 --execute    # cut + draft Zenodo
    uv run python scripts/release/cut_data_release.py --version 1.3.0 --resume --execute
    uv run python scripts/release/cut_data_release.py --set-doi 1.3.0 10.5281/zenodo.NNN

--execute: (1) refuses unless pyproject.toml says the same version,
(2) sweeps every gene, (3) writes the release + members (immutable),
(4) exports deep_dives_X.Y.Z.tar.gz from R2, (5) creates a DRAFT new
version of the Zenodo data record. Then YOU review + publish the draft on
Zenodo, run --set-doi with the version DOI, and create GitHub release vX.Y.Z.

Right after the pyproject-version check — including on a plain (non
``--execute``) dry-run — this does one read-only D1 lookup for whether
``version`` already exists as a release. Without ``--resume``, an
existing release refuses immediately, before the sweep ever runs: a
release's members are meant to be immutable, so re-cutting one is
always a mistake, not something to retry into. With ``--resume``, the
release must already exist AND not yet be published (its
``zenodo_version_doi`` must still be NULL) — sweep and create_release
are then skipped entirely and the run picks up at export + Zenodo
draft, for retrying a run that got through the (slow, expensive) sweep
and release cut but died on the R2 export or the Zenodo upload.

``--set-doi`` always writes D1 immediately, on every invocation — it
has no dry-run gate of its own, unlike the ``--version`` path above.

``--zenodo-api`` defaults to the production Zenodo API. A non-default
value is only accepted together with ``--resume`` — a sandbox rehearsal
must never be the thing that cuts a fresh *production* release row;
rehearse by first cutting for real (or resuming an existing release)
against production, then re-running with ``--resume --zenodo-api
https://sandbox.zenodo.org/api --zenodo-concept-recid <sandbox recid>``
to exercise the newversion/upload/metadata sequence risk-free before
ever trusting it against the real, publish-is-irreversible data record.
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
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from accessible_surfaceome.cloud import r2_client
from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.cloud.r2_client import R2Config
from accessible_surfaceome.cloud.record_history import releases as rel
from accessible_surfaceome.cloud.record_history.store import BUCKET
from accessible_surfaceome.cloud.record_history.zenodo import (
    DATA_CONCEPT_RECID,
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

# get_blob retry budget: transient R2/network blips only. A missing object
# (get_object returning None on a 404) is never retried — that's a real
# archive gap, not a transient failure, and export_release hard-fails on it.
_GET_BLOB_MAX_ATTEMPTS = 3


def pyproject_version() -> str:
    return tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]


def _retryable_r2_error(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


@retry(
    retry=retry_if_exception(_retryable_r2_error),
    stop=stop_after_attempt(_GET_BLOB_MAX_ATTEMPTS),
    wait=wait_exponential(multiplier=0.5, max=5),
    reraise=True,
)
def _get_object_with_retry(key: str, cfg: R2Config) -> bytes | None:
    return r2_client.get_object(key=key, cfg=cfg)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Release already exists and is unpublished: skip sweep + "
            "create_release, go straight to export + Zenodo draft."
        ),
    )
    ap.add_argument("--set-doi", nargs=2, metavar=("VERSION", "DOI"))
    ap.add_argument(
        "--out-dir", type=Path, default=ROOT / "data" / "external" / "zenodo"
    )
    ap.add_argument(
        "--zenodo-api",
        default=ZENODO_API,
        help=(
            "Zenodo API base. A non-default value requires --resume — see "
            "the module docstring for why."
        ),
    )
    ap.add_argument(
        "--zenodo-concept-recid",
        default=DATA_CONCEPT_RECID,
        help="Zenodo concept-record id to draft a new version under.",
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
    if args.zenodo_api != ZENODO_API and not args.resume:
        raise SystemExit(
            "--zenodo-api requires --resume — a sandbox rehearsal must not be "
            "the thing that cuts a fresh production release row"
        )

    with D1Client.public() as d1:
        rows = d1.query(
            "SELECT zenodo_version_doi FROM data_release WHERE version = ?", [version]
        )
    release_exists = bool(rows)
    existing_doi = rows[0]["zenodo_version_doi"] if rows else None

    if args.resume:
        if not release_exists:
            raise SystemExit(f"--resume requires release {version} to already exist")
        if existing_doi is not None:
            raise SystemExit(
                f"release {version} is already published (DOI {existing_doi}) "
                "— refusing --resume"
            )
    elif release_exists:
        raise SystemExit(
            f"release {version} already exists — its members are immutable; "
            "pass --resume to continue export + Zenodo draft, or bump the version"
        )

    if not args.execute:
        if args.resume:
            print(
                f"[dry-run] would export release {version} and draft a Zenodo version."
            )
        else:
            print(
                f"[dry-run] would sweep, cut release {version}, export, and draft a Zenodo version."
            )
        return

    if not args.resume:
        counts = sweep(None, execute=True, workers=8)
        if counts["failed"]:
            raise SystemExit(
                f"sweep had {counts['failed']} failures — fix and re-run before cutting"
            )

    with D1Client.public() as d1:
        if not args.resume:
            members = rel.latest_members(d1)
            rel.create_release(
                d1,
                version=version,
                cut_at=datetime.now(UTC)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z"),
                github_tag=f"v{version}",
                zenodo_version_doi=None,
                notes=None,
                members=members,
            )
            print(f"release {version}: {len(members)} genes")
            purge_paths(["/v1/releases", f"/v1/releases/{version}"])
        r2cfg = dataclasses.replace(R2Config.from_env(), bucket=BUCKET)

        def get_blob(key: str) -> bytes:
            data = _get_object_with_retry(key, r2cfg)
            if data is None:
                raise SystemExit(f"archived object missing: {key}")
            return data

        args.out_dir.mkdir(parents=True, exist_ok=True)
        tarball = rel.export_release(d1, version, args.out_dir, get_blob=get_blob)
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
                concept_recid=args.zenodo_concept_recid,
            )
        except ZenodoDraftError as exc:
            # The release rows + export above are already committed and are
            # not touched here — only the Zenodo draft step failed, and it
            # needs a human in the Zenodo UI, not a retry of this script.
            print(str(exc))
            raise SystemExit(1) from exc
        except httpx.HTTPStatusError as exc:
            print(f"{exc} — re-run cut_data_release.py with --resume")
            raise SystemExit(1) from exc
    print(
        f"Zenodo DRAFT: {url}\nReview + publish it, then: --set-doi {version} <version DOI>"
    )


if __name__ == "__main__":
    main()
