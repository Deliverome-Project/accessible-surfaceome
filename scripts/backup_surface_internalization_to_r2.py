"""Back up public D1's ``surface_internalization`` table to R2 (durable, restorable).

The literature->D1 sweep republishes each gene's record (INSERT OR REPLACE) to
add the literature track on top of the sequence track. That publish path reads
the existing seq track back first, but a bug there would clobber the seq_*
columns — and the sequence sweep cost real money (opus-5 over 3,357 genes). So
snapshot the whole table to R2 BEFORE any lit run.

Exports every row (all columns incl. the full ``record_json``) as JSONL, so a
restore is a straight re-INSERT (or re-``publish_record``). Uploads to the same
``deliverome-d1-backups`` bucket the D1 backups use, under
``surface_internalization/<UTC>-<n>rows.jsonl`` + a stable ``latest.jsonl``.

    uv run python scripts/backup_surface_internalization_to_r2.py            # export + upload
    uv run python scripts/backup_surface_internalization_to_r2.py --no-upload  # local file only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import REPO_ROOT, load_env

_BUCKET = "deliverome-d1-backups"
_PREFIX = "surface_internalization"
_WRANGLER_DIR = REPO_ROOT  # pinned wrangler lives at the repo root (package.json)


def main(argv: list[str] | None = None) -> int:
    load_env()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--no-upload", action="store_true", help="Write the local JSONL only; skip R2.")
    p.add_argument("--out-dir", default=None, help="Local dir for the dump (default: data/backups/).")
    args = p.parse_args(argv)

    out_dir = Path(args.out_dir) if args.out_dir else REPO_ROOT / "data" / "backups"
    out_dir.mkdir(parents=True, exist_ok=True)

    with D1Client.public() as d1:
        rows = d1.query("SELECT * FROM surface_internalization;", [])
    n = len(rows)
    if n == 0:
        print("WARNING: surface_internalization is EMPTY — nothing to back up.", file=sys.stderr)
        return 1

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    local = out_dir / f"surface_internalization-{stamp}-{n}rows.jsonl"
    with local.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    sha = hashlib.sha256(local.read_bytes()).hexdigest()
    size_mb = local.stat().st_size / 1e6
    print(f"exported {n} rows -> {local}  ({size_mb:.1f} MB, sha256 {sha[:16]}…)")

    if args.no_upload:
        print("--no-upload: local file only. (Note: gitignore data/backups/ — do not commit dumps.)")
        return 0

    # Upload to R2 twice: a timestamped immutable copy + a stable `latest` pointer.
    for key in (f"{_PREFIX}/{local.name}", f"{_PREFIX}/latest.jsonl"):
        cmd = [
            "npx", "--yes", "wrangler", "r2", "object", "put",
            f"{_BUCKET}/{key}", "--file", str(local), "--remote",
        ]
        print(f"uploading -> r2://{_BUCKET}/{key}")
        res = subprocess.run(cmd, cwd=_WRANGLER_DIR, capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stdout[-1500:], file=sys.stderr)
            print(res.stderr[-1500:], file=sys.stderr)
            print(f"ERROR: R2 upload failed for {key} (local dump kept at {local}).", file=sys.stderr)
            return 2
    print(f"OK: backed up {n} rows to r2://{_BUCKET}/{_PREFIX}/ (timestamped + latest.jsonl).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
