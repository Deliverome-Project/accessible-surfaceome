"""Command line entry point for the surface-proteome project."""

from __future__ import annotations

import argparse

from surface_proteome.candidates import merge


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("build", help="Run the candidate-universe merge.")
    subparsers.add_parser("run", help="Placeholder for the annotation pipeline.")
    subparsers.add_parser("analyze", help="Placeholder for analysis reports.")
    subparsers.add_parser("export", help="Placeholder for public exports.")
    subparsers.add_parser("audit", help="Placeholder for citation-integrity audits.")

    args = parser.parse_args()
    if args.command == "build":
        merge.main()
        return

    raise SystemExit(f"{args.command!r} is scaffolded but not implemented yet.")


if __name__ == "__main__":
    main()
