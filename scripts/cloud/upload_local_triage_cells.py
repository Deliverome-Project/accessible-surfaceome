"""Upload saved per-cell triage JSON records to D1 after the fact.

``scripts/triage_runner.py --d1`` streams cells into D1 as they finish. A
sweep run without ``--d1`` (a local exploration that later turns out to be
worth publishing) leaves only the per-cell JSON under ``--out-root``. This
script pushes those records through the same :class:`D1RunSink`, so the rows
are byte-for-byte what a live ``--d1`` run would have written, and the sink's
natural-key dedup makes a re-run a no-op.

Refusal fallback. When a resolver-context variant is refused, the runner
retries with the ``naive`` prompt and, if that answers, persists the naive
record in place of the refused one (``_run_one_with_retry``). On a benchmark
that would plant a stray ``naive`` cell for a model that was never run naive.
Every such record found next to the requested variant is uploaded instead as
a refusal of the requested variant (null verdict, ``error='refusal'``), which
is what the benchmark actually measured. Its token counts are unknown (the
refused attempt's usage was not kept) and are left at zero.

Usage — dry run by default, ``--execute`` to write:

    uv run python scripts/cloud/upload_local_triage_cells.py \\
        --cells-dir <out-root> --model claude-opus-5-5 --variant ncbi \\
        --run-id mainbench_canonical_v2 --publish-public --execute

``--as-variant`` relabels the uploaded rows, for a sweep run with a variant
that was later renamed (e.g. an effort experiment saved as ``ncbi``).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from accessible_surfaceome.env import load_env

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCH = ROOT / "data/eval/triage_benchmark_v1.tsv"


def _model_dir(model: str) -> str:
    """The runner writes ``claude-opus-5-5`` cells under ``opus-5-5/``."""
    return model.removeprefix("claude-")


def load_records(cells_dir: Path, model: str, variant: str, as_variant: str) -> list[dict]:
    base = cells_dir / _model_dir(model)
    records = []
    for f in sorted((base / variant).glob("*_run*.json")):
        rec = json.loads(f.read_text())
        if rec.get("api_stop_reason") == "refusal":
            rec["error"] = "refusal"
        rec["variant"] = as_variant
        records.append(rec)
    if variant != "naive":
        for f in sorted((base / "naive").glob("*_run*.json")):
            rec = json.loads(f.read_text())
            records.append({
                **rec,
                "variant": as_variant,
                "predicted_verdict": None, "predicted_reason": None,
                "predicted_confidence": None, "predicted_key_uncertainty": None,
                "verdict_reasoning": "", "correct": False,
                "prompt_tokens": 0, "completion_tokens": 0,
                "cache_creation_tokens": 0, "cache_read_tokens": 0,
                "n_web_searches": 0, "cost_usd": 0.0,
                "error": "refusal", "raw_text": "", "user_message": "",
                "api_response_id": None, "api_stop_reason": "refusal",
                "search_log": [],
            })
    return records


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cells-dir", required=True, type=Path, help="The sweep's --out-root.")
    ap.add_argument("--model", required=True)
    ap.add_argument("--variant", required=True, help="Variant directory the sweep wrote.")
    ap.add_argument("--as-variant", default=None, help="Upload under this variant label instead.")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--bench-tsv", type=Path, default=DEFAULT_BENCH)
    ap.add_argument("--publish-public", action="store_true",
                    help="Also write each row to triage_run_public (whitelisted columns).")
    ap.add_argument("--execute", action="store_true", help="Write to D1 (default: dry run).")
    args = ap.parse_args()

    records = load_records(args.cells_dir, args.model, args.variant, args.as_variant or args.variant)
    n_refused = sum(r.get("error") == "refusal" for r in records)
    n_null = sum(r.get("predicted_verdict") is None for r in records)
    print(f"{args.model} {args.variant} -> {args.as_variant or args.variant}: "
          f"{len(records)} cells, {n_refused} refusals, {n_null} without a verdict")
    if not args.execute:
        print("Dry run; pass --execute to write.")
        return

    load_env()
    from accessible_surfaceome.cloud.triage_upload import D1RunSink

    failed = 0
    with D1RunSink(run_id=args.run_id, bench_tsv=args.bench_tsv,
                   publish_public=args.publish_public) as sink:
        for rec in records:
            if not sink.insert(rec):
                failed += 1
    print(f"inserted {len(records) - failed}/{len(records)} into run_id={args.run_id}")
    if failed:
        raise SystemExit(f"{failed} records failed to insert; re-run to retry (idempotent).")


if __name__ == "__main__":
    main()
