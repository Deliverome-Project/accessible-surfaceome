"""Refresh the canonical SurfaceBench TSV from the public D1 mirror.

Lineage (per CLAUDE.md "Final-figure data flow"):

    private D1 (triage_run)
      ─sync_public_d1.py──▶  public D1 (triage_run_public)
                              │
                              └─export_mainbench_to_tsv.py─▶
                                  data/processed/triage_bench/
                                    mainbench_canonical_v1.tsv
                                  │
                                  └─raw.githubusercontent.com─▶
                                      figure scripts + published gists

Public D1 is the citable source of truth (the same data the public Worker
serves), so this script reads from there rather than private D1. The
committed TSV is what figures + gists pull, pinned to a commit SHA at
publication for stable citation (pre-publication today; Zenodo DOIs
will replace the raw-GitHub URLs at submission time).

Output: ``data/processed/triage_bench/mainbench_canonical_v1.tsv``
(LFS-exempted via ``.gitattributes`` so the raw URL serves text, not a
pointer).

Usage::

    uv run python scripts/export_mainbench_to_tsv.py
    uv run python scripts/export_mainbench_to_tsv.py --run-id genome_full_sonnet_ncbi_v1

Requires CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID +
CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID in the environment.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from typing import Any

import httpx

from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

load_env()

DEFAULT_RUN_ID = "mainbench_canonical_v1"
DEFAULT_OUT = REPO_ROOT / "data/processed/triage_bench/mainbench_canonical_v1.tsv"

# Same 14 columns as `/v1/triage/export.tsv` so the on-repo TSV and the
# Worker endpoint are byte-identical. Figure scripts pin to this shape.
COLUMNS = [
    "gene_symbol",
    "model",
    "prompt_variant",
    "replicate",
    "predicted_verdict",
    "predicted_reason",
    "predicted_confidence",
    "prompt_tokens",
    "completion_tokens",
    "cache_creation_tokens",
    "cache_read_tokens",
    "n_web_searches",
    "cost_usd",
    "latency_s",
]


def _query_public(sql: str, params: list[Any]) -> list[dict[str, Any]]:
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    db = os.environ.get("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "").strip()
    missing = [
        k for k, v in [
            ("CLOUDFLARE_ACCOUNT_ID", acct),
            ("CLOUDFLARE_API_TOKEN", token),
            ("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", db),
        ] if not v
    ]
    if missing:
        raise SystemExit(
            "Missing env vars: " + ", ".join(missing)
            + ". Add them to your .env; see .env.example."
        )
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{acct}"
        f"/d1/database/{db}/query"
    )
    resp = httpx.post(
        url,
        json={"sql": sql, "params": params},
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"D1 error: {data}")
    result = data.get("result")
    if isinstance(result, list) and result:
        return list(result[0].get("results") or [])
    if isinstance(result, dict):
        return list(result.get("results") or [])
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-id", default=DEFAULT_RUN_ID,
                    help=f"triage_run_public.run_id to export (default: {DEFAULT_RUN_ID})")
    ap.add_argument("--replicate", type=int, default=1,
                    help="filter to a single replicate (default: 1 — matches the historical TSV shape)")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="output TSV path")
    args = ap.parse_args()

    sql = (
        f"SELECT {', '.join(COLUMNS)} FROM triage_run_public "
        "WHERE run_id = ? AND replicate = ? "
        "ORDER BY model, prompt_variant, gene_symbol;"
    )
    rows = _query_public(sql, [args.run_id, args.replicate])
    out_path = REPO_ROOT / args.out if not args.out.startswith("/") else args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    rel = out_path.relative_to(REPO_ROOT) if str(out_path).startswith(str(REPO_ROOT)) else out_path
    print(f"Wrote {rel}  ({len(rows):,} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
