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
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from accessible_surfaceome.env import load_env
    from accessible_surfaceome.tools._shared import retraction_watch
    from accessible_surfaceome.tools._shared.http import open_default_client

    load_env()  # NCBI_API_KEYS etc. for the discovery calls

    if not SNAPSHOTS.is_dir():
        logger.error("snapshot dir not found: %s", SNAPSHOTS)
        return 1

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
