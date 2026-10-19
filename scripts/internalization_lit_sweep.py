"""Literature (PMID/DOI-anchored) sweep over the internalization cohort -> public D1.

Augments each gene's existing SEQUENCE record with the literature track, via a
**read-back-merge** so the seq track is never clobbered:

  1. read the gene's existing seq ``model_priors`` from D1 (free — a SELECT),
  2. ``annotate_literature(gene, model_priors=<seq>, use_web_search=True)`` — the
     lit track is graded BLIND to the seq prior (model_priors is stitched into
     the output record only, never fed to any lit LLM stage),
  3. ``publish_seq_record(merged)`` — INSERT OR REPLACE writes BOTH tracks, so the
     seq_* columns survive.

SAFETY: on ``--execute`` this runs the R2 backup of ``surface_internalization``
FIRST (scripts/backup_surface_internalization_to_r2.py), so a bad run is always
recoverable. DRY-RUN BY DEFAULT — lists the cohort + estimate, writes nothing.

Resume is prompt-sha-aware: a gene already at ``has_literature=1`` under the
CURRENT lit-prompt sha is skipped; a lit-prompt edit changes the sha -> re-run.

    uv run python scripts/internalization_lit_sweep.py --genes TMEM123 TFRC   # dry run
    uv run python scripts/internalization_lit_sweep.py --genes TMEM123 TFRC --execute
    uv run python scripts/internalization_lit_sweep.py --execute              # full cohort
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from accessible_surfaceome.agents.internalization.literature_runner import (
    annotate_literature,
    lit_prompt_sha,
)
from accessible_surfaceome.agents.internalization.models import (
    LIT_PROMPT_VERSION,
    SCHEMA_VERSION,
    InternalizationRecord,
)
from accessible_surfaceome.cloud.internalization import ensure_table, publish_seq_record
from accessible_surfaceome.env import REPO_ROOT, load_env

logger = logging.getLogger("internalization_lit_sweep")

# Rough per-gene lit cost (Haiku triage over ~40-80 papers + PDF fetches + 2
# Sonnet calls + one web_search Sonnet call). HIGHLY gene-dependent (well-studied
# genes cost more); the pilot MEASURES the real number — this is only a dry-run
# ballpark so nothing is a surprise.
PER_GENE_USD_EST = 0.25
DEFAULT_CONCURRENCY = 6


def load_cohort(d1, *, genes: list[str] | None) -> list[str]:
    """Explicit ``--genes`` if given, else every gene that already has a seq
    record at the current schema (lit augments seq, so the cohort is seq-first)."""
    if genes:
        return sorted(dict.fromkeys(g.upper() for g in genes))
    rows = d1.query(
        "SELECT gene_symbol FROM surface_internalization WHERE schema_version = ?;",
        [SCHEMA_VERSION],
    )
    return sorted({r["gene_symbol"] for r in rows if r.get("gene_symbol")})


def _run_backup() -> None:
    logger.info("running R2 backup of surface_internalization before any write…")
    res = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "backup_surface_internalization_to_r2.py"),
        ],
        cwd=REPO_ROOT,
    )
    if res.returncode != 0:
        raise SystemExit(
            "backup FAILED — refusing to run the lit sweep without a fresh backup."
        )


def main(argv: list[str] | None = None) -> int:
    load_env()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--execute", action="store_true", help="Run + publish (default: dry run)."
    )
    p.add_argument(
        "--genes", nargs="+", default=None, help="Explicit gene list (the pilot)."
    )
    p.add_argument("--limit", type=int, default=None, help="Cap the number of genes.")
    p.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    p.add_argument(
        "--no-web-search",
        dest="web_search",
        action="store_false",
        help="Disable the web_search discovery complement (on by default).",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Re-run genes already lit-annotated at the current lit-prompt sha.",
    )
    p.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip the pre-run R2 backup (NOT recommended).",
    )
    args = p.parse_args(argv)

    from accessible_surfaceome.cloud.d1_client import D1Client

    cur_sha = lit_prompt_sha()
    with D1Client.public() as d1:
        ensure_table(d1)  # also ALTERs in lit_prompt_sha/version on the live table
        cohort = load_cohort(d1, genes=args.genes)

        done: set[str] = set()
        if not args.force:
            rows = d1.query(
                "SELECT gene_symbol, lit_prompt_sha FROM surface_internalization "
                "WHERE schema_version = ? AND has_literature = 1;",
                [SCHEMA_VERSION],
            )
            done = {
                r["gene_symbol"] for r in rows if r.get("lit_prompt_sha") == cur_sha
            }
        todo = [g for g in cohort if g not in done]
        if args.limit:
            todo = todo[: args.limit]

        logger.info("lit prompt: version=%s sha=%s", LIT_PROMPT_VERSION, cur_sha[:12])
        logger.info(
            "cohort=%d  already-lit@sha=%d  todo=%d  web_search=%s",
            len(cohort),
            len(done),
            len(todo),
            args.web_search,
        )

        if not args.execute:
            est = len(todo) * PER_GENE_USD_EST
            print(f"\nDRY RUN — {len(todo)} genes to lit-annotate (read-back-merge)")
            print(
                f"  web_search: {args.web_search}  |  concurrency: {args.concurrency}"
            )
            print(
                f"  rough est: ~${est:,.0f}  (@ ~${PER_GENE_USD_EST:.2f}/gene — MEASURED on the pilot; gene-dependent)"
            )
            print(
                f"  target: public D1 surface_internalization @ schema {SCHEMA_VERSION}, lit-prompt {LIT_PROMPT_VERSION}"
            )
            print(f"  first {min(15, len(todo))}: {', '.join(todo[:15])}")
            print(
                "\n  → re-run with --execute (runs an R2 backup first, then writes). Nothing written."
            )
            return 0

        if not todo:
            logger.info(
                "nothing to do (all todo genes already lit-annotated at the current sha)."
            )
            return 0

        # Read every seq track UP FRONT (serial, free) so the parallel workers do
        # no concurrent D1 reads — the read-back half of the merge.
        seq_by_gene: dict[str, list] = {}
        for sym in todo:
            r = d1.query(
                "SELECT record_json FROM surface_internalization "
                "WHERE gene_symbol = ? AND schema_version = ?;",
                [sym, SCHEMA_VERSION],
            )
            if r:
                seq_by_gene[sym] = InternalizationRecord.model_validate_json(
                    r[0]["record_json"]
                ).model_priors
            else:
                seq_by_gene[sym] = []  # no seq record yet — lit-only is still valid

        if not args.no_backup:
            _run_backup()

        from accessible_surfaceome.agents._support.client import get_client
        from accessible_surfaceome.tools._shared.http import open_default_client

        shared_client = get_client()
        shared_http = open_default_client()
        conc = max(1, args.concurrency)
        logger.info("running %d genes @ concurrency %d", len(todo), conc)

        def _annotate(sym: str):
            return sym, annotate_literature(
                sym,
                client=shared_client,
                http=shared_http,
                model_priors=seq_by_gene.get(sym) or [],
                use_web_search=args.web_search,
                persist=False,
            )

        ok = fail = 0
        with ThreadPoolExecutor(max_workers=conc) as pool:
            futures = {pool.submit(_annotate, sym): sym for sym in todo}
            for i, fut in enumerate(as_completed(futures), 1):
                sym = futures[fut]
                try:
                    _, rec = fut.result()
                    publish_seq_record(rec, client=d1)  # main-thread-only D1 write
                    ok += 1
                    lit = rec.literature
                    logger.info(
                        "[%d/%d] %s -> lit %s (%d obs, %d discovered, %d fetched)",
                        i,
                        len(todo),
                        sym,
                        lit.overall_grade if lit else "?",
                        lit.n_observations if lit else 0,
                        lit.n_papers_discovered if lit else 0,
                        lit.n_papers_fetched if lit else 0,
                    )
                except Exception as exc:  # noqa: BLE001 — one gene must not abort the sweep
                    fail += 1
                    logger.error(
                        "[%d/%d] %s FAILED: %s", i, len(todo), sym, str(exc)[:200]
                    )
        logger.info("done: %d published, %d failed", ok, fail)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
