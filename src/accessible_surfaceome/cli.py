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
        "agents", help="Manage the surface-annotator Managed Agent."
    )
    agents_sub = agents_parser.add_subparsers(dest="agents_command", required=True)
    agents_sub.add_parser("sync", help="Create-or-update the remote agent + environment.")
    annotate = agents_sub.add_parser(
        "annotate", help="Run a one-off annotation session for a single gene."
    )
    annotate.add_argument("gene", help="Gene symbol or UniProt accession (e.g. KAAG1, Q9UBP8).")
    annotate.add_argument(
        "--audit",
        action="store_true",
        help=(
            "Run the Sonnet claim-entailment audit on each promoted Evidence "
            "(catches 'right citation, wrong direction'). Adds ~$0.05–0.15/gene."
        ),
    )
    audit_corpus = agents_sub.add_parser(
        "audit-corpus",
        help="Verify every persisted Evidence span round-trips against data/sources/.",
    )
    audit_corpus.add_argument(
        "gene",
        nargs="?",
        help=(
            "Gene to audit (e.g. KAAG1). When omitted, audits every record in "
            "data/annotations/."
        ),
    )
    view = agents_sub.add_parser(
        "view",
        help=(
            "Pretty-print a persisted record's Evidence chain with deep-links "
            "that highlight each verbatim quote on the source page."
        ),
    )
    view.add_argument("gene", help="Gene to view (e.g. HER2).")

    triage_parser = subparsers.add_parser(
        "triage", help="Manage the lightweight Sonnet triage agent."
    )
    triage_sub = triage_parser.add_subparsers(dest="triage_command", required=True)
    triage_sub.add_parser("sync", help="Create-or-update the remote triage agent + environment.")
    triage_run = triage_sub.add_parser(
        "run", help="Run a one-off triage session for a single gene."
    )
    triage_run.add_argument("gene", help="Gene symbol or UniProt accession (e.g. MUC5AC, P98088).")

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
    elif args.command == "triage":
        _run_triage(args)
    elif args.command == "triage-bench":
        _run_triage_bench(args)


def _run_agents(args: argparse.Namespace) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
    from accessible_surfaceome.agents.surface_annotator import orchestrator

    if args.agents_command == "sync":
        result = orchestrator.sync_agent_and_environment()
        print(
            json.dumps(
                {
                    "agent_id": result.agent_id,
                    "agent_version": result.agent_version,
                    "environment_id": result.environment_id,
                    "agent_changed": result.agent_changed,
                    "environment_changed": result.environment_changed,
                },
                indent=2,
            )
        )
    elif args.agents_command == "annotate":
        result = orchestrator.annotate_gene(args.gene, audit=args.audit)
        print(
            json.dumps(
                {
                    "gene": args.gene,
                    "session_id": result.session_id,
                    "n_custom_tool_calls": result.n_tool_calls,
                    "annotation_path": str(result.annotation_path) if result.annotation_path else None,
                    "run_dir": str(result.run_dir),
                    "annotation_emitted": result.annotation_json is not None,
                    "audit_enabled": args.audit,
                },
                indent=2,
            )
        )
    elif args.agents_command == "audit-corpus":
        from accessible_surfaceome.agents.surface_annotator import audit as _audit
        from accessible_surfaceome.paths import DATA_DIR, DATA_SOURCES_DIR

        annotations_dir = DATA_DIR / "annotations"
        if args.gene:
            paths = [annotations_dir / f"{args.gene}.json"]
        else:
            paths = sorted(annotations_dir.glob("*.json"))
        any_failed = False
        for path in paths:
            if not path.exists():
                print(f"audit: {path} (missing)")
                any_failed = True
                continue
            report = _audit.audit_record_path(path, sources_dir=DATA_SOURCES_DIR)
            print(_audit.format_report(report))
            if not report.all_passed:
                any_failed = True
        if any_failed:
            raise SystemExit(1)
    elif args.agents_command == "view":
        from accessible_surfaceome.agents.surface_annotator import view as _view
        from accessible_surfaceome.paths import DATA_DIR

        annotation_path = DATA_DIR / "annotations" / f"{args.gene}.json"
        if not annotation_path.exists():
            raise SystemExit(f"no record at {annotation_path}")
        print(_view.format_record(annotation_path))


def _run_triage(args: argparse.Namespace) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
    from accessible_surfaceome.agents.surface_triage import orchestrator

    if args.triage_command == "sync":
        result = orchestrator.sync_agent_and_environment()
        print(
            json.dumps(
                {
                    "agent_id": result.agent_id,
                    "agent_version": result.agent_version,
                    "environment_id": result.environment_id,
                    "agent_changed": result.agent_changed,
                    "environment_changed": result.environment_changed,
                },
                indent=2,
            )
        )
    elif args.triage_command == "run":
        result = orchestrator.triage_gene(args.gene)
        print(
            json.dumps(
                {
                    "gene": args.gene,
                    "session_id": result.session_id,
                    "triage_path": str(result.triage_path) if result.triage_path else None,
                    "run_dir": str(result.run_dir),
                    "validation_status": result.validation_status,
                    "triage_emitted": result.triage_json is not None,
                    "triage_json": result.triage_json,
                },
                indent=2,
            )
        )


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
