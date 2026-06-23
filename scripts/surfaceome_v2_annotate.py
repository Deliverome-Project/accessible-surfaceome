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
from accessible_surfaceome.cloud.harvested_paper import (
    ensure_schema as ensure_harvested_paper_schema,
    harvested_papers_from_dual,
    publish_harvested_papers,
)
from accessible_surfaceome.cloud.intermediates import publish_intermediates
from accessible_surfaceome.cloud.surface_annotation import publish_record
from accessible_surfaceome.env import load_env
from accessible_surfaceome.tools._shared.models import SurfaceomeRecord


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
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Write the assembled record to data/annotations/{symbol}.json "
        "(default on; --no-persist to skip).",
    )
    parser.add_argument(
        "--publish",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="After a valid record, publish it to the viewer snapshot "
        "(viewer/public/data/surfaceome/{symbol}.json) and public D1 so the "
        "Worker + viewer serve it immediately (default on; --no-publish to "
        "skip). The D1 push auto-skips with a warning when CLOUDFLARE_* env "
        "vars are absent.",
    )
    parser.add_argument(
        "--checkpoint",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Read mid-gene PTS checkpoint from .runs/_phase_checkpoint/ on "
            "launch (default on; --no-checkpoint forces a fresh PTS dual "
            "even when a checkpoint exists). Checkpoints save the ~$1.35 "
            "PTS spend when an annotate is restarted mid-gene after a "
            "builder/synth failure. Write is always on — only the read is "
            "guarded by this flag, so a forced re-run still leaves a "
            "checkpoint for the next attempt."
        ),
    )
    parser.add_argument(
        "--cohort-run-id",
        default=None,
        help=(
            "Sweep tag stamped on the published intermediates / "
            "surface_annotation row. None for ad-hoc single-gene runs; set "
            "by the cohort sweep driver to a per-sweep UUID."
        ),
    )
    args = parser.parse_args(argv)

    print(f"=== surfaceome_v2 annotate: {args.gene} ===", flush=True)
    result = annotate(
        args.gene,
        persist=args.persist,
        read_phase_checkpoint=args.checkpoint,
    )

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

    # Publish-by-default: a valid record goes to public D1 so the Worker
    # (and viewer through it) serves the fresh record immediately. The
    # viewer no longer reads from a per-gene JSON fallback — D1 is the
    # only authoritative source. The D1 push auto-skips with a warning
    # when CLOUDFLARE_* env vars are absent, so CI / offline runs still
    # succeed. Opt out with --no-publish.
    publish_result = None
    if args.publish and result.record is not None:
        publish_result = publish_record(
            result.record,
            push_to_d1=True,
            cohort_run_id=args.cohort_run_id,
        )

    # Intermediates go to the PRIVATE surfaceome_agents D1, not local disk.
    # The previous behavior was to write
    # ``.runs/surfaceome_v2_{gene}.intermediates.json``, which is lost the
    # moment a Modal container shuts down — so every $2-3 deep-dive run
    # would silently throw away its post-mortem trail. Pushing to D1 keeps
    # the diagnostic blob (A1/A2 ledgers, builder raw outputs, synthesizer
    # raw_json) queryable from any worktree forever. Independent of
    # ``publish_record`` — a failed annotate that produced no valid
    # ``result.record`` still benefits from having its intermediates
    # captured (in fact, that's the highest-value case). Skips with a
    # warning on a missing CLOUDFLARE_* env or a >900KB blob; never
    # raises and never blocks the publish path.
    # Per-paper harvested_paper rows for analytics (which papers did this
    # deep-dive consider, what bucket each landed in, which fetch tier
    # produced the body). Opt-in via --cohort-run-id — ad-hoc single-gene
    # runs without a sweep tag stay out of the table. Soft-skips when
    # CLOUDFLARE_* env vars are missing (same pattern as publish_record /
    # publish_intermediates) so offline runs still succeed.
    if args.publish and args.cohort_run_id and result.dual is not None:
        try:
            ensure_harvested_paper_schema()
            harvested = harvested_papers_from_dual(
                result.dual,
                run_id=args.cohort_run_id,
                gene_symbol=result.gene,
            )
            if harvested:
                n = publish_harvested_papers(harvested)
                logging.info(
                    "harvested_paper: wrote %d rows (run_id=%s gene=%s)",
                    n, args.cohort_run_id, result.gene,
                )
        except Exception as exc:  # noqa: BLE001
            logging.warning(
                "harvested_paper publish failed (gene=%s): %s — continuing",
                result.gene, exc,
            )

    intermediates_result = None
    if args.publish and result.intermediates:
        # Use the schema_version from the record if it validated, else
        # fall back to the in-tree default so the audit row still pins
        # to a real version string (the run failed under THIS schema).
        sv = (
            result.record.schema_version
            if result.record is not None
            else SurfaceomeRecord.model_fields["schema_version"].default
        )
        intermediates_result = publish_intermediates(
            gene_symbol=result.gene,
            intermediates=result.intermediates,
            schema_version=sv,
            record_valid=result.record is not None,
            cohort_run_id=args.cohort_run_id,
            failure_mode=result.failure_mode,
        )

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
    print(f"record_out:       {record_out}")
    print(f"meta_out:         {meta_out}")
    if intermediates_result is not None:
        if intermediates_result.pushed:
            print(
                f"intermediates:    private D1 row "
                f"({intermediates_result.intermediates_bytes} bytes)"
            )
        else:
            print(
                f"intermediates:    SKIPPED — {intermediates_result.skipped_reason}"
            )
    if result.annotation_path is not None:
        print(f"persisted:   {result.annotation_path}")
    if publish_result is not None:
        if publish_result.skipped_reason:
            print(f"published:   D1 push SKIPPED — {publish_result.skipped_reason}")
        else:
            print(
                f"published:   D1 push={'OK' if publish_result.d1_written else 'FAILED'}"
                + (
                    f" (dropped stale {publish_result.stale_versions_dropped})"
                    if publish_result.stale_versions_dropped
                    else ""
                )
            )
    return 0 if result.record is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
