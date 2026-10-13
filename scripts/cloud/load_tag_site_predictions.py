"""Load third-party per-residue insertion-tolerance predictions into D1.

Three published predictors are scored over the same cohort our two
deterministic tag-site lanes run on, so "our disorder lane and ProDomino
disagree here" is a query rather than an anecdote. See
:mod:`accessible_surfaceome.cloud.tag_site_predictions` for the row shape and
why scores are a hex byte per residue.

Each predictor arrives in its own format, so each gets an adapter that returns
the common ``{uniprot_acc, gene_symbol, length, scores}`` record:

* ``prodomino``  — JSON written by ``modal/prodomino_app.py`` (the GPU run).
* ``indeli_e``   — one row per (protein, position) in the paper's 418 MB
                   genome-wide CSV; we stream it and keep our cohort.
* ``epictope``   — JSON written by the EpicTope harness.

**A length mismatch drops the protein.** When a predictor scored a different
isoform than our cohort row, its residue indices mean different residues than
ours, and a silently misaligned score is the same class of bug as a
symbol-keyed gene lookup (see CLAUDE.md "Gene identifier resolution"). The
script reports every drop rather than publishing a misaligned row.

Dry-run by default::

    uv run python scripts/cloud/load_tag_site_predictions.py --predictor indeli_e \
        --source ~/Downloads/.../genome_wide_prediction.csv
    uv run python scripts/cloud/load_tag_site_predictions.py --predictor indeli_e \
        --source ... --target both --execute
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config  # noqa: E402
from accessible_surfaceome.cloud.tag_site_predictions import (  # noqa: E402
    publish,
    row_for,
)
from accessible_surfaceome.env import load_env  # noqa: E402

logger = logging.getLogger("load_tag_site_predictions")

COHORT_DIR = REPO_ROOT / "data" / "analysis" / "prodomino"

# Per-predictor constants. ``lo``/``hi`` is the encoding range and MUST be a
# property of the predictor, not of any one run — see ``encode_scores``.
PREDICTORS: dict[str, dict[str, Any]] = {
    "prodomino": {
        "licence": "CC-BY-NC-4.0",
        "citation": "ProDomino, Nature Methods 2025",
        "predictor_version": "1.0",
        "model_config": "esm2_t36_3B_UR50D + MLP head",
        # Sigmoid output.
        "lo": 0.0,
        "hi": 1.0,
    },
    "indeli_e": {
        "licence": "CC-BY-4.0",
        "citation": "INDELi-E, Lehner lab genome-wide human proteome predictions",
        "predictor_version": "1.0",
        "model_config": "ESM-1v + secondary structure; score = 1aa insertion before residue",
        # Observed over our cohort: -0.168 .. 3.233. Padded to a round range so
        # the mapping is stable if a later cohort runs slightly outside it.
        "lo": -0.5,
        "hi": 3.5,
    },
    "epictope": {
        "licence": "GPL-3.0",
        "citation": "EpicTope (conservation + DSSP RSA + secondary structure + disorder)",
        "predictor_version": "1.0",
        # Fallback only: run_epictope.py now stamps the real invocation on
        # each record (see model_config_note). This string described the
        # PAPER, and the runs it labelled were unsmoothed and unnormalised
        # -- the hazard of reusing an ingested-predictor template for the
        # one predictor we compute ourselves.
        "model_config": "least-worst per residue (unsmoothed; repo calculate_scores); raw score, not normalised; ss+rsa from AlphaFold+freesasa, NOT DSSP",
        "lo": 0.0,
        "hi": 1.0,
    },
}


def load_cohort(half: str) -> dict[str, dict[str, Any]]:
    """One half of the by-gene split, keyed by UniProt accession.

    The predictors are frozen third-party models with nothing of ours fitted in
    them, so scoring the held-out half leaks nothing. What must not happen is
    our OWN lane thresholds being chosen against test numbers.
    """
    path = COHORT_DIR / f"sequences_{half}.json"
    return {r["acc"]: r for r in json.loads(path.read_text())}


def adapt_prodomino(source: Path, cohort: dict[str, Any]) -> list[dict[str, Any]]:
    """ProDomino's GPU run already emits the common record shape, one per protein.

    ``length`` is re-read from the cohort rather than trusted from the file, so
    a predictor that scored a different isoform surfaces in
    :func:`drop_misaligned` instead of agreeing with itself.
    """
    out = []
    for rec in json.loads(source.read_text()):
        acc = rec["uniprot_acc"]
        if acc not in cohort:
            continue
        out.append(
            {
                "uniprot_acc": acc,
                "gene_symbol": cohort[acc].get("gene"),
                "length": len(cohort[acc]["sequence"]),
                "scores": list(rec["scores"]),
                # Carried through when the harness stamped it (EpicTope does).
                # Ingested predictors have no such key and fall back to the
                # PREDICTORS table, which is correct for them: for a predictor
                # we did not run, the published model description IS the config.
                "model_config": rec.get("model_config"),
            }
        )
    return out


def adapt_indeli_e(source: Path, cohort: dict[str, Any]) -> list[dict[str, Any]]:
    """Stream the genome-wide CSV, keeping our cohort's insertion scores.

    The file is ~418 MB / 7.37M rows (one per protein-position), so it is read
    once with a set-membership test rather than loaded into a DataFrame. We take
    the insertion column, not the deletion one: a tag is inserted.
    """
    want = set(cohort)
    by_acc: dict[str, dict[int, float]] = {}
    with source.open() as fh:
        for row in csv.DictReader(fh):
            acc = row["uniprot_name"]
            if acc not in want:
                continue
            try:
                pos = int(row["Pos"])
                val = float(row["INDELi score: 1aa ins before"])
            except (ValueError, TypeError):
                continue
            by_acc.setdefault(acc, {})[pos] = val

    out = []
    for acc, pos_map in by_acc.items():
        n = len(pos_map)
        # Positions are 1-indexed and contiguous in the published file; assert
        # it rather than trusting it, because a gap would shift every score
        # after it onto the wrong residue.
        if sorted(pos_map) != list(range(1, n + 1)):
            logger.warning("%s: non-contiguous positions, dropped", acc)
            continue
        out.append(
            {
                "uniprot_acc": acc,
                "gene_symbol": cohort[acc].get("gene"),
                "length": len(cohort[acc]["sequence"]),
                "scores": [pos_map[i] for i in range(1, n + 1)],
            }
        )
    return out


def adapt_epictope(source: Path, cohort: dict[str, Any]) -> list[dict[str, Any]]:
    """EpicTope harness output: {acc: [per-residue score]}."""
    return adapt_prodomino(source, cohort)


ADAPTERS = {
    "prodomino": adapt_prodomino,
    "indeli_e": adapt_indeli_e,
    "epictope": adapt_epictope,
}


def drop_misaligned(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[tuple[str, int, int]]]:
    """Split into (aligned, dropped). A dropped record scored another isoform."""
    keep, dropped = [], []
    for r in records:
        if len(r["scores"]) != r["length"]:
            dropped.append((r["uniprot_acc"], r["length"], len(r["scores"])))
        else:
            keep.append(r)
    return keep, dropped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--predictor", required=True, choices=sorted(PREDICTORS))
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument(
        "--target",
        default="public",
        choices=("public", "private", "both"),
        help="Which D1 to write. Default public — these are reference data a "
        "reader should be able to check our lanes against.",
    )
    ap.add_argument(
        "--half",
        default="train",
        help="Which cohort file to load: reads sequences_{half}.json. "
        "'train'/'test' are the frozen by-gene split; any other name is an "
        "extension cohort (e.g. 'new' for genes a later sweep discovered). "
        "An extension NEVER joins the test half — growing a holdout after it "
        "has been read makes it no longer held out.",
    )
    ap.add_argument("--run-id", default="")
    ap.add_argument("--execute", action="store_true", help="Without this, dry-run.")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_env()

    spec = PREDICTORS[args.predictor]
    run_id = args.run_id or f"tag_site_benchmark_v1_{args.half}"
    cohort = load_cohort(args.half)
    logger.info("cohort (%s half): %d accessions", args.half, len(cohort))

    records = ADAPTERS[args.predictor](args.source, cohort)
    logger.info(
        "%s: %d of %d cohort proteins scored", args.predictor, len(records), len(cohort)
    )

    records, dropped = drop_misaligned(records)
    if dropped:
        logger.warning(
            "dropped %d protein(s) whose scored isoform differs from ours "
            "(acc, our_len, their_n):",
            len(dropped),
        )
        for d in dropped:
            logger.warning("    %s", d)
    logger.info("publishable: %d", len(records))
    if not records:
        return 1

    rows = [
        row_for(
            r,
            predictor=args.predictor,
            licence=spec["licence"],
            citation=spec["citation"],
            predictor_version=spec["predictor_version"],
            model_config=r.get("model_config") or spec["model_config"],
            run_id=run_id,
            lo=spec["lo"],
            hi=spec["hi"],
        )
        for r in records
    ]
    biggest = max(rows, key=lambda r: len(r["scores_hex"]))
    logger.info(
        "largest row: %s at %.1f kB (D1 cap is 2 MB)",
        biggest["uniprot_acc"],
        len(biggest["scores_hex"]) / 1024,
    )
    logger.info("licence stamped on every row: %s", spec["licence"])

    if not args.execute:
        logger.info("DRY RUN — re-run with --execute to write to %s D1", args.target)
        return 0

    targets = (
        [("public", D1Config.from_env_public())]
        if args.target == "public"
        else [("private", None)]
        if args.target == "private"
        else [("private", None), ("public", D1Config.from_env_public())]
    )
    for label, cfg in targets:
        with D1Client(cfg) if cfg else D1Client() as d1:
            n = publish(rows, client=d1)
            logger.info("%s D1: wrote %d rows", label, n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
