"""Draft a new version of the Zenodo data record for a numbered release.

Deliberately stops at a DRAFT: publishing a Zenodo version is
irreversible, so a human reviews the draft (files, README, metadata) and
clicks Publish, then records the DOI with
``cut_data_release.py --set-doi``.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx

ZENODO_API = "https://zenodo.org/api"
DATA_CONCEPT_RECID = "20805383"  # concept DOI 10.5281/zenodo.20805383


def create_draft_version(
    *,
    token: str,
    tarball: Path,
    version: str,
    http: httpx.Client,
    api: str = ZENODO_API,
) -> str:
    """Create the draft; return its web URL for review."""
    auth = {"access_token": token}
    # No auth on this call: it reads the public records API, which needs
    # none — only the deposit-API calls below carry the token.
    latest = http.get(
        f"{api}/records/{DATA_CONCEPT_RECID}/versions/latest", follow_redirects=True
    )
    latest.raise_for_status()
    latest_id = latest.json()["id"]

    nv = http.post(
        f"{api}/deposit/depositions/{latest_id}/actions/newversion", params=auth
    )
    nv.raise_for_status()
    draft_url = nv.json()["links"]["latest_draft"]
    draft = http.get(draft_url, params=auth)
    draft.raise_for_status()
    d = draft.json()

    # The new version inherits the previous version's files; replace only
    # the deep-dive tarball. Triage TSVs + README carry over (refresh them
    # by hand in the draft if they changed).
    for f in d.get("files", []):
        if f["filename"].startswith("deep_dives"):
            http.delete(f["links"]["self"], params=auth).raise_for_status()
    with tarball.open("rb") as fh:
        http.put(
            f"{d['links']['bucket']}/{tarball.name}", params=auth, content=fh.read()
        ).raise_for_status()

    meta = dict(d["metadata"])
    meta["version"] = version
    meta["publication_date"] = date.today().isoformat()
    http.put(
        d["links"]["self"], params=auth, json={"metadata": meta}
    ).raise_for_status()
    return d["links"]["html"]
