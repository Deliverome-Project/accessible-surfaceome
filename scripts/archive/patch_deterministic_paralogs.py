"""Patch viewer JSON files with refreshed paralog deterministic features.

Re-runs ``_fetch_paralogs()`` for each gene in
``viewer/public/data/surfaceome/*.json`` and rewrites the
``deterministic_features.paralogs`` block in place. All other fields
(orthologs, isoforms, LLM prose, evidence, executive summary, etc.) are
left untouched.

Background: ``ParalogEntry`` gained a ``full_length_pct_identity`` field —
the whole-protein Ensembl Compara / BioMart identity, which is populated
even for ECD-less proteins (SRC-family kinases, soluble / cytoplasmic
enzymes) whose per-loop ``ecd_pct_identity`` is None. The viewer falls
back to it to color the antibody cross-reactivity risk tier for those
paralogs (instead of a neutral "no ECD" chip). The value already lives in
``compara_paralog.biomart_percent_identity`` for ~all pairs, so this is a
pure re-read + re-serialize: no sweep, no UniProt fetch, no D1 write, and
no agent LLM cost. Mirrors ``patch_deterministic_orthologs.py``.

Usage::

    # Single gene, dry-run:
    uv run python scripts/patch_deterministic_paralogs.py SRC --dry-run

    # Whole viewer cohort:
    uv run python scripts/patch_deterministic_paralogs.py --all
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from accessible_surfaceome.agents.surfaceome_v1.d1_deterministic import (
    _fetch_paralogs,
    _latest_paralog_version,
)
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

VIEWER_DATA_DIR = REPO_ROOT / "viewer" / "public" / "data" / "surfaceome"

logger = logging.getLogger(__name__)


def _patch_one(
    json_path: Path,
    *,
    paralog_version: str,
    dry_run: bool,
) -> dict[str, int]:
    """Patch a single viewer JSON file's paralogs block. Returns log counts."""
    record = json.loads(json_path.read_text(encoding="utf-8"))
    symbol = (record.get("gene") or {}).get("hgnc_symbol") or json_path.stem
    uniprot_acc = (record.get("gene") or {}).get("uniprot_acc")
    if not uniprot_acc:
        logger.warning("[%s] no gene.uniprot_acc in %s — skipping", symbol, json_path.name)
        return {"skipped": 1}

    det = record.setdefault("deterministic_features", {})
    before = det.get("paralogs") or []
    before_full = sum(
        1 for p in before if p.get("full_length_pct_identity") is not None
    )

    fresh = _fetch_paralogs(uniprot_acc, paralog_version)
    fresh_dicts = [p.model_dump(mode="json") for p in fresh]
    after_full = sum(
        1 for p in fresh_dicts if p.get("full_length_pct_identity") is not None
    )

    det["paralogs"] = fresh_dicts

    logger.info(
        "[%s] paralogs %d (full-length %d→%d) (uniprot=%s)",
        symbol, len(fresh_dicts), before_full, after_full, uniprot_acc,
    )

    if dry_run:
        return {"would_write": 1}

    json_path.write_text(
        json.dumps(record, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    return {"wrote": 1}


def _resolve_targets(args: argparse.Namespace) -> list[Path]:
    if args.all:
        return sorted(VIEWER_DATA_DIR.glob("*.json"))
    if not args.symbols:
        raise SystemExit("Pass --all or one or more gene symbols (e.g. SRC GPR75).")
    paths: list[Path] = []
    for sym in args.symbols:
        p = VIEWER_DATA_DIR / f"{sym}.json"
        if not p.exists():
            logger.warning("missing viewer JSON for %s at %s", sym, p)
            continue
        paths.append(p)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbols", nargs="*", help="Gene symbols to patch (e.g. SRC GPR75).")
    parser.add_argument("--all", action="store_true",
                        help="Patch every JSON under viewer/public/data/surfaceome/.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would change without writing.")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_env()

    paralog_version = _latest_paralog_version()
    if not paralog_version:
        logger.error(
            "Cannot resolve latest paralog_version from public D1. Check D1 is reachable."
        )
        return 1
    logger.info("Using paralog_version=%s", paralog_version)
    logger.info("Dry-run: %s", args.dry_run)

    targets = _resolve_targets(args)
    if not targets:
        logger.info("No targets to patch.")
        return 0

    totals = {"wrote": 0, "would_write": 0, "skipped": 0}
    for path in targets:
        try:
            result = _patch_one(path, paralog_version=paralog_version, dry_run=args.dry_run)
        except Exception as exc:
            logger.exception("[%s] patch failed: %s", path.stem, exc)
            continue
        for k, v in result.items():
            totals[k] = totals.get(k, 0) + v

    logger.info(
        "Done. wrote=%d would_write=%d skipped=%d",
        totals["wrote"], totals["would_write"], totals["skipped"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
