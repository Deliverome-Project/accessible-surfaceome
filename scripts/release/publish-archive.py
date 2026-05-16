#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27"]
# ///
"""Publish accessible-surfaceome to Software Heritage + Zenodo.

A manual, run-when-ready release ritual. Each invocation:

  1. Submits this repo to Software Heritage Save Code Now (free,
     durable, content-addressed; gives you a snapshot SWHID).
  2. Submits each per-figure gist to Software Heritage (one SWHID per
     figure, all populated from FIGURE_PROVENANCE in
     scripts/embed_figure_gist_metadata.py).
  3. Polls SWH until each archive succeeds, prints the resulting SWHIDs.
  4. Audits every managed figure's embedded provenance (defers to
     tests/test_figure_provenance.py).
  5. Snapshots the repo as a tar.gz at HEAD.
  6. Creates a DRAFT Zenodo deposit (nothing is published) containing:
        - the repo tarball
        - extra heavy data files listed in EXTRA_FILES below
     The deposit is private until you click "Publish" in the Zenodo UI.

After publication in the Zenodo UI, you populate `zenodo_doi` in
scripts/embed_figure_gist_metadata.py's FIGURE_PROVENANCE, re-run that
script to refresh embedded metadata, and commit. The figures then claim
durability via BOTH SWHID (per-figure) and Zenodo DOI (per-bundle).

Usage:
    # Dry run — describe what would happen, no API calls:
    ./scripts/release/publish-archive.py --dry-run

    # SWH only — submit + poll, no Zenodo activity:
    ./scripts/release/publish-archive.py --skip-zenodo

    # Full run (requires ZENODO_TOKEN):
    ZENODO_TOKEN='...' ./scripts/release/publish-archive.py

Environment:
    ZENODO_TOKEN     Required for the Zenodo phase. Generate at
                     https://zenodo.org/account/settings/applications/tokens/new/
                     with scope `deposit:write` (and `deposit:actions`
                     if you ever want to publish via API).

    ZENODO_SANDBOX   Set to "true" to use sandbox.zenodo.org instead of
                     zenodo.org. Fake DOIs (10.5072/zenodo.X), no
                     DataCite registration — safe for testing the
                     script end-to-end before doing it for real.

Safety:
    - SWH submissions are append-only — irreversible but never lossy.
      Software Heritage's mission is permanent archival; once your
      content is in, you can't take it out.
    - Zenodo deposits start as drafts. Drafts can be deleted from the
      UI before publishing. After publishing, the bytes are immutable
      (you can edit metadata, but not files).
    - --dry-run prints the planned actions and makes no API calls.

Single-record-with-everything model:
    This script bundles the repo tarball + extra heavy data files
    (triage runs with reasoning, benchmark runs with reasoning, deep
    dives) into ONE Zenodo record. One DOI covers everything.

    Alternative: enable the GitHub-release auto-archive feature on
    accessible-surfaceome and you get a SEPARATE record series for
    routine releases of just the repo (no heavy data). Then this
    script becomes "the heavy-data bundle" deposit, a second record
    series. Two DOIs.

    Pick one or the other. The single-record model (this script's
    default) is simpler.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

import httpx

# ── Configuration ──────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[2]

# Repo origin to archive on Software Heritage.
REPO_ORIGIN = "https://github.com/Deliverome-Project/accessible-surfaceome"

# Per-figure gists to archive on Software Heritage. Mirrors
# FIGURE_PROVENANCE in scripts/embed_figure_gist_metadata.py — keep in
# sync as new figure gists are minted.
GIST_ORIGINS = [
    "https://gist.github.com/beccajcarlson/d655abfc9c7deeaff1cfbe584de96ffa",  # db_overlap_venn
    # add more figure gists here as they're built and gain a slot in
    # FIGURE_PROVENANCE
]

# Heavy data outputs to include in the Zenodo deposit alongside the
# repo tarball. Paths are relative to REPO_ROOT. Uncomment / add as
# the files become ready.
#
# CONFIGURE BEFORE RUNNING. The default list is empty; if you run with
# an empty list the script will warn and proceed without extras.
EXTRA_FILES_RELATIVE: list[str] = [
    # "data/analysis/triage/triage-run-complete-with-reasoning.json",
    # "data/analysis/benchmark/benchmark-full-reasoning.json",
    # "data/analysis/deep_dives/deep_dive_1.json",
    # "data/analysis/deep_dives/deep_dive_2.json",
    # "data/analysis/deep_dives/deep_dive_3.json",
]

# Seed metadata for the Zenodo deposit. The Zenodo UI lets you edit
# every field before publishing — these are sensible defaults.
SEED_METADATA = {
    "metadata": {
        "upload_type": "dataset",
        "title": "accessible-surfaceome — open atlas snapshot",
        "description": (
            "Snapshot of the accessible-surfaceome repository plus "
            "large auxiliary data outputs (triage run with reasoning, "
            "benchmark run with full reasoning, deep dives). The "
            "repository itself is also archived continuously by "
            "Software Heritage; this Zenodo deposit provides a "
            "DOI-citeable bundle and a stable home for data files too "
            "large to live in the repo."
        ),
        "creators": [
            {"name": "Carlson, Rebecca"},
            {"name": "Smallegan, Michael"},
        ],
        "access_right": "open",
        "license": "cc-by-4.0",
        "keywords": [
            "surface proteome",
            "drug delivery",
            "reproducible figures",
            "open data",
        ],
    },
}

SWH_BASE = "https://archive.softwareheritage.org/api/1"


# ── Output helpers ─────────────────────────────────────────────────────

def announce(msg: str) -> None:
    print(f"\n→ {msg}")


def ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def warn(msg: str) -> None:
    print(f"  ⚠ {msg}")


def bail(msg: str) -> None:
    print(f"\nerror: {msg}", file=sys.stderr)
    sys.exit(1)


# ── Software Heritage ──────────────────────────────────────────────────

def _swh_url_encoded(origin: str) -> str:
    return urllib.parse.quote(origin, safe="")


def submit_save_code_now(origin: str, *, dry_run: bool) -> dict[str, Any] | None:
    if dry_run:
        ok(f"[dry-run] would POST Save Code Now for {origin}")
        return None
    url = f"{SWH_BASE}/origin/save/git/url/{_swh_url_encoded(origin)}/"
    r = httpx.post(url, headers={"Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    return r.json()


def poll_swh_until_done(origin: str, *, max_wait_s: int = 1200) -> str | None:
    """Poll SWH until the most recent save_request for `origin` finishes.

    Returns the snapshot SWHID on success, or None on timeout/failure.
    """
    encoded = _swh_url_encoded(origin)
    deadline = time.time() + max_wait_s
    while time.time() < deadline:
        r = httpx.get(
            f"{SWH_BASE}/origin/save/git/url/{encoded}/",
            timeout=30,
        )
        if r.status_code != 200:
            time.sleep(30)
            continue
        data = r.json()
        entries = data if isinstance(data, list) else [data]
        latest = entries[-1]
        status = latest.get("save_task_status")
        if status == "succeeded":
            snp = latest.get("snapshot_swhid")
            if snp:
                return snp
            # Fall back: query the latest visit for this origin
            visits = httpx.get(
                f"{SWH_BASE}/origin/{encoded}/visits/latest/", timeout=30,
            ).json()
            if visits.get("snapshot"):
                return f"swh:1:snp:{visits['snapshot']}"
            return None
        if status == "failed":
            return None
        print(f"    {origin}: status={status}, waiting 30s …")
        time.sleep(30)
    return None


# ── Repo snapshot ──────────────────────────────────────────────────────

def git_archive_repo(out_path: Path, *, dry_run: bool) -> str:
    """Snapshot the repo at HEAD as a tar.gz. Returns the HEAD commit SHA."""
    head_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
    ).decode().strip()
    if dry_run:
        ok(f"[dry-run] would `git archive` HEAD ({head_sha[:7]}) → {out_path.name}")
        return head_sha
    subprocess.run(
        [
            "git", "archive", "--format=tar.gz",
            f"--prefix=accessible-surfaceome-{head_sha[:7]}/",
            f"--output={out_path}", "HEAD",
        ],
        cwd=REPO_ROOT,
        check=True,
    )
    return head_sha


# ── Zenodo ─────────────────────────────────────────────────────────────

def zenodo_base() -> str:
    if os.environ.get("ZENODO_SANDBOX", "").lower() == "true":
        return "https://sandbox.zenodo.org/api"
    return "https://zenodo.org/api"


def zenodo_create_deposit(token: str, metadata: dict, *, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        ok("[dry-run] would create Zenodo draft with metadata:")
        for line in json.dumps(metadata["metadata"], indent=2).splitlines():
            print(f"    {line}")
        return {
            "id": "<dry-run>",
            "links": {
                "html": "<dry-run-edit-url>",
                "bucket": "<dry-run-bucket>",
                "self": "<dry-run-self>",
            },
            "metadata": {"prereserve_doi": {"doi": "<dry-run-doi>"}},
        }
    r = httpx.post(
        f"{zenodo_base()}/deposit/depositions",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=metadata,
        timeout=60,
    )
    if not r.is_success:
        bail(f"Zenodo create-deposit failed: HTTP {r.status_code}: {r.text}")
    return r.json()


def zenodo_upload_file(bucket_url: str, token: str, local_path: Path, *, dry_run: bool) -> None:
    if dry_run:
        size_str = (
            f"{local_path.stat().st_size / 1024 / 1024:.1f} MB"
            if local_path.exists()
            else "size unknown — file not yet created"
        )
        ok(f"[dry-run] would upload {local_path.name} ({size_str}) → {bucket_url}/{local_path.name}")
        return
    size_mb = local_path.stat().st_size / 1024 / 1024
    ok(f"uploading {local_path.name} ({size_mb:.1f} MB) → {bucket_url}/{local_path.name}")
    with local_path.open("rb") as fh:
        r = httpx.put(
            f"{bucket_url}/{local_path.name}",
            content=fh.read(),
            headers={"Authorization": f"Bearer {token}"},
            timeout=900,  # 15 min for large files
        )
    if not r.is_success:
        bail(f"Zenodo upload of {local_path.name} failed: HTTP {r.status_code}: {r.text}")


# ── Phases ─────────────────────────────────────────────────────────────

def phase_swh(*, dry_run: bool) -> dict[str, str | None]:
    """Submit repo + all figure gists to SWH; poll for SWHIDs."""
    announce("PHASE 1 — Software Heritage: submit repo + figure gists")

    origins = [REPO_ORIGIN, *GIST_ORIGINS]
    for origin in origins:
        resp = submit_save_code_now(origin, dry_run=dry_run)
        if resp is not None:
            ok(
                f"submitted {origin} (request id={resp.get('id')}, "
                f"status={resp.get('save_task_status')})"
            )

    if dry_run:
        return {origin: None for origin in origins}

    announce("Polling SWH for each archive (1–15 min each)…")
    results: dict[str, str | None] = {}
    for origin in origins:
        print(f"  ↻ {origin}")
        swhid = poll_swh_until_done(origin)
        results[origin] = swhid
        if swhid:
            ok(f"SWHID: {swhid}")
        else:
            warn(f"timed out / failed: {origin}")
    return results


def phase_audit_figures(*, dry_run: bool) -> bool:
    """Run the figure-provenance test suite. Returns True if pass."""
    announce("PHASE 2 — Audit every figure's embedded provenance")
    if dry_run:
        ok("[dry-run] would run: uv run pytest tests/test_figure_provenance.py")
        return True
    try:
        subprocess.run(
            ["uv", "run", "pytest", "tests/test_figure_provenance.py", "-q"],
            cwd=REPO_ROOT,
            check=True,
        )
        ok("all figure provenance checks pass")
        return True
    except subprocess.CalledProcessError:
        warn("figure provenance audit failed — see pytest output above")
        warn("consider re-running scripts/embed_figure_gist_metadata.py before Zenodo")
        return False


def phase_zenodo(*, dry_run: bool, token: str | None) -> None:
    """Snapshot the repo, create Zenodo draft, upload artifacts."""
    announce("PHASE 3 — Zenodo: create draft deposit + upload artifacts")

    if not token and not dry_run:
        bail("ZENODO_TOKEN env var required for the Zenodo phase (or pass --dry-run)")

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    tarball = REPO_ROOT / f"_release-snapshot-{timestamp}.tar.gz"
    head_sha = git_archive_repo(tarball, dry_run=dry_run)
    ok(f"repo tarball: {tarball.name} @ HEAD={head_sha[:12]}")

    deposit = zenodo_create_deposit(token or "", SEED_METADATA, dry_run=dry_run)
    deposit_id = deposit["id"]
    bucket = deposit.get("links", {}).get("bucket", "")
    edit_url = deposit.get("links", {}).get("html", "")
    reserved_doi = (
        deposit.get("metadata", {}).get("prereserve_doi", {}).get("doi")
        or "(no DOI reserved)"
    )

    ok(f"draft created: id={deposit_id} doi={reserved_doi}")

    # Upload repo tarball
    announce(f"Uploading repo tarball to deposit {deposit_id}")
    zenodo_upload_file(bucket, token or "", tarball, dry_run=dry_run)

    # Upload extra heavy data files
    announce("Uploading heavy data files (EXTRA_FILES_RELATIVE)")
    extra_paths = [REPO_ROOT / p for p in EXTRA_FILES_RELATIVE]
    if not extra_paths:
        warn(
            "EXTRA_FILES_RELATIVE is empty — uncomment / add paths in the "
            "config block at the top of this script to bundle heavy data."
        )
    found = [p for p in extra_paths if p.exists()]
    missing = [p for p in extra_paths if not p.exists()]
    if missing:
        warn("missing files (will skip):")
        for p in missing:
            warn(f"  - {p.relative_to(REPO_ROOT)}")
    for p in found:
        zenodo_upload_file(bucket, token or "", p, dry_run=dry_run)

    # Cleanup local tarball
    if not dry_run and tarball.exists():
        tarball.unlink()
        ok(f"removed local snapshot {tarball.name}")

    # Summary
    announce("Zenodo phase complete")
    print()
    print(f"  Zenodo draft URL:   {edit_url}")
    print(f"  Reserved DOI:       {reserved_doi}")
    print(f"  Deposit ID:         {deposit_id}")
    print()
    print("  Next steps:")
    print("    1. Open the draft in the Zenodo UI to review metadata + files")
    print("    2. Add ORCID IDs, affiliations, related identifiers, etc.")
    print("    3. When ready, click Publish")
    print(
        "    4. After publishing, populate `zenodo_doi` in FIGURE_PROVENANCE "
        "in scripts/embed_figure_gist_metadata.py and re-run that script"
    )
    print()


# ── Main ───────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Publish accessible-surfaceome to Software Heritage + Zenodo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="describe what would happen without making API calls",
    )
    ap.add_argument(
        "--skip-zenodo",
        action="store_true",
        help="run SWH phase only (no deposit / draft created)",
    )
    ap.add_argument(
        "--skip-swh",
        action="store_true",
        help="skip Software Heritage submissions; only run audit + Zenodo phases",
    )
    args = ap.parse_args()

    swh_results: dict[str, str | None] = {}
    if not args.skip_swh:
        swh_results = phase_swh(dry_run=args.dry_run)
    else:
        warn("--skip-swh: skipping Software Heritage submissions")

    phase_audit_figures(dry_run=args.dry_run)

    if not args.skip_zenodo:
        phase_zenodo(dry_run=args.dry_run, token=os.environ.get("ZENODO_TOKEN"))
    else:
        warn("--skip-zenodo: skipping Zenodo deposit")

    # Final summary
    announce("DONE")
    if swh_results:
        print()
        print("  SWHIDs minted:")
        for origin, swhid in swh_results.items():
            label = origin.split("/")[-1] or origin
            status = (
                swhid
                if swhid
                else ("(dry-run)" if args.dry_run else "(failed / pending)")
            )
            print(f"    {label:48s} {status}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
