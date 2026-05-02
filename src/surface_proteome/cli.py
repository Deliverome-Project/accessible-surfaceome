"""Command line entry point for the surface-proteome project."""

from __future__ import annotations

import argparse

from surface_proteome.candidates import merge


def _add_build_subparser(subparsers: argparse._SubParsersAction) -> None:
    build_parser = subparsers.add_parser(
        "build",
        help="Run the candidate-universe merge.",
        description=merge.__doc__,
        parents=[merge.build_arg_parser()],
        add_help=True,
        conflict_handler="resolve",
    )
    build_parser.set_defaults(func=lambda args: merge.main(_merge_argv(args)))


def _merge_argv(args: argparse.Namespace) -> list[str]:
    argv: list[str] = []
    if getattr(args, "output_dir", None) is not None:
        argv.extend(["--output-dir", str(args.output_dir)])
    return argv


def _not_implemented(name: str):
    def _run(_args: argparse.Namespace) -> None:
        raise SystemExit(f"{name!r} is scaffolded but not implemented yet.")

    return _run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    _add_build_subparser(subparsers)
    for name, help_text in (
        ("run", "Placeholder for the annotation pipeline."),
        ("analyze", "Placeholder for analysis reports."),
        ("export", "Placeholder for public exports."),
        ("audit", "Placeholder for citation-integrity audits."),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.set_defaults(func=_not_implemented(name))

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
