"""Patch viewer JSON files with refreshed ortholog deterministic features.

Re-runs ``_fetch_orthologs()`` for each gene in
``viewer/public/data/surfaceome/*.json`` and rewrites the
``deterministic_features.orthologs`` block and the related
``filters.{mouse,cyno}_ortholog_ecd_pct_identity`` keys in place. All
other fields (LLM prose, evidence, executive summary, etc.) are left
untouched.

Background: the deep-dive agent's previous ortholog query filtered
``compara_ortholog_ecd.ecd_pct_identity IS NOT NULL``, which dropped
every ECD-less protein (inner-leaflet, soluble, GPI-anchored) and made
the viewer report "no orthologs" for textbook-conserved genes like SRC.
The fixed query surfaces those orthologs alongside their full-length
BioMart % identity. This script applies the new query output to
existing static viewer JSONs without re-spending the agent's $0.30–
0.50/gene LLM cost.

Usage::

    # Single gene, dry-run:
    uv run python scripts/patch_deterministic_orthologs.py SRC --dry-run

    # Whole viewer cohort:
    uv run python scripts/patch_deterministic_orthologs.py --all

    # Only patch genes whose orthologs were previously empty:
    uv run python scripts/patch_deterministic_orthologs.py --all --only-empty
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from accessible_surfaceome.agents.surfaceome_v1.d1_deterministic import (
    _fetch_orthologs,
    _latest_ortholog_ecd_version,
    _latest_topology_version_for_cohort,
)
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

VIEWER_DATA_DIR = REPO_ROOT / "viewer" / "public" / "data" / "surfaceome"

logger = logging.getLogger(__name__)


def _canonical_ecd_pct(entries: list[dict]) -> float | None:
    """Mirror orchestrator._canonical_species_identity for filter rollups."""
    for e in entries:
        if e.get("is_canonical"):
            return e.get("ecd_pct_identity_to_human_canonical")
    return None


def _patch_one(
    json_path: Path,
    *,
    topology_version: str,
    ortholog_ecd_version: str,
    only_empty: bool,
    dry_run: bool,
) -> dict[str, int]:
    """Patch a single viewer JSON file. Returns counts for logging."""
    record = json.loads(json_path.read_text(encoding="utf-8"))
    symbol = (record.get("gene") or {}).get("hgnc_symbol") or json_path.stem
    uniprot_acc = (record.get("gene") or {}).get("uniprot_acc")
    if not uniprot_acc:
        logger.warning("[%s] no gene.uniprot_acc in %s — skipping", symbol, json_path.name)
        return {"skipped": 1}

    det = record.setdefault("deterministic_features", {})
    orthos = det.setdefault("orthologs", {"mouse": [], "cynomolgus": []})

    before_mouse = len(orthos.get("mouse") or [])
    before_cyno = len(orthos.get("cynomolgus") or [])

    if only_empty and (before_mouse > 0 or before_cyno > 0):
        logger.info("[%s] orthologs already populated (m=%d, c=%d) — --only-empty skipped",
                    symbol, before_mouse, before_cyno)
        return {"skipped": 1}

    fresh = _fetch_orthologs(
        uniprot_acc,
        topology_version=topology_version,
        ortholog_ecd_version=ortholog_ecd_version,
    )
    fresh_dict = fresh.model_dump(mode="json")

    after_mouse = len(fresh_dict.get("mouse") or [])
    after_cyno = len(fresh_dict.get("cynomolgus") or [])

    orthos["mouse"] = fresh_dict.get("mouse") or []
    orthos["cynomolgus"] = fresh_dict.get("cynomolgus") or []
    # Drop the dropped rat field if present from older JSONs.
    orthos.pop("rat", None)

    filters = record.setdefault("filters", {})
    filters["mouse_ortholog_ecd_pct_identity"] = _canonical_ecd_pct(orthos["mouse"])
    filters["cyno_ortholog_ecd_pct_identity"] = _canonical_ecd_pct(orthos["cynomolgus"])

    delta_m = after_mouse - before_mouse
    delta_c = after_cyno - before_cyno
    arrow = "→" if (delta_m or delta_c) else "·"
    logger.info(
        "[%s] mouse %d %s %d, cyno %d %s %d (uniprot=%s)",
        symbol, before_mouse, arrow, after_mouse, before_cyno, arrow, after_cyno, uniprot_acc,
    )

    if dry_run:
        return {"would_write": 1, "mouse_delta": delta_m, "cyno_delta": delta_c}

    json_path.write_text(json.dumps(record, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return {"wrote": 1, "mouse_delta": delta_m, "cyno_delta": delta_c}


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
    parser.add_argument("--all", action="store_true", help="Patch every JSON under viewer/public/data/surfaceome/.")
    parser.add_argument("--only-empty", action="store_true",
                        help="Skip genes whose mouse + cyno ortholog arrays are already non-empty.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would change without writing.")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_env()

    # Cohort-aware version: ortholog topology lives under the
    # mouse_ortholog / cyno_ortholog cohorts (which share a version in
    # practice), NOT the global-latest topology_version. Using
    # _latest_topology_version() here was a latent bug — after the
    # 2026-05-25 canonical-only sweep the global latest (topo_2026_05_25)
    # has no ortholog-cohort rows, so the topology LEFT JOIN in
    # _fetch_orthologs returns nothing and this patch would WIPE ortholog
    # topology. Mirror fetch_deterministic_features, which resolves the
    # version per fetcher's cohort.
    topology_version = _latest_topology_version_for_cohort("mouse_ortholog")
    ortholog_ecd_version = _latest_ortholog_ecd_version()
    if not topology_version or not ortholog_ecd_version:
        logger.error(
            "Cannot resolve latest versions from public D1 "
            "(topology_version=%r, ortholog_ecd_version=%r). Check D1 is reachable.",
            topology_version, ortholog_ecd_version,
        )
        return 1
    logger.info("Using topology_version=%s, ortholog_ecd_version=%s",
                topology_version, ortholog_ecd_version)
    logger.info("Dry-run: %s", args.dry_run)

    targets = _resolve_targets(args)
    if not targets:
        logger.info("No targets to patch.")
        return 0

    totals = {"wrote": 0, "would_write": 0, "skipped": 0, "mouse_delta": 0, "cyno_delta": 0}
    for path in targets:
        try:
            result = _patch_one(
                path,
                topology_version=topology_version,
                ortholog_ecd_version=ortholog_ecd_version,
                only_empty=args.only_empty,
                dry_run=args.dry_run,
            )
        except Exception as exc:
            logger.exception("[%s] patch failed: %s", path.stem, exc)
            continue
        for k, v in result.items():
            totals[k] = totals.get(k, 0) + v

    logger.info(
        "Done. wrote=%d would_write=%d skipped=%d Δmouse=%+d Δcyno=%+d",
        totals["wrote"], totals["would_write"], totals["skipped"],
        totals["mouse_delta"], totals["cyno_delta"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
