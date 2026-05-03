"""Command line entry point for the surface-proteome project."""

from __future__ import annotations

import argparse

from accessible_surfaceome.candidates import merge


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "build",
        help="Run the candidate-universe merge.",
        description=merge.__doc__,
        add_help=False,
    )

    args, remainder = parser.parse_known_args(argv)
    if args.command == "build":
        merge.main(remainder)


if __name__ == "__main__":
    main()
