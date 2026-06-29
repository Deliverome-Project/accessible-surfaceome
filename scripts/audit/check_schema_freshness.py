"""Compute which deep-dive records are out of date vs the current schema.

Writes ``viewer/public/data/schema_status.json`` — the manifest the GeneJump
dropdown's freshness dots read (green = the record validates against the
current ``SurfaceomeRecord`` schema, amber = it doesn't and needs re-running).

This is a **lightweight, temporary migration aid**. Records carry a
``schema_version`` string that wasn't maintained across schema reworks, so it
can't be trusted; structural validation is the real signal. Regenerate after a
schema change or a cohort re-run. Once everything is current you can delete the
manifest (or flip ``SCHEMA_FRESHNESS_DOTS_ENABLED`` in the viewer) to retire
the dots.

    uv run python scripts/audit/check_schema_freshness.py

Source: the public Worker's ``/v1/genes`` index + per-gene records (the exact
set the dropdown shows). Validation runs against the *importable*
``SurfaceomeRecord``, so run this where the current schema lives (e.g. the v2
branch until v2 merges to main).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from accessible_surfaceome.tools._shared.models import SurfaceomeRecord


def _schema_fingerprint() -> str:
    """sha256 of the current SurfaceomeRecord JSON schema (canonical form).
    Inlined (rather than importing _version_guard) so this script runs from any
    worktree — e.g. the v2 branch, until v2 merges to main."""
    canonical = json.dumps(
        SurfaceomeRecord.model_json_schema(), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

DEFAULT_API_BASE = "https://api.deliverome.org/surfaceome"
# The Worker bot-blocks non-browser clients on per-gene routes; present a
# browser UA so the per-gene fetch isn't 403'd.
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124 Safari/537.36"
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _get_json(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--api-base", default=DEFAULT_API_BASE)
    ap.add_argument(
        "--out",
        default=str(_repo_root() / "viewer" / "public" / "data" / "schema_status.json"),
        help="Manifest output path (default: viewer/public/data/schema_status.json).",
    )
    args = ap.parse_args(argv)

    index = _get_json(f"{args.api_base}/v1/genes")
    genes = index.get("genes", []) if isinstance(index, dict) else []
    symbols = sorted(
        g["gene_symbol"] for g in genes if isinstance(g, dict) and g.get("gene_symbol")
    )

    current: list[str] = []
    stale: list[str] = []
    for sym in symbols:
        try:
            rec = _get_json(f"{args.api_base}/v1/genes/{sym}")
        except urllib.error.URLError as exc:  # network / 4xx-5xx
            print(f"  ! {sym}: fetch failed ({exc}); marking stale", file=sys.stderr)
            stale.append(sym)
            continue
        cand = rec.get("record") if isinstance(rec, dict) and "record" in rec else rec
        try:
            SurfaceomeRecord.model_validate(cand)
            current.append(sym)
        except ValidationError:
            stale.append(sym)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": str(SurfaceomeRecord.model_fields["schema_version"].default),
        "schema_fingerprint": _schema_fingerprint(),
        "current": current,
        "stale": stale,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {out}: {len(current)} current, {len(stale)} stale")
    if stale:
        print("  stale:", ", ".join(stale))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
