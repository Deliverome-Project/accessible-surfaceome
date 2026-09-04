"""Refresh the canonical SurfaceBench TSV from the public D1 mirror.

Lineage (per CLAUDE.md "Final-figure data flow"):

    private D1 (triage_run)
      ─sync_public_d1.py──▶  public D1 (triage_run_public)
                              │
                              └─export_mainbench_to_tsv.py─▶
                                  data/processed/triage_bench/
                                    mainbench_canonical_v2.tsv
                                  │
                                  └─raw.githubusercontent.com─▶
                                      figure scripts + published gists

Public D1 is the citable source of truth (the same data the public Worker
serves), so this script reads from there rather than private D1. The
committed TSV is what figures + gists pull, pinned to a commit SHA at
publication for stable citation (pre-publication today; Zenodo DOIs
will replace the raw-GitHub URLs at submission time).

Output: ``data/processed/triage_bench/mainbench_canonical_v2.tsv``
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

DEFAULT_RUN_ID = "mainbench_canonical_v2"
DEFAULT_OUT = REPO_ROOT / "data/processed/triage_bench/mainbench_canonical_v2.tsv"

# v2 figure TSV is MAJORITY-COLLAPSED: one row per (gene, model,
# prompt_variant) with the majority verdict over the cell's 2-3 valid
# replicates, n_reps + agreement, and SUMMED token/cost/latency (a real
# aggregate of work done — never zeroed). Representative reason/confidence
# from a winning-side replicate.
COLUMNS = [
    "gene_symbol",
    "model",
    "prompt_variant",
    "predicted_verdict",
    "predicted_reason",
    "predicted_confidence",
    "n_reps",
    "majority_agreement",
    "prompt_tokens",
    "completion_tokens",
    "cache_creation_tokens",
    "cache_read_tokens",
    "n_web_searches",
    "cost_usd",
    "latency_s",
]

# Raw per-replicate columns pulled from D1 before collapsing.
_RAW_COLUMNS = [
    "gene_symbol", "model", "prompt_variant", "replicate",
    "predicted_verdict", "predicted_reason", "predicted_confidence",
    "prompt_tokens", "completion_tokens", "cache_creation_tokens",
    "cache_read_tokens", "n_web_searches", "cost_usd", "latency_s",
]


def _surface_vote(verdict):
    if verdict in ("yes", "contextual"):
        return True
    if verdict == "no":
        return False
    return None


def _collapse_to_majority(raw_rows):
    """One row per (gene, model, prompt_variant); majority verdict over the
    cell's valid-verdict reps; numeric columns summed across reps."""
    from collections import Counter, defaultdict
    cells = defaultdict(list)
    for r in raw_rows:
        cells[(r["gene_symbol"], r["model"], r["prompt_variant"])].append(r)
    out, dropped, ties = [], [], []
    for (gene, model, variant), reps in cells.items():
        valid = [r for r in reps if _surface_vote(r["predicted_verdict"]) is not None]
        if not valid:
            dropped.append((gene, model, variant))
            continue
        votes = Counter(_surface_vote(r["predicted_verdict"]) for r in valid)
        ranked = votes.most_common()
        if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
            ties.append((gene, model, variant))
        win_side = ranked[0][0]
        win_reps = [r for r in valid if _surface_vote(r["predicted_verdict"]) == win_side]
        rep_verdict = Counter(r["predicted_verdict"] for r in win_reps).most_common(1)[0][0]
        representative = next(r for r in win_reps if r["predicted_verdict"] == rep_verdict)

        def _sum(col, _reps=reps):
            total = sum(float(r.get(col) or 0) for r in _reps)
            return total if col in ("cost_usd", "latency_s") else int(total)

        out.append({
            "gene_symbol": gene, "model": model, "prompt_variant": variant,
            "predicted_verdict": rep_verdict,
            "predicted_reason": representative.get("predicted_reason"),
            "predicted_confidence": representative.get("predicted_confidence"),
            "n_reps": len(valid),
            "majority_agreement": round(len(win_reps) / len(valid), 3),
            "prompt_tokens": _sum("prompt_tokens"),
            "completion_tokens": _sum("completion_tokens"),
            "cache_creation_tokens": _sum("cache_creation_tokens"),
            "cache_read_tokens": _sum("cache_read_tokens"),
            "n_web_searches": _sum("n_web_searches"),
            "cost_usd": round(_sum("cost_usd"), 6),
            "latency_s": round(_sum("latency_s"), 3),
        })
    if dropped:
        print(f"WARNING: {len(dropped)} cell(s) dropped — no valid verdict (e.g. {dropped[0]}).")
    if ties:
        print(f"WARNING: {len(ties)} TIED cell(s); arbitrary side chosen (e.g. {ties[0]}).")
    out.sort(key=lambda r: (r["model"], r["prompt_variant"], r["gene_symbol"]))
    return out


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
    ap.add_argument("--replicate", type=int, default=None,
                    help="Filter to a single replicate. Default None = ALL replicates, "
                         "majority-collapsed per cell (the v2 canonical shape). Pass an int "
                         "for the historical single-replicate shape.")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="output TSV path")
    ap.add_argument("--per-rep", action="store_true",
                    help="Emit one row per (gene, model, variant, replicate) — the "
                         "un-collapsed per-replicate shape — to mainbench_replicates_v2.tsv "
                         "(default --out when --per-rep is set). Drives the SEM + "
                         "individual-replicate-point overlays on the bar figures. Skips "
                         "majority collapse; the augment script adds truth + is_match.")
    ap.add_argument("--prefer-fix-run", default=None,
                    help="Optional run_id whose rows should override --run-id for matching "
                         "(gene_symbol, model, prompt_variant, replicate) tuples. Use this "
                         "to fold a `*__resolver_v3_fix` correction run into the export "
                         "without modifying the original sweep's rows. See the "
                         "'run_id conventions' table in CLAUDE.md.")
    args = ap.parse_args()

    if args.replicate is not None:
        sql_base = (
            f"SELECT {', '.join(_RAW_COLUMNS)} FROM triage_run_public "
            "WHERE run_id = ? AND replicate = ? "
            "ORDER BY model, prompt_variant, gene_symbol;"
        )
        base_rows = _query_public(sql_base, [args.run_id, args.replicate])
    else:
        sql_base = (
            f"SELECT {', '.join(_RAW_COLUMNS)} FROM triage_run_public "
            "WHERE run_id = ? "
            "ORDER BY model, prompt_variant, gene_symbol, replicate;"
        )
        base_rows = _query_public(sql_base, [args.run_id])

    if args.prefer_fix_run:
        # Fold the fix-run's rows in, preferring them over the
        # original where (model, prompt_variant, gene_symbol) match.
        # D1 doesn't make a cross-run UPSERT one-shot easy, so we
        # COALESCE in Python: pull the fix rows, key on the tuple,
        # replace originals.
        fix_params = (
            [args.prefer_fix_run, args.replicate]
            if args.replicate is not None else [args.prefer_fix_run]
        )
        fix_rows = _query_public(sql_base, fix_params)

        def key_of(r: dict) -> tuple[str, str, str, int]:
            return (r["model"], r["prompt_variant"], r["gene_symbol"],
                    int(r.get("replicate") or 0))

        fix_by_key = {key_of(r): r for r in fix_rows}
        merged: list[dict] = []
        for r in base_rows:
            merged.append(fix_by_key.get(key_of(r), r))
        # Unmatched fix rows (no matching key in the cohort) are SKIPPED,
        # not appended — a fix run is scoped to its parent cohort, so any
        # rows that don't intersect mean the wrong --prefer-fix-run was
        # passed (e.g. a genome-cohort fix run against the 147-row main
        # bench). Bloating the export with off-cohort rows would silently
        # change the figures' denominator; the loud warning lets the
        # operator notice + correct the invocation.
        original_keys = {key_of(r) for r in base_rows}
        unmatched = [r for r in fix_rows if key_of(r) not in original_keys]
        replaced = sum(1 for r in base_rows if key_of(r) in fix_by_key)
        msg = (
            f"Merged {len(fix_rows):,} fix-run rows from {args.prefer_fix_run!r}; "
            f"{replaced} rows replaced"
        )
        if unmatched:
            msg += (
                f"; SKIPPED {len(unmatched)} fix rows with no matching cohort "
                f"row (e.g. {unmatched[0]['gene_symbol']}). Likely cause: the "
                f"fix run was scoped to a different cohort than --run-id "
                f"{args.run_id!r}. If you meant to export the fix run's "
                f"parent cohort, pass --run-id <parent> too."
            )
        print(msg)
        rows = merged
    else:
        rows = base_rows

    from pathlib import Path
    if args.per_rep:
        # Per-replicate shape: one row per (gene, model, variant, replicate),
        # no collapse. Fieldnames = the raw per-rep columns. Default output
        # is the replicates TSV unless --out was overridden.
        out_cols = _RAW_COLUMNS
        if args.out == str(DEFAULT_OUT):
            out_path = REPO_ROOT / "data/processed/triage_bench/mainbench_replicates_v2.tsv"
        else:
            out_path = Path(args.out) if args.out.startswith("/") else REPO_ROOT / args.out
        rows.sort(key=lambda r: (r["model"], r["prompt_variant"],
                                 r["gene_symbol"], int(r.get("replicate") or 0)))
    else:
        # Majority-collapse unless a single replicate was explicitly requested.
        if args.replicate is None:
            rows = _collapse_to_majority(rows)
        out_cols = COLUMNS
        out_path = Path(args.out) if args.out.startswith("/") else REPO_ROOT / args.out

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # ``lineterminator="\n"`` (not csv's RFC-4180 default of "\r\n") matches
    # the on-repo TSV's line endings, so a re-export is byte-identical when
    # the underlying D1 rows haven't changed. The gist + figure consumers
    # don't care, but byte-equality keeps `git diff` quiet on cosmetic-only
    # re-runs.
    with open(out_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=out_cols, delimiter="\t",
                           lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    rel = out_path.relative_to(REPO_ROOT) if str(out_path).startswith(str(REPO_ROOT)) else out_path
    print(f"Wrote {rel}  ({len(rows):,} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
