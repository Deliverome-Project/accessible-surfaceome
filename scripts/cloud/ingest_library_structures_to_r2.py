#!/usr/bin/env python
"""Ingest the Deliverome library's own predicted structures into public R2.

The viewer currently shows every library member the AlphaFold DB model for its canonical
accession. For a large minority that is not the protein we are ordering: 70 L1 members had
no AFDB model at all, and 200 more have a model of a *different* proteoform, measured
residue-exact against the designed CDS (see deliverome-analysis S4E9). Those were folded
with ColabFold, and this puts the coordinates where the viewer can reach them.

Same split as the Schweke models: the *coordinates* live in the public R2 bucket
``surfaceome-structures`` under ``library-colabfold/``, and the *index* stays in D1. D1
caps a row at 2 MB, and a 1,500-residue PDB does not fit.

Takes a local directory of the published coordinates rather than reaching into S3, so this
repository keeps no dependency on the deliverome-analysis package. Fetch them first with
that repo's ``publish_predicted_structures.py`` output, or straight from
``processed://sprint4/s4e9-orf-design-fg-panel/predicted-structures/colabfold/<release>/``.

    uv run python scripts/cloud/ingest_library_structures_to_r2.py \
        --from-dir ~/.cache/deliverome-analysis/predicted_structures --release 2026-10-14 --dry-run
    uv run python scripts/cloud/ingest_library_structures_to_r2.py \
        --from-dir ~/.cache/deliverome-analysis/predicted_structures --release 2026-10-14

Auth: ``CLOUDFLARE_API_TOKEN`` + ``CLOUDFLARE_ACCOUNT_ID`` from ``.env``, the same bearer
the D1 tooling uses. Uploads are idempotent -- one paginated LIST decides what is already
there, so a re-run after a partial upload costs nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BUCKET = "surfaceome-structures"
KEY_PREFIX = "library-colabfold"
CONTENT_TYPE = "chemical/x-pdb"
CACHE_CONTROL = "public, max-age=31536000, immutable"

def _env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"{name} is not set; it lives in .env alongside the D1 token")
    return value


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
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status == 200, str(resp.status)
    except urllib.error.HTTPError as exc:
        return False, f"{exc.code} {exc.read().decode()[:160]}"
    except Exception as exc:
        return False, repr(exc)[:160]


def _r2_list_existing(acct: str, tok: str) -> dict[str, int]:
    """``{key: size}`` for everything already under the prefix, in one paginated LIST."""
    out: dict[str, int] = {}
    cursor = ""
    while True:
        url = (
            f"https://api.cloudflare.com/client/v4/accounts/{acct}/r2/buckets/{BUCKET}/objects"
            f"?prefix={KEY_PREFIX}/&per_page=1000"
        )
        if cursor:
            url += f"&cursor={cursor}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
        for obj in data.get("result") or []:
            out[obj["key"]] = int(obj.get("size") or 0)
        cursor = (data.get("result_info") or {}).get("cursor") or ""
        if not cursor:
            break
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from-dir", type=Path, required=True,
                    help="directory of published .pdb files for one release")
    ap.add_argument("--release", required=True,
                    help="release folder under the R2 prefix, e.g. 2026-10-14")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--concurrency", type=int, default=8)
    args = ap.parse_args(argv)

    acct, tok = _env("CLOUDFLARE_ACCOUNT_ID"), _env("CLOUDFLARE_API_TOKEN")
    pairs = [
        (path, f"{KEY_PREFIX}/{args.release}/{path.name}")
        for path in sorted(args.from_dir.glob("*.pdb"))
    ]
    if not pairs:
        raise SystemExit(f"no .pdb under {args.from_dir} — nothing to ingest")
    existing = {} if args.dry_run else _r2_list_existing(acct, tok)
    todo = [(s3, r2) for s3, r2 in pairs if r2 not in existing]
    print(
        f"{len(pairs)} published prediction(s); {len(existing)} already in R2; "
        f"{len(todo)} to upload"
    )
    if args.dry_run:
        for _, r2 in todo[:10]:
            print(f"  would upload {r2}")
        return 0

    def work(pair: tuple[Path, str]) -> tuple[str, bool, str]:
        src, r2_key = pair
        ok, msg = _r2_put(acct, tok, r2_key, src.read_bytes())
        return r2_key, ok, msg

    failed = []
    with ThreadPoolExecutor(args.concurrency) as pool:
        for fut in as_completed([pool.submit(work, p) for p in todo]):
            key, ok, msg = fut.result()
            if not ok:
                failed.append((key, msg))
                print(f"  FAILED {key}: {msg}", file=sys.stderr)
    print(f"uploaded {len(todo) - len(failed)}/{len(todo)}; {len(failed)} failed")
    if failed:
        return 1
    print(f"public prefix: r2://{BUCKET}/{KEY_PREFIX}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
