"""Annotate one gene's internalization model-prior track (Opus + Sonnet).

Usage:
    uv run python scripts/internalization_annotate.py TFRC
    uv run python scripts/internalization_annotate.py HGNC:3236 --no-persist
    uv run python scripts/internalization_annotate.py CD20 --models claude-sonnet-4-6
"""

from __future__ import annotations

import argparse
import logging
import sys

from accessible_surfaceome.agents.internalization.runner import (
    DEFAULT_MODELS,
    annotate_model_prior,
)
from accessible_surfaceome.env import load_env


def main(argv: list[str] | None = None) -> int:
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gene", help="Gene symbol or HGNC:id")
    parser.add_argument(
        "--persist",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Write data/annotations/internalization/{SYMBOL}.json (default: on)",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=list(DEFAULT_MODELS),
        help=f"Model ids to grade with (default: {' '.join(DEFAULT_MODELS)})",
    )
    args = parser.parse_args(argv)

    record = annotate_model_prior(
        args.gene, models=tuple(args.models), persist=args.persist
    )

    print(f"\n{record.gene_symbol}  ({record.uniprot_acc}, {record.hgnc_id})")
    for track in record.model_priors:
        print(
            f"  [{track.model}] overall={track.overall_grade} "
            f"({track.overall_confidence})"
        )
        for iso in track.per_isoform:
            flag = "canonical" if iso.is_canonical else "isoform"
            print(
                f"      {iso.isoform_id} ({flag}): {iso.grade} "
                f"({iso.confidence}) — {iso.rationale[:90]}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
