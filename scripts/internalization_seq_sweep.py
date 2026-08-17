"""Sequence (model-prior) sweep over the internalization cohort → public D1.

Cohort = the UNION of the catalog's authoritative baked ``deep_dive_tier`` tags:
  * ``deep_dive_tier`` in {canonical, likely} (the deep-dive tier taxonomy — these
    are DISJOINT tiers, not the nested passes_canonical ⊆ passes_likely predicate),
    and
  * the ``low_lit_uniprot`` set (understudied UniProt-positive genes).

These are the same tags the viewer shows, so the sweep cohort matches the site.
(The older path re-derived membership from catalog_presets over the ``ddf``
projection, which gave a different, stricter canonical count.)

Runs the BLIND Opus model-prior on the CANONICAL isoform only (sequence + E/C
topology, no gene identity) and UPSERTs each ``InternalizationRecord`` into
public D1's ``surface_internalization`` (schema 0.3.0: 5-point SeqGrade +
structured motifs).

DRY-RUN BY DEFAULT — lists the cohort + estimated cost and writes nothing.
Pass ``--execute`` to actually run + publish. Resumable: genes already in D1 at
the current schema are skipped unless ``--force``.

    uv run python scripts/internalization_seq_sweep.py                 # dry run
    uv run python scripts/internalization_seq_sweep.py --limit 5 --execute
    uv run python scripts/internalization_seq_sweep.py --execute       # full sweep
"""

from __future__ import annotations

import argparse
import logging
import sys

import httpx

from accessible_surfaceome.agents.internalization.model_prior import prompt_sha
from accessible_surfaceome.agents.internalization.models import (
    MODEL_PRIOR_PROMPT_VERSION,
    SCHEMA_VERSION,
)
from accessible_surfaceome.agents.internalization.runner import (
    annotate_model_prior,
    load_prompt,
)
from accessible_surfaceome.cloud.internalization import ensure_table, publish_seq_record
from accessible_surfaceome.env import load_env

logger = logging.getLogger("internalization_seq_sweep")

CATALOG_URL = "https://api.deliverome.org/surfaceome/v1/catalog"
# opus-5: chosen over opus-4.8 for the full sweep because opus-4.8 CLUSTERS at
# `high` (barely uses the 5-point scale), whereas opus-5 discriminates — e.g. it
# pulls a recycling-resistant, phospho-gated RTK down to `moderate` where 4.8
# over-calls `high`. ~3× the output tokens, hence ~3× the cost, but the scale
# spread is the whole point of the grade. (opus-4.8 stays available via --models.)
OPUS_MODEL = "claude-opus-5"
# measured: opus-5 on the schema-0.3.0 prompt, canonical isoform only, cohort
# mean length ~690 aa. ~1.86k input + ~2.4k cached-system read + ~3.1k output
# tok/gene at $5/$25/$0.50 per MTok. Output-dominated; ranges ~$0.08–0.10/gene
# depending on topology complexity → full union (3,357) ≈ $295 (range ~$290–340).
PER_GENE_USD = 0.088
# Baked catalog tags (row_schema 7+) that define the cohort.
COHORT_TIERS = ("canonical", "likely")


def load_cohort(*, catalog_url: str = CATALOG_URL, include_low_lit: bool = True) -> list[str]:
    """Return the sorted union cohort from the catalog's baked ``deep_dive_tier``
    tags: genes tiered ``canonical`` or ``likely``, plus (optionally) the
    ``low_lit_uniprot`` set. Reads the authoritative server-side tags — the same
    the viewer shows — rather than re-deriving from the (stricter) ``ddf``."""
    payload = httpx.get(catalog_url, timeout=120).json()
    rows = payload["rows"]
    tier: set[str] = set()
    lowlit: set[str] = set()
    for r in rows:
        sym = r.get("symbol")
        if not sym:
            continue
        if r.get("deep_dive_tier") in COHORT_TIERS:
            tier.add(sym)
        if include_low_lit and r.get("low_lit_uniprot"):
            lowlit.add(sym)
    logger.info(
        "cohort tags: tier(canonical|likely)=%d low_lit_uniprot=%d "
        "(low_lit net-new=%d)",
        len(tier), len(lowlit), len(lowlit - tier),
    )
    return sorted(tier | lowlit)


