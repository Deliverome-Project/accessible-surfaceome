"""Command line entry point for the surface-proteome project."""

from __future__ import annotations

import argparse
import json
import logging

from accessible_surfaceome import merge
from accessible_surfaceome.env import load_env


def main(argv: list[str] | None = None) -> None:
    load_env()
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "build",
        help="Run the candidate-universe merge.",
        description=merge.__doc__,
        add_help=False,
    )
    # The v1.0.0 ``agents annotate`` deep-dive (Surface Evidence Compiler ∥
    # Biology Compiler → Synthesizer) was removed — it is deprecated; the
    # production deep-dive is ``surfaceome_v2``, run via
    # ``scripts/surfaceome_v2_annotate.py``. (TODO: repoint a CLI ``annotate``
    # command at the v2 orchestrator if a first-class CLI entry is wanted.)

    bench_parser = subparsers.add_parser(
        "triage-bench",
        help="Run + score variant comparisons (A pure model, B deterministic).",
    )
    bench_sub = bench_parser.add_subparsers(dest="bench_command", required=True)
    bench_sub.add_parser(
        "prepare",
        help="Print the loaded benchmark (named + programmatic OpenCell) for sanity check.",
    )
    bench_run = bench_sub.add_parser(
        "run",
        help="Run one (variant, model) cell across the benchmark.",
    )
    bench_run.add_argument("--variant", required=True, choices=["A", "B"], help="Variant to run.")
    bench_run.add_argument(
        "--model",
        default=None,
        help="Anthropic model id (variant A only). Common: claude-haiku-4-5, claude-sonnet-4-6, claude-opus-4-7.",
    )
    bench_run.add_argument("--gene", default=None, help="Limit to one gene (smoke test).")
    bench_run.add_argument("--force", action="store_true", help="Re-run even if cell record exists.")
    bench_sub.add_parser("report", help="Aggregate per-run records into summary + scatter.")

    args, remainder = parser.parse_known_args(argv)
    if args.command == "build":
        merge.main(remainder)
    elif args.command == "triage-bench":
        _run_triage_bench(args)


def _run_triage_bench(args: argparse.Namespace) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
    from accessible_surfaceome.agents._eval import benchmark, runner, scoring

    if args.bench_command == "prepare":
        rows = benchmark.load_benchmark()
        print(f"Loaded {len(rows)} benchmark rows:")
        for r in rows:
            print(
                f"  {r.gene_symbol:<10} {r.uniprot_acc:<10} "
                f"verdict={r.ground_truth_verdict:<6} signal={r.ground_truth_signal:<22} "
                f"class={r.class_}"
            )
    elif args.bench_command == "run":
        if args.variant == "A" and not args.model:
            raise SystemExit("--model is required for variant A")
        if args.variant == "B" and args.model:
            print("(note: --model is ignored for variant B)")
        cell = runner.cell_spec(args.variant, args.model if args.variant == "A" else None)
        result = runner.run_cell(cell, force=args.force, only_gene=args.gene)
        print(json.dumps(result, indent=2, sort_keys=True))
    elif args.bench_command == "report":
        artifacts = scoring.write_report()
        print(json.dumps({k: str(v) for k, v in artifacts.items()}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
