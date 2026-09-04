#!/usr/bin/env python
"""Ingest Schweke 2024 homo-oligomer PDB models into public R2.

The viewer's Schweke 3D tab fetches AlphaFold coordinate files as plain
static assets. We do NOT commit ~1,478 multi-MB PDBs to git (repo bloat)
nor stuff them into D1 (2 MB/row hard cap — the largest c13 complexes blow
it). Instead the *coordinates* live in the public R2 bucket
``surfaceome-structures`` (served at the bucket's r2.dev domain with CORS +
range support), while the *metadata* index stays in D1's
``schweke_homomer_public`` table. Classic "DB indexes the object, object
store holds the bytes" split.

Source archives (figshare deposit 10.6084/m9.figshare.22309177, reachable
only via the reserved deposit's private share link):

  * higher-order complexes — ``full_complexes_bigbang.zip`` (file 41122979),
    members ``full_complexes_bigbang/{ACC}_V1_{N}_c{K}_model_0_rank_1.pdb``.
  * homo-dimers (core/trimmed set) — ``AF_dimer_models_core.zip``
    (file 41122997), members ``AF_dimer_models_core/{ACC}_V1_{N}.pdb``.

For each homomer in ``schweke_d1_payload.tsv`` we upload the dimer model and,
where a c>=3 reconstruction exists, the complex model. The R2 object key is
the CANONICAL SHORT filename (``{ACC}_V1_{N}_c{K}.pdb`` — the figshare
``_model_0_rank_1`` suffix stripped) under the ``schweke/`` prefix, matching
the convention in ``structure-viewer.ts`` and ``schweke_homomer.py``.

Auth: uses ``CLOUDFLARE_API_TOKEN`` + ``CLOUDFLARE_ACCOUNT_ID`` from ``.env``
(the same bearer token the D1 tooling uses) against Cloudflare's R2 REST API
for object PUT — no separate S3 credentials required.

Usage::

    # dry-run — print the worklist + byte totals, upload nothing
    uv run --with remotezip python scripts/ingest_schweke_pdbs_to_r2.py

    # do it (downloads the two zips to a gitignored cache, then uploads)
    uv run --with remotezip python scripts/ingest_schweke_pdbs_to_r2.py --execute

    # re-upload even objects already present in R2
    uv run --with remotezip python scripts/ingest_schweke_pdbs_to_r2.py --execute --force
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from accessible_surfaceome.env import load_env  # noqa: E402

PAYLOAD = REPO / "data/external/schweke_homomer_atlas/schweke_d1_payload.tsv"
MANIFEST = REPO / "data/external/schweke_homomer_atlas/r2_pdb_manifest.tsv"
# Gitignored blob cache (per CLAUDE.md: copyrighted PDFs/blobs live here, never committed).
CACHE_DIR = REPO / "data/external/blob_cache/schweke_zips"

PRIVATE_LINK = "af3c1d5969f7468f2caa"
ARCHIVES = {
    "complex": (41122979, "full_complexes_bigbang"),
    "dimer": (41122997, "AF_dimer_models_core"),
}
BUCKET = "surfaceome-structures"
KEY_PREFIX = "schweke"
CONTENT_TYPE = "chemical/x-pdb"
CACHE_CONTROL = "public, max-age=31536000, immutable"


@dataclass(frozen=True)
class Want:
    """One PDB we need: which archive, the zip member path, and the R2 key."""

    kind: str  # "dimer" | "complex"
    acc: str
    member: str  # path inside the zip
    short_name: str  # canonical short filename == R2 object basename


def _read_worklist() -> list[Want]:
    wants: list[Want] = []
    with PAYLOAD.open() as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            acc = row["uniprot_acc"]
            dimer_fn = (row.get("dimer_pdb_filename") or "").strip()
            complex_fn = (row.get("complex_pdb_filename") or "").strip()
            if dimer_fn:
                wants.append(
                    Want(
                        "dimer",
                        acc,
                        f"{ARCHIVES['dimer'][1]}/{dimer_fn}",
                        dimer_fn,
                    )
                )
            if complex_fn:
                # payload is already normalized to the short name
                # (``{ACC}_V1_{N}_c{K}.pdb``); the zip member carries the long
                # figshare export name with the ``_model_0_rank_1`` suffix.
                short = complex_fn
                stem = short[:-4]  # drop ".pdb"
                long_member = f"{ARCHIVES['complex'][1]}/{stem}_model_0_rank_1.pdb"
                wants.append(Want("complex", acc, long_member, short))
    return wants


def _download_zip(file_id: int, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  cached: {dest.name} ({dest.stat().st_size/1e6:.1f} MB)")
        return
    url = f"https://ndownloader.figshare.com/files/{file_id}?private_link={PRIVATE_LINK}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"  downloading file {file_id} -> {dest.name} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "accessible-surfaceome/1.0 (becca@deliverome.org)"})
    with urllib.request.urlopen(req, timeout=120) as r, tmp.open("wb") as out:
        total = 0
        while chunk := r.read(1 << 20):
            out.write(chunk)
            total += len(chunk)
    tmp.rename(dest)
    print(f"    done: {total/1e6:.1f} MB")


def _r2_put(acct: str, tok: str, key: str, body: bytes) -> tuple[bool, str]:
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/r2/buckets/{BUCKET}/objects/{key}"
    req = urllib.request.Request(
        url,
        data=body,
        method="PUT",
        headers={
            "Authorization": f"Bearer {tok}",
            "Content-Type": CONTENT_TYPE,
            "Cache-Control": CACHE_CONTROL,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status == 200, str(r.status)
    except urllib.error.HTTPError as e:
        return False, f"{e.code} {e.read().decode()[:120]}"
    except Exception as e:  # noqa: BLE001
        return False, repr(e)[:120]


def _r2_list_existing(acct: str, tok: str) -> dict[str, int]:
    """Return ``{key: size}`` for every object under ``{KEY_PREFIX}/`` in one
    paginated LIST — far cheaper + more reliable than a per-object HEAD
    (the REST object endpoint doesn't answer HEAD consistently)."""
    import json

    out: dict[str, int] = {}
    cursor = None
    while True:
        url = (
            f"https://api.cloudflare.com/client/v4/accounts/{acct}/r2/buckets/"
            f"{BUCKET}/objects?prefix={KEY_PREFIX}/&per_page=1000"
        )
        if cursor:
            url += f"&cursor={cursor}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        res = d.get("result", []) or []
        for o in res:
            out[o["key"]] = o.get("size", 0)
        cursor = (d.get("result_info") or {}).get("cursor")
        if not cursor or not res:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="actually download + upload (default: dry-run)")
    ap.add_argument("--force", action="store_true", help="re-upload objects already in R2")
    ap.add_argument("--concurrency", type=int, default=12)
    ap.add_argument("--limit", type=int, default=0, help="cap worklist size (testing)")
    args = ap.parse_args()

    load_env()
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    tok = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not acct or not tok:
        print("ERROR: CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN not set", file=sys.stderr)
        return 2

    wants = _read_worklist()
    if args.limit:
        wants = wants[: args.limit]
    n_dimer = sum(1 for w in wants if w.kind == "dimer")
    n_complex = sum(1 for w in wants if w.kind == "complex")
    print(f"worklist: {len(wants)} files ({n_dimer} dimers + {n_complex} complexes)")
    print(f"R2 bucket: {BUCKET}  key prefix: {KEY_PREFIX}/")

    if not args.execute:
        print("\n[dry-run] sample worklist entries:")
        for w in wants[:6]:
            print(f"  {w.kind:8} {w.member}  ->  {KEY_PREFIX}/{w.short_name}")
        print("\nre-run with --execute to download archives + upload.")
        return 0

    import zipfile

    # 1) Download both archives to the gitignored cache.
    print("\n--- fetching source archives ---")
    zips: dict[str, zipfile.ZipFile] = {}
    for kind, (fid, _) in ARCHIVES.items():
        needed = any(w.kind == kind for w in wants)
        if not needed:
            continue
        dest = CACHE_DIR / f"{fid}.zip"
        _download_zip(fid, dest)
        zips[kind] = zipfile.ZipFile(dest)

    # 2) Extract + upload.
    print("\n--- extracting + uploading to R2 ---")
    members = {kind: set(z.namelist()) for kind, z in zips.items()}
    existing = {} if args.force else _r2_list_existing(acct, tok)
    print(f"  {len(existing)} objects already in R2 (skipped unless --force)")
    uploaded: list[tuple[str, int]] = []
    skipped_present = 0
    missing_member = 0
    failed: list[tuple[str, str]] = []

    def work(w: Want):
        key = f"{KEY_PREFIX}/{w.short_name}"
        if key in existing:
            return ("present", w, 0, "")
        if w.member not in members[w.kind]:
            return ("missing", w, 0, "")
        body = zips[w.kind].read(w.member)
        ok, msg = _r2_put(acct, tok, key, body)
        return ("ok" if ok else "fail", w, len(body), msg)

    done = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = [ex.submit(work, w) for w in wants]
        for fut in as_completed(futs):
            status, w, size, msg = fut.result()
            done += 1
            if status == "ok":
                uploaded.append((w.short_name, size))
            elif status == "present":
                skipped_present += 1
            elif status == "missing":
                missing_member += 1
                print(f"  MISSING in zip: {w.member}")
            else:
                failed.append((w.short_name, msg))
                print(f"  FAIL {w.short_name}: {msg}")
            if done % 100 == 0:
                print(f"  progress {done}/{len(wants)}")

    # 3) Manifest — re-list R2 so it reflects ALL objects present (this
    # run's uploads + any from prior runs), not just this invocation's.
    total_bytes = sum(s for _, s in uploaded)
    final = _r2_list_existing(acct, tok)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["r2_key", "bytes"])
        for key, size in sorted(final.items()):
            w.writerow([key, size])

    print("\n--- summary ---")
    print(f"  uploaded        : {len(uploaded)} ({total_bytes/1e6:.1f} MB)")
    print(f"  total in R2     : {len(final)}")
    print(f"  already present : {skipped_present}")
    print(f"  missing in zip  : {missing_member}")
    print(f"  failed          : {len(failed)}")
    print(f"  manifest        : {MANIFEST.relative_to(REPO)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
