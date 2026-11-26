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
    DEFAULT_LIT_MODEL,
    DEFAULT_LIT_TRIAGE_MODEL,
    DEFAULT_LIT_WEB_SCOUT_MODEL,
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
    parser.add_argument(
        "--all-isoforms",
        action="store_true",
        help="Grade every isoform (default: canonical only, to cut input cost).",
    )
    parser.add_argument(
        "--web-search-mode",
        choices=("adaptive", "always", "off"),
        default="adaptive",
        help="Web-search discovery policy for the literature track (default: adaptive).",
    )
    parser.add_argument(
        "--no-web-search",
        dest="no_web_search",
        action="store_true",
        help="Legacy alias for --web-search-mode off.",
    )
    parser.add_argument(
        "--lit-model",
        default=DEFAULT_LIT_MODEL,
        help=f"Select/grade model for literature track (default: {DEFAULT_LIT_MODEL}).",
    )
    parser.add_argument(
        "--triage-model",
        default=DEFAULT_LIT_TRIAGE_MODEL,
        help=f"Abstract triage model (default: {DEFAULT_LIT_TRIAGE_MODEL}).",
    )
    parser.add_argument(
        "--web-scout-model",
        default=DEFAULT_LIT_WEB_SCOUT_MODEL,
        help=f"Web-search scout model (default: {DEFAULT_LIT_WEB_SCOUT_MODEL}).",
    )
    parser.add_argument(
        "--from-r2",
        action="store_true",
        help="Seed discovered papers & triage verdicts from R2 intermediates before running.",
    )
    parser.add_argument(
        "--upload-r2",
        action="store_true",
        help="Upload updated gzipped intermediates bundle to R2 after grading.",
    )
    parser.add_argument(
        "--add-papers",
        nargs="+",
        default=None,
        help="Additional PMID/PMCID/DOI identifiers to hydrate & force-fetch (for incremental updates).",
    )
    parser.add_argument(
        "--skip-discovery",
        action="store_true",
        help="Skip fresh EuropePMC/PubTator queries (use R2/local seed + --add-papers only).",
    )
    args = parser.parse_args(argv)
    ws_mode = "off" if args.no_web_search else args.web_search_mode

    priors = None
    record = None

    if args.track in ("model_prior", "both"):
        # On 'both', don't persist here — the literature runner writes the merged record.
        mp = annotate_model_prior(
            args.gene,
            models=tuple(args.models),
            persist=(args.track == "model_prior" and args.persist),
            canonical_only=not args.all_isoforms,
        )
        priors = mp.model_priors
        record = mp

    if args.track in ("literature", "both"):
        record = annotate_literature(
            args.gene,
            persist=args.persist,
            model_priors=priors,
            use_web_search=(ws_mode != "off"),
            web_search_mode=ws_mode,
            model=args.lit_model,
            triage_model=args.triage_model,
            web_scout_model=args.web_scout_model,
            extra_paper_ids=args.add_papers,
            skip_discovery=args.skip_discovery,
            load_from_r2=args.from_r2,
            upload_to_r2=args.upload_r2,
        )

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
