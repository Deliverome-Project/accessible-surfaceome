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

After publication in the Zenodo UI, you populate `doi` in
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
# repo tarball. Each entry is either:
#
#   - a string starting with "https://" or "http://" — fetched from
#     the URL at upload time; saved into the Zenodo deposit as the
#     URL's basename (the last path segment)
#
#   - a dict {"url": "https://...", "filename": "name.ext"} — fetched
#     from the URL, saved into the Zenodo deposit under the explicit
#     filename. Use this when the URL doesn't end with a meaningful
#     filename (e.g., an API path) or when you want a different
#     destination name.
#
#   - any other string — treated as a path relative to REPO_ROOT;
#     read from the local filesystem
#
# CONFIGURE BEFORE RUNNING. The default list is empty; if you run with
# an empty list the script will warn and proceed without extras.
EXTRA_FILES: list[str | dict[str, str]] = [
    # Local-file examples:
    # "data/analysis/triage/triage-run-complete-with-reasoning.json",
    # "data/analysis/deep_dives/deep_dive_1.json",
    #
    # API-fetch examples (string form — destination uses URL basename):
    # "https://api.deliverome.org/triage/runs/latest.json",
    #
    # API-fetch with explicit destination filename (dict form):
    # {
    #     "url": "https://api.deliverome.org/benchmark/runs?format=jsonl&latest=1",
    #     "filename": "benchmark-full-reasoning.jsonl",
    # },
]

