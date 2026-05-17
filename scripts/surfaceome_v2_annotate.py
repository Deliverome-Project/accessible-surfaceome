"""End-to-end driver for the v2 annotate pipeline.

Usage:

    uv run python scripts/surfaceome_v2_annotate.py HGNC:4526
    uv run python scripts/surfaceome_v2_annotate.py GPR75

Runs:
1. plan-trim-select dual (warm cache → cheap HTTP).
2. 9 block-builders + B synthesizer.
3. Writes ``.runs/surfaceome_v2_<gene>.json`` (the SurfaceomeRecord dump,
   or the error meta when assembly failed) and a per-builder
   ``.runs/surfaceome_v2_<gene>.meta.json``.
4. Prints summary table: cost per stage, builder-level cost + block
   counts, schema-validation pass/fail.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from accessible_surfaceome.agents.surfaceome_v2 import annotate
from accessible_surfaceome.agents.surfaceome_v2.orchestrator import write_summary_meta
from accessible_surfaceome.env import load_env


def main(argv: list[str] | None = None) -> int:
    load_env()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("gene", help="Gene symbol / HGNC ID / UniProt acc")
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Write the assembled record to data/annotations/{symbol}.json",
    )
    args = parser.parse_args(argv)

    print(f"=== surfaceome_v2 annotate: {args.gene} ===", flush=True)
    result = annotate(args.gene, persist=args.persist)

    safe_id = result.gene.replace(":", "_")
    runs = Path(".runs")
    runs.mkdir(exist_ok=True)
    record_out = runs / f"surfaceome_v2_{safe_id}.json"
    timing_payload = [t.as_dict() for t in result.timing]
    # Two distinct numbers:
    # * ``total_elapsed_s`` = end-to-end wall clock (max(end) - min(start)).
    #   This is what users want to see for "how long did this gene take".
    # * ``total_step_seconds`` = sum of every step's elapsed_s. With
    #   concurrency this can be > wall clock by a factor equal to the
    #   achieved parallelism; it's the right number for cost-attribution
    #   spreadsheets but not for runtime reporting.
    from datetime import datetime as _dt
    def _ts(s: str) -> float:
        return _dt.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    if result.timing:
        starts = [_ts(t.started_at) for t in result.timing]
        ends = [_ts(t.started_at) + t.elapsed_s for t in result.timing]
        wall_clock = round(max(ends) - min(starts), 3)
    else:
        wall_clock = 0.0
    total_step_seconds = round(sum(t.elapsed_s for t in result.timing), 3)
    total_elapsed = wall_clock
    if result.record is not None:
        # Merge timing into the record dump so the HTML viewer can render
        # Section 0.5 without an extra file. SurfaceomeRecord doesn't carry
        # a ``timing`` field, so we serialize the model first then add the
        # key — readers that don't expect timing simply ignore the extra
        # top-level field.
        record_dict = result.record.model_dump(mode="json")
        record_dict["timing"] = timing_payload
        record_dict["total_elapsed_s"] = total_elapsed
        record_dict["total_step_seconds"] = total_step_seconds
        record_out.write_text(json.dumps(record_dict, indent=2))
    else:
        record_out.write_text(
            json.dumps(
                {
                    "gene": result.gene,
                    "error": result.error,
                    "blocks_used": result.blocks_used,
                    "timing": timing_payload,
                    "total_elapsed_s": total_elapsed,
                    "total_step_seconds": total_step_seconds,
                },
                indent=2,
            )
        )

    meta_out = write_summary_meta(result)

    print()
    print(f"gene:        {result.gene}")
    print(f"record:      {'VALID' if result.record is not None else 'INVALID'}")
    if result.error is not None:
        print(f"error:       {result.error}")
    print()
    print("--- block counts ---")
    for k, v in sorted(result.blocks_used.items()):
        print(f"  {k:35s} {v}")
    print()
    print("--- cost breakdown ---")
    print(f"  plan-trim-select dual:    ${result.plan_trim_select_cost_usd:.4f}")
    for label, bu in sorted(result.builder_usage.items()):
        print(
            f"  builder {label:30s} ${bu.cost_usd:.4f}  "
            f"({bu.n_calls} call{'s' if bu.n_calls != 1 else ''})"
        )
    print(f"  builders total:           ${result.builders_cost_usd:.4f}")
    print(f"  synthesizer:              ${result.synthesizer_cost_usd:.4f}")
    print(f"  TOTAL:                    ${result.total_cost_usd:.4f}")
    print()
    if result.timing:
        speedup = (total_step_seconds / total_elapsed) if total_elapsed > 0 else 0.0
        print(
            f"--- step timing (wall clock {total_elapsed:.1f}s; "
            f"sum-of-steps {total_step_seconds:.1f}s; parallelism {speedup:.1f}x; "
            f"top 5 slowest) ---"
        )
        slowest = sorted(result.timing, key=lambda t: t.elapsed_s, reverse=True)[:5]
        for t in slowest:
            print(
                f"  {t.elapsed_s:7.2f}s  {t.phase:24s} {t.step_name}"
                + (
                    f"  ({t.n_items} items)" if t.n_items is not None else ""
                )
            )
        print()
    print(f"record_out:  {record_out}")
    print(f"meta_out:    {meta_out}")
    if result.annotation_path is not None:
        print(f"persisted:   {result.annotation_path}")
    return 0 if result.record is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
