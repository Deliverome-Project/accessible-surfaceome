"""Push the agent-side annotation snapshots to public D1 ``surface_annotation``.

The Worker at ``api.deliverome.org/surfaceome/v1/genes/:symbol`` reads from
``surface_annotation.annotation_json``. The agent's canonical disk
artifact lives at ``data/annotations/{SYMBOL}.json`` — same shape as the
per-gene ``SurfaceomeRecord`` the Worker serves.

This script syncs those agent-side snapshots → public D1 so D1 stays
aligned with the in-tree records. Idempotent INSERT OR REPLACE on
``(gene_symbol, schema_version)``, with stale older-``schema_version``
rows dropped per gene.

The viewer no longer reads from any per-gene JSON fallback — D1 is the
only authoritative surface — so the previous source
(``viewer/public/data/surfaceome/*.json``) was removed and this script
now reads from ``data/annotations/`` directly. Pass ``--source PATH`` to
override (e.g. point at ``data/eval/surfaceome_v2_samples/`` for a
historical-sample reimport).

In normal day-to-day operation you shouldn't need to run this:
``scripts/surfaceome_v2_annotate.py`` publishes by default after every
successful annotate run (via the same
:func:`accessible_surfaceome.cloud.surface_annotation.publish_record`
helper this script delegates to). Run it explicitly when:

* You hand-edited an in-tree annotation and want to reflect the edit in D1.
* You bulk-re-imported a set of historical samples from
  ``data/eval/surfaceome_v2_samples/`` and want the viewer to render them.
* You're verifying that an out-of-sync D1 row matches what's in tree.

Run from the repo root:

    uv run python scripts/upload_viewer_snapshots_to_d1.py            # dry-run
    uv run python scripts/upload_viewer_snapshots_to_d1.py --execute  # write
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from accessible_surfaceome.cloud.surface_annotation import publish_record_dict
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

# Default source — the agent's canonical disk artifact dir. Previously
# this script read from ``viewer/public/data/surfaceome/`` (the viewer
# fallback snapshots); when that fallback was removed the source moved to
# ``data/annotations/``. Use ``--source PATH`` to override.
DEFAULT_ANNOTATION_DIR = REPO_ROOT / "data" / "annotations"

logger = logging.getLogger(__name__)

# Non-schema convenience keys the annotate driver merges into the JSON dump
# so the HTML viewer can render the per-run timing breakdown. Strip before
# pushing to D1 so the on-disk blob stays small and matches what other
# consumers expect from a SurfaceomeRecord.
_NON_SCHEMA_KEYS = ("timing", "total_elapsed_s", "total_step_seconds")


def _load_blob(path: Path) -> dict[str, Any] | None:
    """Load a committed snapshot dict. Logs + returns None on parse errors.

    Skips Pydantic validation deliberately — see ``publish_record_dict``'s
    docstring for the rationale. The validation contract is at agent-
    write time, not at republish time.
    """
    try:
        rec_dict = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("  %s: bad JSON (%s) — skipping", path.name, exc)
        return None
    for k in _NON_SCHEMA_KEYS:
        rec_dict.pop(k, None)
    gene = rec_dict.get("gene") or {}
    if not gene.get("hgnc_symbol"):
        logger.warning("  %s: missing gene.hgnc_symbol — skipping", path.name)
        return None
    return rec_dict


def main() -> int:
    load_env()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--execute",
        action="store_true",
        help="Actually push to D1 (default: dry-run, list-only)",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help=(
            "Override the publish guards: the STALENESS guard (refuses to "
            "overwrite a D1 row generated more recently than the snapshot — "
            "prevents a stale snapshot from clobbering a newer run) and the "
            "REGRESSION guard (refuses to blank a populated deterministic "
            "block with has_data=False). Only use when you're certain the "
            "snapshot should win — e.g. an intentional hand-edit that is "
            "genuinely newer than what's in D1."
        ),
    )
    ap.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_ANNOTATION_DIR,
        help=(
            "Directory to read SurfaceomeRecord JSONs from. Default is "
            "data/annotations/ — the agent's canonical disk artifact. "
            "Override e.g. with data/eval/surfaceome_v2_samples/ for a "
            "historical-sample reimport."
        ),
    )
    ap.add_argument(
        "--no-purge",
        action="store_true",
        help=(
            "Skip the per-gene Cloudflare edge-cache purge after each D1 "
            "write. Use for bulk loads (≥ a few hundred genes) — Cloudflare's "
            "purge-cache rate limit is ~1k/day on the free plan and ~30k/h on "
            "Pro+, so per-URL purges across the 6,500-gene cohort would burn "
            "the budget. With --no-purge, records still land in D1 atomically; "
            "the Worker's edge cache refreshes on its Cache-Control TTL "
            "(≤ 1 day for per-gene records) instead of immediately."
        ),
    )
    args = ap.parse_args()

    source_dir: Path = args.source
    logger.info("source dir: %s", source_dir.relative_to(REPO_ROOT))

    if not source_dir.exists():
        logger.error("source dir missing: %s", source_dir)
        return 1
    files = sorted(source_dir.glob("*.json"))
    if not files:
        logger.error("no *.json files found in %s", source_dir)
        return 1

    blobs: list[tuple[Path, dict[str, Any]]] = []
    for path in files:
        blob = _load_blob(path)
        if blob is not None:
            blobs.append((path, blob))
    logger.info("loaded %d snapshot(s)", len(blobs))

    if not args.execute:
        for _path, blob in blobs:
            gene = blob.get("gene") or {}
            logger.info(
                "  [DRY] would publish %s@%s  (uniprot=%s)",
                gene.get("hgnc_symbol"),
                blob.get("schema_version") or "1.0.0",
                gene.get("uniprot_acc"),
            )
        logger.info("dry-run; rerun with --execute to push")
        return 0

    # Delegate to the canonical publish helper — same code path the v2
    # annotate driver uses, so the two surfaces (annotate-time publish
    # and bulk-sync publish) can't drift.
    if args.no_purge:
        logger.info(
            "edge-cache purge SUPPRESSED (--no-purge); records live on "
            "Worker Cache-Control TTL (≤ 1 day) instead of immediately"
        )
    n_written = 0
    n_skipped = 0
    for _path, blob in blobs:
        # write_snapshot=False — the snapshot is already on disk; we're
        # just bringing D1 in line with it.
        pub = publish_record_dict(
            blob,
            write_snapshot=False,
            force=args.force,
            skip_purge=args.no_purge,
        )
        if pub.d1_written:
            n_written += 1
            stale = (
                f"  (dropped stale {','.join(pub.stale_versions_dropped)})"
                if pub.stale_versions_dropped
                else ""
            )
            logger.info("  pushed %s%s", pub.gene_symbol, stale)
        else:
            n_skipped += 1
            logger.warning("  skipped %s: %s", pub.gene_symbol, pub.skipped_reason)
    logger.info("done: %d pushed, %d skipped", n_written, n_skipped)
    return 0 if n_skipped == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
