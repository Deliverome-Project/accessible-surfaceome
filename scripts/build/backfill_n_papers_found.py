"""Backfill ``filters.n_papers_found`` on published ``SurfaceomeRecord`` snapshots.

``n_papers_found`` is the **pre-trim discovery corpus** — the count of unique
papers the deterministic kickoff searches surface (EuropePMC + PubTator NER +
gene2pubmed) *before* plan-trim-select picks any clips. It's the honest "is this
gene generally understudied?" signal, distinct from its sibling
``n_papers_selected`` (post-selection unique papers, a free JSON recount handled
by ``scripts/backfill_n_papers_selected.py``).

Unlike that sibling, this field can't be derived from the stored record — the
discovery count is shed at publish time. It has to be **recomputed by re-running
the discovery step**: NO LLM calls, but ~30 s/gene of network I/O (and ~2×/gene
here, since we run both the A1 and A2 kickoffs and take the max — exactly the
``_max_or_none`` reducer ``surfaceome_v2.orchestrator`` uses, so a backfilled
value matches what a fresh annotate would emit).

Faithful by construction: it calls the **same** pipeline functions
(``_build_gene_context`` → ``build_kickoff`` → ``_execute_plan``) the runner
uses, rather than reimplementing the union of discovery sources. Each gene is
resolved by **HGNC ID** (``record['gene']['hgnc_id']``) per CLAUDE.md — never by
bare symbol (the COX1 / WAS class).

Dry-run by default; ``--execute`` writes ``filters.n_papers_found`` into the JSON.
``--only SYM1,SYM2`` restricts to named genes; ``--limit N`` caps the count
(handy for a single-gene validation); ``--overwrite`` recomputes even where a
value is already set. After running, push the updated snapshots to public D1:

    uv run python scripts/upload_viewer_snapshots_to_d1.py --execute

(then the edge cache is purged by that script's publish path).

**``--from-d1`` — the D1-only genes.** The snapshot loop above only reaches the
handful of committed ``viewer/public/data/surfaceome/*.json`` snapshots (3 today).
The ~485 published records with a NULL discovery corpus (FAM234A / Q9H0X4 class)
live only in public D1 with no snapshot, so the snapshot path cannot touch them.
``--from-d1`` backfills them in place: it selects the NULL rows straight from
``surface_annotation`` (identifier-only projection — never the whole-cohort blob),
recomputes the corpus with the same reducer, patches ``filters.n_papers_found``,
revalidates against ``SurfaceomeRecord``, and republishes each via
``publish_record`` (which UPDATEs D1 and purges the edge cache). No separate
upload step. Same ``--execute`` / ``--only`` / ``--limit`` / ``--overwrite`` flags.

    # pilot one gene (dry-run — 1 discovery, no write):
    uv run python scripts/build/backfill_n_papers_found.py --from-d1 --only FAM234A
    # then execute the whole D1-only backlog (~485 genes; needs CLOUDFLARE_* creds):
    uv run python scripts/build/backfill_n_papers_found.py --from-d1 --execute
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOTS = ROOT / "viewer/public/data/surfaceome"

logger = logging.getLogger("backfill_n_papers_found")


def discover_n_papers_found(hgnc_id: str, *, http, retraction) -> int:
    """Recompute ``n_papers_found`` for one gene by re-running discovery.

    Runs the deterministic kickoff for both A1 and A2 focuses through the real
    runner internals and returns ``max(len(discovered_a1), len(discovered_a2))``
    — the same value path the orchestrator persists. No model calls.
    """
    # Lazy imports: keep --help fast and avoid the heavy agent import unless a
    # gene is actually processed.
    from accessible_surfaceome.agents._support.timing import TimingRecorder
    from accessible_surfaceome.agents.plan_trim_select.kickoff_templates import (
        build_kickoff,
    )
    from accessible_surfaceome.agents.plan_trim_select.runner import (
        _build_gene_context,
        _execute_plan,
    )

    # Context (gene resolution + canonical topology) is focus-independent —
    # build once, run both kickoffs against it.
    context = _build_gene_context(hgnc_id, http=http, retraction_index=retraction)
    counts: list[int] = []
    for focus in ("a1", "a2"):
        plan = build_kickoff(focus, context.n_tmh, context.ecd_aa)
        _pool, _log, _by_source, discovered = _execute_plan(
            plan,
            context=context,
            http=http,
            retraction_index=retraction,
            timing=TimingRecorder(),
            timing_phase="backfill_n_papers_found",
        )
        counts.append(len(discovered))
    return max(counts) if counts else 0


def _run_from_d1(
    args: argparse.Namespace, *, http, retraction, only: set[str] | None
) -> int:
    """D1-direct backfill: patch ``filters.n_papers_found`` on published
    ``surface_annotation`` rows that have none.

    The snapshot loop in :func:`main` can only reach the 3 committed
    ``viewer/public/data/surfaceome/*.json`` snapshots; the ~485 records with
    a NULL discovery corpus live only in D1 (FAM234A-class). This path selects
    those rows (identifier-only projection — never the full blob), recomputes
    the corpus with the same ``discover_n_papers_found`` reducer, and republishes
    each patched record through ``publish_record`` so it is revalidated,
    UPDATEd into D1, and its edge cache purged.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
    from accessible_surfaceome.cloud.n_papers_found_backfill import (
        NEEDS_BACKFILL_SQL,
        patch_n_papers_found,
    )
    from accessible_surfaceome.cloud.surface_annotation import publish_record
    from accessible_surfaceome.tools._shared.models import SurfaceomeRecord

    cfg = D1Config.from_env_public()

    def _backfill_one(d1: D1Client, sym: str, hgnc_id: str | None) -> str:
        """Process one gene. Returns a status: 'written' | 'dry' | 'no_hgnc'
        | 'failed'. Thread-safe: the shared HTTP client's limiter and the D1
        client's httpx transport are both concurrency-safe, and publish_record
        opens its own client + writes a distinct gene row."""
        if not hgnc_id:
            logger.warning("  %-14s SKIP — no gene.hgnc_id in D1 record", sym)
            return "no_hgnc"
        try:
            n_found = discover_n_papers_found(hgnc_id, http=http, retraction=retraction)
        except Exception as exc:  # noqa: BLE001 — one gene must not abort the batch
            logger.warning(
                "  %-14s FAILED — discovery: %s (%s)", sym, type(exc).__name__, exc
            )
            return "failed"

        if not args.execute:
            logger.info("  %-14s would write n_papers_found → %d", sym, n_found)
            return "dry"

        # Fetch the full record ONE row at a time (never a whole-cohort blob pull
        # — that is the isolate-memory-cap crash), patch, revalidate, republish.
        # publish_record does the UPDATE + edge-cache purge.
        blob_rows = d1.query(
            "SELECT annotation_json FROM surface_annotation "
            "WHERE gene_symbol = ? LIMIT 1;",
            [sym],
        )
        if not blob_rows:
            logger.warning("  %-14s FAILED — no annotation_json row", sym)
            return "failed"
        try:
            record = json.loads(blob_rows[0]["annotation_json"])
            patched = patch_n_papers_found(record, n_found)
            model = SurfaceomeRecord.model_validate(patched)
        except Exception as exc:  # noqa: BLE001 — skip loudly, never write junk
            logger.warning(
                "  %-14s FAILED — patch/validate: %s (%s)",
                sym,
                type(exc).__name__,
                exc,
            )
            return "failed"

        result = publish_record(model, write_snapshot=False, push_to_d1=True)
        if not result.d1_written:
            logger.warning("  %-14s D1 write skipped: %s", sym, result.skipped_reason)
            return "failed"
        logger.info("  %-14s wrote n_papers_found → %d", sym, n_found)
        return "written"

    with D1Client(cfg) as d1:
        if args.overwrite:
            select_rows = (
                "SELECT gene_symbol, "
                "json_extract(annotation_json, '$.gene.hgnc_id') AS hgnc_id "
                "FROM surface_annotation ORDER BY gene_symbol;"
            )
            rows = d1.query(select_rows, [])
        else:
            rows = d1.query(NEEDS_BACKFILL_SQL, [])

        targets = [
            (r["gene_symbol"], r.get("hgnc_id"))
            for r in rows
            if only is None or (r["gene_symbol"] or "").upper() in only
        ]
        if args.limit is not None:
            targets = targets[: args.limit]

        workers = max(1, args.workers)
        logger.info(
            "  %d D1 record(s) to backfill%s%s — %d worker(s)",
            len(targets),
            " (--overwrite: all rows)" if args.overwrite else " (n_papers_found IS NULL)",
            "" if only is None else f" — filtered to --only {sorted(only)}",
            workers,
        )

        tally = {"written": 0, "dry": 0, "no_hgnc": 0, "failed": 0}
        if workers == 1:
            for sym, hgnc_id in targets:
                tally[_backfill_one(d1, sym, hgnc_id)] += 1
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(_backfill_one, d1, sym, hgnc_id): sym
                    for sym, hgnc_id in targets
                }
                for fut in as_completed(futures):
                    tally[fut.result()] += 1

    n_done = tally["written"] + tally["dry"]
    suffix = "" if args.execute else "  (dry-run — pass --execute to write)"
    logger.info("")
    logger.info("  backfilled:         %d%s", n_done, suffix)
    logger.info("  no hgnc_id:         %d", tally["no_hgnc"])
    logger.info("  discovery/write failed: %d", tally["failed"])
    if args.execute and tally["written"]:
        logger.info(
            "\n  %d record(s) UPDATEd in public D1 and their edge caches purged. "
            "\n  Verify: uv run pytest tests/test_n_papers_found_backfill.py"
            "::test_all_published_records_have_n_papers_found --run-network",
            tally["written"],
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write the recomputed value to disk (default: dry-run).",
    )
    parser.add_argument(
        "--only",
        default=None,
        help="Comma-separated gene symbols to restrict to (default: all snapshots).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N genes (after --only filtering). Useful for a "
        "single-gene validation run.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Recompute even when n_papers_found is already populated "
        "(default: only fill null/missing).",
    )
    parser.add_argument(
        "--from-d1",
        action="store_true",
        help="Backfill directly against public D1 surface_annotation instead "
        "of the committed viewer snapshots. This is the ONLY path that reaches "
        "the ~485 D1-only genes (FAM234A-class) — they have no committed "
        "snapshot, so the default snapshot loop can't touch them. Recomputes "
        "the discovery corpus, patches filters.n_papers_found into the stored "
        "record, revalidates, and republishes via publish_record (which UPDATEs "
        "D1 and purges the edge cache).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=6,
        help="Concurrent discovery workers for --from-d1 (default: 6). Discovery "
        "is network-I/O-bound; the shared HTTP client's per-key NCBI limiter "
        "(~9 qps/key, thread-safe) self-throttles, so more workers than the key "
        "pool size just queue. 1 = sequential.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from accessible_surfaceome.env import load_env
    from accessible_surfaceome.tools._shared import retraction_watch
    from accessible_surfaceome.tools._shared.http import open_default_client

    load_env()  # NCBI_API_KEYS etc. for the discovery calls

    only = (
        {s.strip().upper() for s in args.only.split(",") if s.strip()}
        if args.only
        else None
    )

    # Shared cached HTTP client + (empty) retraction index — the same default
    # the runner falls back to when no index is passed. Discovery is the union
    # of gene2pubmed + topic search; the retraction index only affects
    # downstream evidence filtering, not the discovery count, so empty is a
    # faithful and network-light default here.
    http = open_default_client()
    retraction = retraction_watch.empty()

    if args.from_d1:
        return _run_from_d1(args, http=http, retraction=retraction, only=only)

    if not SNAPSHOTS.is_dir():
        logger.error("snapshot dir not found: %s", SNAPSHOTS)
        return 1

    n_written = 0
    n_skipped_present = 0
    n_skipped_no_hgnc = 0
    n_failed = 0
    n_processed = 0
    present_symbols: set[str] = set()

    for path in sorted(SNAPSHOTS.glob("*.json")):
        raw = json.loads(path.read_text())
        symbol = (raw.get("gene") or {}).get("hgnc_symbol") or path.stem
        present_symbols.add(symbol.upper())
        if only is not None and symbol.upper() not in only:
            continue

        filters = raw.get("filters")
        if not isinstance(filters, dict):
            filters = {}
        if filters.get("n_papers_found") is not None and not args.overwrite:
            n_skipped_present += 1
            continue

        hgnc_id = (raw.get("gene") or {}).get("hgnc_id")
        if not hgnc_id:
            logger.warning("  %-14s SKIP — no gene.hgnc_id in record", symbol)
            n_skipped_no_hgnc += 1
            continue

        if args.limit is not None and n_processed >= args.limit:
            break
        n_processed += 1

        try:
            n_found = discover_n_papers_found(hgnc_id, http=http, retraction=retraction)
        except Exception as exc:  # noqa: BLE001 — one gene's failure must not abort the batch
            logger.warning("  %-14s FAILED — %s (%s)", symbol, type(exc).__name__, exc)
            n_failed += 1
            continue

        prev = filters.get("n_papers_found")
        action = "wrote" if args.execute else "would write"
        logger.info(
            "  %-14s %s n_papers_found: %s → %d",
            symbol,
            action,
            "null" if prev is None else prev,
            n_found,
        )
        if args.execute:
            raw.setdefault("filters", {})["n_papers_found"] = n_found
            path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n")
        n_written += 1

    # Surface --only genes that matched no snapshot (e.g. validation genes that
    # live in D1 but were never committed under viewer/public/data) so a missing
    # gene is loud, not a silent no-op.
    if only is not None:
        unmatched = sorted(only - present_symbols)
        if unmatched:
            logger.warning(
                "  %d requested gene(s) have NO committed snapshot and were "
                "NOT processed: %s\n"
                "  (this snapshot-scoped backfill can't reach them — they need a "
                "snapshot created or a D1-direct backfill).",
                len(unmatched),
                ", ".join(unmatched),
            )

    suffix = "" if args.execute else "  (dry-run — pass --execute to write)"
    logger.info("")
    logger.info("  recomputed:         %d%s", n_written, suffix)
    logger.info("  already populated:  %d", n_skipped_present)
    logger.info("  no hgnc_id:         %d", n_skipped_no_hgnc)
    logger.info("  discovery failed:   %d", n_failed)
    if args.execute and n_written:
        logger.info(
            "\n  Next: push to public D1 →\n"
            "    uv run python scripts/upload_viewer_snapshots_to_d1.py --execute"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
