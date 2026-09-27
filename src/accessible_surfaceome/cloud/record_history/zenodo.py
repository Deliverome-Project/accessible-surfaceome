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

from datetime import date
from pathlib import Path

import httpx

ZENODO_API = "https://zenodo.org/api"
DATA_CONCEPT_RECID = "20805383"  # concept DOI 10.5281/zenodo.20805383


class ZenodoDraftError(RuntimeError):
    """The draft could not be created or located — needs a human in the Zenodo UI."""


def create_draft_version(
    *,
    token: str,
    tarball: Path,
    version: str,
    http: httpx.Client,
    api: str = ZENODO_API,
) -> str:
    """Create the draft; return its web URL for review."""
    # House pattern (matches scripts/release/publish-archive.py): the
    # token travels as an ``Authorization: Bearer`` header, never as an
    # ``access_token`` query param — a query param lands the secret in
    # server/proxy access logs and browser history.
    auth_header = {"Authorization": f"Bearer {token}"}

    # No auth at all on this call: it reads the public records API, which
    # needs none.
    latest = http.get(
        f"{api}/records/{DATA_CONCEPT_RECID}/versions/latest", follow_redirects=True
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
            "then re-run."
        )
    nv.raise_for_status()
    draft_url = nv.json().get("links", {}).get("latest_draft")
    if not draft_url:
        raise ZenodoDraftError(
            "Zenodo's newversion response had no links.latest_draft — this "
            "usually means an unpublished draft already exists for this "
            "record. Publish or discard the existing draft in the Zenodo "
            "web UI, then re-run."
        )
    draft = http.get(draft_url, headers=auth_header)
    draft.raise_for_status()
    d = draft.json()

    # The new version inherits the previous version's files; replace only
    # the deep-dive tarball. Triage TSVs + README carry over (refresh them
    # by hand in the draft if they changed).
    for f in d.get("files", []):
        if f["filename"].startswith("deep_dives"):
            http.delete(f["links"]["self"], headers=auth_header).raise_for_status()
    with tarball.open("rb") as fh:
        http.put(
            f"{d['links']['bucket']}/{tarball.name}",
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
