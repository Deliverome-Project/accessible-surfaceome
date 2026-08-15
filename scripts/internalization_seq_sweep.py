"""Sequence (model-prior) sweep over the internalization cohort → public D1.

Cohort = the UNION of:
  * ``passes_likely`` genes (deep-dive shortlist; ``passes_canonical`` ⊆ this), and
  * the low-lit UniProt-positive set: UniProt surface-vote genes whose true
    discovery corpus is under a paper threshold (``n_papers_found < --lowlit-max``,
    or has no deep-dive paper count at all → understudied by default).

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

from accessible_surfaceome.agents.internalization.models import SCHEMA_VERSION
from accessible_surfaceome.agents.internalization.runner import annotate_model_prior
from accessible_surfaceome.cloud.internalization import ensure_table, publish_seq_record
from accessible_surfaceome.env import load_env
from accessible_surfaceome.release.catalog_presets import passes_likely

logger = logging.getLogger("internalization_seq_sweep")

CATALOG_URL = "https://api.deliverome.org/surfaceome/v1/catalog"
OPUS_MODEL = "claude-opus-4-8"
PER_GENE_USD = 0.037  # measured: Opus, canonical isoform only (see cost estimate)


def load_cohort(
    *, catalog_url: str = CATALOG_URL, lowlit_max_papers: int = 100
) -> list[str]:
    """Return the sorted union cohort of gene symbols from the public catalog."""
    payload = httpx.get(catalog_url, timeout=120).json()
    rows = payload["rows"]
    db_keys = payload.get("db_keys") or ["uniprot", "go", "surfy", "cspa", "hpa"]
    uni_bit = db_keys.index("uniprot")

    def uniprot_pos(row: dict) -> bool:
        db = row.get("db")
        return isinstance(db, int) and bool(db & (1 << uni_bit))

    likely: set[str] = set()
    lowlit: set[str] = set()
    for r in rows:
        sym = r.get("symbol")
        if not sym:
            continue
        ddf = r.get("ddf")
        if ddf and passes_likely(ddf):
            likely.add(sym)
        if uniprot_pos(r):
            npf = (ddf or {}).get("n_papers_found")
            # low-lit: under the paper threshold, or no deep-dive count at all
            if npf is None or npf < lowlit_max_papers:
                lowlit.add(sym)
    return sorted(likely | lowlit)


def main(argv: list[str] | None = None) -> int:
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--execute", action="store_true", help="Run + publish (default: dry run).")
    p.add_argument("--limit", type=int, default=None, help="Cap the number of genes.")
    p.add_argument("--models", nargs="+", default=[OPUS_MODEL], help="Model-prior model ids.")
    p.add_argument("--lowlit-max-papers", type=int, default=100,
                   help="Low-lit threshold: UniProt-pos genes with n_papers_found < N.")
    p.add_argument("--catalog-url", default=CATALOG_URL)
    p.add_argument("--force", action="store_true",
                   help="Re-run genes already present in D1 at the current schema.")
    args = p.parse_args(argv)

    cohort = load_cohort(
        catalog_url=args.catalog_url, lowlit_max_papers=args.lowlit_max_papers
    )
    logger.info("cohort (likely ∪ uniprot-pos-<%dpapers): %d genes",
                args.lowlit_max_papers, len(cohort))

    if not args.execute:
        est = len(cohort) * PER_GENE_USD * len(args.models)
        print(f"\nDRY RUN — cohort {len(cohort)} genes × {len(args.models)} model(s)")
        print(f"  models: {', '.join(args.models)} (canonical isoform only)")
        print(f"  est. cost: ~${est:,.0f}  (@ ${PER_GENE_USD:.3f}/gene/model)")
        print(f"  target: public D1 surface_internalization @ schema {SCHEMA_VERSION}")
        print(f"  first 15: {', '.join(cohort[:15])}")
        print("\n  → re-run with --execute to run + publish. Nothing was written.")
        return 0

    from accessible_surfaceome.cloud.d1_client import D1Client

    with D1Client.public() as d1:
        ensure_table(d1)
        done: set[str] = set()
        if not args.force:
            rows = d1.query(
                "SELECT gene_symbol FROM surface_internalization WHERE schema_version = ?;",
                [SCHEMA_VERSION],
            )
            done = {r["gene_symbol"] for r in rows}
            logger.info("already in D1 @ %s: %d (skipping)", SCHEMA_VERSION, len(done))

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
