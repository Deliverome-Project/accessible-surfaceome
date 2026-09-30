"""Draft a new version of the Zenodo data record for a numbered release.

Deliberately stops at a DRAFT: publishing a Zenodo version is
irreversible, so a human reviews the draft (files, README, metadata) and
clicks Publish, then records the DOI with
``cut_data_release.py --set-doi``.

``publication_date`` is set below to today's date, but that's the DRAFT's
creation date — a draft can sit for a while before a human actually
clicks Publish, so re-check (and if needed bump) ``publication_date`` in
the Zenodo UI at publish time rather than trusting the value this
function wrote.

Before ever pointing this at the real ``10.5281/zenodo.20805383`` concept
record, run the whole flow once against Zenodo's sandbox
(``api="https://sandbox.zenodo.org/api"``, a sandbox access token, and
the sandbox's own concept record id) to confirm the
newversion/upload/metadata sequence behaves as expected — a real Zenodo
version, once published, can never be un-published.
"""

from __future__ import annotations

import gzip
import io
import tarfile
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import httpx

ZENODO_API = "https://zenodo.org/api"
DATA_CONCEPT_RECID = "20805383"  # concept DOI 10.5281/zenodo.20805383
# Reproducibility replicates (Supplementary Figure 15). Not published records —
# a frozen study bundle, deposited alongside every release from the one it
# first ships in (a new version inherits the file; re-uploading an unchanged
# bundle is byte-identical because the tarball is built deterministically).
REPLICATES_TARBALL_NAME = "deep-dive-reproducibility-replicates-v1.tar.gz"


def build_replicates_tarball(bundle: Path, out_dir: Path) -> Path:
    """Tar ``bundle`` (the frozen replicate study) deterministically: sorted
    members, zeroed mtime / owner, gzip mtime 0 — same bytes on every run."""
    files = sorted(p for p in bundle.iterdir() if p.is_file())
    for p in files:
        if p.read_bytes()[:40].startswith(b"version https://git-lfs"):
            raise RuntimeError(f"{p.name} is an LFS pointer — run `git lfs pull` first")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for p in files:
            data = p.read_bytes()
            info = tarfile.TarInfo(f"{REPLICATES_TARBALL_NAME.removesuffix('.tar.gz')}/{p.name}")
            info.size, info.mtime, info.mode = len(data), 0, 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(data))
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / REPLICATES_TARBALL_NAME
    with out.open("wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
        gz.write(buf.getvalue())
    return out


class ZenodoDraftError(RuntimeError):
    """The draft could not be created or located — needs a human in the Zenodo UI."""


def create_draft_version(
    *,
    token: str,
    tarball: Path,
    version: str,
    http: httpx.Client,
    api: str = ZENODO_API,
    concept_recid: str = DATA_CONCEPT_RECID,
    extra_files: Sequence[Path] = (),
) -> str:
    """Create the draft; return its web URL for review.

    ``extra_files`` are uploaded alongside the tarball, each replacing an
    inherited file of the same name (e.g. the reproducibility-replicate
    bundle); every other inherited file is kept.

    ``concept_recid`` defaults to the real data record's concept id; pass
    a sandbox concept record id together with ``api="https://sandbox.
    zenodo.org/api"`` to rehearse this against sandbox instead.
    """
    # House pattern (matches scripts/release/publish-archive.py): the
    # token travels as an ``Authorization: Bearer`` header, never as an
    # ``access_token`` query param — a query param lands the secret in
    # server/proxy access logs and browser history.
    auth_header = {"Authorization": f"Bearer {token}"}

    # No auth at all on this call: it reads the public records API, which
    # needs none.
    latest = http.get(
        f"{api}/records/{concept_recid}/versions/latest", follow_redirects=True
    )
    latest.raise_for_status()
    latest_id = latest.json()["id"]

    nv = http.post(
        f"{api}/deposit/depositions/{latest_id}/actions/newversion",
        headers=auth_header,
    )
    if nv.status_code == 400:
        raise ZenodoDraftError(
            "Zenodo refused to start a new version (HTTP 400) — this usually "
            "means an unpublished draft already exists for this record. "
            "Publish or discard the existing draft in the Zenodo web UI, "
            "then re-run cut_data_release.py with --resume."
        )
    nv.raise_for_status()
    draft_url = nv.json().get("links", {}).get("latest_draft")
    if not draft_url:
        raise ZenodoDraftError(
            "Zenodo's newversion response had no links.latest_draft — this "
            "usually means an unpublished draft already exists for this "
            "record. Publish or discard the existing draft in the Zenodo "
            "web UI, then re-run cut_data_release.py with --resume."
        )
    draft = http.get(draft_url, headers=auth_header)
    draft.raise_for_status()
    d = draft.json()

    # The new version inherits the previous version's files; replace only
    # the deep-dive tarball. Triage TSVs + README carry over (refresh them
    # by hand in the draft if they changed).
    extra_names = {p.name for p in extra_files}
    for f in d.get("files", []):
        if f["filename"].startswith("deep_dives") or f["filename"] in extra_names:
            http.delete(f["links"]["self"], headers=auth_header).raise_for_status()
    for path in (tarball, *extra_files):
        with path.open("rb") as fh:
            http.put(
                f"{d['links']['bucket']}/{path.name}",
                headers=auth_header,
                content=fh.read(),
                timeout=900,  # the deep-dive tarball is a large upload
            ).raise_for_status()

    meta = dict(d["metadata"])
    # These are server-assigned per-version identifiers on the PREVIOUS
    # version's metadata; echoing them back on the new version's PUT would
    # try to reuse an already-minted DOI instead of letting Zenodo mint a
    # fresh one for this version.
    meta.pop("doi", None)
    meta.pop("prereserve_doi", None)
    meta["version"] = version
    meta["publication_date"] = date.today().isoformat()
    http.put(
        d["links"]["self"], headers=auth_header, json={"metadata": meta}
    ).raise_for_status()
    return d["links"]["html"]
