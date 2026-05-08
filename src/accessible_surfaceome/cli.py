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

    args, remainder = parser.parse_known_args(argv)
    if args.command == "build":
        merge.main(remainder)
    elif args.command == "agents":
        _run_agents(args)
    elif args.command == "triage":
        _run_triage(args)


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
                    "n_custom_tool_calls": result.n_tool_calls,
                    "triage_path": str(result.triage_path) if result.triage_path else None,
                    "run_dir": str(result.run_dir),
                    "validation_status": result.validation_status,
                    "triage_emitted": result.triage_json is not None,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
