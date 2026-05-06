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

    args, remainder = parser.parse_known_args(argv)
    if args.command == "build":
        merge.main(remainder)
    elif args.command == "agents":
        _run_agents(args)


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
        result = orchestrator.annotate_gene(args.gene)
        print(
            json.dumps(
                {
                    "gene": args.gene,
                    "session_id": result.session_id,
                    "n_custom_tool_calls": result.n_tool_calls,
                    "annotation_path": str(result.annotation_path) if result.annotation_path else None,
                    "run_dir": str(result.run_dir),
                    "annotation_emitted": result.annotation_json is not None,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
