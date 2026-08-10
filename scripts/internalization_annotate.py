"""Annotate one gene's internalization record (model-prior and/or literature tracks).

Usage:
    uv run python scripts/internalization_annotate.py TFRC                      # both tracks
    uv run python scripts/internalization_annotate.py TFRC --track model_prior  # sequence+topology only
    uv run python scripts/internalization_annotate.py ERBB2 --track literature   # PMID-anchored only
    uv run python scripts/internalization_annotate.py HGNC:3236 --no-persist
    uv run python scripts/internalization_annotate.py CD20 --models claude-sonnet-4-6
"""

from __future__ import annotations

import argparse
import logging
import sys

from accessible_surfaceome.agents.internalization.literature_runner import (
    annotate_literature,
)
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
        "--track",
        choices=("model_prior", "literature", "both"),
        default="both",
        help="Which track(s) to run (default: both). 'both' writes one merged record.",
    )
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
        help=f"Model-prior model ids (default: {' '.join(DEFAULT_MODELS)})",
    )
    args = parser.parse_args(argv)

    priors = None
    record = None

    if args.track in ("model_prior", "both"):
        # On 'both', don't persist here — the literature runner writes the merged record.
        mp = annotate_model_prior(
            args.gene,
            models=tuple(args.models),
            persist=(args.track == "model_prior" and args.persist),
        )
        priors = mp.model_priors
        record = mp

    if args.track in ("literature", "both"):
        record = annotate_literature(args.gene, persist=args.persist, model_priors=priors)

    assert record is not None
    print(f"\n{record.gene_symbol}  ({record.uniprot_acc}, {record.hgnc_id})")

    for track in record.model_priors:
        print(
            f"  model-prior [{track.model}] overall={track.overall_grade} "
            f"({track.overall_confidence})"
        )
        for iso in track.per_isoform:
            flag = "canonical" if iso.is_canonical else "isoform"
            print(
                f"      {iso.isoform_id} ({flag}): {iso.grade} "
                f"({iso.confidence}) — {iso.rationale[:90]}"
            )

    lit = record.literature
    if lit is not None:
        gbm = lit.grades_by_mode
        print(
            f"  literature overall={lit.overall_grade} ({lit.overall_confidence}) | "
            f"basal={gbm.basal.grade} native={gbm.native_ligand.grade} "
            f"therapeutic={gbm.therapeutic.grade}"
        )
        print(
            f"      {lit.n_papers_discovered} papers discovered, "
            f"{lit.n_papers_fetched} full-text; {lit.n_observations} observations; "
            f"{len(lit.sources)} cited sources"
        )
        for obs in lit.observations[:8]:
            print(
                f"      - {obs.assay_type} / {obs.cell_context} / {obs.internalization_mode}"
                f" / mag={obs.magnitude} cites={obs.cited_source_ids}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
