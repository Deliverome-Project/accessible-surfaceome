#!/usr/bin/env python
"""One-time, content-preserving backfill of the SURFACE-Bind citation.

Records written before the SURFACE-Bind first-author fix carry the
mislabeled "Marchand 2026" source/attribution. The correct lead author is
Balbi PEM (verified: PMID 41604262 == DOI 10.1073/pnas.2506269123). This
brings the already-stored records in line with the corrected model default
in ``SurfaceBindFeatures``.

WHY A STRING SWAP, NOT A RE-UPLOAD: this swaps ONLY the two citation
substrings inside each record and leaves every other byte intact. It
therefore cannot clobber a record's content — in particular it preserves
runs published earlier today, which a whole-record re-upload
(``upload_viewer_snapshots_to_d1.py``) could overwrite with a possibly
staler on-disk snapshot. Both the disk snapshots and the D1 ``annotation_json``
blob are written with ``json.dumps(ensure_ascii=True)``, so © / — are
stored as ``\\u00a9`` / ``\\u2014`` in the JSON *text*; we match that exact
representation.

Idempotent (a record without the old string is skipped) and dry-run by
default.

    uv run python scripts/backfill_surface_bind_attribution.py            # dry-run
    uv run python scripts/backfill_surface_bind_attribution.py --execute  # write
"""
from __future__ import annotations

import argparse
import json

import httpx

from accessible_surfaceome.cloud.surface_annotation import (
    _post,
    _public_config_from_env,
)
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

# Build the (old, new) text pairs that appear in the stored JSON *text*.
# Source is plain ASCII. The attribution contains © / —; rather than
# hand-type the escaped form, we let json.dumps render it the SAME way the
# records were written (ensure_ascii=True → © / —), so the match
# is exact regardless of this file's own encoding. We include both that
# escaped form (how it is actually stored, on disk and in D1) and the
# raw-UTF-8 form as a belt-and-suspenders fallback.
_OLD_ATTR = "© Marchand, Khakzad, Correia et al. — EPFL / Inria / Novo Nordisk"
_NEW_ATTR = "© Balbi et al., Correia lab — EPFL / Inria / Novo Nordisk"


def _stored(s: str) -> str:
    """Exact text ``json.dumps(ensure_ascii=True)`` writes for ``s`` (quotes stripped)."""
    return json.dumps(s)[1:-1]


REPLACEMENTS = [
    (
        "SURFACE-Bind v1 (Marchand 2026 PNAS)",
        "SURFACE-Bind v1 (Balbi et al. 2026 PNAS)",
    ),
    (_stored(_OLD_ATTR), _stored(_NEW_ATTR)),  # escaped form — how it is stored
    (_OLD_ATTR, _NEW_ATTR),  # raw-UTF-8 fallback
]

DISK_DIRS = [
    REPO_ROOT / "viewer" / "public" / "data" / "surfaceome",
    REPO_ROOT / "data" / "annotations",
]


def patch_text(text: str) -> tuple[str, int]:
    """Return (new_text, num_substrings_replaced)."""
    n = 0
    for old, new in REPLACEMENTS:
        if old in text:
            n += text.count(old)
            text = text.replace(old, new)
    return text, n


def backfill_disk(*, execute: bool) -> int:
    touched = 0
    for d in DISK_DIRS:
        if not d.exists():
            print(f"  (skip, missing) {d}")
            continue
        for f in sorted(d.glob("*.json")):
            new_text, n = patch_text(f.read_text())
            if n == 0:
                continue
            json.loads(new_text)  # sanity: still valid JSON
            touched += 1
            print(
                f"  {'patched' if execute else 'would patch'} "
                f"{f.relative_to(REPO_ROOT)} ({n} field(s))"
            )
            if execute:
                f.write_text(new_text)
    return touched


def backfill_d1(*, execute: bool) -> int:
    cfg = _public_config_from_env()
    if cfg is None:
        print("  (skip) public D1 creds not set (CLOUDFLARE_*)")
        return 0
    touched = 0
    with httpx.Client(timeout=60) as client:
        rows = _post(
            cfg,
            "SELECT gene_symbol, schema_version, annotation_json "
            "FROM surface_annotation",
            [],
            client=client,
        )["result"][0]["results"]
        for r in rows:
            new_text, n = patch_text(r["annotation_json"])
            if n == 0:
                continue
            json.loads(new_text)  # sanity
            touched += 1
            print(
                f"  {'patched' if execute else 'would patch'} D1 "
                f"{r['gene_symbol']}@{r['schema_version']} ({n} field(s))"
            )
            if execute:
                # Touch ONLY annotation_json — annotated_at and every other
                # column (and the rest of the blob) are left exactly as the
                # original run wrote them.
                _post(
                    cfg,
                    "UPDATE surface_annotation SET annotation_json = ? "
                    "WHERE gene_symbol = ? AND schema_version = ?",
                    [new_text, r["gene_symbol"], r["schema_version"]],
                    client=client,
                )
    return touched


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Backfill SURFACE-Bind citation (Marchand → Balbi)."
    )
    ap.add_argument(
        "--execute", action="store_true", help="write changes (default: dry-run)"
    )
    ap.add_argument("--skip-disk", action="store_true", help="don't touch disk files")
    ap.add_argument("--skip-d1", action="store_true", help="don't touch D1")
    args = ap.parse_args()
    load_env()

    mode = "EXECUTE" if args.execute else "DRY-RUN"
    print(f"=== SURFACE-Bind attribution backfill [{mode}] ===")
    print("disk (viewer snapshots + data/annotations):")
    disk = 0 if args.skip_disk else backfill_disk(execute=args.execute)
    if args.skip_disk:
        print("  (skipped)")
    print("public D1 surface_annotation:")
    d1 = 0 if args.skip_d1 else backfill_d1(execute=args.execute)
    if args.skip_d1:
        print("  (skipped)")

    print(f"\n{'patched' if args.execute else 'would patch'}: {disk} disk file(s), {d1} D1 row(s)")
    if not args.execute:
        print("(dry-run — re-run with --execute to apply)")


if __name__ == "__main__":
    main()
