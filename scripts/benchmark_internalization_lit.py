"""Score or run the internalization literature benchmark.

Usage:
    # Score the current live D1 records (zero cost — baseline audit)
    uv run python scripts/benchmark_internalization_lit.py --from-d1

    # Score saved JSON records from a local directory
    uv run python scripts/benchmark_internalization_lit.py --from-dir /tmp/int_bench

    # Run the pipeline on the benchmark (or a subset) and score + estimate 3,011-gene cost
    uv run python scripts/benchmark_internalization_lit.py --run --out-dir /tmp/int_bench_v2
    uv run python scripts/benchmark_internalization_lit.py --run --genes TFRC LDLR ERBB2 ADRB2 THBD OR10A3 --web-search-mode adaptive
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from accessible_surfaceome.agents.internalization.benchmark import (
    BenchmarkSummary,
    format_report,
    load_benchmark,
    score_record,
)
from accessible_surfaceome.env import load_env

logger = logging.getLogger("benchmark_internalization_lit")


def main(argv: list[str] | None = None) -> int:
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    p = argparse.ArgumentParser(description=__doc__)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-d1", action="store_true", help="Score live D1 records (no LLM calls).")
    src.add_argument("--from-dir", type=Path, help="Score saved {GENE}.json files from a directory.")
    src.add_argument("--run", action="store_true", help="Run annotate_literature on benchmark genes.")

    p.add_argument("--genes", nargs="+", default=None, help="Filter to specific benchmark genes.")
    p.add_argument("--out-dir", type=Path, default=None, help="Directory to persist records when using --run.")
    p.add_argument("--concurrency", type=int, default=4, help="Parallel workers when using --run.")
    p.add_argument(
        "--web-search-mode",
        choices=("always", "adaptive", "off"),
        default="adaptive",
        help="Web-search policy when using --run (default: adaptive).",
    )
    p.add_argument(
        "--model",
        default="claude-sonnet-5-5",
        help="Select/grade model (default: claude-sonnet-5-5).",
    )
    p.add_argument(
        "--triage-model",
        default="claude-haiku-5-5",
        help="Abstract triage model (default: claude-haiku-5-5).",
    )
    p.add_argument(
        "--web-scout-model",
        default=None,
        help="Optional separate model for web-search scout (e.g. claude-haiku-5-5).",
    )
    p.add_argument(
        "--cohort-size",
        type=int,
        default=3213,
        help="Cohort size for cost projection (default: 3213 L1+Canonical+Likely).",
    )
    args = p.parse_args(argv)

    rows = load_benchmark()
    if args.genes:
        wanted = {g.upper() for g in args.genes}
        rows = [r for r in rows if r.gene_symbol in wanted]
        if not rows:
            raise SystemExit(f"No matching genes in benchmark: {sorted(wanted)}")

    records: dict[str, Any] = {}

    if args.from_d1:
        from accessible_surfaceome.cloud.d1_client import D1Client

        with D1Client.public() as d1:
            d1_rows = d1.query(
                "SELECT gene_symbol, record_json FROM surface_internalization WHERE has_literature = 1;"
            )
        by_sym = {r["gene_symbol"].upper(): json.loads(r["record_json"]) for r in d1_rows}
        for r in rows:
            if r.gene_symbol in by_sym:
                records[r.gene_symbol] = by_sym[r.gene_symbol]

    elif args.from_dir:
        for r in rows:
            fp = args.from_dir / f"{r.gene_symbol}.json"
            if fp.exists():
                records[r.gene_symbol] = json.loads(fp.read_text(encoding="utf-8"))

    elif args.run:
        from accessible_surfaceome.agents._support.client import get_client
        from accessible_surfaceome.agents.internalization.literature_runner import (
            annotate_literature,
        )
        from accessible_surfaceome.tools._shared.cache import Cache
        from accessible_surfaceome.tools._shared.http import CachedHTTP, default_cache_path
        from accessible_surfaceome.tools._shared.ratelimit import default_limiter

        client = get_client()
        shared_cache = Cache(default_cache_path())
        shared_limiter = default_limiter()
        out_dir = args.out_dir
        if out_dir:
            out_dir.mkdir(parents=True, exist_ok=True)

        def _run_one(sym: str):
            with CachedHTTP(shared_cache, shared_limiter) as http:
                rec = annotate_literature(
                    sym,
                    client=client,
                    http=http,
                    persist=bool(out_dir),
                    annotations_dir=out_dir,
                    use_web_search=(args.web_search_mode != "off"),
                    web_search_mode=args.web_search_mode,
                    model=args.model,
                    triage_model=args.triage_model,
                    web_scout_model=args.web_scout_model,
                    triage_concurrency=4,
                )
            return sym, rec

        with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as ex:
            futs = {ex.submit(_run_one, r.gene_symbol): r.gene_symbol for r in rows}
            for fut in as_completed(futs):
                sym = futs[fut]
                try:
                    _, rec = fut.result()
                    records[sym] = rec
                    lit = rec.literature
                    logger.info(
                        "%s -> %s (%s) obs=%d cost=$%.4f",
                        sym,
                        lit.overall_grade if lit else "?",
                        lit.overall_confidence if lit else "?",
                        lit.n_observations if lit else 0,
                        lit.cost_usd if lit else 0.0,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error("%s FAILED: %s", sym, exc)

    summary = BenchmarkSummary()
    for r in rows:
        rec = records.get(r.gene_symbol)
        if rec is None:
            continue
        summary.scores.append(score_record(rec, r))

    print(format_report(summary, cohort_size=args.cohort_size))
    missing = [r.gene_symbol for r in rows if r.gene_symbol not in records]
    if missing:
        print(f"\nNot scored (absent from source): {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
