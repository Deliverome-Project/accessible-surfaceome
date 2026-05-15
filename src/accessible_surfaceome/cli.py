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
    agents_parser = subparsers.add_parser(
        "agents", help="Run the v1.0.0 deep-dive pipeline (A1 ∥ A2 → B → assemble)."
    )
    agents_sub = agents_parser.add_subparsers(dest="agents_command", required=True)
    annotate = agents_sub.add_parser(
        "annotate", help="Run a one-off annotation session for a single gene."
    )
    annotate.add_argument("gene", help="Gene symbol or UniProt accession (e.g. KAAG1, Q9UBP8).")
    # ``sync`` (Managed-Agents create/update), ``audit-corpus`` (v0.5.1
    # ``surface_annotator.audit``), and ``view`` (v0.5.1 record viewer) were
    # retired alongside the surface_annotator/ directory when the v1.0.0
    # 3-agent pipeline replaced the single Managed Agent. v1.0.0 runs on the
    # Messages API — no remote agent registry to sync; viewer-style
    # rendering moved to the per-agent ``render_html.py`` modules.

    # The legacy `triage` subcommand (Managed Agents one-off via
    # `client.beta.sessions`) was retired because Anthropic's
    # ``beta.agents`` API doesn't expose ``cache_control`` blocks — at
    # genome scale that's roughly $200 of avoidable cost per sweep
    # relative to the direct ``messages.create`` runner. For sweeps,
    # use ``scripts/triage_subbench_runner.py``; for benchmark eval,
    # use ``accessible-surfaceome triage-bench`` below.

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
    elif args.command == "agents":
        _run_agents(args)
    elif args.command == "triage-bench":
        _run_triage_bench(args)


def _run_agents(args: argparse.Namespace) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")

    if args.agents_command == "annotate":
        # v1.0.0 deep-dive pipeline: dispatch A1 ∥ A2 → B → assemble via
        # ``surfaceome_v1.annotate``. Output JSON carries per-agent counters
        # and the assembled-record path.
        from accessible_surfaceome.agents import surfaceome_v1

        result = surfaceome_v1.annotate(args.gene)
        a1, a2, b = result.a1, result.a2, result.b
        print(
            json.dumps(
                {
                    "gene": result.gene,
                    "schema_version": "1.0.0",
                    "annotation_path": str(result.annotation_path) if result.annotation_path else None,
                    "annotation_emitted": result.record is not None,
                    "error": result.error,
                    "evidence_count": result.record.evidence_count if result.record else None,
                    "n_tool_calls": {
                        "a1": a1.n_tool_calls if a1 else None,
                        "a2": a2.n_tool_calls if a2 else None,
                        "b": b.n_tool_calls if b else None,
                    },
                    "n_repair_attempts": {
                        "a1": a1.n_repair_attempts if a1 else None,
                        "a2": a2.n_repair_attempts if a2 else None,
                        "b": b.n_repair_attempts if b else None,
                    },
                },
                indent=2,
            )
        )
        if result.error:
            raise SystemExit(1)


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
