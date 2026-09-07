"""Patch viewer JSON files with isoform→canonical sequence %identity.

Re-runs ``_fetch_isoform_topologies()`` (now identity-aware) for each gene
in ``viewer/public/data/surfaceome/*.json`` and rewrites the
``deterministic_features.isoform_topologies`` block in place, populating the
new ``full_length_pct_identity_to_canonical`` /
``ecd_pct_identity_to_canonical`` fields. All other fields (LLM prose,
evidence, topology cells, etc.) are left untouched.

Background: alternative isoforms are splice products of the same gene, so
Ensembl Compara emits no pairwise identity for them. The topology sweep
already landed every isoform's sequence in ``topology_public.sequence``;
this computes the BLOSUM62 identity from those sequences without re-spending
the deep-dive agent's LLM cost. See ``merge/isoform_identity.py``.

Usage::

    # Single gene, dry-run (prints the computed numbers):
    uv run python scripts/patch_deterministic_isoform_identity.py EGFR --dry-run

    # Whole viewer cohort:
    uv run python scripts/patch_deterministic_isoform_identity.py --all
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from accessible_surfaceome.agents.surfaceome_v1.d1_deterministic import (
    _fetch_canonical_sequence,
    _fetch_canonical_topology,
    _fetch_isoform_topologies,
    _latest_topology_version_for_cohort,
)
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

VIEWER_DATA_DIR = REPO_ROOT / "viewer" / "public" / "data" / "surfaceome"

logger = logging.getLogger(__name__)


def _fmt(v: float | None) -> str:
    return f"{v:.1f}%" if isinstance(v, (int, float)) else "—"


def _patch_one(
    json_path: Path,
    *,
    canonical_topo_version: str,
    isoform_topo_version: str,
    dry_run: bool,
) -> dict[str, int]:
    """Patch a single viewer JSON file. Returns counts for logging."""
    record = json.loads(json_path.read_text(encoding="utf-8"))
    symbol = (record.get("gene") or {}).get("hgnc_symbol") or json_path.stem
    uniprot_acc = (record.get("gene") or {}).get("uniprot_acc")
    if not uniprot_acc:
        logger.warning("[%s] no gene.uniprot_acc — skipping", symbol)
        return {"skipped": 1}

    det = record.setdefault("deterministic_features", {})
    before = det.get("isoform_topologies") or []
    if not before:
        logger.info("[%s] no alternative isoforms — nothing to patch", symbol)
        return {"skipped": 1}

    # Canonical topology + sequence drive the identity comparison.
    canonical = (
        _fetch_canonical_topology(uniprot_acc, canonical_topo_version)
        if canonical_topo_version else None
    )
    canonical_topology = canonical.per_residue_topology if canonical else ""
    canonical_sequence = (
        _fetch_canonical_sequence(uniprot_acc, canonical_topo_version)
        if canonical_topo_version else ""
    )

    fresh = _fetch_isoform_topologies(
        uniprot_acc,
        isoform_topo_version,
        canonical_topology=canonical_topology,
        canonical_sequence=canonical_sequence,
    )
    fresh_dump = [iso.model_dump(mode="json") for iso in fresh]

    if len(fresh_dump) != len(before):
        logger.warning(
            "[%s] isoform count changed (%d → %d); rewriting whole block",
            symbol, len(before), len(fresh_dump),
        )

    for iso in fresh_dump:
        logger.info(
            "[%s]   %s: full-length %s · ECD %s",
            symbol,
            iso.get("isoform_id"),
            _fmt(iso.get("full_length_pct_identity_to_canonical")),
            _fmt(iso.get("ecd_pct_identity_to_canonical")),
        )

    if dry_run:
        return {"would_write": 1}

    det["isoform_topologies"] = fresh_dump
    json_path.write_text(
        json.dumps(record, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    return {"wrote": 1}


def _resolve_targets(args: argparse.Namespace) -> list[Path]:
    if args.all:
        return sorted(VIEWER_DATA_DIR.glob("*.json"))
    if not args.symbols:
        raise SystemExit("Pass --all or one or more gene symbols (e.g. EGFR SRC).")
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
    parser.add_argument("symbols", nargs="*", help="Gene symbols to patch (e.g. EGFR SRC).")
    parser.add_argument("--all", action="store_true",
                        help="Patch every JSON under viewer/public/data/surfaceome/.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the computed identities without writing.")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_env()

    canonical_topo_version = _latest_topology_version_for_cohort("human_canonical")
    isoform_topo_version = _latest_topology_version_for_cohort("human_isoforms")
    if not canonical_topo_version or not isoform_topo_version:
        logger.error(
            "Cannot resolve topology versions from public D1 "
            "(canonical=%r, isoforms=%r). Check D1 is reachable.",
            canonical_topo_version, isoform_topo_version,
        )
        return 1
    logger.info("canonical_topo_version=%s, isoform_topo_version=%s",
                canonical_topo_version, isoform_topo_version)
    logger.info("Dry-run: %s", args.dry_run)

    targets = _resolve_targets(args)
    if not targets:
        logger.info("No targets to patch.")
        return 0

    totals = {"wrote": 0, "would_write": 0, "skipped": 0}
    for path in targets:
        try:
            result = _patch_one(
                path,
                canonical_topo_version=canonical_topo_version,
                isoform_topo_version=isoform_topo_version,
                dry_run=args.dry_run,
            )
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