def main(argv: list[str] | None = None) -> int:
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--execute", action="store_true", help="Run + publish (default: dry run).")
    p.add_argument("--limit", type=int, default=None, help="Cap the number of genes.")
    p.add_argument("--models", nargs="+", default=[OPUS_MODEL], help="Model-prior model ids.")
    p.add_argument("--no-low-lit", action="store_true",
                   help="Exclude the low_lit_uniprot set (tiers canonical|likely only).")
    p.add_argument("--catalog-url", default=CATALOG_URL)
    p.add_argument("--force", action="store_true",
                   help="Re-run genes already present in D1 at the current schema.")
    args = p.parse_args(argv)

    cohort = load_cohort(
        catalog_url=args.catalog_url, include_low_lit=not args.no_low_lit
    )
    logger.info("cohort (deep_dive_tier canonical|likely%s): %d genes",
                "" if args.no_low_lit else " ∪ low_lit_uniprot", len(cohort))

    if not args.execute:
        est = len(cohort) * PER_GENE_USD * len(args.models)
        print(f"\nDRY RUN — cohort {len(cohort)} genes × {len(args.models)} model(s)")
        print(f"  models: {', '.join(args.models)} (canonical isoform only)")
        print(f"  est. cost: ~${est:,.0f}  (@ ${PER_GENE_USD:.3f}/gene/model)")
        print(f"  target: public D1 surface_internalization @ schema {SCHEMA_VERSION}")
        print(f"  prompt: version {MODEL_PRIOR_PROMPT_VERSION}, "
              f"sha {prompt_sha(load_prompt())[:12]}")
        print(f"  first 15: {', '.join(cohort[:15])}")
        print("\n  → re-run with --execute to run + publish. Nothing was written.")
        return 0

    from accessible_surfaceome.cloud.d1_client import D1Client

    with D1Client.public() as d1:
        ensure_table(d1)
        current_sha = prompt_sha(load_prompt())
        logger.info(
            "model-prior prompt: version=%s sha=%s",
            MODEL_PRIOR_PROMPT_VERSION, current_sha[:12],
        )
        done: set[str] = set()
        if not args.force:
            rows = d1.query(
                "SELECT gene_symbol, seq_prompt_sha FROM surface_internalization "
                "WHERE schema_version = ?;",
                [SCHEMA_VERSION],
            )
            # Skip a gene only if its stored prompt_sha matches the CURRENT prompt.
            # A prompt edit changes the sha, so those genes fall out of `done` and
            # get re-run — i.e. an edit is never silently stale.
            done = {r["gene_symbol"] for r in rows if r.get("seq_prompt_sha") == current_sha}
            stale = sum(1 for r in rows if r.get("seq_prompt_sha") != current_sha)
            logger.info(
                "already in D1 @ %s w/ current prompt: %d (skipping); "
                "stale-prompt rows to re-run: %d", SCHEMA_VERSION, len(done), stale,
            )

        todo = [g for g in cohort if g not in done]
        if args.limit:
            todo = todo[: args.limit]
        logger.info("running %d genes", len(todo))

        ok = fail = 0
        for i, sym in enumerate(todo, 1):
            try:
                rec = annotate_model_prior(
                    sym, models=tuple(args.models), persist=False, canonical_only=True
                )
                publish_seq_record(rec, client=d1)
                ok += 1
                logger.info("[%d/%d] %s -> %s (%s)", i, len(todo), sym,
                            rec.model_priors[0].overall_grade if rec.model_priors else "?",
                            rec.uniprot_acc)
            except Exception as exc:  # noqa: BLE001 — one gene must not abort the sweep
                fail += 1
                logger.error("[%d/%d] %s FAILED: %s", i, len(todo), sym, str(exc)[:200])
        logger.info("done: %d published, %d failed", ok, fail)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
