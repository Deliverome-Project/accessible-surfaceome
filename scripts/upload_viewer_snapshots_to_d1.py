"""Push the committed viewer snapshots to public D1 ``surface_annotation``.

The Worker at ``api.deliverome.org/surfaceome/v1/genes/:symbol`` reads from
``surface_annotation.annotation_json``. The committed snapshots under
``viewer/public/data/surfaceome/*.json`` are the source of truth for what
the viewer should render — same shape as the per-gene ``SurfaceomeRecord``
the Worker serves.

This script syncs the committed snapshots → public D1 so D1 stays
aligned with whatever's in the viewer dir. Idempotent INSERT OR REPLACE on
``(gene_symbol, schema_version)``, with stale older-``schema_version``
rows dropped per gene.

When records older than the current schema live in D1 (e.g. ones that
predate the ``deterministic_features.surface_bind`` field) the viewer
would crash on ``rec.deterministic_features.surface_bind.has_data``. The
right fix is to add the field to the records — not to add defensive
``?.`` chains in the viewer — so this script is the maintenance utility
that brings D1 up to date with the field-complete snapshots in tree.

In normal day-to-day operation you shouldn't need to run this:
``scripts/surfaceome_v2_annotate.py`` publishes by default after every
successful annotate run (via the same
:func:`accessible_surfaceome.cloud.surface_annotation.publish_record`
helper this script delegates to). The use cases for running it
explicitly are:

* You hand-edited a committed snapshot and want to reflect the edit in D1.
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

from accessible_surfaceome.cloud.surface_annotation import (
    DEFAULT_SNAPSHOT_DIR,
    publish_record_dict,
)
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

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
    args = ap.parse_args()

    logger.info("snapshot dir: %s", DEFAULT_SNAPSHOT_DIR.relative_to(REPO_ROOT))

    if not DEFAULT_SNAPSHOT_DIR.exists():
        logger.error("snapshot dir missing: %s", DEFAULT_SNAPSHOT_DIR)
        return 1
    files = sorted(DEFAULT_SNAPSHOT_DIR.glob("*.json"))
    if not files:
        logger.error("no *.json snapshots found in %s", DEFAULT_SNAPSHOT_DIR)
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
    n_written = 0
    n_skipped = 0
    for _path, blob in blobs:
        # write_snapshot=False — the snapshot is already on disk; we're
        # just bringing D1 in line with it.
        pub = publish_record_dict(blob, write_snapshot=False, force=args.force)
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