# Seed metadata for the Zenodo deposit. The Zenodo UI lets you edit
# every field before publishing — these are sensible defaults.
SEED_METADATA = {
    "metadata": {
        "upload_type": "dataset",
        "title": "accessible-surfaceome — auxiliary data outputs",
        "description": (
            "Large auxiliary data outputs for the accessible-surfaceome "
            "project: triage runs with full reasoning, benchmark runs "
            "with reasoning, and deep-dive analyses. These files are too "
            "large to live in the repository directly. The repository "
            "code itself is archived separately, both via the "
            "GitHub-Zenodo auto-archive (one DOI per tagged release) "
            "and via Software Heritage (continuous crawl, content-"
            "addressed SWHIDs). This record is the supplementary "
            "data layer."
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
        # Link this data record to the auto-archived code record(s).
        # Fill in concept DOI(s) once the auto-archive has produced its
        # first release; the link makes the relationship explicit in
        # CrossRef/DataCite and Zenodo's UI.
        "related_identifiers": [
            # {
            #     "identifier": "10.5281/zenodo.<CODE-CONCEPT-DOI>",
            #     "relation": "isSupplementTo",
            #     "scheme": "doi",
            # },
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

def _resolve_extra_file(
    entry: str | dict[str, str], *, dry_run: bool,
) -> tuple[Path, bool] | None:
    """Resolve one EXTRA_FILES entry to a (local_path, cleanup) pair.

    Three input shapes:

      - bare HTTP(S) URL: fetched to a tempfile, returned with
        cleanup=True so the caller deletes it after upload. Destination
        name is the URL's last path segment.

      - {"url": "...", "filename": "..."} dict: same fetch behaviour
        but destination name is the explicit filename.

      - other string: treated as a path relative to REPO_ROOT. If the
        local file doesn't exist, warns and returns None.

    Raises on fetch errors so the caller can decide whether to skip.
    """
    # Bare URL
    if isinstance(entry, str) and entry.startswith(("http://", "https://")):
        return _download_to_tempfile(entry, filename=None, dry_run=dry_run), True

    # Dict form: {url, filename}
    if isinstance(entry, dict):
        url = entry.get("url")
        filename = entry.get("filename")
        if not url:
            raise ValueError("dict entry missing 'url'")
        return _download_to_tempfile(url, filename=filename, dry_run=dry_run), True

    # Local path
    if isinstance(entry, str):
        path = REPO_ROOT / entry
        if not path.exists():
            warn(f"  - missing local file (will skip): {entry}")
            return None
        return path, False

    raise ValueError(f"unsupported entry type: {type(entry).__name__}")


def _download_to_tempfile(
    url: str, *, filename: str | None, dry_run: bool,
) -> Path:
    """Fetch `url` to a tempfile and return the local path.

    `filename` overrides the destination name (otherwise derived from
    the URL's last path segment). In dry-run mode, returns a fake Path
    of length 0 without making any HTTP request.
    """
    name = filename or urllib.parse.unquote(
        urllib.parse.urlparse(url).path.rsplit("/", 1)[-1]
    ) or "download.bin"
    if not name:
        raise ValueError(f"could not derive filename from URL: {url}")

    tmp_root = Path(REPO_ROOT) / "_extra-download"
    if dry_run:
        ok(f"[dry-run] would fetch {url}  → upload as {name}")
        # Return a fake path; the upload step also dry-runs.
        return tmp_root / name
    tmp_root.mkdir(exist_ok=True)
    out = tmp_root / name
    with httpx.stream("GET", url, timeout=300, follow_redirects=True) as r:
        r.raise_for_status()
        with out.open("wb") as fh:
            for chunk in r.iter_bytes(chunk_size=1 << 20):  # 1 MiB
                fh.write(chunk)
    size_mb = out.stat().st_size / 1024 / 1024
    ok(f"fetched {url} ({size_mb:.1f} MB) → {out.name}")
    return out


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


def zenodo_upload_file(
    bucket_url: str, token: str, local_path: Path, *, dry_run: bool,
    destination_name: str | None = None,
) -> None:
    dest = destination_name or local_path.name
    if dry_run:
        size_str = (
            f"{local_path.stat().st_size / 1024 / 1024:.1f} MB"
            if local_path.exists()
            else "size unknown — file not yet created"
        )
        ok(f"[dry-run] would upload {local_path.name} ({size_str}) → {bucket_url}/{dest}")
        return
    size_mb = local_path.stat().st_size / 1024 / 1024
    ok(f"uploading {local_path.name} ({size_mb:.1f} MB) → {bucket_url}/{dest}")
    with local_path.open("rb") as fh:
        r = httpx.put(
            f"{bucket_url}/{dest}",
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


def phase_audit_data_inputs() -> None:
    """Surface every data input referenced by a managed figure's
    provenance, so the operator can decide which to include in the
    Zenodo deposit.

    Reads ``FIGURE_PROVENANCE`` from ``scripts/embed_figure_gist_metadata.py``
    (the source of truth for which data sources back which figures).
    For each ``data[]`` entry:

    * If the URL is already on a durable archive (Zenodo, Figshare,
      OSF, archive.softwareheritage.org), report it as already-deposited.
    * If the URL is on a mutable host (raw.githubusercontent.com without
      a pinned commit SHA, etc.), flag it as a candidate for deposit.
    * If a ``swhid`` or ``doi`` is already set on the entry, treat it
      as durably referenced and skip.

    This phase doesn't ADD anything to EXTRA_FILES — it just
    surfaces a checklist for the operator. Adding to the deposit is a
    deliberate human step.
    """
    announce("PHASE 2.5 — Audit data inputs referenced by figure gists")

    # Read FIGURE_PROVENANCE from the project venv via subprocess, so this
    # PEP 723 script's isolated venv (which doesn't know about the
    # accessible_surfaceome package) can still see the canonical
    # registry of which data inputs back which figures.
    try:
        out = subprocess.check_output(
            [
                "uv", "run", "--project", str(REPO_ROOT), "python", "-c",
                "import json, sys; "
                "sys.path.insert(0, 'scripts'); "
                "from embed_figure_gist_metadata import FIGURE_PROVENANCE; "
                "print(json.dumps(FIGURE_PROVENANCE))",
            ],
            cwd=REPO_ROOT,
            text=True,
        )
        FIGURE_PROVENANCE: dict[str, dict[str, Any]] = json.loads(out)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        warn(f"could not load FIGURE_PROVENANCE for audit: {exc}")
        return

    durable_hosts = {
        "zenodo.org",
        "sandbox.zenodo.org",
        "figshare.com",
        "ndownloader.figshare.com",
        "osf.io",
        "datadryad.org",
        "archive.softwareheritage.org",
    }

    rows: list[tuple[str, str, str, str]] = []  # (slug, url, status, note)
    for slug, prov in FIGURE_PROVENANCE.items():
        for i, entry in enumerate(prov.get("data") or []):
            url = entry.get("url") or ""
            sha = entry.get("sha256") or ""
            swhid = entry.get("swhid") or ""
            doi = entry.get("doi") or ""
            try:
                host = urllib.parse.urlparse(url).hostname or ""
            except Exception:
                host = ""
            if doi:
                rows.append((slug, url, "DOI",
                             f"deposited (doi={doi})"))
            elif swhid:
                rows.append((slug, url, "SWHID",
                             f"archived (swhid={swhid[:24]}…)"))
            elif host in durable_hosts:
                rows.append((slug, url, "durable host", host))
            elif "raw.githubusercontent.com" in host and "/main/" not in url:
                # Pinned to a commit SHA — content-verifiable but storage-fragile.
                rows.append((slug, f"data[{i}]: {url}", "review",
                             f"pinned to commit SHA; sha256={'set' if sha else 'MISSING'}; "
                             "consider Zenodo deposit"))
            else:
                rows.append((slug, f"data[{i}]: {url}", "review",
                             "mutable URL — needs Zenodo deposit"))

    if not rows:
        warn("FIGURE_PROVENANCE has no data[] entries — nothing to audit")
        return

    print()
    print("  Data inputs referenced by figure gists:")
    print()
    for slug, url, status, note in rows:
        flag = "  ✓" if status in {"DOI", "SWHID", "durable host"} else "  ⚠"
        print(f"  {flag} [{slug}] {status}: {note}")
        print(f"      url: {url[:96]}…" if len(url) > 96 else f"      url: {url}")
    print()
    print(
        "  Review: any '⚠ review' rows above should probably be added to "
        "EXTRA_FILES (or deposited separately) before publishing.\n"
        "  Edit the top of this script and re-run."
    )
    print()


def phase_zenodo(*, dry_run: bool, token: str | None, include_repo_tarball: bool) -> None:
    """Create Zenodo draft and upload artifacts.

    By default this is a HEAVY-DATA deposit: just the files in
    EXTRA_FILES. The repo tarball is omitted because the
    GitHub-Zenodo auto-archive handles routine code-release deposits
    in a separate record series.

    Pass --include-repo-tarball if you've DISABLED auto-archive and
    want this script to be the single bundled record (code + data).
    """
    announce("PHASE 3 — Zenodo: create draft deposit + upload artifacts")

    if not token and not dry_run:
        bail("ZENODO_TOKEN env var required for the Zenodo phase (or pass --dry-run)")

    tarball: Path | None = None
    head_sha: str | None = None
    if include_repo_tarball:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        tarball = REPO_ROOT / f"_release-snapshot-{timestamp}.tar.gz"
        head_sha = git_archive_repo(tarball, dry_run=dry_run)
        ok(f"repo tarball: {tarball.name} @ HEAD={head_sha[:12]}")
    else:
        ok(
            "skipping repo tarball (auto-archive handles code-release "
            "deposits — pass --include-repo-tarball to override)"
        )

    deposit = zenodo_create_deposit(token or "", SEED_METADATA, dry_run=dry_run)
    deposit_id = deposit["id"]
    bucket = deposit.get("links", {}).get("bucket", "")
    edit_url = deposit.get("links", {}).get("html", "")
    reserved_doi = (
        deposit.get("metadata", {}).get("prereserve_doi", {}).get("doi")
        or "(no DOI reserved)"
    )

    ok(f"draft created: id={deposit_id} doi={reserved_doi}")

    # Upload repo tarball if requested
    if include_repo_tarball and tarball is not None:
        announce(f"Uploading repo tarball to deposit {deposit_id}")
        zenodo_upload_file(bucket, token or "", tarball, dry_run=dry_run)

    # Upload extra heavy data files. Each entry in EXTRA_FILES is
    # either a local path, a bare URL, or a {url, filename} dict.
    announce("Uploading heavy data files (EXTRA_FILES)")
    if not EXTRA_FILES:
        warn(
            "EXTRA_FILES is empty — uncomment / add entries in the "
            "config block at the top of this script to bundle heavy data."
        )
    for entry in EXTRA_FILES:
        try:
            resolved = _resolve_extra_file(entry, dry_run=dry_run)
        except Exception as exc:
            warn(f"skipping entry {entry!r}: {exc}")
            continue
        if resolved is None:
            continue  # already warned (missing local file)
        local_path, cleanup = resolved
        try:
            zenodo_upload_file(
                bucket, token or "", local_path,
                dry_run=dry_run, destination_name=local_path.name,
            )
        finally:
            if cleanup:
                try:
                    local_path.unlink()
                except FileNotFoundError:
                    pass

    # Cleanup local tarball (if we created one)
    if tarball is not None and not dry_run and tarball.exists():
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
        "    4. After publishing, populate `doi` in FIGURE_PROVENANCE "
        "in scripts/embed_figure_gist_metadata.py and re-run that script"
    )
    print()


def phase_github_release(tag: str, *, dry_run: bool) -> None:
    """Tag HEAD, push the tag, and create a GitHub Release.

    Once the GitHub Release is published, the Zenodo GitHub-archive
    integration (assumed enabled) auto-deposits the repo tarball at
    that tag as a new version in the code record series.

    Pre-conditions checked:
      - working tree is clean (or in dry-run mode)
      - `gh` CLI is authenticated
      - tag doesn't already exist locally (refuse to overwrite)
    """
    announce(f"PHASE 4 — Tag + GitHub Release: {tag}")

    if dry_run:
        ok(f"[dry-run] would run: git tag -a {tag} -m '<auto-generated>'")
        ok(f"[dry-run] would run: git push origin {tag}")
        ok(f"[dry-run] would run: gh release create {tag} --generate-notes")
        ok("[dry-run] Zenodo auto-archive would fire on the release event")
        return

    # Working tree must be clean — refuse to tag on top of dirty state
    status = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT,
    ).decode().strip()
    if status:
        bail(
            f"working tree not clean — refusing to tag.\n"
            f"  modified: {status.splitlines()[:5]}"
        )

    # Tag must not already exist
    existing = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"],
        cwd=REPO_ROOT, capture_output=True,
    )
    if existing.returncode == 0:
        bail(
            f"tag {tag} already exists locally — refusing to overwrite.\n"
            f"  delete it first with `git tag -d {tag}` if intentional."
        )

    # gh must be authed
    gh_auth = subprocess.run(
        ["gh", "auth", "status"], cwd=REPO_ROOT, capture_output=True,
    )
    if gh_auth.returncode != 0:
        bail(
            "`gh` CLI is not authenticated — run `gh auth login` first."
        )

    # Tag and push
    subprocess.run(
        ["git", "tag", "-a", tag, "-m", f"Release {tag}"],
        cwd=REPO_ROOT, check=True,
    )
    ok(f"tagged {tag}")
    subprocess.run(
        ["git", "push", "origin", tag], cwd=REPO_ROOT, check=True,
    )
    ok(f"pushed {tag} to origin")

    # Create the GitHub Release with auto-generated notes
    subprocess.run(
        ["gh", "release", "create", tag, "--generate-notes"],
        cwd=REPO_ROOT, check=True,
    )
    ok(f"created GitHub Release {tag}")
    print()
    print(
        "  Zenodo GitHub-archive integration should fire within a few "
        "minutes. Visit https://zenodo.org/account/settings/github/ "
        "to confirm, or watch for the new code-record DOI."
    )
    print()


def _print_release_hint() -> None:
    """If --gh-release wasn't passed, remind the operator how to do it."""
    announce("Next step (optional): GitHub Release → Zenodo code-record")
    print()
    print(
        "  To refresh the code-record DOI series, tag a release in this repo.\n"
        "  Zenodo's GitHub-archive integration (must be enabled) auto-deposits.\n"
    )
    print("    git tag -a vX.Y.Z -m 'Release vX.Y.Z'")
    print("    git push origin vX.Y.Z")
    print("    gh release create vX.Y.Z --generate-notes")
    print()
    print(
        "  Or re-run this script with --gh-release vX.Y.Z to do it automatically."
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
    ap.add_argument(
        "--include-repo-tarball",
        action="store_true",
        help=(
            "snapshot the repo at HEAD as a tar.gz and include it in the Zenodo "
            "deposit. OFF by default: assumes GitHub-Zenodo auto-archive handles "
            "code-release deposits in a separate record series. Pass this flag "
            "if you've disabled auto-archive and want one bundled record."
        ),
    )
    ap.add_argument(
        "--gh-release",
        metavar="TAG",
        help=(
            "after the Zenodo phase finishes, tag HEAD as TAG (e.g. v1.2.0), "
            "push the tag, and create a GitHub Release with auto-generated notes. "
            "Triggers the GitHub-Zenodo auto-archive to mint a code-record DOI. "
            "OFF by default — the script prints the commands instead and lets "
            "you decide when to tag."
        ),
    )
    args = ap.parse_args()

    swh_results: dict[str, str | None] = {}
    if not args.skip_swh:
        swh_results = phase_swh(dry_run=args.dry_run)
    else:
        warn("--skip-swh: skipping Software Heritage submissions")

    phase_audit_figures(dry_run=args.dry_run)
    phase_audit_data_inputs()

    if not args.skip_zenodo:
        phase_zenodo(
            dry_run=args.dry_run,
            token=os.environ.get("ZENODO_TOKEN"),
            include_repo_tarball=args.include_repo_tarball,
        )
    else:
        warn("--skip-zenodo: skipping Zenodo deposit")

    if args.gh_release:
        phase_github_release(args.gh_release, dry_run=args.dry_run)
    else:
        _print_release_hint()

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
