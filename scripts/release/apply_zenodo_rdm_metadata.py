"""Set creators, funders and licence on a Zenodo record through the InvenioRDM API.

The release tooling talks to Zenodo's legacy deposit API, which cannot read or
write funding. A metadata PUT through it can drop the funders a record already
carries. Run this as the last step before publishing a data-record draft, and
once on each new code record after its GitHub release (the GitHub integration
builds that record from ``.zenodo.json``, which has no funder field).

Creators come from ``.zenodo.json``; funders and licences from
``accessible_surfaceome.cloud.record_history.zenodo``.

    # a data-record draft (applies to the open draft; you still click Publish)
    uv run python scripts/release/apply_zenodo_rdm_metadata.py --record <id> --kind data
    # a published code record (opens an edit, applies it, republishes)
    uv run python scripts/release/apply_zenodo_rdm_metadata.py --record <id> --kind code --published --execute

Dry-run by default: prints the before/after summary and changes nothing.
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx

from accessible_surfaceome.cloud.record_history.zenodo import (
    CODE_LICENSE,
    DATA_LICENSE,
    FUNDERS,
    rdm_creators,
)
from accessible_surfaceome.env import load_env

API = "https://zenodo.org/api/records"


def summarize(m: dict) -> dict:
    return {
        "creators": [
            (
                f"{c['person_or_org'].get('family_name')}, {c['person_or_org'].get('given_name')}",
                [i["identifier"] for i in c["person_or_org"].get("identifiers", [])],
            )
            for c in m.get("creators", [])
        ],
        "rights": [r.get("id") or r.get("title") for r in m.get("rights", [])],
        "funding": [
            f["funder"].get("id") or f["funder"].get("name")
            for f in m.get("funding") or []
        ],
    }


def apply(m: dict, kind: str) -> dict:
    m = dict(m)
    m["creators"] = rdm_creators()
    m["funding"] = FUNDERS
    # A bare id: records made by the GitHub integration carry the licence as
    # id + free-text title, which the RDM API rejects on save.
    m["rights"] = [{"id": DATA_LICENSE if kind == "data" else CODE_LICENSE}]
    return m


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--record", required=True, help="Zenodo record / deposition id")
    ap.add_argument("--kind", required=True, choices=["data", "code"])
    ap.add_argument(
        "--published",
        action="store_true",
        help="the record is published: open an edit draft and republish it",
    )
    ap.add_argument("--execute", action="store_true", help="write (default: dry-run)")
    args = ap.parse_args()

    load_env()
    headers = {
        "Authorization": f"Bearer {os.environ['ZENODO_TOKEN']}",
        "User-Agent": "accessible-surfaceome release (becca@deliverome.org)",
        "Accept": "application/vnd.inveniordm.v1+json",
        "Content-Type": "application/json",
    }
    with httpx.Client(headers=headers, timeout=60) as c:
        url = f"{API}/{args.record}/draft"
        if args.published and args.execute:
            draft = c.post(url).raise_for_status().json()
        else:
            draft = c.get(url if not args.published else f"{API}/{args.record}")
            draft = draft.raise_for_status().json()
        new = apply(draft["metadata"], args.kind)
        print(f"before {summarize(draft['metadata'])}\nafter  {summarize(new)}")
        if not args.execute:
            print("dry-run: nothing written (--execute to apply)")
            return
        draft["metadata"] = new
        r = c.put(url, json=draft).raise_for_status().json()
        if r.get("errors"):
            sys.exit(f"Zenodo rejected the metadata: {r['errors']}")
        if args.published:
            c.post(f"{url}/actions/publish").raise_for_status()
            print(f"republished {args.record}")
        else:
            print(f"draft {args.record} updated — review it on Zenodo, then Publish")


if __name__ == "__main__":
    main()
